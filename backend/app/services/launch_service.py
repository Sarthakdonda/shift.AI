"""Durable one-click deployment of a generated web application.

validate -> database -> repository -> backend -> connectivity -> frontend -> verification

Each stage persists its results. A retry resumes at the failed stage and reuses
the repository, database, backend and frontend that already exist, so nothing is
duplicated. Stored records never contain provider credentials or the database
URI; the URI is decrypted only while the backend environment is written.
"""
import json
import secrets
import time
from datetime import timedelta
import httpx
from bson import ObjectId
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now
from app.services import atlas_provisioning as atlas, github_app as gh, render_provisioning as render, vercel_provisioning as vercel
from app.services.account_security import cipher
from app.services.application_generator import compatibility
from app.services.deploy_validation import validate_build
from app.services.launch_verify import check as verify_live

STAGES = [('validate', 'Validating application'), ('database', 'Preparing database'),
          ('repository', 'Preparing GitHub repository'), ('backend', 'Deploying backend'),
          ('connectivity', 'Configuring connectivity'), ('frontend', 'Deploying frontend'),
          ('verification', 'Running verification')]
ACTIVE = ('queued', 'running')
HOURLY_LIMIT = 10
MAX_ATTEMPTS = 5
sleep = time.sleep  # replaced in tests


def requirements():
    return list(dict.fromkeys(atlas.requirements() + gh.requirements() + render.requirements() + vercel.requirements()))


# ---- application identity and locking -------------------------------------------
def ensure_site(db, pid, spec, account):
    """One durable identity per application; names never change after the first deploy."""
    name = gh.repository_name(pid, spec.get('name', 'app'))
    db.application_sites.update_one({'_id': pid}, {'$setOnInsert': {
        'name': name, 'created_at': now(), 'active_launch': None,
        'admin_email': (account.get('email') or '').strip().lower() or 'owner@' + name + '.local',
        'admin_password': cipher().encrypt(secrets.token_urlsafe(24).encode()).decode()}}, upsert=True)
    return db.application_sites.find_one({'_id': pid})


def lock(db, pid, lid):
    moment = now()
    held = db.application_sites.find_one_and_update(
        {'_id': pid, '$or': [{'active_launch': None}, {'lock_until': {'$lt': moment}}]},
        {'$set': {'active_launch': lid, 'lock_until': moment + timedelta(minutes=get_settings().deploy_timeout_minutes + 20)}})
    if not held:
        raise AppError('A deployment of this application is already running. Wait for it to finish.', 409, 'deployment_active')


def unlock(db, pid, lid):
    db.application_sites.update_one({'_id': pid, 'active_launch': lid}, {'$set': {'active_launch': None}, '$unset': {'lock_until': ''}})


def public_site(site):
    if not site:
        return None
    return {k: v for k, v in site.items() if k not in ('admin_password', 'active_launch', 'lock_until')}


def credentials(db, pid):
    site = db.application_sites.find_one({'_id': pid})
    if not site:
        raise AppError('This application has not been deployed.', 404)
    return {'email': site['admin_email'], 'password': cipher().decrypt(site['admin_password'].encode()).decode()}


# ---- starting and retrying ---------------------------------------------------------
def start(store, project, account, build_id, *, prototype=False):
    db, pid = store.db, str(project['_id'])
    missing = requirements()
    if missing:
        raise AppError('One-click deployment needs ' + ', '.join(missing) + ' in backend/.env.', 503, 'deployment_configuration')
    if not ObjectId.is_valid(build_id):
        raise AppError('Build not found.', 404)
    build = db.application_builds.find_one({'_id': ObjectId(build_id), 'project_id': pid})
    if not build:
        raise AppError('Build not found.', 404)
    validate_build(build, allow_manual=prototype)
    manual = [{'id': r['id'], 'description': r['description']} for r in build['spec'].get('requirements', [])
              if r.get('implementation') == 'manual']
    if db.application_launches.count_documents({'actor': account['id'], 'created_at': {'$gt': now() - timedelta(hours=1)}}) >= HOURLY_LIMIT:
        raise AppError('Deployment limit reached (' + str(HOURLY_LIMIT) + ' per hour). Retry later.', 429, 'deployment_rate_limited')
    site = ensure_site(db, pid, build['spec'], account)
    lid = ObjectId()
    lock(db, pid, str(lid))
    doc = {'_id': lid, 'project_id': pid, 'build_id': build_id, 'actor': account['id'], 'name': site['name'],
           'status': 'queued', 'stage': STAGES[0][0], 'attempt': 1, 'error': None,
           'prototype': prototype, 'manual_requirements': manual,
           'logs': ['Deployment requested.'] + ([f'Prototype scope: {len(manual)} requirements remain unimplemented. Deployment verifies the generated functionality only.'] if manual else []),
           'stages': [{'key': key, 'label': label, 'status': 'pending'} for key, label in STAGES],
           'created_at': now(), 'updated_at': now(), 'heartbeat_at': now()}
    try:
        db.application_launches.insert_one(doc)
    except Exception:
        unlock(db, pid, str(lid))
        raise
    return doc


def get(db, pid, lid):
    if not ObjectId.is_valid(lid):
        raise AppError('Deployment not found.', 404)
    launch = db.application_launches.find_one({'_id': ObjectId(lid), 'project_id': pid})
    if not launch:
        raise AppError('Deployment not found.', 404)
    return recover(db, launch)


def recover(db, launch):
    """A deployment whose worker vanished is marked failed so it can be retried."""
    stale = now() - timedelta(minutes=15)
    beat = launch.get('heartbeat_at') or launch['created_at']
    if launch['status'] in ACTIVE and beat.replace(tzinfo=stale.tzinfo) < stale:
        pending = db.builder_jobs.find_one({'kind': 'launch', 'payload.launch_id': str(launch['_id']), 'status': {'$in': ['queued', 'running']}})
        if not pending:
            error = {'stage': launch.get('stage'), 'code': 'deployment_interrupted',
                     'message': 'The deployment worker stopped. Completed stages are preserved; retry to resume.'}
            db.application_launches.update_one({'_id': launch['_id'], 'status': {'$in': list(ACTIVE)}},
                                               {'$set': {'status': 'failed', 'error': error, 'finished_at': now()}})
            unlock(db, launch['project_id'], str(launch['_id']))
            launch = db.application_launches.find_one({'_id': launch['_id']})
    return launch


def retry(store, project, lid):
    db, pid = store.db, str(project['_id'])
    launch = get(db, pid, lid)
    if launch['status'] != 'failed':
        raise AppError('Only a failed deployment can be retried.', 409)
    if launch['attempt'] >= MAX_ATTEMPTS:
        raise AppError('This deployment was retried ' + str(MAX_ATTEMPTS) + ' times. Resolve the reported problem and start a new deployment.', 429, 'deployment_rate_limited')
    lock(db, pid, lid)
    failed = next((i for i, s in enumerate(launch['stages']) if s['status'] != 'done'), 0)
    stages = [s if i < failed else {'key': s['key'], 'label': s['label'], 'status': 'pending'} for i, s in enumerate(launch['stages'])]
    db.application_launches.update_one({'_id': launch['_id'], 'status': 'failed'}, {
        '$set': {'status': 'queued', 'stages': stages, 'error': None, 'finished_at': None, 'updated_at': now(), 'heartbeat_at': now()},
        '$inc': {'attempt': 1}, '$push': {'logs': 'Retry requested. Completed stages are reused.'}})
    return db.application_launches.find_one({'_id': launch['_id']})


# ---- execution ---------------------------------------------------------------------
class Context:
    def __init__(self, store, launch):
        self.store, self.db, self.launch = store, store.db, launch
        self.pid, self.lid = launch['project_id'], launch['_id']
        self._build = None

    @property
    def site(self):
        return self.db.application_sites.find_one({'_id': self.pid})

    @property
    def build(self):
        if self._build is None:
            self._build = self.db.application_builds.find_one({'_id': ObjectId(self.launch['build_id']), 'project_id': self.pid})
            if not self._build:
                raise AppError('The build for this deployment no longer exists.', 409, 'deployment_validation')
        return self._build

    @property
    def plan(self):
        return json.loads(self.build['files']['deploy.json'])

    def admin_password(self):
        return cipher().decrypt(self.site['admin_password'].encode()).decode()

    def set(self, **values):
        self.launch.update(values)
        self.db.application_launches.update_one({'_id': self.lid}, {'$set': {**values, 'updated_at': now(), 'heartbeat_at': now()}})

    def site_set(self, **values):
        self.db.application_sites.update_one({'_id': self.pid}, {'$set': values})

    def log(self, text):
        self.db.application_launches.update_one({'_id': self.lid}, {'$push': {'logs': gh.redact(text)[:500]}, '$set': {'heartbeat_at': now()}})

    def mark(self, key, status, detail=None):
        values = {'stages.$.status': status, 'stage': key, 'heartbeat_at': now(), 'updated_at': now()}
        values['stages.$.' + ('started_at' if status == 'running' else 'finished_at')] = now()
        if detail is not None:
            values['stages.$.detail'] = gh.redact(detail)[:600]
        self.db.application_launches.update_one({'_id': self.lid, 'stages.key': key}, {'$set': values})

    def wait(self, check, timeout_minutes, what):
        deadline = time.monotonic() + timeout_minutes * 60
        while True:
            outcome = check()
            if outcome is not None:
                return outcome
            if time.monotonic() > deadline:
                raise AppError(what + ' did not finish within ' + str(timeout_minutes) + ' minutes. Retry to keep waiting; nothing will be duplicated.', 504, 'deployment_timeout')
            self.db.application_launches.update_one({'_id': self.lid}, {'$set': {'heartbeat_at': now()}})
            sleep(get_settings().deploy_poll_seconds)


def stage_validate(ctx):
    plan = validate_build(ctx.build, allow_manual=ctx.launch.get('prototype', False))
    live = ctx.site.get('live') or {}
    if live.get('build_id') and live['build_id'] != ctx.launch['build_id']:
        previous = ctx.db.application_builds.find_one({'_id': ObjectId(live['build_id'])}, {'spec': 1})
        issues = compatibility(previous['spec'], ctx.build['spec']) if previous else []
        if issues:
            raise AppError('This version would break the live database: ' + ' '.join(issues[:3]), 409, 'deployment_validation')
    return plan['name'] + ': Python backend, static frontend and MongoDB for ' + str(len(ctx.build['spec']['entities'])) + ' modules.'


def stage_database(ctx):
    record = atlas.provision(ctx.db, ctx.pid)
    ctx.site_set(database={'database': record['database'], 'username': record['username'], 'cluster': record['cluster']})
    return 'Database ' + record['database'] + ' with user ' + record['username'] + ' (readWrite on this database only).'


def stage_repository(ctx):
    site = ctx.site
    try:
        token = gh.user_token(ctx.db, ctx.launch['actor'])
    except AppError:
        token = None
    repo = gh.ensure_repository(site['name'], 'Generated by shift.AI: ' + ctx.build['spec']['name'], user_access_token=token)
    if not repo.get('private', True):
        ctx.log('Warning: the existing repository ' + repo['full_name'] + ' is public.')
    pushed = gh.push_source(repo['full_name'], ctx.build['files'],
                            'shift.AI release ' + ctx.launch['build_id'] + ' (' + json.loads(ctx.build['files']['release.json'])['spec_hash'][:12] + ')')
    ctx.set(repository=repo['full_name'], repository_url=repo['html_url'], commit=pushed['commit'], branch=pushed['branch'])
    ctx.site_set(repository={'full_name': repo['full_name'], 'html_url': repo['html_url'], 'branch': pushed['branch']})
    return repo['full_name'] + ' at ' + pushed['commit'][:7] + (' (new commit)' if pushed['changed'] else ' (source unchanged)') + '.'


def stage_backend(ctx):
    site = ctx.site
    database = site['database']
    env = {'DATABASE_BACKEND': 'mongodb', 'MONGODB_URI': atlas.uri_of(ctx.db, ctx.pid), 'MONGODB_DATABASE': database['database'],
           'ADMIN_EMAIL': site['admin_email'], 'ADMIN_PASSWORD': ctx.admin_password(), 'COOKIE_SECURE': 'true'}
    known = (site.get('render') or {}).get('service_id')
    service = (render.get_service(known, site['name']) if known else None) or render.find_service(site['name'])
    if service:
        render.set_env(service['id'], env)
        deploy = render.trigger_deploy(service['id'], ctx.launch['commit'])
        action = 'Updated'
    else:
        service, deploy = render.create_service(site['name'], 'https://github.com/' + ctx.launch['repository'],
                                                ctx.launch['branch'], env, ctx.plan)
        deploy = deploy or render.trigger_deploy(service['id'], ctx.launch['commit'])
        action = 'Created'
    del env
    url = render.service_url(service)
    ctx.set(service_id=service['id'], deploy_id=deploy, backend_url=url)
    ctx.site_set(render={'service_id': service['id'], 'url': url, 'dashboard_url': service.get('dashboardUrl', '')})
    return action + ' Render service ' + site['name'] + '; deploying commit ' + ctx.launch['commit'][:7] + '.'


def stage_connectivity(ctx):
    ips = render.outbound_ips(ctx.launch['service_id'])
    access = atlas.ensure_access(ips, 'shift.AI ' + ctx.site['name'])
    ctx.log('Database network access for Render ranges ' + ', '.join(ips) + ': added ' + (', '.join(access['added']) or 'none') + '.')

    def deployed():
        status, commit = render.deploy_status(ctx.launch['service_id'], ctx.launch['deploy_id'])
        if status in render.FAILED:
            raise AppError('Render reported the deploy as ' + status + '. Open the service logs in Render, fix the cause, then retry.', 502, 'render_deploy_failed')
        return status if status == 'live' else None

    ctx.wait(deployed, get_settings().deploy_timeout_minutes, 'The Render deploy')
    reason = {'text': 'no response'}

    def healthy():
        try:
            response = httpx.get(ctx.launch['backend_url'] + '/health', timeout=60, follow_redirects=False, trust_env=False)
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if response.status_code == 200 and body.get('build_id') == ctx.launch['build_id'] and body.get('database') == 'mongodb':
            return body
        reason['text'] = 'database unreachable' if response.status_code == 503 else 'HTTP ' + str(response.status_code)
        return None

    try:
        ctx.wait(healthy, 5, 'The backend health check')
    except AppError:
        raise AppError('The backend is live but its health check failed (' + reason['text'] + '). Check that the Atlas '
                       'network access list includes the Render ranges, then retry.', 502, 'backend_unhealthy') from None
    return 'Backend ' + ctx.launch['backend_url'] + ' is live and connected to its MongoDB database.'


def stage_frontend(ctx):
    name = ctx.site['name']
    vercel.ensure_project(name)
    previous = ctx.launch.get('vercel_deployment')
    if not previous or vercel.deployment_state(previous) in ('ERROR', 'CANCELED'):
        files = vercel.frontend_files(ctx.build['files'], ctx.launch['backend_url'], ctx.build['spec'])
        previous = vercel.create_deployment(name, files, {'shiftBuild': ctx.launch['build_id'], 'shiftCommit': ctx.launch['commit']})
        ctx.set(vercel_deployment=previous)

    def ready():
        state = vercel.deployment_state(previous)
        if state in ('ERROR', 'CANCELED'):
            raise AppError('Vercel reported the frontend deployment as ' + state + '. Retry to deploy it again.', 502, 'vercel_deploy_failed')
        return state if state == 'READY' else None

    ctx.wait(ready, 10, 'The Vercel deployment')
    url = ctx.wait(lambda: _production(name), 2, 'Vercel production domain assignment')
    ctx.set(vercel_project=name, frontend_url=url)
    ctx.site_set(vercel={'project': name, 'url': url})
    return 'Frontend ' + url + ' is serving this build through a gateway pinned to the backend.'


def _production(name):
    try:
        return vercel.production_url(name)
    except AppError:
        return None


def stage_verification(ctx):
    site = ctx.site
    summary = verify_live(ctx.launch['frontend_url'], ctx.launch['build_id'], ctx.build['spec'], site['admin_email'], ctx.admin_password())
    ctx.set(verification=summary)
    return 'Verified through the public URL: ' + ', '.join(summary['checks']) + '.'


RUNNERS = {'validate': stage_validate, 'database': stage_database, 'repository': stage_repository, 'backend': stage_backend,
           'connectivity': stage_connectivity, 'frontend': stage_frontend, 'verification': stage_verification}


def run(store, lid):
    db = store.db
    launch = db.application_launches.find_one({'_id': ObjectId(lid)})
    if not launch or launch['status'] not in ACTIVE:
        return
    ctx = Context(store, launch)
    ctx.set(status='running')
    current = STAGES[0][0]
    try:
        store.project(launch['project_id'], launch['actor'], 'admin')
        for key, _ in STAGES:
            current = key
            if next(s for s in ctx.launch['stages'] if s['key'] == key)['status'] == 'done':
                continue
            ctx.mark(key, 'running')
            detail = RUNNERS[key](ctx)
            ctx.mark(key, 'done', detail)
            ctx.launch['stages'] = [{**s, 'status': 'done'} if s['key'] == key else s for s in ctx.launch['stages']]
            ctx.log(detail)
        ctx.set(status='live', stage='complete', finished_at=now())
        ctx.site_set(live={'launch_id': str(ctx.lid), 'build_id': launch['build_id'], 'commit': ctx.launch.get('commit'),
                           'frontend_url': ctx.launch['frontend_url'], 'backend_url': ctx.launch['backend_url'], 'at': now()})
        ctx.log('Deployment successful: ' + ctx.launch['frontend_url'])
    except Exception as exc:
        message = exc.message if isinstance(exc, AppError) else ('Unexpected ' + type(exc).__name__ + ' while ' + dict(STAGES)[current].lower()
                                                                  + '. Completed stages are preserved; retry to resume.')
        code = exc.code if isinstance(exc, AppError) else 'deployment_error'
        ctx.mark(current, 'failed', message)
        ctx.set(status='failed', error={'stage': current, 'code': code, 'message': gh.redact(message)}, finished_at=now())
        ctx.log('Failed at ' + dict(STAGES)[current] + ': ' + message)
    finally:
        unlock(db, launch['project_id'], str(ctx.lid))
