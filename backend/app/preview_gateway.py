"""Separate ASGI service: uvicorn app.preview_gateway:app --port 8090.

Expose only on PREVIEW_PUBLIC_ORIGIN through HTTPS. This process needs access to
the builder host's loopback previews and the same MongoDB/session secret.
"""
import hashlib
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from bson import ObjectId
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from itsdangerous import BadSignature
from starlette.concurrency import run_in_threadpool
from app.core.errors import AppError
from app.repositories.store import get_store, now
from app.services import remote_preview

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
COOKIE = '__Host-shift_preview'


@app.exception_handler(AppError)
async def error(request, exc):
    return JSONResponse({'error': exc.message}, status_code=exc.status)


def session_record(request, ticket=None):
    try:
        claims = remote_preview.signer().loads(ticket or request.cookies.get(COOKIE, ''), max_age=60 if ticket else 900)
        if not ObjectId.is_valid(claims.get('id', '')):
            raise BadSignature('Invalid identity')
        store = get_store()
        query = {'_id': ObjectId(claims['id']), 'status': 'running', 'expires_at': {'$gt': now()}}
        if ticket:
            query.update(ticket_hash=hashlib.sha256(claims['nonce'].encode()).hexdigest(), ticket_expires={'$gt': now()})
            row = store.db.application_previews.find_one_and_update(query, {'$unset': {'ticket_hash': '', 'ticket_expires': ''}})
        else:
            row = store.db.application_previews.find_one(query)
        if not row:
            raise BadSignature('Preview expired')
        store.project(row['project_id'], claims['actor'], 'write')
        return row, claims
    except (BadSignature, KeyError, TypeError):
        raise AppError('This preview link expired. Open a new link from the Application studio.', 401) from None


@app.api_route('/{path:path}', methods=['GET', 'POST', 'DELETE'])
async def proxy(path: str, request: Request):
    base = remote_preview.origin()
    if not base or request.headers.get('host') != urlsplit(base).netloc:
        raise AppError('Preview host is not configured for this request.', 403)
    if path == 'session' and request.method == 'GET':
        row, claims = await run_in_threadpool(session_record, request, request.query_params.get('ticket', ''))
        response = RedirectResponse('/workspace', status_code=303)
        response.set_cookie(COOKIE, remote_preview.signer().dumps({'id': claims['id'], 'actor': claims['actor']}),
            secure=True, httponly=True, samesite='strict', max_age=900, path='/')
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response
    row, _ = await run_in_threadpool(session_record, request)
    upstream = urlsplit(row['url'])
    if upstream.scheme != 'http' or upstream.hostname != '127.0.0.1' or not upstream.port or upstream.path:
        raise AppError('Invalid preview upstream.', 503)
    if request.method != 'GET' and request.headers.get('origin') != base:
        raise AppError('Preview request origin rejected.', 403)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise AppError('Preview request is too large.', 413)
    if path.startswith('/') or '\\' in path or any(part in ('.', '..') for part in path.split('/')):
        raise AppError('Invalid preview path.', 400)
    headers = {'Origin': row['url']}
    if request.headers.get('content-type'):
        headers['Content-Type'] = request.headers['content-type']
    cookies = SimpleCookie(); cookies.load(request.headers.get('cookie', ''))
    if 'app_session' in cookies:
        headers['Cookie'] = 'app_session=' + cookies['app_session'].value
    url = row['url'] + '/' + path
    if request.url.query:
        url += '?' + request.url.query
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            async with client.stream(request.method, url, content=bytes(body), headers=headers) as result:
                data = bytearray()
                async for chunk in result.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 2 * 1024 * 1024:
                        raise AppError('Preview response exceeded its limit.', 502)
                safe = {key: result.headers[key] for key in ('content-type', 'content-security-policy', 'x-content-type-options') if key in result.headers}
                safe.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
                response = Response(bytes(data), status_code=result.status_code, headers=safe)
                for value in result.headers.get_list('set-cookie'):
                    parsed = SimpleCookie(); parsed.load(value)
                    if 'app_session' in parsed:
                        morsel = parsed['app_session']
                        response.set_cookie('app_session', morsel.value, secure=True, httponly=True, samesite='strict', path='/', max_age=min(900, int(morsel['max-age'] or 900)))
                return response
    except httpx.HTTPError:
        raise AppError('Preview is unavailable or expired. Start a new preview.', 502) from None
