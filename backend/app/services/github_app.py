"""GitHub App source delivery for generated applications.

Verified against the live API: an installation token on a *personal* account
returns 403 "Resource not accessible by integration" for POST /user/repos, and
the organization endpoint 404s because the owner is a User. So the two
capabilities are deliberately separated:

  create repository -> organization endpoint (App) or a user PAT
  upload source     -> installation token (contents: write)

Nothing here ever writes a credential into a repository, and every log line is
passed through `redact` so tokens cannot reach stored deployment logs.
"""
import base64
import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from app.core.config import get_settings
from app.core.errors import AppError

API = 'https://api.github.com'
AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'
HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
# Files that must never reach a generated repository, whatever the generator emits.
FORBIDDEN = re.compile(r'(^|/)(\.env$|\.env\.[^e]|.*\.pem$|.*\.p12$|.*\.pfx$|.*\.keystore$|'
                       r'.*\.jks$|.*\.mobileprovision$|id_rsa|\.git/|\.npmrc$|\.netrc$)', re.IGNORECASE)
SECRET_VALUE = re.compile(r'(gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}|'
                          r'mongodb(\+srv)?://[^\s"\']+|mdb_sa_sk_[A-Za-z0-9]+|'
                          r'rnd_[A-Za-z0-9]{20,}|vcp_[A-Za-z0-9]{20,}|'
                          r'-----BEGIN [A-Z ]*PRIVATE KEY-----)')

_key_cache: dict = {}
_token = {'value': '', 'expires': 0.0}
# Separate locks: installation_token() mints a JWT (which loads the key) while
# holding the token lock. A single non-reentrant lock here deadlocks forever.
_key_lock = threading.Lock()
_token_lock = threading.Lock()
# GitHub refresh tokens are single use; concurrent refreshes would revoke each other.
_refresh_lock = threading.Lock()


def redact(text):
    """Remove anything credential-shaped before a message is stored or shown."""
    return SECRET_VALUE.sub('[redacted]', str(text))[:4000]


def configured():
    s = get_settings()
    return bool(s.github_app_id and (s.github_app_private_key or s.github_app_private_key_path)
                and s.github_installation_id)


def requirements():
    s = get_settings()
    return [name for name, value in (
        ('GITHUB_APP_ID', s.github_app_id),
        ('GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH',
         s.github_app_private_key or s.github_app_private_key_path),
        ('GITHUB_INSTALLATION_ID', s.github_installation_id)) if not value]


def require():
    missing = requirements()
    if missing:
        raise AppError('Source delivery needs ' + ', '.join(missing) + ' in backend/.env.',
                       503, 'github_configuration')


def _private_key():
    s = get_settings()
    material = s.github_app_private_key.strip()
    if not material:
        path = Path(s.github_app_private_key_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        if not path.is_file():
            raise AppError('The GitHub App private key file was not found at the configured path.',
                           503, 'github_configuration')
        material = path.read_text('utf-8')
    with _key_lock:
        if _key_cache.get('pem') != material:
            try:
                _key_cache['pem'] = material
                _key_cache['key'] = serialization.load_pem_private_key(material.encode(), password=None)
            except (ValueError, TypeError):
                _key_cache.pop('key', None)
                raise AppError('The GitHub App private key could not be read. Supply the unencrypted PEM.',
                               503, 'github_configuration') from None
        return _key_cache['key']


def app_jwt():
    """Short-lived RS256 assertion identifying the App itself."""
    require()
    key = _private_key()
    encode = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b'=')
    issued = int(time.time()) - 60
    header = encode(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
    claims = encode(json.dumps({'iat': issued, 'exp': issued + 540,
                                'iss': get_settings().github_app_id}).encode())
    signed = header + b'.' + claims
    return (signed + b'.' + encode(key.sign(signed, padding.PKCS1v15(), hashes.SHA256()))).decode()


def _request(method, path, token, body=None, scheme='Bearer'):
    try:
        result = httpx.request(method, API + path, json=body, timeout=30, trust_env=False,
                               follow_redirects=False,
                               headers={**HEADERS, 'Authorization': scheme + ' ' + token})
    except httpx.HTTPError:
        raise AppError('GitHub is unreachable. Check network access, then retry.', 502, 'github_provider') from None
    if result.status_code == 401:
        raise AppError('GitHub rejected the credential. Confirm the App private key and installation.',
                       502, 'github_provider')
    if result.status_code == 403 and 'rate limit' in result.text.lower():
        raise AppError('GitHub rate limit reached. Retry after the limit resets.', 429, 'github_rate_limited')
    if not result.is_success and result.status_code not in (404, 409, 422):
        message = ''
        try:
            message = str(result.json().get('message', ''))
        except ValueError:
            pass
        raise AppError('GitHub returned HTTP ' + str(result.status_code) + '. ' + redact(message),
                       502, 'github_provider')
    return result


def installation():
    """Owner login, type and granted permissions for the configured install."""
    require()
    result = _request('GET', '/app/installations/' + get_settings().github_installation_id, app_jwt())
    if result.status_code == 404:
        raise AppError('The configured GitHub App installation was not found. Reinstall the App and '
                       'update GITHUB_INSTALLATION_ID.', 503, 'github_configuration')
    body = result.json()
    account = body.get('account', {})
    return {'owner': account.get('login', ''), 'owner_type': account.get('type', ''),
            'permissions': body.get('permissions', {}),
            'repository_selection': body.get('repository_selection', '')}


def installation_token():
    """Repository-scoped token, cached until shortly before it expires."""
    require()
    with _token_lock:
        if _token['value'] and _token['expires'] > time.monotonic():
            return _token['value']
        result = _request('POST', '/app/installations/' + get_settings().github_installation_id
                          + '/access_tokens', app_jwt())
        if not result.is_success:
            raise AppError('GitHub would not issue an installation token. Confirm the installation is active.',
                           502, 'github_provider')
        _token['value'] = result.json()['token']
        # Installation tokens last an hour; refresh five minutes early.
        _token['expires'] = time.monotonic() + 3300
        return _token['value']


def repository_name(application_id, app_name=''):
    """Deterministic, collision-resistant and valid as a GitHub repository name."""
    slug = re.sub(r'-+', '-', re.sub(r'[^a-z0-9-]', '-', (app_name or 'app').lower())).strip('-')[:28]
    token = re.sub(r'[^a-z0-9]', '', str(application_id).lower())[-10:] or 'generated'
    return ('shift-' + (slug or 'app') + '-' + token)[:90]


def owner():
    configured_owner = get_settings().github_owner.strip()
    return configured_owner or installation()['owner']


# ---- User-to-server authorization ------------------------------------------------
# POST /user/repos accepts only a GitHub App *user* access token (or a fine-grained
# PAT), never an installation token. The App's web flow issues one; it expires in
# eight hours and is refreshed with a single-use refresh token. Both are stored
# encrypted and never returned to the browser.

def oauth_configured():
    s = get_settings()
    return bool(s.github_client_id and s.github_client_secret)


def authorize_url(state, challenge, redirect_uri):
    return AUTHORIZE_URL + '?' + urlencode({'client_id': get_settings().github_client_id, 'redirect_uri': redirect_uri,
                                            'state': state, 'code_challenge': challenge,
                                            'code_challenge_method': 'S256', 'allow_signup': 'false'})


def _token_request(data):
    s = get_settings()
    try:
        result = httpx.post(TOKEN_URL, data={'client_id': s.github_client_id, 'client_secret': s.github_client_secret, **data},
                            headers={'Accept': 'application/json'}, timeout=30, trust_env=False)
        body = result.json()
    except (httpx.HTTPError, ValueError):
        raise AppError('GitHub authorization is unreachable. Retry shortly.', 502, 'github_provider') from None
    if not result.is_success or body.get('error') or not body.get('access_token'):
        raise AppError('GitHub did not authorize repository creation (' + redact(body.get('error', 'HTTP ' + str(result.status_code)))
                       + '). Connect GitHub again.', 409, 'github_authorization')
    return body


def _cipher():
    from app.services.account_security import cipher
    return cipher()


def _save_user_token(db, account_id, body, login=None):
    values = {'access': _cipher().encrypt(body['access_token'].encode()).decode(),
              'access_expires': time.time() + int(body.get('expires_in', 28800)) - 300, 'updated_at': time.time()}
    if body.get('refresh_token'):
        values['refresh'] = _cipher().encrypt(body['refresh_token'].encode()).decode()
        values['refresh_expires'] = time.time() + int(body.get('refresh_token_expires_in', 15897600)) - 3600
    if login:
        values['login'] = login
    db.github_user_tokens.update_one({'_id': account_id}, {'$set': values}, upsert=True)


def exchange_code(db, account_id, code, verifier, redirect_uri):
    """Complete the web flow and remember which GitHub user authorized."""
    body = _token_request({'code': code, 'code_verifier': verifier, 'redirect_uri': redirect_uri})
    who = _request('GET', '/user', body['access_token'])
    if not who.is_success:
        raise AppError('GitHub did not return the authorizing user.', 502, 'github_provider')
    login = who.json().get('login', '')
    _save_user_token(db, account_id, body, login)
    return login


def user_link(db, account_id):
    row = db.github_user_tokens.find_one({'_id': account_id}) if account_id else None
    return {'connected': bool(row and row.get('refresh_expires', row.get('access_expires', 0)) > time.time()),
            'login': (row or {}).get('login', '')}


def user_token(db, account_id):
    """A valid user access token for this platform account, refreshing if needed."""
    row = db.github_user_tokens.find_one({'_id': account_id}) if account_id else None
    if not row:
        return None
    if row.get('access_expires', 0) > time.time():
        return _cipher().decrypt(row['access'].encode()).decode()
    if not row.get('refresh') or row.get('refresh_expires', 0) < time.time():
        return None
    with _refresh_lock:
        row = db.github_user_tokens.find_one({'_id': account_id})
        if row.get('access_expires', 0) > time.time():
            return _cipher().decrypt(row['access'].encode()).decode()
        body = _token_request({'grant_type': 'refresh_token', 'refresh_token': _cipher().decrypt(row['refresh'].encode()).decode()})
        _save_user_token(db, account_id, body)
        return body['access_token']


def ensure_repository(name, description='', user_access_token=None):
    """Idempotent. Returns the repository, creating it only when absent."""
    require()
    account = owner()
    if not re.fullmatch(r'[A-Za-z0-9-]{1,90}', name):
        raise AppError('Generated repository name is invalid.', 500)
    token = installation_token()
    existing = _request('GET', '/repos/' + account + '/' + name, token)
    if existing.is_success:
        body = existing.json()
        return {'full_name': body['full_name'], 'default_branch': body.get('default_branch') or 'main',
                'html_url': body['html_url'], 'private': body.get('private', True), 'created': False}
    details = installation()
    payload = {'name': name, 'private': True, 'auto_init': False,
               'description': (description or 'Generated by shift.AI')[:300],
               'has_issues': False, 'has_wiki': False, 'has_projects': False}
    if details['owner_type'] == 'Organization':
        created = _request('POST', '/orgs/' + account + '/repos', token, payload)
    elif user_access_token or get_settings().github_pat:
        # Verified: an installation token cannot create a repository on a personal
        # account, so a user-authorised credential is required for this one call.
        credential = user_access_token or get_settings().github_pat
        who = _request('GET', '/user', credential)
        login = who.json().get('login', '') if who.is_success else ''
        if login.lower() != account.lower():
            raise AppError('GitHub is connected as "' + (login or 'unknown') + '", but repositories are delivered to "'
                           + account + '", where the App is installed. Connect GitHub as ' + account + '.', 409,
                           'github_authorization')
        created = _request('POST', '/user/repos', credential, payload)
    else:
        raise AppError('Connect GitHub as "' + account + '" so shift.AI can create the private repository. An App '
                       'installation token cannot create repositories on a personal account (GitHub returns 403). '
                       'Alternatively set GITHUB_PAT, or install the App on an organization.',
                       409, 'github_authorization')
    if not created.is_success:
        detail = ''
        try:
            detail = redact(str(created.json().get('message', '')))
        except ValueError:
            pass
        raise AppError('GitHub would not create the repository (HTTP ' + str(created.status_code) + '). ' + detail,
                       502, 'github_provider')
    body = created.json()
    return {'full_name': body['full_name'], 'default_branch': body.get('default_branch') or 'main',
            'html_url': body['html_url'], 'private': body.get('private', True), 'created': True}


def _safe_files(files):
    """Drop anything credential-shaped before it can be committed."""
    clean, refused = {}, []
    for name, data in files.items():
        if FORBIDDEN.search('/' + name) or name.startswith('..') or '\\' in name:
            refused.append(name)
            continue
        if SECRET_VALUE.search(data if isinstance(data, str) else ''):
            refused.append(name)
            continue
        clean[name] = data
    return clean, refused


def push_source(full_name, files, message='shift.AI generated release'):
    """Commit the whole generated tree with the installation token.

    Returns the commit sha. Refuses to push files that look like secrets rather
    than filtering silently, so the caller can report what was withheld.
    """
    require()
    if not files:
        raise AppError('There is no generated source to upload.', 409)
    clean, refused = _safe_files(files)
    if refused:
        raise AppError('Refusing to upload files that look like credentials: ' + ', '.join(sorted(refused)[:8])
                       + '. Generated applications must read secrets from environment variables.', 409,
                       'github_secret_blocked')
    token = installation_token()
    base = '/repos/' + full_name
    repo = _request('GET', base, token)
    if not repo.is_success:
        raise AppError('The generated repository is not reachable by the App installation. Add it to the '
                       'installation, then retry.', 502, 'github_provider')
    branch = repo.json().get('default_branch') or 'main'
    head = _request('GET', base + '/git/ref/heads/' + branch, token)
    if not head.is_success:
        # The Git database API rejects writes to an empty repository (409), so
        # create the first commit through the contents API.
        first = _request('PUT', base + '/contents/.gitignore', token, {
            'message': 'Initialize repository', 'content': base64.b64encode(clean.get('.gitignore', '.env\n').encode()).decode()})
        head = _request('GET', base + '/git/ref/heads/' + branch, token) if first.is_success else first
        if not head.is_success:
            raise AppError('GitHub would not initialize the empty repository.', 502, 'github_provider')
    parent = head.json()['object']['sha']
    previous = _request('GET', base + '/git/commits/' + parent, token)
    parent_tree = previous.json()['tree']['sha'] if previous.is_success else None
    # Full snapshot: the repository mirrors exactly this generated release;
    # earlier releases remain in the commit history.
    tree = [{'path': name, 'mode': '100644', 'type': 'blob', 'content': data} for name, data in sorted(clean.items())]
    created_tree = _request('POST', base + '/git/trees', token, {'tree': tree})
    if not created_tree.is_success:
        raise AppError('GitHub rejected the generated source tree.', 502, 'github_provider')
    tree_sha = created_tree.json()['sha']
    if tree_sha == parent_tree:
        # Identical source, for example a retried deployment: no new commit.
        return {'commit': parent, 'branch': branch, 'files': len(tree), 'changed': False}
    commit = _request('POST', base + '/git/commits', token,
                      {'message': message[:200], 'tree': tree_sha, 'parents': [parent]})
    if not commit.is_success:
        raise AppError('GitHub rejected the release commit.', 502, 'github_provider')
    sha = commit.json()['sha']
    moved = _request('PATCH', base + '/git/refs/heads/' + branch, token, {'sha': sha, 'force': False})
    if not moved.is_success:
        raise AppError('GitHub would not move the branch to the new release commit.', 502, 'github_provider')
    return {'commit': sha, 'branch': branch, 'files': len(tree), 'changed': True}
