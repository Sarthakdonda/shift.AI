"""Expose saved planning runs independently of the project's current job pointer."""
from bson import ObjectId
from app.core.errors import AppError
from app.services.application_context import business_context
from app.services.application_planning import fingerprint, VERSION


def history(store, project):
    pid = str(project['_id'])
    runs = list(store.db.application_generation_runs.find({'project_id': pid}, {
        'instructions': 1, 'status': 1, 'updated_at': 1, 'base_version': 1,
        'blueprint_id': 1, 'error': 1}).sort('updated_at', -1).limit(30))
    counts = {row['_id']: row['count'] for row in store.db.application_generation_steps.aggregate([
        {'$match': {'run_id': {'$in': [run['_id'] for run in runs]}, 'status': 'complete'}},
        {'$group': {'_id': '$run_id', 'count': {'$sum': 1}}},
    ])} if runs else {}
    return [{**run, 'completed_steps': counts.get(run['_id'], 0)} for run in runs]


def restore(store, project, run_id):
    from app.services.application_service import latest_spec
    pid = str(project['_id'])
    run = store.db.application_generation_runs.find_one({'_id': run_id, 'project_id': pid})
    if not run:
        raise AppError('Saved specification work was not found.', 404)
    previous = latest_spec(store, pid)
    if (run.get('pipeline') != VERSION or run.get('base_version', 0) != (previous or {}).get('version', 0)
            or run.get('previous') != (fingerprint(previous['spec']) if previous else None)
            or run.get('context_revision', 0) != project.get('context_revision', 0)
            or run.get('business') != business_context(project)):
        raise AppError('The project or application has changed since this run. Its saved stages are preserved; create a new specification for the current requirements.', 409, 'application_resume_stale')
    if not ObjectId.is_valid(run.get('blueprint_id', '')):
        raise AppError('The saved blueprint is unavailable.', 409)
    key = {'_id': ObjectId(run['blueprint_id']), 'project_id': pid}
    blueprint = store.db.application_blueprints.find_one(key)
    source = str(blueprint['_id']) if blueprint else None
    if not blueprint:
        blueprint = store.latest('blueprints', pid)
        if not blueprint or str(blueprint['_id']) != run['blueprint_id']:
            raise AppError('This run uses an older project blueprint. Its saved stages are preserved; select the current blueprint to start a new specification.', 409, 'application_resume_stale')
    if fingerprint(blueprint['content']) != run['blueprint_hash']:
        raise AppError('The saved blueprint content changed. Its saved stages are preserved.', 409, 'application_resume_stale')
    completed = store.db.application_generation_steps.count_documents({'run_id': run_id, 'status': 'complete'})
    job = {'status': 'failed', 'generation_id': run_id, 'completed_steps': completed, 'resumable': True}
    # Restoring selects the saved source and exposes Resume; it does not generate,
    # approve, build or charge credits, and never deletes another run or version.
    store.update(pid, application_source=source, application_job=job)
    return {'job': job, 'instructions': run['instructions']}
