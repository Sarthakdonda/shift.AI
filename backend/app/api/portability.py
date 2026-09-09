import json
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from bson import ObjectId
from app.core.auth import user
from app.core.errors import AppError
from app.repositories.store import get_store, now, serialize
from app.models.schemas import ProjectCreate, DocumentSummary, Discovery, WorkflowAnalysis, RootCause, Necessity, Solution, RedTeam, BusinessValue, Conclusion
from app.models.deliverables import Deliverable, KINDS

router = APIRouter(prefix='/api', tags=['Backup and restore'])


class BackupMessage(BaseModel):
    role: Literal['user','assistant']
    content: str = Field(max_length=12000)


class BackupArtifact(BaseModel):
    kind: Literal['business','architecture','process','ux','data_api','planning','transformation']
    version: int = Field(ge=1)
    content: Deliverable
    language: str = Field(default='en', max_length=50)


class BackupDocument(DocumentSummary):
    id: str
    filename: str = Field(max_length=180)
    file_type: str = Field(max_length=10)
    status: Literal['processed','failed','processing']


class BackupChunk(BaseModel):
    document_id: str
    text: str = Field(max_length=2000)
    chunk_index: int = Field(ge=0)
    metadata: dict


class BackupProject(BaseModel):
    project: ProjectCreate
    messages: list[BackupMessage] = Field(default_factory=list, max_length=5000)
    artifacts: list[BackupArtifact] = Field(default_factory=list, max_length=700)
    documents: list[BackupDocument] = Field(default_factory=list, max_length=20)
    document_chunks: list[BackupChunk] = Field(default_factory=list, max_length=10000)
    blueprint_archive: list[dict] = Field(default_factory=list, max_length=100)
    reviews_archive: list[dict] = Field(default_factory=list, max_length=1000)
    comments_archive: list[dict] = Field(default_factory=list, max_length=5000)


class Backup(BaseModel):
    format: Literal['shift-ai-workspace-v1']
    projects: list[BackupProject] = Field(max_length=100)


@router.get('/workspaces/{wid}/backup')
def backup(wid: str, account=Depends(user)):
    s = get_store(); s.workspace(wid, account['id'], 'admin')
    projects = list(s.db.projects.find({'workspace_id': wid}).limit(101))
    if len(projects)>100: raise AppError('A backup supports up to 100 projects. Split the workspace before export.', 413)
    output = {'format': 'shift-ai-workspace-v1', 'projects': []}
    for p in projects:
        if p.get('busy'): raise AppError('Wait for project processing to finish before backing up.', 409)
        pid = str(p['_id'])
        docs = []
        for d in s.related('documents', pid):
            docs.append({**serialize(d), 'facts': d.get('facts', []), 'summary': d.get('summary', '')})
        output['projects'].append({'project': {k:p.get(k) for k in ['name','initial_problem','industry','language'] if p.get(k) is not None},
            'messages': serialize(s.related('messages', pid)), 'documents': docs,
            'document_chunks': serialize(list(s.db.document_chunks.find({'project_id':pid}, {'embedding':0}))),
            'artifacts': serialize(list(s.db.artifacts.find({'project_id':pid}).sort('version',1))),
            'blueprint_archive': serialize(s.related('blueprints',pid)), 'reviews_archive':serialize(s.related('reviews',pid)),
            'comments_archive':serialize(s.related('comments',pid))})
    payload = json.dumps(output, ensure_ascii=False).encode()
    if len(payload)>15*1024*1024: raise AppError('Backup exceeds 15 MB. Export projects individually instead.', 413)
    return Response(payload, media_type='application/json', headers={'Content-Disposition':'attachment; filename="shift-ai-workspace-backup.json"'})


@router.post('/workspaces/{wid}/restore', status_code=201)
def restore(wid: str, body: Backup, account=Depends(user)):
    s = get_store(); s.workspace(wid, account['id'], 'admin')
    created = []
    try:
        for source in body.projects:
            p = s.create({**source.project.model_dump(), 'workspace_id':wid}, account['id'])
            pid = str(p['_id']); created.append(pid)
            s.db.messages.delete_many({'project_id':pid})
            for message in source.messages:
                s.message(pid, message.role, message.content)
            if not source.messages: s.message(pid,'user',source.project.initial_problem)
            document_ids={}
            for document in source.documents:
                values=document.model_dump(exclude={'id'})
                values.update(project_id=pid,status='processed' if document.status=='processed' else 'failed',size=0,created_at=now(),error=None)
                values['filename']=values['filename'].replace('\\','/').split('/')[-1]
                new_id=s.db.documents.insert_one(values).inserted_id
                document_ids[document.id]=str(new_id)
            for chunk in source.document_chunks:
                if chunk.document_id not in document_ids: raise AppError('A chunk refers to a missing document.', 422)
                s.db.document_chunks.insert_one({'project_id':pid,'document_id':document_ids[chunk.document_id], 'text':chunk.text,
                    'chunk_index':chunk.chunk_index,'metadata':{k:str(v)[:180] for k,v in chunk.metadata.items() if k in ['page','filename']}})
            for artifact in source.artifacts:
                s.db.artifacts.insert_one({**artifact.model_dump(), 'project_id':pid,'author':account['id'], 'source_revision':-1,
                    'note':'Restored from backup; revalidate against current discovery', 'ai_reviews':[], 'created_at':now()})
            archive = {k:getattr(source,k) for k in ['blueprint_archive','reviews_archive','comments_archive']}
            s.db.restored_archives.insert_one({'project_id':pid,'content':archive,'created_at':now()})
            s.activity(p,account['id'],'Restored project','Restored content requires discovery and review; approval is not imported.')
        return {'project_ids':created, 'message':'Restored as new projects. Revalidate discovery and review restored drafts.'}
    except Exception:
        # Compensate only projects created by this operation, never existing projects.
        for pid in created:
            s.delete(pid,account['id'])
        raise


@router.get('/projects/{pid}/restored-history')
def restored_history(pid: str, account=Depends(user)):
    s=get_store(); s.project(pid,account['id'])
    archive=s.db.restored_archives.find_one({'project_id':pid})
    return Response(json.dumps(serialize(archive['content'] if archive else {}),ensure_ascii=False),media_type='application/json',
                    headers={'Content-Disposition':'attachment; filename="restored-history.json"'})
