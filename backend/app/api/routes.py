from bson import ObjectId
from fastapi import APIRouter, Depends, Request, BackgroundTasks, UploadFile, File
from app.core.auth import user
from app.core.errors import AppError
from app.core.config import get_settings
from app.models.schemas import ProjectCreate, ChatInput, ModelChoice
from app.repositories.store import get_store, serialize, now
from app.services.gemini_service import get_gemini
from app.services.model_catalog import catalog
from app.services.document_service import validate_file
from app.services.project_service import ProjectService

router = APIRouter(prefix='/api', tags=['Workspace'])


def service():
    return ProjectService(get_store(), get_gemini())


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
    return {'status': 'ok' if database == 'connected' else 'degraded', 'database': database, 'gemini_configured': bool(s.gemini_keys), 'google_configured': bool(s.google_client_id), 'google_client_id': s.google_client_id, 'vector_search_configured': s.vector_search_enabled, 'local_access_enabled': s.allow_local_access and not bool(s.google_client_id), 'max_upload_mb': s.max_upload_mb}


@router.post('/projects', status_code=201)
def create(body: ProjectCreate, account=Depends(user)):
    return serialize(get_store().create(body.model_dump(), account['id']))


@router.get('/projects')
def projects(account=Depends(user)):
    s = get_store()
    return serialize(list(s.db.projects.find(s.project_filter(account['id'])).sort('updated_at', -1)))


@router.get('/projects/{pid}')
def project(pid: str, account=Depends(user)):
    return serialize(get_store().project(pid, account['id']))


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


@router.post('/projects/{pid}/chat')
def chat(pid: str, body: ChatInput, account=Depends(user)):
    return service().chat(pid, account['id'], body.content)


@router.post('/projects/{pid}/discovery/next')
def next_question(pid: str, account=Depends(user)):
    return service().chat(pid, account['id'])


@router.post('/projects/{pid}/analysis/run', status_code=202)
def analyze(pid: str, tasks: BackgroundTasks, account=Depends(user)):
    svc = service()
    p = svc.store.project(pid, account['id'])
    if not p.get('analysis_ready') or p.get('discovery', {}).get('critical_missing'):
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
    finally:
        s.update(pid, busy=False)
    return {'ok': True}
