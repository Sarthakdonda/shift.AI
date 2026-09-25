"""Deploy exact validated images; never infer success from an accepted request."""
import json
from urllib.parse import urlsplit
import httpx
from bson import ObjectId
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.application import TargetInput
from app.repositories.store import now
from app.services.application_generator import digest
from app.services.application_runner import docker, image_name
from app.services.url_service import fetch_public


def target_for(pid):
    settings = get_settings()
    try:
        entry = json.loads(settings.render_targets_json).get(pid)
        target = TargetInput.model_validate(entry).model_dump() if entry else None
    except (ValueError, TypeError, AttributeError):
        raise AppError('RENDER_TARGETS_JSON must map project IDs to valid Render service IDs and image repositories.', 503)
    return target if settings.render_api_key and target else None


def render_api(method, path, body=None):
    try:
        response = httpx.request(method, 'https://api.render.com/v1' + path,
            headers={'Authorization': 'Bearer ' + get_settings().render_api_key}, json=body, timeout=30, follow_redirects=False, trust_env=False)
        if response.status_code >= 300:
            raise AppError(f'Render returned HTTP {response.status_code}. Check service permissions and provider dashboard logs.', 502)
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise AppError('Render could not be reached. Refresh deployment status before retrying.', 502) from None


def preflight(target):
    sid = target['service_id']
    service = render_api('GET', '/services/' + sid)
    details = service.get('serviceDetails', {})
    if service.get('type') != 'web_service' or details.get('env') != 'image':
        raise AppError('Configure an image-backed Render web service for this project.', 409)
    image = service.get('imagePath') or service.get('image', {}).get('imagePath') or details.get('image', {}).get('imagePath', '')
    if image and not (image.startswith(target['image_repository'] + ':') or image.startswith(target['image_repository'] + '@')):
        raise AppError('Render service image does not match the configured repository.', 409)
    disks = render_api('GET', '/disks?serviceId=' + sid + '&limit=100')
    if not any(item.get('disk', item).get('mountPath') == '/app/data' for item in disks):
        raise AppError('Attach a persistent Render disk at /app/data before deployment.', 409)
    entries = render_api('GET', '/services/' + sid + '/env-vars?limit=100')
    env = {item.get('envVar', item).get('key'): item.get('envVar', item).get('value', '') for item in entries}
    missing = [key for key in ('ADMIN_EMAIL', 'ADMIN_PASSWORD', 'APP_ORIGIN') if not env.get(key)]
    if missing or len(env.get('ADMIN_PASSWORD', '')) < 12 or env.get('COOKIE_SECURE', 'true').lower() != 'true':
        raise AppError('Configure ADMIN_EMAIL, a 12+ character ADMIN_PASSWORD, APP_ORIGIN and COOKIE_SECURE=true in Render.', 409)
    if env.get('DATABASE_PATH', '/app/data/application.db') != '/app/data/application.db':
        raise AppError('DATABASE_PATH must be /app/data/application.db on the persistent disk.', 409)
    if details.get('numInstances', 1) != 1:
        raise AppError('The SQLite runtime requires one instance.', 409)
    return service


def deploy_job(s, pid, actor, deployment_id):
    did = ObjectId(deployment_id)
    deployment = s.db.application_deployments.find_one({'_id': did})
    try:
        s.project(pid, actor, 'admin')
        target = target_for(pid)
        if not target:
            raise AppError('Configure RENDER_API_KEY and RENDER_TARGETS_JSON first.', 503)
        preflight(target)
        build_id = deployment['build_id']
        build = s.db.application_builds.find_one({'_id': ObjectId(build_id), 'project_id': pid})
        if not build or build['status'] != 'ready':
            raise AppError('Only an application that passed isolated validation can be deployed.', 409)
        tag = target['image_repository'] + ':' + build_id
        docker('tag', image_name(build_id), tag)
        s.db.application_deployments.update_one({'_id': did}, {'$set': {'status': 'pushing'}, '$push': {'logs': 'Publishing the validated container image.'}})
        docker('push', tag, timeout=180)
        # Use the immutable registry digest, not a mutable tag.
        images = json.loads(docker('image', 'inspect', tag))
        refs = images[0].get('RepoDigests', [])
        image_url = next((ref for ref in refs if ref.startswith(target['image_repository'] + '@sha256:')), None)
        if not image_url:
            raise AppError('The pushed image digest could not be verified. Deployment stopped.', 409)
        s.db.application_deployments.update_one({'_id': did}, {'$set': {'status': 'submitting', 'image_url': image_url}, '$push': {'logs': 'Image digest verified. Requesting deployment from Render.'}})
        result = render_api('POST', '/services/' + target['service_id'] + '/deploys', {'imageUrl': image_url})
        s.db.application_deployments.update_one({'_id': did}, {'$set': {'status': 'deploying', 'provider_id': result['id'], 'service_id': target['service_id']}, '$push': {'logs': 'Render accepted the deployment. Awaiting provider status and health check.'}})
    except Exception as exc:
        s.db.application_deployments.update_one({'_id': did}, {'$set': {'status': 'failed', 'error': exc.message if isinstance(exc, AppError) else 'Deployment failed. Check provider logs before retrying.', 'finished_at': now()}})
    finally:
        s.update(pid, busy=False)


def refresh(s, deployment):
    if deployment['status'] in ('queued', 'pushing', 'submitting') and (now() - deployment['created_at'].replace(tzinfo=now().tzinfo)).total_seconds() > 1800:
        values = {'status': 'failed', 'error': 'Deployment worker was interrupted. Inspect provider history before retrying; a submitted release may still be running.'}
        s.db.application_deployments.update_one({'_id': deployment['_id']}, {'$set': values})
        return {**deployment, **values}
    if deployment['status'] not in ('deploying', 'health_pending'):
        return deployment
    sid, provider = deployment['service_id'], deployment['provider_id']
    result = render_api('GET', f'/services/{sid}/deploys/{provider}')
    state = result.get('status', 'unknown')
    values = {'provider_status': state, 'checked_at': now()}
    if state in ('build_failed', 'update_failed', 'pre_deploy_failed', 'canceled', 'deactivated'):
        values.update(status='failed', error='Render reported ' + state + '. Open the provider dashboard for details.')
    elif state == 'live':
        service = render_api('GET', '/services/' + sid)
        url = service.get('serviceDetails', {}).get('url', '')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.onrender.com'):
            raise AppError('Render did not return a supported HTTPS service URL.', 502)
        values.update(status='health_pending')
        try:
            raw, _, _ = fetch_public(url.rstrip('/') + '/health', max_bytes=10000, content_types=('application/json',), redirects=0)
            health = json.loads(raw)
            build = s.db.application_builds.find_one({'_id': ObjectId(deployment['build_id'])})
            if health.get('status') == 'ok' and health.get('build_id') == deployment['build_id'] and health.get('spec_hash') == digest(build['spec']):
                values.update(status='live', live_url=url, finished_at=now(), error=None)
            else:
                values['error'] = 'Health endpoint has not confirmed this exact application version yet.'
        except (AppError, ValueError):
            values['error'] = 'Provider reports live; application health is not verified yet. Retry status check.'
    s.db.application_deployments.update_one({'_id': deployment['_id']}, {'$set': values})
    return {**deployment, **values}
