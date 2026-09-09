import secrets
import hashlib
import re
import time
from datetime import timedelta
from fastapi import APIRouter, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.repositories.store import get_store, now
from app.core.passwords import hash_password, verify_password
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
    if token:
        try:
            account = signer().loads(token, max_age=60 * 60 * 24 * 7)
            if not isinstance(account, dict):
                raise BadSignature('Invalid session')
            if str(account.get('id', '')).startswith('email:'):
                if not ObjectId.is_valid(account['id'][6:]):
                    raise BadSignature('Invalid account')
                record = get_store().db.users.find_one({'_id': ObjectId(account['id'][6:]), 'disabled': {'$ne': True}})
                if not record or record.get('session_version', 0) != account.get('session_version', 0):
                    raise BadSignature('Revoked session')
                return public_account(record)
            if str(account.get('id', '')).startswith('google:') and s.google_client_id:
                return account
            raise BadSignature('Unknown session')
        except (BadSignature, SignatureExpired):
            raise AppError('Your session has expired. Please sign in again.', 401) from None
    if not s.google_client_id and s.allow_local_access and request.client and request.client.host in ('127.0.0.1', '::1', 'testclient'):
        return {'id': 'local-workspace', 'name': 'Local workspace', 'email': '', 'local': True}
    raise AppError('Sign in to access your workspace.', 401, 'authentication_required')


def public_account(record):
    return {'id': 'email:' + str(record['_id']), 'name': record['name'], 'email': record['email'],
            'local': False, 'session_version': record.get('session_version', 0)}


def set_session(response, account):
    response.set_cookie('shift_session', signer().dumps(account), httponly=True,
                        secure=get_settings().cookie_secure, samesite='lax', max_age=60 * 60 * 24 * 7)


class EmailLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address.')
        return value


class EmailSignup(EmailLogin):
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError('Enter your name.')
        return value.strip()


def limit_auth(request, email):
    db = get_store().db
    for category, value, limit in [('ip', request.client.host if request.client else 'unknown', 30), ('email', email, 10)]:
        identifier = hashlib.sha256(f'{category}:{value}:{int(time.time()) // 300}'.encode()).hexdigest()
        counter = db.auth_attempts.find_one_and_update({'_id': identifier},
            {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now() + timedelta(minutes=10)}},
            upsert=True, return_document=ReturnDocument.AFTER)
        if counter['count'] > limit:
            raise AppError('Too many sign-in attempts. Try again in five minutes.', 429)


@router.post('/signup', status_code=201)
def signup(body: EmailSignup, request: Request, response: Response):
    signer()
    limit_auth(request, body.email)
    db = get_store().db
    db.users.create_index('email', unique=True)
    record = {'name': body.name, 'email': body.email, 'password_hash': hash_password(body.password),
              'created_at': now(), 'session_version': 0, 'disabled': False}
    try:
        record['_id'] = db.users.insert_one(record).inserted_id
    except DuplicateKeyError:
        raise AppError('An account with this email already exists. Sign in instead.', 409) from None
    account = public_account(record)
    set_session(response, account)
    return account


@router.post('/login')
def email_login(body: EmailLogin, request: Request, response: Response):
    limit_auth(request, body.email)
    record = get_store().db.users.find_one({'email': body.email})
    encoded = record['password_hash'] if record else 'pbkdf2_sha256$600000$' + '00' * 16 + '$' + '00' * 32
    if not verify_password(body.password, encoded) or not record or record.get('disabled'):
        raise AppError('Email or password is incorrect.', 401)
    account = public_account(record)
    set_session(response, account)
    return account


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
