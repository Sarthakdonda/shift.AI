"""Vercel frontend provisioning for generated applications (Vercel REST API).

The frontend is the generated public/ directory plus a trusted same-origin
gateway function pinned to the application's verified Render backend. No
environment variables are set on Vercel: the backend origin is public
information compiled into the gateway, and no secret ever reaches the frontend.
"""
import json
import re
import time
from pathlib import Path
import httpx
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.github_app import redact

API = 'https://api.vercel.com'
NAME = re.compile(r'^shift-[a-z0-9-]{1,90}$')
UPSTREAM = re.compile(r'^https://[a-z0-9-]+\.onrender\.com$')
PROXY = Path(__file__).resolve().parents[1] / 'templates' / 'vercel_proxy.mjs'
SECURITY_HEADERS = [{'key': 'Cache-Control', 'value': 'no-store'}, {'key': 'X-Content-Type-Options', 'value': 'nosniff'},
                    {'key': 'Referrer-Policy', 'value': 'no-referrer'},
                    {'key': 'Content-Security-Policy', 'value': "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}]


def requirements():
    return [] if get_settings().vercel_token else ['VERCEL_TOKEN']


def api(method, path, body=None, params=None):
    s = get_settings()
    query = {**(params or {}), **({'teamId': s.vercel_team_id} if s.vercel_team_id else {})}
    attempts = 3 if method in ('GET', 'PATCH') else 1
    result = None
    for attempt in range(3):
        try:
            result = httpx.request(method, API + path, json=body, params=query, timeout=60, trust_env=False,
                                   follow_redirects=False, headers={'Authorization': 'Bearer ' + s.vercel_token})
        except httpx.HTTPError:
            if attempt + 1 >= attempts:
                raise AppError('Vercel is unreachable. Check network access, then retry the deployment.', 502, 'vercel_provider') from None
            time.sleep(2 * (attempt + 1))
            continue
        if (result.status_code == 429 or (result.status_code >= 500 and attempt + 1 < attempts)) and attempt < 2:
            time.sleep(3 * (attempt + 1))
            continue
        break
    if result.status_code == 429:
        raise AppError('Vercel rate limit reached. Retry the deployment shortly.', 429, 'vercel_rate_limited')
    if result.status_code in (401, 403):
        raise AppError('Vercel rejected the token. Check VERCEL_TOKEN and VERCEL_TEAM_ID.', 502, 'vercel_configuration')
    if result.status_code == 404:
        return None
    if not result.is_success:
        message = ''
        try:
            message = str((result.json().get('error') or {}).get('message', ''))
        except (ValueError, AttributeError):
            pass
        raise AppError('Vercel returned HTTP ' + str(result.status_code) + '. ' + redact(message)[:300], 502, 'vercel_provider')
    return result.json() if result.content else {}


def guard(name):
    if not NAME.fullmatch(name or ''):
        raise AppError('Refusing to manage a Vercel project that shift.AI did not generate.', 500, 'vercel_configuration')


def ensure_project(name):
    """Create or reuse the project. Plain static output, no framework, no env vars."""
    guard(name)
    project = api('GET', '/v9/projects/' + name)
    if not project:
        project = api('POST', '/v11/projects', {'name': name, 'framework': None})
    if (project or {}).get('name') != name:
        raise AppError('Vercel did not confirm the frontend project.', 502, 'vercel_provider')
    return project


def production_url(project_name):
    """The production domain Vercel assigned to the project.

    Standard Deployment Protection covers generated deployment URLs, not the
    production domain, so this is the public URL. `<name>.vercel.app` is
    preferred; Vercel adds a suffix when that name is taken.
    """
    guard(project_name)
    project = api('GET', '/v9/projects/' + project_name) or {}
    aliases = ((project.get('targets') or {}).get('production') or {}).get('alias') or []
    preferred = project_name + '.vercel.app'
    chosen = preferred if preferred in aliases else next((a for a in aliases if a.endswith('.vercel.app')), None)
    if not chosen:
        raise AppError('Vercel has not assigned a production domain yet.', 502, 'vercel_provider')
    return 'https://' + chosen


def frontend_files(build_files, upstream, spec):
    if not UPSTREAM.fullmatch(upstream):
        raise AppError('The backend origin is not a verified Render URL.', 409, 'deployment_validation')
    proxy = PROXY.read_text('utf-8').replace('__UPSTREAM__', json.dumps(upstream))
    files = [{'file': name.removeprefix('public/'), 'data': data} for name, data in build_files.items() if name.startswith('public/')]
    rewrites = [{'source': '/health', 'destination': '/api/proxy?route=health'},
                {'source': '/api/:route*', 'destination': '/api/proxy?route=:route*'},
                {'source': '/workspace', 'destination': '/index.html'},
                {'source': '/site/:slug', 'destination': '/site/:slug.html'}]
    pages = spec.get('public_pages', [])
    if pages:
        rewrites.insert(0, {'source': '/', 'destination': '/site/' + pages[0]['slug'] + '.html'})
    files += [{'file': 'release.json', 'data': build_files['release.json']},
              {'file': 'api/proxy.mjs', 'data': proxy},
              {'file': 'vercel.json', 'data': json.dumps({'rewrites': rewrites, 'headers': [{'source': '/(.*)', 'headers': SECURITY_HEADERS}]})}]
    return files


def create_deployment(project_name, files, meta):
    guard(project_name)
    result = api('POST', '/v13/deployments', {'name': project_name, 'project': project_name, 'target': 'production',
                                              'files': files, 'projectSettings': {'framework': None},
                                              'meta': {k: str(v)[:100] for k, v in meta.items()}})
    if not result or not result.get('id'):
        raise AppError('Vercel did not accept the frontend deployment.', 502, 'vercel_provider')
    return result['id']


def deployment_state(deployment_id):
    result = api('GET', '/v13/deployments/' + deployment_id)
    if not result:
        raise AppError('The Vercel deployment was not found.', 502, 'vercel_provider')
    return result.get('readyState') or result.get('status') or 'UNKNOWN'
