"""Read-only per-project preview origins. No platform API or cookies reach this host."""
import re
from urllib.parse import urlsplit
from bson import ObjectId
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import get_settings
from app.core.errors import AppError

ASSETS={'index.html':'text/html','app.js':'text/javascript','storage.js':'text/javascript','spec.js':'text/javascript','style.css':'text/css','icon.svg':'image/svg+xml','manifest.webmanifest':'application/manifest+json'}


def base_origin():
    settings=get_settings()
    parsed=urlsplit(settings.portable_preview_origin.rstrip('/'))
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise AppError('Configure a valid portable preview origin.',503)
    if parsed.scheme!='https' and parsed.hostname!='localhost':
        raise AppError('Portable previews require HTTPS except on localhost.',503)
    # A dedicated project subdomain is mandatory even when sharing an HTTP server.
    return parsed


def signer():
    secret=get_settings().session_secret
    if len(secret)<32:raise AppError('A strong SESSION_SECRET is required for isolated preview links.',503)
    return URLSafeTimedSerializer(secret,salt='shift-portable-readonly-v1')


def preview_url(pid,bid,actor):
    parsed=base_origin()
    token=signer().dumps({'project':pid,'build':bid,'actor':actor})
    host=pid+'.'+parsed.hostname+(':'+str(parsed.port) if parsed.port else '')
    return parsed.scheme+'://'+host+'/_portable/'+token+'/index.html'


class PortablePreviewMiddleware:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        host=dict(scope['headers']).get(b'host',b'').decode().split(':')[0].lower()
        try:base=base_origin().hostname
        except AppError:return await self.app(scope,receive,send)
        match=re.fullmatch(r'([0-9a-f]{24})\.'+re.escape(base),host)
        if not match:return await self.app(scope,receive,send)
        request=Request(scope,receive)
        response=await self.serve(request,match[1])
        await response(scope,receive,send)

    async def serve(self,request,pid):
        from app.api import applications
        from starlette.concurrency import run_in_threadpool
        parts=request.url.path.split('/')
        if request.method!='GET' or len(parts)!=4 or parts[1]!='_portable' or parts[3] not in ASSETS:
            return Response('Preview resource not found.',status_code=404)
        try:
            ticket=signer().loads(parts[2],max_age=3600)
            if ticket.get('project')!=pid or not ObjectId.is_valid(ticket.get('build','')):raise ValueError()
            def read():
                store=applications.get_store();store.project(pid,ticket['actor'],'write')
                row=store.db.application_builds.find_one({'_id':ObjectId(ticket['build']),'project_id':pid,'status':'ready'})
                if not row or row['spec'].get('storage_mode','shared_server')=='shared_server':raise ValueError()
                return row['files'][parts[3]]
            body=await run_in_threadpool(read)
        except (BadSignature,SignatureExpired,ValueError,KeyError,AppError):
            return Response('This preview link expired or access changed. Open a fresh preview from Application studio.',status_code=403)
        origins=' '.join(get_settings().origins)
        policy="default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; manifest-src 'self'; base-uri 'none'; object-src 'none'; form-action 'none'; frame-ancestors "+origins
        return Response(body,media_type=ASSETS[parts[3]],headers={'Content-Security-Policy':policy,'X-Content-Type-Options':'nosniff','Cache-Control':'no-store','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()'})
