import time
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from app.core.auth import user
from app.core.errors import AppError
from app.repositories.store import get_store, serialize, now
from app.services.gemini_service import get_gemini
from app.services.project_service import ProjectService
from app.models.deliverables import KINDS, LANGUAGES, Deliverable, GenerateInput, EditInput, CommentInput, ReviewInput, validate_coverage
from app.models.schemas import RedTeam
from app.agents import prompts
from app.agents.deliverable_prompts import SPECS, instruction

router = APIRouter(prefix='/api', tags=['Deliverables and review'])


def latest(s, pid, kind):
    return s.db.artifacts.find_one({'project_id': pid, 'kind': kind}, sort=[('version', -1)])


def kind_exists(kind):
    if kind not in KINDS:
        raise AppError('Deliverable type not found.', 404)


def save(s, p, kind, content, actor, language, note, reviews=None):
    pid = str(p['_id'])
    previous = latest(s, pid, kind)
    doc = {'project_id': pid, 'kind': kind, 'version': previous['version'] + 1 if previous else 1,
           'source_revision': p.get('context_revision', 0), 'content': content, 'language': language,
           'author': actor, 'note': note, 'ai_reviews': reviews or [], 'created_at': now()}
    doc['_id'] = s.db.artifacts.insert_one(doc).inserted_id
    s.activity(p, actor, 'Deliverable saved', f"{SPECS[kind][0]} version {doc['version']}")
    return serialize(doc)


def generate_job(pid, actor, kinds, body):
    s, ai = get_store(), get_gemini()
    jobs = {}
    try:
        p = s.project(pid, actor)
        service = ProjectService(s, ai)
        context = service.context(pid, actor)
        context['blueprint'] = serialize(s.latest('blueprints', pid)) if p['status'] == 'BLUEPRINT_READY' else None
        context['feedback'] = serialize(list(s.db.comments.find({'project_id': pid}).sort('created_at', -1).limit(30)))
        context['human_reviews'] = serialize(list(s.db.reviews.find({'project_id': pid}).sort('created_at', -1).limit(30)))
        language = LANGUAGES.get(body.language, body.language)
        for kind in kinds:
            started = time.monotonic()
            jobs[kind] = {'status': 'generating', 'started_at': now()}
            s.update(pid, artifact_jobs=jobs)
            try:
                previous = latest(s, pid, kind)
                data = {'context': context, 'previous_version': serialize(previous), 'user_feedback': body.instructions}
                reviews = []
                for cycle in range(3):
                    s.update(pid, lease_until=now() + timedelta(minutes=30))
                    result = service.ai.generate_structured(instruction(kind, language), data, Deliverable)
                    try:
                        validate_coverage(kind, result)
                    except ValueError as exc:
                        result = service.ai.generate_structured(instruction(kind, language) + '\nRepair this missing coverage: ' + str(exc),
                            {**data, 'incomplete_draft': result.model_dump()}, Deliverable)
                        validate_coverage(kind, result)
                    review = service.ai.generate_structured(prompts.RED_TEAM, {'context': context, 'deliverable': result.model_dump(), 'previous_reviews': reviews}, RedTeam)
                    reviews.append(review.model_dump())
                    if not any(f.requires_revision for f in review.findings):
                        break
                    data.update(previous_draft=result.model_dump(), red_team_findings=reviews)
                saved = save(s, p, kind, result.model_dump(), actor, body.language, 'AI generation with independent review', reviews)
                jobs[kind] = {'status': 'complete', 'version': saved['version'], 'finished_at': now()}
                status = 'complete'
            except Exception as exc:
                message = exc.message if isinstance(exc, AppError) else 'Generation failed. Your earlier versions are preserved.'
                jobs[kind] = {'status': 'error', 'error': message, 'finished_at': now()}
                status = 'error'
            s.db.usage.insert_one({'project_id': pid, 'kind': kind, 'model': getattr(getattr(service.ai, 'settings', None), 'gemini_model', 'test'),
                                   'status': status, 'duration_seconds': round(time.monotonic() - started, 2), 'created_at': now()})
            s.update(pid, artifact_jobs=jobs)
    except Exception as exc:
        message = exc.message if isinstance(exc, AppError) else 'Generation was interrupted. Retry; earlier versions are preserved.'
        s.update(pid, artifact_jobs={k: jobs.get(k, {'status': 'error', 'error': message}) for k in kinds}, error=message)
    finally:
        s.update(pid, busy=False)


@router.get('/languages')
def languages():
    return LANGUAGES


@router.get('/projects/{pid}/deliverables')
def deliverables(pid: str, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'])
    result = []
    for kind in KINDS:
        item = latest(s, pid, kind)
        result.append({'kind': kind, 'label': SPECS[kind][0], 'artifact': serialize(item),
                       'stale': bool(item and item.get('source_revision', 0) != p.get('context_revision', 0))})
    return {'items': result, 'jobs': serialize(p.get('artifact_jobs', {})), 'busy': p.get('busy', False), 'role': p['access_role']}


@router.post('/projects/{pid}/deliverables/{kind}/generate', status_code=202)
def generate(pid: str, kind: str, body: GenerateInput, tasks: BackgroundTasks, account=Depends(user)):
    if kind != 'all': kind_exists(kind)
    s = get_store(); p = s.project(pid, account['id'], 'write')
    if not p.get('analysis_ready') or p['status'] != 'BLUEPRINT_READY':
        raise AppError('Complete discovery and the core analysis before generating implementation deliverables.', 409)
    get_gemini().require()
    s.acquire(pid, account['id'])
    kinds = list(KINDS) if kind == 'all' else [kind]
    s.update(pid, artifact_jobs={k: {'status': 'queued'} for k in kinds})
    tasks.add_task(generate_job, pid, account['id'], kinds, body)
    return {'status': 'queued'}


@router.get('/projects/{pid}/deliverables/{kind}/versions')
def versions(pid: str, kind: str, account=Depends(user)):
    kind_exists(kind); s = get_store(); s.project(pid, account['id'])
    return serialize(list(s.db.artifacts.find({'project_id': pid, 'kind': kind}).sort('version', -1).limit(100)))


@router.post('/projects/{pid}/deliverables/{kind}')
def edit(pid: str, kind: str, body: EditInput, account=Depends(user)):
    kind_exists(kind); s = get_store(); p = s.project(pid, account['id'], 'write')
    s.acquire(pid, account['id'])
    try:
        previous = latest(s, pid, kind)
        if body.base_version != (previous['version'] if previous else 0):
            raise AppError('Another version was saved. Reload before applying your edits.', 409)
        return save(s, p, kind, body.content.model_dump(), account['id'], previous.get('language', 'en') if previous else p.get('language', 'en'), body.note)
    finally:
        s.update(pid, busy=False)


@router.post('/projects/{pid}/deliverables/{kind}/review')
def review(pid: str, kind: str, body: ReviewInput, account=Depends(user)):
    kind_exists(kind); s = get_store(); p = s.project(pid, account['id'], 'review')
    s.acquire(pid, account['id'], 'review')
    try:
        item = latest(s, pid, kind)
        if not item or item['version'] != body.version or item.get('source_revision', 0) != p.get('context_revision', 0):
            raise AppError('Review the latest version for the current project context.', 409)
        if body.decision == 'approved':
            try: validate_coverage(kind, Deliverable.model_validate(item['content']))
            except ValueError as exc: raise AppError(str(exc), 409) from None
        doc = {'project_id': pid, 'kind': kind, 'version': body.version, 'reviewer': account['id'], 'reviewer_name': account['name'], **body.model_dump(), 'created_at': now()}
        doc['_id'] = s.db.reviews.insert_one(doc).inserted_id
        s.activity(p, account['id'], body.decision.replace('_', ' ').title(), SPECS[kind][0])
        return serialize(doc)
    finally:
        s.update(pid, busy=False)


@router.get('/projects/{pid}/collaboration')
def collaboration(pid: str, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'])
    return {name: serialize(list(s.db[name].find({'project_id': pid}).sort('created_at', -1).limit(100))) for name in ['comments','reviews','activity']}


@router.post('/projects/{pid}/comments', status_code=201)
def comment(pid: str, body: CommentInput, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'])
    if not body.content.strip(): raise AppError('Write a comment first.')
    doc = {**body.model_dump(), 'project_id': pid, 'author': account['id'], 'author_name': account['name'], 'created_at': now()}
    doc['_id'] = s.db.comments.insert_one(doc).inserted_id
    s.activity(p, account['id'], 'New comment', body.content)
    return serialize(doc)


class ProjectPreferences(BaseModel):
    language: str = Field(max_length=50)


@router.post('/projects/{pid}/preferences')
def preferences(pid: str, body: ProjectPreferences, account=Depends(user)):
    s = get_store(); s.project(pid, account['id'], 'write')
    s.acquire(pid, account['id'])
    try: s.update(pid, language=body.language)
    finally: s.update(pid, busy=False)
    return {'ok': True}
