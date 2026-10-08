"""One-click deployment API. Owners and admins deploy; every project member can watch progress."""
import base64
import hashlib
import secrets
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from app.core.auth import user
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import get_store, now, serialize
from app.services import github_app as gh, launch_service
from app.services.account_security import cipher
from app.services.job_queue import enqueue

router = APIRouter(prefix='/api', tags=['One-click deployment'])


class DeployInput(BaseModel):
    build_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    prototype: bool = False


def callback_uri():
    return get_settings().deploy_callback_origin.rstrip('/') + '/api/deploy/github/callback'


def schedule(s, pid, account, launch, tasks):
    lid = str(launch['_id'])
    try:
        enqueue(s, 'launch', pid, account['id'], {'launch_id': lid, 'attempt': launch['attempt']}, tasks, launch_service.run, s, lid)
    except Exception:
        s.db.application_launches.update_one({'_id': launch['_id']}, {'$set': {'status': 'failed', 'error': {
            'stage': launch.get('stage'), 'code': 'deployment_error', 'message': 'The deployment could not be queued. Retry.'}}})
        launch_service.unlock(s.db, pid, lid)
        raise


@router.get('/projects/{pid}/deploy')
def overview(pid: str, account=Depends(user)):
    s = get_store()
    project = s.project(pid, account['id'])
    launches = [launch_service.recover(s.db, row) for row in s.db.application_launches.find({'project_id': pid}).sort('created_at', -1).limit(20)]
    return serialize({'missing': launch_service.requirements(), 'can_deploy': project['access_role'] in ('owner', 'admin'),
                      'github': {**gh.user_link(s.db, account['id']), 'oauth': gh.oauth_configured(), 'owner': get_settings().github_owner},
                      'site': launch_service.public_site(s.db.application_sites.find_one({'_id': pid})), 'launches': launches,
                      'stages': [{'key': key, 'label': label} for key, label in launch_service.STAGES]})


@router.post('/projects/{pid}/deploy', status_code=202)
def deploy(pid: str, body: DeployInput, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store()
    project = s.project(pid, account['id'], 'admin')
    launch = launch_service.start(s, project, account, body.build_id, prototype=body.prototype)
    s.activity(project, account['id'], 'One-click deployment started', body.build_id)
    schedule(s, pid, account, launch, tasks)
    return serialize(launch)


@router.get('/projects/{pid}/deploy/{lid}')
def status(pid: str, lid: str, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    return serialize(launch_service.get(s.db, pid, lid))


@router.post('/projects/{pid}/deploy/{lid}/retry', status_code=202)
def retry(pid: str, lid: str, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store()
    project = s.project(pid, account['id'], 'admin')
    launch = launch_service.retry(s, project, lid)
    s.activity(project, account['id'], 'Deployment retried', lid)
    schedule(s, pid, account, launch, tasks)
    return serialize(launch)


@router.post('/projects/{pid}/deploy/credentials')
def reveal_credentials(pid: str, account=Depends(user)):
    """The deployed application's initial administrator sign-in. Owners and admins only."""
    s = get_store()
    project = s.project(pid, account['id'], 'admin')
    s.activity(project, account['id'], 'Deployed application credentials viewed')
    return launch_service.credentials(s.db, pid)


@router.get('/deploy/github/connect')
def github_connect(project_id: str, account=Depends(user)):
    if not gh.oauth_configured():
        raise AppError('Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET of the GitHub App first.', 503, 'github_configuration')
    s = get_store()
    s.project(project_id, account['id'], 'admin')
    s.db.github_oauth_states.create_index('expires_at', expireAfterSeconds=0)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    s.db.github_oauth_states.insert_one({'_id': hashlib.sha256(state.encode()).hexdigest(), 'account': account['id'],
                                         'project_id': project_id, 'verifier': cipher().encrypt(verifier.encode()).decode(),
                                         'expires_at': now() + timedelta(minutes=10)})
    return {'url': gh.authorize_url(state, challenge, callback_uri())}


@router.get('/deploy/github/callback')
def github_callback(request: Request, code: str = '', state: str = '', error: str = ''):
    s = get_store()
    row = s.db.github_oauth_states.find_one_and_delete({'_id': hashlib.sha256(state.encode()).hexdigest()}) if state else None
    project = row['project_id'] if row and ObjectId.is_valid(row.get('project_id', '')) else ''
    target = get_settings().app_base_url.rstrip('/') + ('/project/' + project + '/application' if project else '/dashboard')
    try:
        account = user(request)
        expires = row['expires_at'].replace(tzinfo=now().tzinfo) if row else None
        if not row or row['account'] != account['id'] or expires < now():
            raise AppError('This GitHub authorization link expired. Start again from the deployment panel.', 400)
        if error or not code:
            raise AppError('GitHub authorization was cancelled.', 400)
        gh.exchange_code(s.db, account['id'], code, cipher().decrypt(row['verifier'].encode()).decode(), callback_uri())
    except AppError:
        return RedirectResponse(target + '?github=failed', status_code=303)
    return RedirectResponse(target + '?github=connected', status_code=303)
