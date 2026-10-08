"""One-use preview tickets; a dedicated origin isolates generated pages from shift.AI."""
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlsplit
from itsdangerous import URLSafeTimedSerializer
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now


def origin():
    settings = get_settings()
    value = settings.preview_public_origin.rstrip('/')
    parsed = urlsplit(value)
    platform = [urlsplit(item).hostname for item in [settings.app_base_url, settings.api_public_origin, *settings.origins] if item]
    if not value:
        return ''
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or parsed.hostname in platform:
        raise AppError('PREVIEW_PUBLIC_ORIGIN must be a separate HTTPS host from the platform frontend and API.', 503, 'preview_configuration')
    if not settings.api_public_origin:
        raise AppError('Set API_PUBLIC_ORIGIN before enabling remote previews.', 503, 'preview_configuration')
    return value


def signer():
    secret = get_settings().session_secret
    if len(secret) < 32:
        raise AppError('Configure SESSION_SECRET before enabling remote previews.', 503)
    return URLSafeTimedSerializer(secret, salt='shift-preview-session-v1')


def access_link(store, row, actor):
    base = origin()
    if not base:
        return row['url']
    nonce = secrets.token_urlsafe(32)
    store.db.application_previews.update_one({'_id': row['_id'], 'status': 'running'}, {'$set': {
        'ticket_hash': hashlib.sha256(nonce.encode()).hexdigest(), 'ticket_expires': now() + timedelta(seconds=60)}})
    ticket = signer().dumps({'id': str(row['_id']), 'actor': actor, 'nonce': nonce})
    return base + '/session?ticket=' + ticket
