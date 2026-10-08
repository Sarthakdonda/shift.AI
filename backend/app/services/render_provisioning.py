"""Render backend provisioning for generated applications (Render REST API v1).

Only services this platform generated are managed: names must match the
generated pattern, so the Shift.AI platform service itself is never modified,
redeployed or deleted. Non-idempotent POSTs are never blindly retried; callers
look the service up by name first.
"""
import re
import time
from urllib.parse import urlsplit
import httpx
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.github_app import redact

API = 'https://api.render.com/v1'
NAME = re.compile(r'^shift-[a-z0-9-]{1,80}$')
FAILED = {'build_failed', 'update_failed', 'pre_deploy_failed', 'canceled', 'deactivated'}


def requirements():
    s = get_settings()
    return [name for name, value in (('RENDER_API_KEY', s.render_api_key), ('RENDER_OWNER_ID', s.render_owner_id)) if not value]


def api(method, path, body=None, params=None):
    s = get_settings()
    attempts = 3 if method in ('GET', 'PUT') else 1
    result = None
    for attempt in range(3):
        try:
            result = httpx.request(method, API + path, json=body, params=params, timeout=30, trust_env=False,
                                   follow_redirects=False,
                                   headers={'Authorization': 'Bearer ' + s.render_api_key, 'Accept': 'application/json'})
        except httpx.HTTPError:
            if attempt + 1 >= attempts:
                raise AppError('Render is unreachable. Check network access, then retry the deployment.', 502, 'render_provider') from None
            time.sleep(2 * (attempt + 1))
            continue
        # 429 means the request was not processed, so retrying is safe for any method.
        retryable = result.status_code == 429 or (result.status_code >= 500 and attempt + 1 < attempts)
        if retryable and attempt < 2:
            try:
                wait = float(result.headers.get('Retry-After') or 2 * (attempt + 1))
            except ValueError:
                wait = 5.0
            time.sleep(min(30.0, wait))
            continue
        break
    if result.status_code == 429:
        raise AppError('Render rate limit reached. Retry the deployment in a minute.', 429, 'render_rate_limited')
    if result.status_code in (401, 403):
        raise AppError('Render rejected the API key. Check RENDER_API_KEY and its workspace access.', 502, 'render_configuration')
    if result.status_code == 404:
        return None
    if not result.is_success:
        message = ''
        try:
            message = str(result.json().get('message', ''))
        except ValueError:
            pass
        raise AppError('Render returned HTTP ' + str(result.status_code) + '. ' + redact(message)[:300], 502, 'render_provider')
    return result.json() if result.content else {}


def guard(name):
    if not NAME.fullmatch(name or ''):
        raise AppError('Refusing to manage a Render service that shift.AI did not generate.', 500, 'render_configuration')


def service_url(service):
    url = (service.get('serviceDetails') or {}).get('url', '')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.onrender.com'):
        raise AppError('Render did not return an HTTPS onrender.com URL for the service.', 502, 'render_provider')
    return url.rstrip('/')


def find_service(name):
    guard(name)
    rows = api('GET', '/services', params={'name': name, 'ownerId': get_settings().render_owner_id, 'limit': 20}) or []
    return next((item.get('service', item) for item in rows if item.get('service', item).get('name') == name), None)


def get_service(service_id, name):
    service = api('GET', '/services/' + service_id)
    if service:
        guard(service.get('name'))
        if service.get('name') != name:
            raise AppError('The recorded Render service belongs to another application.', 409, 'render_configuration')
    return service


def create_service(name, repo_url, branch, env, manifest):
    """POST /services. Returns (service, initial deploy id)."""
    guard(name)
    s = get_settings()
    backend = manifest['backend']
    body = {'type': 'web_service', 'name': name, 'ownerId': s.render_owner_id, 'repo': repo_url, 'branch': branch,
            'autoDeploy': 'no', 'envVars': [{'key': k, 'value': v} for k, v in env.items()],
            'serviceDetails': {'runtime': 'python', 'plan': s.render_plan, 'region': s.render_region,
                               'healthCheckPath': backend['health_check_path'], 'numInstances': 1,
                               'envSpecificDetails': {'buildCommand': backend['build_command'],
                                                      'startCommand': backend['start_command']}}}
    try:
        result = api('POST', '/services', body)
    except AppError as exc:
        if 'repo' in exc.message.lower() or 'git' in exc.message.lower():
            raise AppError('Render cannot access ' + repo_url + '. In Render, connect the GitHub account that owns it '
                           '(Account settings > Git credentials) and allow this repository, then retry. ' + exc.message,
                           409, 'render_repository_access') from None
        raise
    if not result or 'service' not in result:
        raise AppError('Render did not confirm service creation.', 502, 'render_provider')
    return result['service'], result.get('deployId')


def set_env(service_id, env):
    """Add or update only the managed keys; variables the owner added are preserved.

    Values are never logged or returned.
    """
    for key, value in env.items():
        api('PUT', '/services/' + service_id + '/env-vars/' + key, {'value': value})


def trigger_deploy(service_id, commit):
    result = api('POST', '/services/' + service_id + '/deploys', {'commitId': commit, 'clearCache': 'do_not_clear'}) or {}
    if result.get('id'):
        return result['id']
    # 202: queued behind an in-progress deploy; find it by commit.
    for item in api('GET', '/services/' + service_id + '/deploys', params={'limit': 10}) or []:
        deploy = item.get('deploy', item)
        if (deploy.get('commit') or {}).get('id') == commit:
            return deploy['id']
    raise AppError('Render accepted the deploy but did not return its identifier. Retry to resume.', 502, 'render_provider')


def deploy_status(service_id, deploy_id):
    deploy = api('GET', '/services/' + service_id + '/deploys/' + deploy_id)
    if not deploy:
        raise AppError('The Render deploy was not found.', 502, 'render_provider')
    return deploy.get('status', 'unknown'), (deploy.get('commit') or {}).get('id')


def outbound_ips(service_id):
    result = api('GET', '/services/' + service_id + '/outbound-ips')
    ips = (result or {}).get('ips') or []
    if not ips:
        raise AppError('Render did not report outbound IP ranges for the service.', 502, 'render_provider')
    return ips
