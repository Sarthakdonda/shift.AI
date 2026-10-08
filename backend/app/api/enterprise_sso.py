"""Confidential OIDC code flow with PKCE and single-use browser-bound state."""
import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
import httpx
import jwt
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.core.auth import signer, set_session, limit_auth
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import get_store, now
from app.services.account_security import audit

router = APIRouter(prefix='/api/auth/sso', tags=['Enterprise SSO'])


def configured():
    s = get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_client_secret and s.oidc_redirect_uri)


def secure_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise AppError('SSO endpoints must use HTTPS.', 503, 'sso_configuration')
    return value


def fetch(method, url, **kwargs):
    try:
        response = httpx.request(method, secure_url(url), timeout=15, follow_redirects=False, trust_env=False, **kwargs)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise AppError('Your identity provider is unavailable or rejected sign-in.', 502, 'sso_provider') from None


def discovery():
    if not configured():
        raise AppError('Enterprise SSO is not configured.', 503, 'sso_configuration')
    issuer = get_settings().oidc_issuer.rstrip('/')
    data = fetch('GET', issuer + '/.well-known/openid-configuration')
    if data.get('issuer') != get_settings().oidc_issuer:
        raise AppError('SSO issuer does not match discovery.', 503, 'sso_configuration')
    for name in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
        secure_url(data[name])
    return data


@router.get('/config')
def config():
    return {'enabled': configured()}


@router.get('/start')
def start(request: Request):
    limit_auth(request, 'sso-start')
    metadata = discovery()
    s = get_settings()
    secure_url(s.oidc_redirect_uri)
    verifier, state, nonce, browser = (secrets.token_urlsafe(32) for _ in range(4))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    db = get_store().db
    db.oidc_states.create_index('expires_at', expireAfterSeconds=0)
    db.oidc_states.insert_one({'_id': hashlib.sha256(state.encode()).hexdigest(), 'browser': hashlib.sha256(browser.encode()).hexdigest(),
        'nonce': nonce, 'verifier': verifier, 'expires_at': now() + timedelta(minutes=5)})
    response = RedirectResponse(metadata['authorization_endpoint'] + '?' + urlencode({'client_id': s.oidc_client_id,
        'redirect_uri': s.oidc_redirect_uri, 'response_type': 'code', 'scope': 'openid email profile',
        'state': state, 'nonce': nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256'}), status_code=303)
    response.set_cookie('shift_sso', signer().dumps(browser), secure=s.cookie_secure, httponly=True, samesite='lax', max_age=300)
    response.headers['Cache-Control'] = 'no-store'
    return response


@router.get('/callback')
def callback(request: Request, state: str = '', code: str = ''):
    if not 20 <= len(state) <= 100 or not 1 <= len(code) <= 8192:
        raise AppError('SSO sign-in was cancelled or returned invalid state.', 401)
    db = get_store().db
    try:
        browser = signer().loads(request.cookies.get('shift_sso', ''), max_age=300)
    except Exception:
        raise AppError('Restart SSO sign-in in this browser.', 401) from None
    pending = db.oidc_states.find_one_and_delete({'_id': hashlib.sha256(state.encode()).hexdigest(),
        'browser': hashlib.sha256(browser.encode()).hexdigest(), 'expires_at': {'$gt': now()}})
    if not pending:
        raise AppError('SSO sign-in expired or was already used.', 401)
    s, metadata = get_settings(), discovery()
    tokens = fetch('POST', metadata['token_endpoint'], auth=(s.oidc_client_id, s.oidc_client_secret),
        data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': s.oidc_redirect_uri, 'code_verifier': pending['verifier']})
    try:
        token = tokens['id_token']
        header = jwt.get_unverified_header(token)
        keys = fetch('GET', metadata['jwks_uri'])['keys']
        key = next(k for k in keys if k.get('kid') == header.get('kid') and k.get('kty') == 'RSA' and k.get('use', 'sig') == 'sig' and k.get('alg', 'RS256') == 'RS256')
        claims = jwt.decode(token, jwt.PyJWK.from_dict(key).key, algorithms=['RS256'], audience=s.oidc_client_id,
            issuer=s.oidc_issuer, options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'nonce']}, leeway=30)
        if claims['nonce'] != pending['nonce'] or claims.get('azp', s.oidc_client_id) != s.oidc_client_id:
            raise ValueError()
        if isinstance(claims['aud'], list) and len(claims['aud']) > 1 and claims.get('azp') != s.oidc_client_id:
            raise ValueError()
        if claims.get('email_verified') is not True or not isinstance(claims.get('email'), str) or '@' not in claims['email']:
            raise ValueError()
        domains = [v.strip().lower() for v in s.oidc_email_domains.split(',') if v.strip()]
        if domains and claims['email'].rsplit('@', 1)[1].lower() not in domains:
            raise ValueError()
    except (ValueError, KeyError, StopIteration, TypeError, jwt.PyJWTError):
        raise AppError('SSO identity could not be verified for this workspace.', 401) from None
    # Never auto-link by email: an existing password account retains its identity.
    identity = 'oidc:' + hashlib.sha256((s.oidc_issuer + '\0' + claims['sub']).encode()).hexdigest()
    db.external_accounts.update_one({'_id': identity}, {'$setOnInsert': {'disabled': False, 'session_version': 0},
        '$set': {'name': str(claims.get('name', 'Workspace member'))[:100], 'email': claims['email'][:254]}}, upsert=True)
    record = db.external_accounts.find_one({'_id': identity})
    if record['disabled']:
        raise AppError('This account is disabled.', 403)
    account = {'id': identity, 'name': record['name'], 'email': record['email'], 'local': False, 'session_version': record['session_version']}
    response = RedirectResponse(s.app_base_url.rstrip('/') + '/dashboard', status_code=303)
    set_session(response, account)
    response.delete_cookie('shift_sso')
    response.headers['Referrer-Policy'] = 'no-referrer'
    audit(db, identity, 'login.sso')
    return response
