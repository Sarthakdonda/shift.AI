"""Mongo-backed leased jobs; no provider credentials or file bytes in job payloads."""
import threading
from datetime import timedelta
from uuid import uuid4
from bson import ObjectId
from pymongo import ReturnDocument
from app.core.config import get_settings
from app.repositories.store import now

KINDS = {'plan', 'build', 'render', 'vercel', 'sync', 'launch'}


def enqueue(store, kind, pid, actor, payload, tasks, fallback, *args):
    if get_settings().builder_job_mode == 'background':
        tasks.add_task(fallback, *args)
        return
    if kind not in KINDS:
        raise ValueError('Unknown job kind.')
    ident = payload.get('build_id') or payload.get('deployment_id') or payload.get('proposal_id') or payload.get('base_version', 0)
    if kind == 'launch':
        # Each retry of a deployment is its own job; completed attempts never block a retry.
        ident = payload['launch_id'] + ':' + str(payload.get('attempt', 1))
    key = kind + ':' + pid + ':' + str(ident)
    previous = store.db.builder_jobs.find_one({'_id': key})
    if previous and previous['status'] in ('queued', 'running'):
        return
    if previous and previous['status'] == 'complete' and kind != 'plan':
        return
    store.db.builder_jobs.update_one({'_id': key}, {'$set': {'kind': kind, 'project_id': pid,
        'actor': actor, 'payload': payload, 'status': 'queued', 'attempts': 0,
        'created_at': now(), 'available_at': now(), 'error': None}}, upsert=True)


def execute(store, job):
    from app.services import application_service, deployment_service, vercel_deployment
    from app.services.groq_service import get_builder_ai
    pid, actor, payload = job['project_id'], job['actor'], job['payload']
    if job['kind'] == 'plan':
        latest = application_service.latest_spec(store, pid)
        if latest and latest['version'] > payload['base_version']:
            store.update(pid, busy=False)
            return
        application_service.plan_job(store, get_builder_ai(), pid, actor, payload['instructions'], payload['base_version'], payload.get('resume_id'))
    elif job['kind'] == 'sync':
        from app.services.application_sync import prepare_job
        prepare_job(store, get_builder_ai(), pid, actor, payload['proposal_id'])
    elif job['kind'] == 'build':
        row = store.db.application_builds.find_one({'_id': ObjectId(payload['build_id'])})
        if row and row['status'] in ('ready', 'failed', 'validation_required'):
            store.update(pid, busy=False)
            return
        application_service.build_job(store, pid, actor, payload['build_id'])
    elif job['kind'] == 'package':
        from app.services.native_packaging import package_job
        artifact = store.db.application_artifacts.find_one({'_id': ObjectId(payload['artifact_id'])})
        if artifact and artifact['status'] in ('ready', 'failed', 'requires_configuration'):
            return
        package_job(store,pid,actor,payload['artifact_id'])
    elif job['kind'] == 'launch':
        from app.services import launch_service
        # The launch record persists stage progress; a restarted worker resumes it.
        launch_service.run(store, payload['launch_id'])
    else:
        row = store.db.application_deployments.find_one({'_id': ObjectId(payload['deployment_id'])})
        if row and row['status'] != 'queued':
            # Never repeat an external submission after an uncertain result.
            store.update(pid, busy=False)
            return
        provider = vercel_deployment if job['kind'] == 'vercel' else deployment_service
        provider.deploy_job(store, pid, actor, payload['deployment_id'])


def run_one(store, worker_id, native_targets=None):
    token = uuid4().hex
    filters={'kind':'package','payload.target':{'$in':native_targets}} if native_targets else {'kind':{'$in':list(KINDS)}}
    job = store.db.builder_jobs.find_one_and_update({**filters, 'attempts': {'$lt': 3}, '$or': [
        {'status': 'queued', 'available_at': {'$lte': now()}},
        {'status': 'running', 'lease_until': {'$lt': now()}}]},
        {'$set': {'status': 'running', 'worker_id': worker_id, 'token': token,
                  'lease_until': now() + timedelta(seconds=120)}, '$inc': {'attempts': 1}},
        sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)
    if not job:
        return False
    owned = {'_id': job['_id'], 'token': token, 'status': 'running'}
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(20):
            try:
                result = store.db.builder_jobs.update_one(owned, {'$set': {'lease_until': now() + timedelta(seconds=120)}})
                if not result.modified_count:
                    return
                if job['kind']!='package':
                    store.db.projects.update_one({'_id': ObjectId(job['project_id']), 'busy': True}, {'$set': {'lease_until': now() + timedelta(minutes=30)}})
                else:
                    store.db.native_workers.update_one({'_id':worker_id},{'$set':{'heartbeat_at':now()}})
                store.db.worker_health.update_one({'_id': worker_id}, {'$set': {'heartbeat_at': now(), 'job': job['_id']}}, upsert=True)
            except Exception:
                # A lost DB connection must not authorize a second external submission.
                return
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        # Re-establish the project lease after worker restart before service reads.
        # Deployments hold their own per-application lock instead of the project lease.
        if job['kind'] not in ('package', 'launch'):
            store.db.projects.update_one({'_id': ObjectId(job['project_id'])}, {'$set': {'busy': True, 'lease_until': now() + timedelta(minutes=30)}})
        execute(store, job)
        store.db.builder_jobs.update_one(owned, {'$set': {'status': 'complete', 'finished_at': now()}})
    except Exception:
        status = 'failed' if job['attempts'] >= 3 else 'queued'
        store.db.builder_jobs.update_one(owned, {'$set': {'status': status,
            'available_at': now() + timedelta(seconds=10 * job['attempts']),
            'error': 'Worker operation failed. Retry details are retained without credentials.'}})
        if status == 'failed' and job['kind'] == 'launch':
            pass  # the launch record already carries its own failure state
        elif status == 'failed' and job['kind']!='package':
            store.update(job['project_id'], busy=False, application_job={'status': 'failed', 'error': 'The durable job exhausted its retries. Previous versions are preserved.'})
            if job['kind'] == 'sync':
                store.db.application_syncs.update_one({'_id': ObjectId(job['payload']['proposal_id']), 'status': {'$in': ['queued', 'preparing']}}, {'$set': {'status': 'failed', 'error': 'The worker exhausted its retries. Prepare a new proposal.'}})
        elif status == 'failed':
            store.db.application_artifacts.update_one({'_id': ObjectId(job['payload']['artifact_id']), 'status': {'$in': ['queued', 'building']}}, {'$set': {'status': 'failed', 'error': 'The packaging worker exhausted its retries. Request packaging again.', 'finished_at': now()}})
    finally:
        stop.set(); thread.join(timeout=2)
    return True


def run_worker(get_store, stop, native_targets=None):
    worker_id = uuid4().hex
    while not stop.is_set():
        try:
            store = get_store()
            if native_targets:
                import platform
                store.db.native_workers.update_one({'_id':worker_id},{'$set':{'heartbeat_at':now(),'targets':native_targets,'platform':platform.system()}},upsert=True)
            store.db.worker_health.update_one({'_id': worker_id}, {'$set': {'heartbeat_at': now()}}, upsert=True)
            # Exhausted interrupted jobs cannot remain permanently marked running.
            for job in store.db.builder_jobs.find({'status': 'running', 'attempts': {'$gte': 3}, 'lease_until': {'$lt': now()}}):
                if store.db.builder_jobs.update_one({'_id': job['_id'], 'token': job['token'], 'status': 'running'}, {'$set': {'status': 'failed', 'error': 'Worker interrupted after three attempts.'}}).modified_count:
                    if job['kind'] == 'package':
                        store.db.application_artifacts.update_one({'_id': ObjectId(job['payload']['artifact_id']), 'status': {'$in': ['queued', 'building']}}, {'$set': {'status': 'failed', 'error': 'Packaging was interrupted after three attempts. Request packaging again.', 'finished_at': now()}})
                    else:
                        store.update(job['project_id'], busy=False)
                        if job['kind'] == 'sync':
                            store.db.application_syncs.update_one({'_id': ObjectId(job['payload']['proposal_id']), 'status': {'$in': ['queued', 'preparing']}}, {'$set': {'status': 'failed', 'error': 'Synchronization was interrupted after three attempts. Prepare a new proposal.'}})
            if run_one(store, worker_id, native_targets):
                continue
        except Exception:
            pass
        stop.wait(2)
