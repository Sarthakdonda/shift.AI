"""Imported blueprint sources, stable isolated previews and native artifacts."""
from datetime import timedelta
from pathlib import Path
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal
from app.api import applications
from app.core.auth import user
from app.core.errors import AppError
from app.core.config import get_settings
from app.repositories.store import now, serialize
from app.services import application_import, application_service, native_packaging
from app.services.application_generator import digest
from app.models.application import VersionInput
from app.services import application_sync
from app.services.job_queue import enqueue

router=APIRouter(prefix='/api',tags=['Application portability'])


class SourceChoice(BaseModel):
    project_id: str = Field(pattern=r'^[0-9a-f]{24}$')
    version: int = Field(ge=1)


class PackageInput(BaseModel):
    target: Literal['windows','macos','android','android_bundle','ios']


@router.get('/projects/{pid}/application/blueprint-sync')
def sync_status(pid: str, account=Depends(user)):
    s = applications.get_store(); s.project(pid, account['id'])
    row = application_sync.latest(s, pid)
    return serialize({k: v for k, v in row.items() if k != 'candidate'}) if row else None


@router.post('/projects/{pid}/application/blueprint-sync', status_code=202)
def prepare_sync(pid: str, body: VersionInput, tasks: BackgroundTasks, account=Depends(user)):
    s = applications.get_store(); s.acquire(pid, account['id'])
    try:
        p = s.project(pid, account['id'], 'write')
        spec, source = application_sync.inputs(s, p, body.version)
        ai = applications.get_builder_ai(); ai.require()
        target = s.latest('blueprints', pid)
        row = {'project_id': pid, 'spec_id': str(spec['_id']), 'spec_version': spec['version'],
               'spec_hash': digest(spec['spec']), 'source_id': str(source['_id']),
               'source_hash': digest(source['content']), 'context_revision': p.get('context_revision', 0),
               'target_id': str(target['_id']) if target else None,
               'target_hash': digest(target['content']) if target else None,
               'status': 'queued', 'actor': account['id'], 'created_at': now()}
        row['_id'] = s.db.application_syncs.insert_one(row).inserted_id
        s.update(pid, application_job={'status': 'syncing'})
        enqueue(s, 'sync', pid, account['id'], {'proposal_id': str(row['_id'])}, tasks,
                application_sync.prepare_job, s, ai, pid, account['id'], str(row['_id']))
        return {'id': str(row['_id']), 'status': 'queued'}
    except Exception:
        s.update(pid, busy=False)
        raise


@router.post('/projects/{pid}/application/blueprint-sync/{sid}/apply')
def apply_sync(pid: str, sid: str, account=Depends(user)):
    s = applications.get_store(); s.acquire(pid, account['id'])
    try:
        return application_sync.apply(s, s.project(pid, account['id'], 'write'), account['id'], sid)
    finally:
        s.update(pid, busy=False)


@router.get('/projects/{pid}/application/sources')
def sources(pid:str,account=Depends(user)):
    s=applications.get_store();p=s.project(pid,account['id'])
    projects=list(s.db.projects.find(s.project_filter(account['id']),{'name':1}).limit(200))
    choices=[]
    for project in projects:
        saved=s.latest('blueprints',str(project['_id']))
        if saved:
            choices.append({'project_id':str(project['_id']),'name':project['name'],'version':saved['version']})
    imported=application_import.selected(s,p)
    current=s.latest('blueprints',pid)
    try:
        application_service.current_blueprint(s,p)
        ready,reason=True,None
    except AppError as exc:
        ready,reason=False,exc.message
    return {'choices':choices,'selected':serialize({k:v for k,v in imported.items() if k!='content'}) if imported else None,
            'current':{'name':p['name'],'version':current['version']} if current else None,
            'ready':ready,'reason':reason}


@router.post('/projects/{pid}/application/import',status_code=201)
def upload(pid:str,file:UploadFile=File(...),account=Depends(user)):
    s=applications.get_store();s.acquire(pid,account['id'])
    try:
        p=s.project(pid,account['id'],'write')
        name,content,sha=application_import.parse_upload(file.filename,file.file.read(10*1024*1024+1))
        row=application_import.attach(s,p,account['id'],content,name,sha)
        return serialize({k:v for k,v in row.items() if k!='content'})
    finally:s.update(pid,busy=False)


@router.post('/projects/{pid}/application/source')
def select_source(pid:str,body:SourceChoice,account=Depends(user)):
    s=applications.get_store();source=s.project(body.project_id,account['id'])
    saved=s.db.blueprints.find_one({'project_id':body.project_id,'version':body.version})
    if not saved:raise AppError('Blueprint version not found.',404)
    # Existing shift.AI blueprints retain their review gate; imports cannot silently bypass it.
    from app.services.blueprint_quality import assess
    if saved['content'].get('review_gate')=='blocked' or (saved['content'].get('final_report',{}).get('schema_version',0)>=3 and not assess(saved['content'])['complete']):
        raise AppError('Complete the selected blueprint quality checks and Red Team review first.',409)
    s.acquire(pid,account['id'])
    try:
        p=s.project(pid,account['id'],'write')
        row=application_import.attach(s,p,account['id'],saved['content'],source['name']+' · blueprint v'+str(body.version),digest(saved['content']),{'project_id':body.project_id,'version':body.version,'blueprint_id':str(saved['_id'])})
        return serialize({k:v for k,v in row.items() if k!='content'})
    finally:s.update(pid,busy=False)


@router.delete('/projects/{pid}/application/source')
def use_current(pid:str,account=Depends(user)):
    s=applications.get_store();s.acquire(pid,account['id'])
    try:
        p=s.project(pid,account['id'],'write')
        if p.get('application_source'):
            s.update(pid,application_source=None,application_job=None)
        return {'ok':True}
    finally:s.update(pid,busy=False)


@router.post('/projects/{pid}/application/builds/{bid}/portable-preview')
def preview(pid:str,bid:str,account=Depends(user)):
    s=applications.get_store();s.project(pid,account['id'],'write')
    build=applications.build_for(s,pid,bid)
    if build['status']!='ready' or build['spec'].get('storage_mode','shared_server')=='shared_server':
        raise AppError('A validated portable application is required.',409)
    from app.portable_preview import preview_url
    return {'url':preview_url(pid,bid,account['id']),'expires_in_seconds':3600,'storage':'Browser-local records persist on the same preview origin. Export a backup to transfer them to a download.'}


@router.get('/projects/{pid}/application/artifacts')
def artifacts(pid:str,account=Depends(user)):
    s=applications.get_store();s.project(pid,account['id'])
    rows=list(s.db.application_artifacts.find({'project_id':pid},{'path':0}).sort('created_at',-1).limit(100))
    workers=list(s.db.native_workers.find({'heartbeat_at':{'$gte':now()-timedelta(minutes=2)}},{'_id':0,'targets':1,'platform':1}))
    return serialize({'items':rows,'workers':workers,'targets':list(native_packaging.TARGETS)})


@router.post('/projects/{pid}/application/builds/{bid}/package',status_code=202)
def package(pid:str,bid:str,body:PackageInput,account=Depends(user)):
    s=applications.get_store();s.project(pid,account['id'],'write')
    build=applications.build_for(s,pid,bid)
    if build['status']!='ready' or build['spec'].get('storage_mode','shared_server')=='shared_server':
        raise AppError('Generate and validate a portable application before packaging.',409)
    active=s.db.application_artifacts.find_one({'project_id':pid,'build_id':bid,'target':body.target,'status':{'$in':['queued','building']}})
    if active:return serialize({k:v for k,v in active.items() if k!='path'})
    worker=s.db.native_workers.find_one({'targets':body.target,'heartbeat_at':{'$gte':now()-timedelta(minutes=2)}})
    row={'project_id':pid,'build_id':bid,'target':body.target,'status':'queued' if worker else 'requires_configuration','created_at':now(),'actor':account['id'],'logs':['Requested '+body.target+' packaging.'],'signing':'not_executed','device_validation':'not_executed'}
    if not worker:row['error']='Start a dedicated '+body.target+' native worker with the required toolchain. No installer has been generated.'
    row['_id']=s.db.application_artifacts.insert_one(row).inserted_id
    if worker:
        s.db.builder_jobs.insert_one({'_id':'package:'+str(row['_id']),'kind':'package','project_id':pid,'actor':account['id'],
            'payload':{'artifact_id':str(row['_id']),'target':body.target},'status':'queued','attempts':0,'created_at':now(),'available_at':now()})
    s.activity(s.project(pid,account['id']),account['id'],'Application packaging requested',body.target)
    return serialize(row)


@router.get('/projects/{pid}/application/artifacts/{aid}/download')
def artifact_download(pid:str,aid:str,account=Depends(user)):
    s=applications.get_store();s.project(pid,account['id'])
    if not ObjectId.is_valid(aid):raise AppError('Artifact not found.',404)
    row=s.db.application_artifacts.find_one({'_id':ObjectId(aid),'project_id':pid,'status':'ready'})
    if not row:raise AppError('A verified artifact is not available.',404)
    root=Path(get_settings().native_artifact_dir).resolve()
    path=Path(row['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise AppError('Artifact is unavailable on this download host. Configure shared artifact storage.',503)
    import hashlib
    if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise AppError('Artifact integrity verification failed.',409)
    return FileResponse(path,filename='application-'+row['target']+path.suffix,media_type='application/octet-stream',headers={'Cache-Control':'no-store'})
