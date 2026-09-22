from bson import ObjectId
from fastapi import APIRouter, Depends, Request, BackgroundTasks, UploadFile, File
from app.core.auth import user
from app.core.errors import AppError
from app.core.config import get_settings
from app.core.mailer import email_configured
from app.models.schemas import ProjectCreate, ChatInput, ModelChoice, GenerationInput, ReviewInput
from app.repositories.store import get_store, serialize, now
from app.services.gemini_service import get_gemini
from app.services.model_catalog import catalog
from app.services.document_service import validate_file
from app.services.project_service import ProjectService
from app.services.generation_service import Generation

router = APIRouter(prefix='/api', tags=['Workspace'])


def service():
    return ProjectService(get_store(), get_gemini())


@router.get('/health/live')
def liveness():
    """Fast process/config check used by local clients before opening the UI."""
    s = get_settings()
    return {
        'status': 'ok',
        'gemini_configured': bool(s.gemini_keys),
        'google_configured': bool(s.google_client_id),
        'google_client_id': s.google_client_id,
    }


@router.get('/health')
def health():
    s = get_settings()
    database = 'not_configured'
    if s.mongodb_uri:
        try:
            get_store().db.command('ping')
            database = 'connected'
        except Exception:
            database = 'unavailable'
    return {'status': 'ok' if database == 'connected' else 'degraded', 'database': database, 'gemini_configured': bool(s.gemini_keys), 'google_configured': bool(s.google_client_id), 'google_client_id': s.google_client_id, 'vector_search_configured': s.vector_search_enabled, 'local_access_enabled': s.allow_local_access and not bool(s.google_client_id), 'max_upload_mb': s.max_upload_mb, 'email_configured': email_configured()}


@router.post('/projects', status_code=201)
def create(body: ProjectCreate, account=Depends(user)):
    return serialize(get_store().create(body.model_dump(), account['id']))


@router.get('/projects')
def projects(account=Depends(user)):
    s = get_store()
    return serialize(list(s.db.projects.find(s.project_filter(account['id'])).sort('updated_at', -1)))


@router.get('/projects/{pid}')
def project(pid: str, account=Depends(user)):
    svc = service()
    p = svc.store.project(pid, account['id'])
    # Old score-only decisions must not advertise readiness before verification.
    # Completed reports remain accessible; this does not mutate saved projects.
    if p.get('analysis_ready') and p['status'] != 'BLUEPRINT_READY' and not svc.readiness_verified(pid, p):
        p['analysis_ready'] = False
    return serialize(p)


@router.delete('/projects/{pid}')
def delete_project(pid: str, account=Depends(user)):
    get_store().delete(pid, account['id'])
    return {'ok': True}


@router.get('/projects/{pid}/messages')
def messages(pid: str, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    return serialize(s.related('messages', pid))


@router.get('/models')
def models(account=Depends(user)):
    """Models this account's keys can use, plus the effort levels for the composer."""
    return catalog(get_gemini(), get_settings().gemini_model)


@router.post('/projects/{pid}/model')
def choose_model(pid: str, body: ModelChoice, account=Depends(user)):
    s = get_store()
    p = s.project(pid, account['id'], 'write')
    if p.get('busy'):
        raise AppError('This project is processing. Change the model when it finishes.', 409)
    allowed = {m['id'] for m in catalog(get_gemini(), get_settings().gemini_model)['models']}
    if body.model not in allowed:
        raise AppError('That model is not available for your API keys. Choose another.', 400, 'model_unavailable')
    s.update(pid, model=body.model, effort=body.effort)
    return {'model': body.model, 'effort': body.effort}


@router.get('/projects/{pid}/usage')
def usage(pid: str, account=Depends(user)):
    p = get_store().project(pid, account['id'])
    ai = get_gemini()
    return ai.availability(p.get('model') or get_settings().gemini_model)


@router.post('/projects/{pid}/generation/cancel')
def cancel_generation(pid: str, body: GenerationInput, account=Depends(user)):
    store = get_store()
    store.project(pid, account['id'], 'write')
    # Recording before the generation starts also handles a fast Stop click.
    Generation(store, pid, body.request_id).cancel()
    return {'status': 'stopped', 'request_id': body.request_id}


@router.post('/projects/{pid}/chat')
def chat(pid: str, body: ChatInput, tasks: BackgroundTasks, account=Depends(user)):
    return service().chat(pid, account['id'], body.content, tasks=tasks, request_id=body.request_id)


@router.post('/projects/{pid}/discovery/next')
def next_question(pid: str, tasks: BackgroundTasks, body: GenerationInput | None = None, account=Depends(user)):
    return service().chat(pid, account['id'], tasks=tasks, request_id=body.request_id if body else None)


@router.post('/projects/{pid}/analysis/run', status_code=202)
def analyze(pid: str, tasks: BackgroundTasks, account=Depends(user)):
    svc = service()
    p = svc.store.project(pid, account['id'])
    if not p.get('analysis_ready') or (p.get('discovery') or {}).get('critical_missing') or not svc.readiness_verified(pid, p):
        raise AppError('Complete the critical discovery questions before running analysis.', 409)
    svc.ai.require()
    svc.store.acquire(pid, account['id'])
    svc.store.db.analyses.delete_many({'project_id': pid})
    svc.store.update(pid, status='SYSTEM_ANALYSIS')
    tasks.add_task(svc.analyze, pid, account['id'])
    return {'status': 'SYSTEM_ANALYSIS', 'project_id': pid}


@router.get('/projects/{pid}/analysis')
def analysis(pid: str, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    return serialize(s.db.analyses.find_one({'project_id': pid}))


@router.get('/projects/{pid}/blueprint')
def blueprint(pid: str, account=Depends(user)):
    s = get_store()
    p = s.project(pid, account['id'])
    return serialize(s.latest('blueprints', pid)) if p['status'] == 'BLUEPRINT_READY' else None


@router.post('/projects/{pid}/red-team/revise', status_code=202)
def revise_blueprint(pid: str, body: ReviewInput, tasks: BackgroundTasks, account=Depends(user)):
    """Resume from the saved design, preserving discovery and previous versions."""
    import copy
    svc = service()
    p = svc.store.project(pid, account['id'], 'write')
    svc.ai.require()
    svc.store.acquire(pid, account['id'])
    try:
        p = svc.store.project(pid, account['id'], 'write')
        saved = svc.store.latest('blueprints', pid)
        if not saved or saved['version'] != body.version:
            raise AppError('The blueprint changed. Refresh before submitting a review decision.', 409)
        seed = copy.deepcopy(saved['content'])
        if seed.get('source_revision', seed.get('final_report', {}).get('source_revision', 0)) != p.get('context_revision', 0):
            raise AppError('Project evidence changed. Run analysis with the updated context first.', 409)
        if not all(key in seed for key in ('solution', 'option_decision', 'architecture_report', 'planning_report', 'data_report', 'experience_report')):
            raise AppError('This older blueprint needs a full analysis before targeted review.', 409)
        if body.action != 'review':
            finding = next((f for f in seed.get('review_ledger', []) if f['id'] == body.finding_id), None)
            if not finding or finding['status'] not in ('open', 'needs_input'):
                raise AppError('This finding is no longer awaiting a decision. Refresh the review.', 409)
            response = {'finding_id': body.finding_id, 'action': body.action, 'response': body.response,
                        'actor': account['id'], 'created_at': now().isoformat()}
            seed['review_responses'] = [*seed.get('review_responses', []), response]
            if body.action == 'accept_risk':
                finding.update(status='accepted_risk', accepted_by=account['id'], acceptance_reason=body.response)
            else:
                finding.update(status='open', action='revise', requires_revision=True, user_response=body.response)
            svc.store.message(pid, 'user', body.response, message_type='review_decision', finding_id=body.finding_id,
                              review_action=body.action)
        svc.store.update(pid, status='RED_TEAM_REVIEW')
        tasks.add_task(svc.analyze, pid, account['id'], seed)
        return {'status': 'RED_TEAM_REVIEW', 'project_id': pid}
    except Exception:
        svc.store.update(pid, busy=False)
        raise


@router.get('/projects/{pid}/blueprint/versions')
def blueprint_versions(pid: str, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    return serialize(list(s.db.blueprints.find({'project_id': pid},
        {'content': 0}).sort('version', -1)))


@router.get('/projects/{pid}/blueprint/versions/{version}')
def blueprint_version(pid: str, version: int, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    saved = s.db.blueprints.find_one({'project_id': pid, 'version': version})
    if not saved:
        raise AppError('Blueprint version not found.', 404)
    return serialize(saved)


@router.post('/projects/{pid}/blueprint/versions/{version}/restore')
def restore_blueprint(pid: str, version: int, body: ReviewInput, account=Depends(user)):
    s = get_store()
    p = s.project(pid, account['id'], 'write')
    s.acquire(pid, account['id'])
    try:
        p = s.project(pid, account['id'], 'write')
        latest = s.latest('blueprints', pid)
        if not latest or latest['version'] != body.version:
            raise AppError('The blueprint changed. Refresh before restoring a version.', 409)
        saved = s.db.blueprints.find_one({'project_id': pid, 'version': version})
        if not saved:
            raise AppError('Blueprint version not found.', 404)
        content = saved['content']
        if content.get('source_revision', content.get('final_report', {}).get('source_revision', 0)) != p.get('context_revision', 0):
            raise AppError('This version uses older project evidence. Run analysis instead of restoring it.', 409)
        restored = s.save_blueprint(pid, {**content, 'restored_from_version': version})
        s.save_analysis(pid, restored['content'])
        s.update(pid, status='BLUEPRINT_READY', review_gate=content.get('review_gate'), ai_necessity=content.get('ai_necessity'))
        return serialize(restored)
    finally:
        s.update(pid, busy=False)


@router.post('/projects/{pid}/blueprint/generate')
def generate_blueprint(pid: str, account=Depends(user)):
    s = get_store()
    p = s.project(pid, account['id'])
    if p['status'] != 'BLUEPRINT_READY':
        raise AppError('Finish analysis and Red Team review before generating a blueprint.', 409)
    return serialize(s.latest('blueprints', pid))


@router.get('/projects/{pid}/documents')
def documents(pid: str, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    return serialize(s.related('documents', pid))


@router.post('/projects/{pid}/documents', status_code=202)
def upload(pid: str, tasks: BackgroundTasks, file: UploadFile = File(...), account=Depends(user)):
    svc = service()
    svc.store.project(pid, account['id'])
    svc.ai.require()
    s = get_settings()
    data = file.file.read(s.max_upload_mb * 1024 * 1024 + 1)
    filename, ext = validate_file(file.filename or '', data, s.max_upload_mb)
    if svc.store.db.documents.count_documents({'project_id': pid}) >= 20:
        raise AppError('Each project supports up to 20 documents. Remove a document to add another.')
    svc.store.acquire(pid, account['id'])
    doc = {'project_id': pid, 'filename': filename, 'file_type': ext[1:], 'size': len(data), 'status': 'processing', 'summary': '', 'error': None, 'created_at': now()}
    try:
        doc['_id'] = svc.store.db.documents.insert_one(doc).inserted_id
    except Exception:
        svc.store.update(pid, busy=False)
        raise
    tasks.add_task(svc.process_document, pid, account['id'], doc['_id'], data, ext, filename)
    return serialize(doc)


@router.delete('/projects/{pid}/documents/{did}')
def delete_document(pid: str, did: str, account=Depends(user)):
    s = get_store()
    s.project(pid, account['id'])
    if not ObjectId.is_valid(did) or not s.db.documents.find_one({'_id': ObjectId(did), 'project_id': pid}):
        raise AppError('Document not found.', 404)
    s.acquire(pid, account['id'])
    try:
        s.db.documents.delete_one({'_id': ObjectId(did), 'project_id': pid})
        s.db.document_chunks.delete_many({'project_id': pid, 'document_id': did})
        s.invalidate(pid)
        # Clear distilled document facts so deleted evidence cannot survive in prompts.
        s.update(pid, discovery=None, discovery_scores={})
        # Remove evidence-dependent memory immediately; preserve user facts and question history.
        from app.services.discovery_service import load_memory
        p = s.project(pid, account['id'])
        memory = load_memory(serialize(p), serialize(s.related('messages', pid)), serialize(s.related('documents', pid)))
        memory.assumptions = []
        memory.unknowns = []
        memory.ready_for_analysis = False
        memory.information_sufficiency = 0
        memory.readiness_reason = ''
        s.update(pid, project_context=memory.model_dump())
    finally:
        s.update(pid, busy=False)
    return {'ok': True}
