import hashlib
import secrets
from datetime import timedelta, timezone
from typing import Literal
from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from app.core.auth import user
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import get_store, now, serialize

router = APIRouter(prefix='/api', tags=['Organizations and governance'])


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    organization: str = Field(default='', max_length=100)


class RoleInput(BaseModel):
    role: Literal['admin', 'editor', 'reviewer', 'viewer']


class InviteAccept(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class PolicyInput(BaseModel):
    model: str = Field(default='', max_length=100, pattern=r'^[a-zA-Z0-9._/-]*$')
    retention_days: int = Field(default=90, ge=1, le=3650)
    ai_policy: str = Field(default='', max_length=4000)


@router.get('/workspaces')
def workspaces(account=Depends(user)):
    s = get_store()
    ids = [ObjectId(m['workspace_id']) for m in s.db.memberships.find({'user_id': account['id']})]
    return [serialize(s.workspace(str(w['_id']), account['id'])) for w in s.db.workspaces.find({'$or': [{'owner_id': account['id']}, {'_id': {'$in': ids}}]})]


@router.post('/workspaces', status_code=201)
def create_workspace(body: WorkspaceInput, account=Depends(user)):
    s = get_store()
    w = {**body.model_dump(), 'owner_id': account['id'], 'created_at': now(), 'retention_days': 90, 'ai_policy': '', 'model': ''}
    w['_id'] = s.db.workspaces.insert_one(w).inserted_id
    return serialize({**w, 'access_role': 'owner'})


@router.get('/workspaces/{wid}')
def workspace(wid: str, account=Depends(user)):
    return serialize(get_store().workspace(wid, account['id']))


@router.post('/workspaces/{wid}/policy')
def policy(wid: str, body: PolicyInput, account=Depends(user)):
    s = get_store(); s.workspace(wid, account['id'], 'admin')
    s.db.workspaces.update_one({'_id': ObjectId(wid)}, {'$set': body.model_dump()})
    s.db.activity.insert_one({'workspace_id': wid, 'actor': account['id'], 'action': 'Workspace policy updated', 'created_at': now()})
    return {'ok': True}


@router.get('/workspaces/{wid}/members')
def members(wid: str, account=Depends(user)):
    s = get_store(); w = s.workspace(wid, account['id'])
    result = [{'user_id': w['owner_id'], 'role': 'owner'}, *s.db.memberships.find({'workspace_id': wid})]
    for member in result:
        uid = member['user_id']
        record = s.db.users.find_one({'_id': ObjectId(uid[6:])}) if uid.startswith('email:') and ObjectId.is_valid(uid[6:]) else None
        member['name'] = record['name'] if record else ('Local workspace' if uid == 'local-workspace' else uid)
    return serialize(result)


@router.post('/workspaces/{wid}/invitations', status_code=201)
def invite(wid: str, body: RoleInput, account=Depends(user)):
    s = get_store(); s.workspace(wid, account['id'], 'admin')
    token = secrets.token_urlsafe(32)
    s.db.invitations.insert_one({'workspace_id': wid, 'role': body.role, 'token_hash': hashlib.sha256(token.encode()).hexdigest(),
                                 'expires_at': now() + timedelta(days=7), 'created_by': account['id']})
    return {'token': token, 'expires_in_days': 7, 'role': body.role}


@router.post('/invitations/accept')
def accept(body: InviteAccept, account=Depends(user)):
    if account.get('local'):
        raise AppError('Create an account or sign in before joining a team.', 401)
    s = get_store()
    invite = s.db.invitations.find_one({'token_hash': hashlib.sha256(body.token.encode()).hexdigest()})
    if not invite or invite.get('accepted_by') or invite['expires_at'].replace(tzinfo=timezone.utc) <= now():
        raise AppError('This invitation has expired or was already used.', 400)
    w = s.db.workspaces.find_one({'_id': ObjectId(invite['workspace_id'])})
    if not w:
        raise AppError('Workspace not found.', 404)
    claimed = s.db.invitations.update_one({'_id': invite['_id'], 'accepted_by': {'$exists': False}}, {'$set': {'accepted_by': account['id']}})
    if not claimed.modified_count:
        raise AppError('This invitation was already used.', 409)
    if w['owner_id'] != account['id']:
        s.db.memberships.update_one({'workspace_id': invite['workspace_id'], 'user_id': account['id']},
            {'$setOnInsert': {'role': invite['role'], 'joined_at': now()}}, upsert=True)
    return {'workspace_id': invite['workspace_id']}


@router.post('/workspaces/{wid}/members/{uid}')
def change_role(wid: str, uid: str, body: RoleInput, account=Depends(user)):
    s = get_store(); w = s.workspace(wid, account['id'], 'owner')
    if uid == w['owner_id']:
        raise AppError('The workspace owner cannot be demoted.', 409)
    result = s.db.memberships.update_one({'workspace_id': wid, 'user_id': uid}, {'$set': {'role': body.role}})
    if not result.matched_count:
        raise AppError('Member not found.', 404)
    return {'ok': True}


@router.delete('/workspaces/{wid}/members/{uid}')
def remove_member(wid: str, uid: str, account=Depends(user)):
    s = get_store(); w = s.workspace(wid, account['id'], 'owner')
    if uid == w['owner_id']:
        raise AppError('The workspace owner cannot be removed.', 409)
    s.db.memberships.delete_one({'workspace_id': wid, 'user_id': uid})
    return {'ok': True}


@router.get('/workspaces/{wid}/admin')
def admin(wid: str, account=Depends(user)):
    s = get_store(); w = s.workspace(wid, account['id'], 'admin')
    projects = list(s.db.projects.find({'workspace_id': wid}))
    ids = [str(p['_id']) for p in projects]
    return {'workspace': serialize(w), 'project_count': len(projects), 'member_count': s.db.memberships.count_documents({'workspace_id': wid}) + 1,
            'busy_projects': sum(bool(p.get('busy')) for p in projects), 'failed_projects': sum(p['status'] == 'ERROR' for p in projects),
            'artifact_versions': s.db.artifacts.count_documents({'project_id': {'$in': ids}}),
            'usage': serialize(list(s.db.usage.find({'project_id': {'$in': ids}}).sort('created_at', -1).limit(100))),
            'activity': serialize(list(s.db.activity.find({'workspace_id': wid}).sort('created_at', -1).limit(100))),
            'provider_configured': bool(get_settings().gemini_keys), 'default_model': get_settings().gemini_model}


@router.get('/notifications')
def notifications(account=Depends(user)):
    return serialize(list(get_store().db.notifications.find({'user_id': account['id']}).sort('created_at', -1).limit(100)))


@router.post('/notifications/read')
def read_notifications(account=Depends(user)):
    get_store().db.notifications.update_many({'user_id': account['id']}, {'$set': {'read': True}})
    return {'ok': True}
