import base64
import secrets
from datetime import timedelta
from urllib.parse import quote
from bson import ObjectId
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from app.core.auth import user, limit_auth, public_account, set_session
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.passwords import verify_password
from app.repositories.store import get_store, now
from app.services import account_security as security

router = APIRouter(prefix='/api/security', tags=['Account security'])


class Credentials(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(default='', max_length=64)


def local_account(account, db):
    if not account['id'].startswith('email:'):
        raise AppError('Manage authentication factors with your sign-in provider.', 409)
    return db.users.find_one({'_id': ObjectId(account['id'][6:]), 'disabled': {'$ne': True}})


def reauthenticate(body, request, account, db):
    limit_auth(request, account['id'])
    record = local_account(account, db)
    if not record or not verify_password(body.password, record['password_hash']):
        raise AppError('Password is incorrect.', 401)
    return record


def is_admin(account):
    return not account.get('local') and account['id'] in [v.strip() for v in get_settings().builder_admin_ids.split(',') if v.strip()]


def admin(account=Depends(user)):
    if not is_admin(account):
        raise AppError('Administrator access is required.', 403)
    return account


@router.get('')
def overview(account=Depends(user)):
    db = get_store().db
    record = local_account(account, db) if account['id'].startswith('email:') else {}
    return {'password_account': account['id'].startswith('email:'), 'mfa_enabled': bool(record.get('mfa_secret')),
        'recovery_codes_remaining': len(record.get('mfa_recovery', [])), 'admin': is_admin(account),
        'events': [{'action': r['action'], 'created_at': r['created_at']} for r in db.security_events.find({'actor': account['id']}).sort('created_at', -1).limit(30)]}


@router.post('/mfa/enroll')
def enroll(body: Credentials, request: Request, account=Depends(user)):
    db = get_store().db
    record = reauthenticate(body, request, account, db)
    if record.get('mfa_secret'):
        raise AppError('MFA is already enabled.', 409)
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    db.users.update_one({'_id': record['_id']}, {'$set': {'mfa_pending': security.cipher().encrypt(secret.encode()).decode(),
        'mfa_pending_until': now() + timedelta(minutes=10)}})
    return {'secret': secret, 'uri': f'otpauth://totp/shift.AI:{quote(record["email"])}?secret={secret}&issuer=shift.AI&digits=6&period=30'}


@router.post('/mfa/confirm')
def confirm(body: Credentials, request: Request, response: Response, account=Depends(user)):
    db = get_store().db
    record = reauthenticate(body, request, account, db)
    pending = db.users.find_one({'_id': record['_id'], 'mfa_pending_until': {'$gt': now()}, 'mfa_secret': {'$exists': False}})
    if not pending:
        raise AppError('Start MFA enrollment again.', 409)
    secret = security.cipher().decrypt(pending['mfa_pending'].encode()).decode()
    counter = security.matched_counter(secret, body.code.strip())
    if counter is None:
        raise AppError('Authenticator code is incorrect.', 400)
    codes = security.recovery_codes()
    result = db.users.update_one({'_id': record['_id'], 'mfa_pending': pending['mfa_pending'], 'mfa_secret': {'$exists': False}},
        {'$set': {'mfa_secret': pending['mfa_pending'], 'mfa_last_counter': counter, 'mfa_recovery': [security.recovery_hash(c) for c in codes]},
         '$unset': {'mfa_pending': '', 'mfa_pending_until': ''}, '$inc': {'session_version': 1}})
    if not result.modified_count:
        raise AppError('Enrollment changed. Start again.', 409)
    set_session(response, public_account(db.users.find_one({'_id': record['_id']})))
    security.audit(db, account['id'], 'mfa.enabled')
    return {'recovery_codes': codes}


@router.post('/mfa/disable')
def disable(body: Credentials, request: Request, response: Response, account=Depends(user)):
    db = get_store().db
    record = reauthenticate(body, request, account, db)
    security.verify(db, record, body.code)
    db.users.update_one({'_id': record['_id']}, {'$unset': {'mfa_secret': '', 'mfa_recovery': '', 'mfa_last_counter': '', 'mfa_pending': '', 'mfa_pending_until': ''}, '$inc': {'session_version': 1}})
    set_session(response, public_account(db.users.find_one({'_id': record['_id']})))
    security.audit(db, account['id'], 'mfa.disabled')
    return {'ok': True}


@router.post('/sessions/revoke')
def revoke(body: Credentials, request: Request, response: Response, account=Depends(user)):
    db = get_store().db
    record = reauthenticate(body, request, account, db)
    security.verify(db, record, body.code)
    db.users.update_one({'_id': record['_id']}, {'$inc': {'session_version': 1}})
    set_session(response, public_account(db.users.find_one({'_id': record['_id']})))
    security.audit(db, account['id'], 'sessions.revoked')
    return {'ok': True}


@router.get('/admin')
def admin_overview(account=Depends(admin)):
    db = get_store().db
    accounts = [{'id': 'email:' + str(r['_id']), 'name': r['name'], 'email': r['email'], 'disabled': r.get('disabled', False), 'mfa': bool(r.get('mfa_secret'))} for r in db.users.find().limit(200)]
    accounts += [{'id': r['_id'], 'name': r['name'], 'email': r['email'], 'disabled': r.get('disabled', False), 'mfa': None} for r in db.external_accounts.find().limit(200)]
    return {'users': accounts,
        'events': [{'actor': r['actor'], 'action': r['action'], 'target': r.get('target'), 'created_at': r['created_at']} for r in db.security_events.find().sort('created_at', -1).limit(100)],
        'workers': [{'id': r['_id'], 'heartbeat_at': r['heartbeat_at']} for r in db.worker_health.find().limit(50)],
        'jobs': [{'id': r['_id'], 'kind': r['kind'], 'status': r['status'], 'attempts': r['attempts'], 'error': r.get('error')} for r in db.builder_jobs.find().sort('created_at', -1).limit(50)]}


class AccountChange(BaseModel):
    id: str = Field(pattern=r'^(email:[0-9a-f]{24}|oidc:[0-9a-f]{64})$')
    disabled: bool


@router.post('/admin/account')
def change_account(body: AccountChange, account=Depends(admin)):
    if body.id == account['id']:
        raise AppError('You cannot disable your own administrator account.', 409)
    db = get_store().db
    collection = db.users if body.id.startswith('email:') else db.external_accounts
    identity = ObjectId(body.id[6:]) if body.id.startswith('email:') else body.id
    result = collection.update_one({'_id': identity}, {'$set': {'disabled': body.disabled}, '$inc': {'session_version': 1}})
    if not result.matched_count:
        raise AppError('Account not found.', 404)
    security.audit(db, account['id'], 'account.disabled' if body.disabled else 'account.enabled', body.id)
    return {'ok': True}
