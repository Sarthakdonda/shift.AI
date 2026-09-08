import secrets
from fastapi import APIRouter, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.core.errors import AppError

router = APIRouter(prefix='/api/auth', tags=['Authentication'])


def signer():
    s = get_settings()
    if len(s.session_secret) < 32:
        raise AppError('Set SESSION_SECRET to a random value of at least 32 characters in backend/.env.', 503)
    return URLSafeTimedSerializer(s.session_secret, salt='shift-session-v1')


def user(request: Request):
    s = get_settings()
    token = request.cookies.get('shift_session')
    if token and s.google_client_id:
        try:
            return signer().loads(token, max_age=60 * 60 * 24 * 7)
        except (BadSignature, SignatureExpired):
            raise AppError('Your session has expired. Please sign in again.', 401) from None
    if not s.google_client_id and s.allow_local_access and request.client and request.client.host in ('127.0.0.1', '::1', 'testclient'):
        return {'id': 'local-workspace', 'name': 'Local workspace', 'email': '', 'local': True}
    raise AppError('Sign in with Google to access your workspace.', 401, 'authentication_required')


@router.get('/me')
def me(request: Request):
    return user(request)


@router.get('/nonce')
def nonce(response: Response):
    value = secrets.token_urlsafe(32)
    response.set_cookie('shift_nonce', signer().dumps(value), httponly=True, secure=get_settings().cookie_secure, samesite='lax', max_age=600)
    return {'nonce': value}


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=20, max_length=10000)


@router.post('/google')
def google_login(body: GoogleCredential, request: Request, response: Response):
    s = get_settings()
    if not s.google_client_id:
        raise AppError('Set GOOGLE_CLIENT_ID in backend/.env to enable Google sign-in.', 503)
    try:
        expected_nonce = signer().loads(request.cookies.get('shift_nonce', ''), max_age=600)
        claims = id_token.verify_oauth2_token(body.credential, GoogleRequest(), s.google_client_id)
        if not claims.get('email_verified') or claims.get('nonce') != expected_nonce:
            raise ValueError('Invalid credentials')
    except AppError:
        raise
    except Exception:
        raise AppError('Google sign-in could not be verified. Please try again.', 401) from None
    account = {'id': 'google:' + claims['sub'], 'name': claims.get('name', 'Workspace member'), 'email': claims.get('email', ''), 'local': False}
    response.set_cookie('shift_session', signer().dumps(account), httponly=True, secure=s.cookie_secure, samesite='lax', max_age=60 * 60 * 24 * 7)
    response.delete_cookie('shift_nonce')
    return account


@router.post('/logout')
def logout(response: Response):
    response.delete_cookie('shift_session')
    return {'ok': True}
