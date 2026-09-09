import base64
import hashlib
import json
import httpx
from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from app.core.auth import user
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import get_store, now
from app.services.gemini_service import get_gemini
from app.services.project_service import ProjectService

router=APIRouter(prefix='/api',tags=['Enterprise integrations'])


def cipher():
    secret=get_settings().session_secret
    if len(secret)<32: raise AppError('Configure a session secret before storing a connection.',503)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('shift-integrations:'+secret).encode()).digest()))


def graph(token, path):
    # Fixed Microsoft host and fixed operations; never accept arbitrary remote URLs.
    try:
        response=httpx.get('https://graph.microsoft.com/v1.0/'+path,headers={'Authorization':'Bearer '+token},timeout=20,follow_redirects=False)
        if response.status_code!=200:
            raise AppError('Microsoft rejected the request. Check token expiry and delegated permissions.',502)
        return response.json()
    except AppError: raise
    except Exception: raise AppError('Microsoft could not be reached. Retry later.',503) from None


class ConnectInput(BaseModel):
    access_token: str = Field(min_length=20,max_length=12000)


@router.get('/workspaces/{wid}/integrations')
def connections(wid:str,account=Depends(user)):
    s=get_store();s.workspace(wid,account['id'],'admin')
    record=s.db.integrations.find_one({'workspace_id':wid,'provider':'microsoft_graph'})
    return {'microsoft_graph':{'connected':bool(record),'label':record.get('label','') if record else '', 'scope':'Read assigned Planner tasks; import a snapshot as evidence.'}}


@router.post('/workspaces/{wid}/integrations/microsoft_graph')
def connect(wid:str,body:ConnectInput,account=Depends(user)):
    s=get_store();s.workspace(wid,account['id'],'admin')
    profile=graph(body.access_token,'me?$select=displayName')
    s.db.integrations.update_one({'workspace_id':wid,'provider':'microsoft_graph'},{'$set':{'encrypted_token':cipher().encrypt(body.access_token.encode()).decode(),'label':str(profile.get('displayName','Microsoft account'))[:100],'updated_at':now()}},upsert=True)
    return {'connected':True}


@router.delete('/workspaces/{wid}/integrations/microsoft_graph')
def disconnect(wid:str,account=Depends(user)):
    s=get_store();s.workspace(wid,account['id'],'admin')
    s.db.integrations.delete_one({'workspace_id':wid,'provider':'microsoft_graph'})
    return {'ok':True}


@router.post('/projects/{pid}/integrations/microsoft_graph/import',status_code=202)
def import_tasks(pid:str,tasks:BackgroundTasks,account=Depends(user)):
    s=get_store();p=s.project(pid,account['id'],'write')
    if not p.get('workspace_id'): raise AppError('Use a team project with a configured Microsoft connection.',409)
    s.workspace(p['workspace_id'],account['id'],'admin')
    record=s.db.integrations.find_one({'workspace_id':p['workspace_id'],'provider':'microsoft_graph'})
    if not record: raise AppError('Connect Microsoft in team administration first.',409)
    try: token=cipher().decrypt(record['encrypted_token'].encode()).decode()
    except InvalidToken: raise AppError('Reconnect Microsoft after the session secret changes.',409) from None
    get_gemini().require()
    snapshot=graph(token,'me/planner/tasks')
    rows=[{k:task.get(k) for k in ['id','title','percentComplete','createdDateTime','dueDateTime','planId','bucketId']} for task in snapshot.get('value',[])[:100]]
    text=json.dumps({'source':'Microsoft Planner assigned tasks','captured_at':now().isoformat(),'scope':'First page, at most 100 tasks; not a complete organization inventory.','tasks':rows},ensure_ascii=False).encode()
    if not rows: raise AppError('No assigned Planner tasks were returned.',409)
    if s.db.documents.count_documents({'project_id':pid})>=20: raise AppError('Remove a document before importing another snapshot.',409)
    s.acquire(pid,account['id'])
    try:
        did=s.db.documents.insert_one({'project_id':pid,'filename':'microsoft-planner-snapshot.txt','file_type':'txt','size':len(text),'status':'processing','summary':'','error':None,'created_at':now()}).inserted_id
    except Exception:
        s.update(pid,busy=False);raise
    tasks.add_task(ProjectService(s,get_gemini()).process_document,pid,account['id'],did,text,'.txt','microsoft-planner-snapshot.txt')
    return {'status':'processing','id':str(did)}
