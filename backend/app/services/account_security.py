"""TOTP secrets encrypted at rest; atomic anti-replay and one-use recovery codes."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from cryptography.fernet import Fernet
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now


def cipher():
    secret = get_settings().session_secret
    if len(secret) < 32:
        raise AppError('Configure a strong session secret before enabling MFA.', 503)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('shift-mfa-v1:' + secret).encode()).digest()))


def totp(secret, counter):
    digest = hmac.new(base64.b32decode(secret), struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f'{(struct.unpack(">I", digest[offset:offset+4])[0] & 0x7fffffff) % 1000000:06d}'


def matched_counter(secret, code):
    current = int(time.time()) // 30
    return next((n for n in (current, current - 1, current + 1) if hmac.compare_digest(totp(secret, n), code)), None)


def recovery_hash(code):
    return hashlib.sha256(code.strip().replace('-', '').lower().encode()).hexdigest()


def verify(db, record, code):
    if not record.get('mfa_secret'):
        return
    code = code.strip().replace(' ', '')
    secret = cipher().decrypt(record['mfa_secret'].encode()).decode()
    counter = matched_counter(secret, code) if code.isdigit() and len(code) == 6 else None
    if counter is not None:
        accepted = db.users.update_one({'_id': record['_id'], 'mfa_secret': record['mfa_secret'],
            '$or': [{'mfa_last_counter': {'$lt': counter}}, {'mfa_last_counter': {'$exists': False}}]},
            {'$set': {'mfa_last_counter': counter}}).modified_count
    else:
        digest = recovery_hash(code)
        accepted = db.users.update_one({'_id': record['_id'], 'mfa_recovery': digest},
            {'$pull': {'mfa_recovery': digest}}).modified_count if code else False
    if not accepted:
        raise AppError('Enter a current authenticator code or an unused recovery code.', 401, 'mfa_required')


def audit(db, actor, action, target=''):
    db.security_events.insert_one({'actor': actor, 'action': action, 'target': target, 'created_at': now()})


def recovery_codes():
    return [secrets.token_hex(8) for _ in range(10)]
