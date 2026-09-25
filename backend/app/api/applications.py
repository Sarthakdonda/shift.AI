from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.core.auth import user
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.application import PlanInput, SpecEdit, VersionInput, BuildInput, CreditGrant, PlanConfig
from app.repositories.store import get_store, now, serialize
from app.services.gemini_service import get_gemini
from app.services import application_service as service, application_runner as runner, billing_service as billing, deployment_service as deployment
from app.services.application_generator import archive, compatibility, digest
from app.services.project_service import ProjectService
from app.services.url_service import extract_url
from app.services import vercel_deployment

router = APIRouter(prefix='/api', tags=['Application builder'])


def build_for(s, pid, bid):
    if not ObjectId.is_valid(bid):
        raise AppError('Build not found.', 404)
    build = s.db.application_builds.find_one({'_id': ObjectId(bid), 'project_id': pid})
    if not build:
        raise AppError('Build not found.', 404)
    return build


@router.get('/billing')
def credits(account=Depends(user)):
    s = get_store()
    billing.recover_orphans(s, account['id'])
    return {'account': serialize(billing.account(s, account['id'])), 'plans': billing.PLANS, 'plan': billing.policy(s), 'build_cost': billing.policy(s)['build_cost'],
            'policy': 'Credits are reserved once and charged only after isolated runtime validation succeeds. Failed or unvalidated builds are refunded.', 'payments_enabled': False}


@router.get('/projects/{pid}/application')
def overview(pid: str, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'])
    for preview in s.db.application_previews.find({'project_id': pid, 'status': 'running', 'expires_at': {'$lte': now()}}):
        try:
            runner.stop_preview(preview['container'])
        except AppError as exc:
            # Leave the stop action available when Docker cleanup needs a retry.
            s.db.application_previews.update_one({'_id': preview['_id']}, {'$set': {'cleanup_error': exc.message}})
        else:
            s.db.application_previews.update_one({'_id': preview['_id']}, {'$set': {'status': 'expired'}, '$unset': {'cleanup_error': ''}})
    # Recover interrupted build reservations after the existing project lease expires.
    if not p.get('busy'):
        for build in s.db.application_builds.find({'project_id': pid, 'status': {'$in': ['queued', 'compiling', 'validating']}, 'created_at': {'$lt': now() - timedelta(minutes=30)}}):
            billing.settle(s, build['billing_actor'], build['request_id'], False)
            s.db.application_builds.update_one({'_id': build['_id']}, {'$set': {'status': 'failed', 'error': 'Build interrupted. Credits refunded; retry generation.'}})
    # Reconcile crash windows after the build result was persisted but before billing.
    for build in s.db.application_builds.find({'project_id': pid, 'status': {'$in': ['ready', 'failed', 'validation_required']}}):
        billing.settle(s, build['billing_actor'], build['request_id'], build['status'] == 'ready')
    specs = list(s.db.application_specs.find({'project_id': pid}, {'blueprint_snapshot': 0}).sort('version', -1).limit(100))
    builds = list(s.db.application_builds.find({'project_id': pid}, {'files': 0}).sort('created_at', -1).limit(100))
    deployments = list(s.db.application_deployments.find({'project_id': pid}).sort('created_at', -1).limit(100))
    stale = False
    if specs:
        try:
            service.assert_current(s, p, service.latest_spec(s, pid))
        except AppError:
            stale = True
    return serialize({'specs': specs, 'builds': builds, 'deployments': deployments, 'job': p.get('application_job'),
                      'role': p['access_role'], 'busy': p.get('busy', False), 'stale': stale,
                      'deployment_configured': bool(deployment.target_for(pid)), 'build_cost': billing.policy(s)['build_cost'],
                      'vercel_configured': bool(get_settings().vercel_token),
                      'platform_admin': account['id'] in [v.strip() for v in get_settings().builder_admin_ids.split(',')],
                      'preview': s.db.application_previews.find_one({'project_id': pid, 'status': 'running'}, {'password': 0})})


@router.post('/projects/{pid}/application/plan', status_code=202)
def plan(pid: str, body: PlanInput, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'], 'write')
    service.current_blueprint(s, p)
    ai = get_gemini(); ai.require()
    s.acquire(pid, account['id'])
    s.update(pid, application_job={'status': 'planning'})
    tasks.add_task(service.plan_job, s, ai, pid, account['id'], body.instructions, body.base_version)
    return {'status': 'planning'}


@router.post('/projects/{pid}/application/spec')
def edit_spec(pid: str, body: SpecEdit, account=Depends(user)):
    s = get_store(); s.acquire(pid, account['id'])
    try:
        p = s.project(pid, account['id'], 'write'); previous = service.latest_spec(s, pid)
        if not previous or previous['version'] != body.base_version:
            raise AppError('A newer specification exists. Refresh before saving.', 409)
        return serialize(service.save_spec(s, p, body.spec.model_dump(), account['id'], previous))
    finally:
        s.update(pid, busy=False)


@router.post('/projects/{pid}/application/approve')
def approve(pid: str, body: VersionInput, account=Depends(user)):
    s = get_store(); s.acquire(pid, account['id'], 'review')
    try:
        p = s.project(pid, account['id'], 'review'); spec = service.latest_spec(s, pid)
        if not spec or spec['version'] != body.version:
            raise AppError('Review the latest specification before approval.', 409)
        service.assert_current(s, p, spec)
        if spec.get('migration_issues'):
            raise AppError('Resolve unsafe schema changes before approval: ' + ' '.join(spec['migration_issues']), 409)
        if spec.get('ai_reviews') and any(f.get('requires_revision') and f.get('severity') in ('HIGH', 'CRITICAL') for f in spec['ai_reviews'][-1]['findings']):
            raise AppError('Resolve the application review findings and save a revised draft before approval.', 409)
        approval = {'actor': account['id'], 'created_at': now(), 'spec_hash': digest(spec['spec']), 'blueprint_hash': spec['blueprint_hash']}
        s.db.application_specs.update_one({'_id': spec['_id']}, {'$set': {'approval': approval}})
        s.activity(p, account['id'], 'Application blueprint approved', f"Blueprint v{spec['blueprint_version']}, application specification v{spec['version']}")
        return serialize(approval)
    finally:
        s.update(pid, busy=False)


@router.post('/projects/{pid}/application/build', status_code=202)
def build(pid: str, body: BuildInput, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'], 'write')
    if not get_settings().builder_enabled:
        raise AppError('Application generation is disabled by the operator.', 503, 'builder_configuration')
    previous = s.db.application_builds.find_one({'project_id': pid, 'request_id': pid + ':' + body.request_id})
    if previous:
        if previous['spec_version'] != body.version:
            raise AppError('This request ID belongs to a different specification version.', 409)
        return serialize({k: v for k, v in previous.items() if k != 'files'})
    s.acquire(pid, account['id'])
    reserved = False
    # Scope the ledger key to the project as well as client retry identity.
    key = pid + ':' + body.request_id
    try:
        p = s.project(pid, account['id'], 'write'); spec = service.latest_spec(s, pid)
        if not spec or spec['version'] != body.version:
            raise AppError('Review and approve the latest specification.', 409)
        service.assert_current(s, p, spec, approved=True)
        if body.quoted_cost is not None and body.quoted_cost != billing.policy(s)['build_cost']:
            raise AppError('The build price changed. Refresh and review the new cost before generating.', 409)
        reserved = billing.reserve(s, account['id'], key)
        if not reserved:
            raise AppError('This operation was already attempted. Use a new request ID for a new build.', 409)
        doc = {'project_id': pid, 'request_id': key, 'client_request_id': body.request_id, 'spec_id': str(spec['_id']), 'spec_version': spec['version'],
               'spec': spec['spec'], 'blueprint_id': spec['blueprint_id'], 'approval': spec['approval'], 'billing_actor': account['id'],
               'status': 'queued', 'logs': ['Queued application generation.'], 'created_at': now()}
        doc['_id'] = s.db.application_builds.insert_one(doc).inserted_id
        tasks.add_task(service.build_job, s, pid, account['id'], str(doc['_id']))
        return serialize(doc)
    except Exception:
        if reserved:
            billing.settle(s, account['id'], key, False)
        s.update(pid, busy=False)
        raise


@router.get('/projects/{pid}/application/builds/{bid}/download')
def download(pid: str, bid: str, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'])
    build = build_for(s, pid, bid)
    if not build.get('files'):
        raise AppError('Application files are not available yet.', 409)
    return Response(archive(build['files']), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="application-{bid}.zip"'})


@router.post('/projects/{pid}/application/builds/{bid}/preview')
def preview(pid: str, bid: str, request: Request, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'], 'write')
    if not get_settings().application_preview_enabled:
        raise AppError('Local container preview is disabled on this server.', 409)
    if not request.client or request.client.host not in ('127.0.0.1', '::1', 'localhost', 'testclient'):
        raise AppError('This preview runs on the builder host. A remote preview gateway is not configured.', 409)
    build = build_for(s, pid, bid)
    if build['status'] != 'ready':
        raise AppError('Run successful isolated validation before starting a preview.', 409)
    s.acquire(pid, account['id'])
    try:
        old = s.db.application_previews.find_one({'project_id': pid, 'status': 'running'})
        if old:
            runner.stop_preview(old['container'])
            s.db.application_previews.update_one({'_id': old['_id']}, {'$set': {'status': 'stopped'}})
        result = runner.preview(bid)
        row = {k: v for k, v in result.items() if k != 'password'}
        row.update(project_id=pid, build_id=bid, actor=account['id'], status='running', created_at=now(), expires_at=now() + timedelta(seconds=result['expires_in_seconds']))
        try:
            s.db.application_previews.insert_one(row)
        except Exception:
            runner.stop_preview(result['container'])
            raise
        return result
    finally:
        s.update(pid, busy=False)


@router.post('/projects/{pid}/application/preview/stop')
def stop_preview(pid: str, account=Depends(user)):
    s = get_store(); s.acquire(pid, account['id'])
    try:
        for row in s.db.application_previews.find({'project_id': pid, 'status': 'running'}):
            runner.stop_preview(row['container'])
            s.db.application_previews.update_one({'_id': row['_id']}, {'$set': {'status': 'stopped'}})
        return {'ok': True}
    finally:
        s.update(pid, busy=False)


def platform_admin(account):
    if account['id'] not in [v.strip() for v in get_settings().builder_admin_ids.split(',') if v.strip()]:
        raise AppError('Platform administrator permission required.', 403)


@router.get('/builder/admin')
def admin_monitor(account=Depends(user)):
    platform_admin(account); s = get_store()
    return serialize({'plan': billing.policy(s), 'accounts': list(s.db.credit_accounts.find({}, {'entries': 0}).limit(100)),
        'builds': list(s.db.application_builds.find({}, {'files': 0, 'spec': 0}).sort('created_at', -1).limit(100)),
        'deployments': list(s.db.application_deployments.find({}).sort('created_at', -1).limit(100))})


@router.post('/builder/admin/credits')
def admin_credit(body: CreditGrant, account=Depends(user)):
    platform_admin(account); s = get_store()
    billing.grant(s, body.account_id, 'grant:' + body.request_id, body.amount)
    s.db.builder_audit.insert_one({'actor': account['id'], 'action': 'credit_grant', **body.model_dump(), 'created_at': now()})
    return {'ok': True}


@router.post('/builder/admin/plan')
def admin_plan(body: PlanConfig, account=Depends(user)):
    platform_admin(account); s = get_store()
    s.db.builder_plans.update_one({'_id': 'default'}, {'$set': body.model_dump()}, upsert=True)
    s.db.builder_audit.insert_one({'actor': account['id'], 'action': 'plan_updated', 'policy': body.model_dump(), 'created_at': now()})
    return {'ok': True}


@router.post('/projects/{pid}/application/builds/{bid}/deploy', status_code=202)
def deploy(pid: str, bid: str, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'], 'admin')
    build = build_for(s, pid, bid)
    if build['status'] != 'ready':
        raise AppError('This build has not passed isolated validation.', 409)
    if not deployment.target_for(pid):
        raise AppError('Set RENDER_API_KEY and the project entry in RENDER_TARGETS_JSON.', 503)
    if any(r['implementation'] == 'manual' for r in build['spec']['requirements']):
        raise AppError('This specification includes unimplemented requirements. Resolve them before deployment.', 409)
    # Historical builds can only be deployed when compatible with the current live data schema.
    live = s.db.application_deployments.find_one({'project_id': pid, 'status': 'live'}, sort=[('created_at', -1)])
    if live:
        current = build_for(s, pid, live['build_id'])
        issues = compatibility(current['spec'], build['spec'])
        if issues:
            raise AppError('Unsafe downgrade blocked. ' + ' '.join(issues), 409)
    s.acquire(pid, account['id'], 'admin')
    try:
        active = s.db.application_deployments.find_one({'project_id': pid, 'status': {'$in': ['queued', 'pushing', 'submitting', 'deploying', 'health_pending']}})
        if active:
            raise AppError('A deployment is already pending. Refresh its provider status first.', 409)
        doc = {'project_id': pid, 'build_id': bid, 'status': 'queued', 'logs': ['Checking deployment readiness.'], 'actor': account['id'], 'created_at': now()}
        doc['_id'] = s.db.application_deployments.insert_one(doc).inserted_id
        s.activity(p, account['id'], 'Application deployment requested', bid)
        tasks.add_task(deployment.deploy_job, s, pid, account['id'], str(doc['_id']))
        return serialize(doc)
    except Exception:
        s.update(pid, busy=False)
        raise


@router.post('/projects/{pid}/application/deployments/{did}/refresh')
def refresh_deployment(pid: str, did: str, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'])
    if not ObjectId.is_valid(did):
        raise AppError('Deployment not found.', 404)
    item = s.db.application_deployments.find_one({'_id': ObjectId(did), 'project_id': pid})
    if not item:
        raise AppError('Deployment not found.', 404)
    provider = vercel_deployment if item.get('target') == 'vercel' else deployment
    return serialize(provider.refresh(s, item))


@router.post('/projects/{pid}/application/builds/{bid}/deploy/vercel', status_code=202)
def deploy_vercel(pid: str, bid: str, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'], 'admin')
    build = build_for(s, pid, bid)
    if build['status'] != 'ready' or any(r['implementation'] == 'manual' for r in build['spec']['requirements']):
        raise AppError('Deploy only validated applications with all requirements implemented.', 409)
    if not get_settings().vercel_token:
        raise AppError('Set VERCEL_TOKEN on the backend first.', 503, 'deployment_configuration')
    if not s.db.application_deployments.find_one({'project_id': pid, 'build_id': bid, 'target': {'$ne': 'vercel'}, 'status': 'live'}):
        raise AppError('Deploy and verify this build on Render first.', 409)
    s.acquire(pid, account['id'], 'admin')
    try:
        if s.db.application_deployments.find_one({'project_id': pid, 'status': {'$in': ['queued', 'pushing', 'submitting', 'deploying', 'health_pending']}}):
            raise AppError('Another deployment is pending. Refresh its status first.', 409)
        row = {'project_id': pid, 'build_id': bid, 'target': 'vercel', 'status': 'queued', 'actor': account['id'], 'logs': ['Preparing Vercel frontend with the verified Render backend.'], 'created_at': now()}
        row['_id'] = s.db.application_deployments.insert_one(row).inserted_id
        tasks.add_task(vercel_deployment.deploy_job, s, pid, account['id'], str(row['_id']))
        return serialize(row)
    except Exception:
        s.update(pid, busy=False)
        raise


class URLInput(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


@router.post('/projects/{pid}/documents/url', status_code=202)
def import_url(pid: str, body: URLInput, tasks: BackgroundTasks, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'], 'write')
    ai = get_gemini(); ai.require()
    s.acquire(pid, account['id'])
    try:
        if s.db.documents.count_documents({'project_id': pid}) >= 20:
            raise AppError('Each project supports up to 20 sources.')
        text, final_url = extract_url(body.url)
        data = text.encode('utf-8')
        doc = {'project_id': pid, 'filename': 'website.txt', 'source_url': final_url, 'file_type': 'txt', 'size': len(data),
               'status': 'processing', 'summary': '', 'error': None, 'created_at': now()}
        doc['_id'] = s.db.documents.insert_one(doc).inserted_id
        tasks.add_task(ProjectService(s, ai).process_document, pid, account['id'], doc['_id'], data, '.txt', 'website.txt')
        return serialize(doc)
    except Exception:
        s.update(pid, busy=False)
        raise
