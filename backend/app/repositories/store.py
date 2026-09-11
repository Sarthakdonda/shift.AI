from datetime import datetime, timezone, timedelta
from functools import lru_cache
from bson import ObjectId
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import InvalidURI
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.schemas import Scores


def now():
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat()
    if isinstance(value, dict):
        return {('id' if k == '_id' else k): serialize(v) for k, v in value.items() if k not in ('owner_id', 'lease_until', 'password_hash', 'token_hash', 'encrypted_token')}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


class Store:
    def __init__(self, db):
        self.db = db

    def indexes(self):
        self.db.generation_requests.create_index('expires_at', expireAfterSeconds=0)
        self.db.users.create_index('email', unique=True)
        self.db.auth_attempts.create_index('expires_at', expireAfterSeconds=0)
        self.db.password_resets.create_index('token_hash', unique=True)
        self.db.password_resets.create_index('expires_at', expireAfterSeconds=0)
        self.db.memberships.create_index([('workspace_id', 1), ('user_id', 1)], unique=True)
        self.db.integrations.create_index([('workspace_id', 1), ('provider', 1)], unique=True)
        self.db.invitations.create_index('token_hash', unique=True)
        self.db.invitations.create_index('expires_at', expireAfterSeconds=0)
        self.db.artifacts.create_index([('project_id', 1), ('kind', 1), ('version', -1)], unique=True)
        self.db.activity.create_index([('workspace_id', 1), ('created_at', -1)])
        self.db.notifications.create_index([('user_id', 1), ('created_at', -1)])
        self.db.projects.create_index([('owner_id', 1), ('updated_at', -1)])
        self.db.messages.create_index([('project_id', 1), ('created_at', 1)])
        self.db.documents.create_index('project_id')
        self.db.document_chunks.create_index([('project_id', 1), ('document_id', 1)])
        self.db.analyses.create_index('project_id', unique=True)
        self.db.blueprints.create_index([('project_id', 1), ('version', -1)], unique=True)

    def workspace(self, wid, actor, permission='read'):
        if not ObjectId.is_valid(wid):
            raise AppError('Workspace not found.', 404)
        w = self.db.workspaces.find_one({'_id': ObjectId(wid)})
        membership = self.db.memberships.find_one({'workspace_id': wid, 'user_id': actor})
        role = 'owner' if w and w['owner_id'] == actor else membership.get('role') if membership else None
        if not w or not role:
            raise AppError('Workspace not found.', 404)
        allowed = {'read': ['owner','admin','editor','reviewer','viewer'], 'write': ['owner','admin','editor'],
                   'review': ['owner','admin','reviewer'], 'admin': ['owner','admin'], 'owner': ['owner']}
        if role not in allowed[permission]:
            raise AppError('Your workspace role does not allow this action.', 403)
        return {**w, 'access_role': role}

    def project_filter(self, actor):
        workspaces = [str(w['_id']) for w in self.db.workspaces.find({'owner_id': actor}, {'_id': 1})]
        workspaces += [m['workspace_id'] for m in self.db.memberships.find({'user_id': actor})]
        return {'$or': [{'owner_id': actor, 'workspace_id': {'$in': [None, '']}}, {'workspace_id': {'$in': workspaces}}]}

    def project(self, pid, owner, permission='read'):
        if not ObjectId.is_valid(pid):
            raise AppError('Project not found.', 404)
        p = self.db.projects.find_one({'_id': ObjectId(pid)})
        if not p:
            raise AppError('Project not found.', 404)
        if p.get('workspace_id'):
            role = self.workspace(p['workspace_id'], owner, permission)['access_role']
        elif p['owner_id'] == owner:
            role = 'owner'
        else:
            raise AppError('Project not found.', 404)
        if p.get('busy') and p.get('lease_until', now()).replace(tzinfo=timezone.utc) < now():
            self.update(pid, busy=False, status='ERROR', error='The previous operation was interrupted. Please retry.')
            p = self.db.projects.find_one({'_id': ObjectId(pid)})
        return {**p, 'access_role': role}

    def create(self, data, owner):
        if data.get('workspace_id'):
            self.workspace(data['workspace_id'], owner, 'write')
        p = {**data, 'owner_id': owner, 'status': 'DISCOVERY', 'discovery_scores': Scores().model_dump(), 'discovery': None, 'analysis_ready': False, 'ai_necessity': None, 'busy': False, 'error': None, 'created_at': now(), 'updated_at': now()}
        p['_id'] = self.db.projects.insert_one(p).inserted_id
        self.message(str(p['_id']), 'user', data['initial_problem'])
        return p

    def update(self, pid, **values):
        self.db.projects.update_one({'_id': ObjectId(pid)}, {'$set': {**values, 'updated_at': now()}})

    def acquire(self, pid, owner, permission='write'):
        self.project(pid, owner, permission)
        result = self.db.projects.find_one_and_update({'_id': ObjectId(pid), 'busy': {'$ne': True}}, {'$set': {'busy': True, 'lease_until': now() + timedelta(minutes=30), 'error': None}}, return_document=ReturnDocument.AFTER)
        if not result:
            raise AppError('This project is already processing. Please wait for it to finish.', 409)

    def message(self, pid, role, content, **extra):
        self.db.messages.insert_one({'project_id': pid, 'role': role, 'content': content, 'created_at': now(), **extra})

    def related(self, collection, pid):
        return list(self.db[collection].find({'project_id': pid}).sort('created_at', 1))

    def latest(self, collection, pid):
        return self.db[collection].find_one({'project_id': pid}, sort=[('created_at', -1)])

    def save_analysis(self, pid, state):
        self.db.analyses.update_one({'project_id': pid}, {'$set': {**state, 'updated_at': now()}}, upsert=True)

    def save_blueprint(self, pid, content):
        previous = self.latest('blueprints', pid)
        b = {'project_id': pid, 'version': (previous['version'] if previous else 0) + 1, 'content': content, 'created_at': now()}
        b['_id'] = self.db.blueprints.insert_one(b).inserted_id
        return b

    def invalidate(self, pid):
        self.db.analyses.delete_many({'project_id': pid})
        # Retain version history; latest blueprint is inaccessible until reanalysis.
        self.update(pid, analysis_ready=False, ai_necessity=None, status='DISCOVERY')
        self.db.projects.update_one({'_id': ObjectId(pid)}, {'$inc': {'context_revision': 1}})

    def delete(self, pid, owner):
        self.project(pid, owner, 'admin')
        self.acquire(pid, owner)
        for name in ['messages', 'documents', 'document_chunks', 'analyses', 'blueprints', 'artifacts', 'comments', 'reviews', 'outcomes', 'usage', 'notifications', 'activity', 'restored_archives', 'generation_requests']:
            self.db[name].delete_many({'project_id': pid})
        self.db.projects.delete_one({'_id': ObjectId(pid)})

    def activity(self, project, actor, action, detail=''):
        self.db.activity.insert_one({'project_id': str(project['_id']), 'workspace_id': project.get('workspace_id'),
                                     'actor': actor, 'action': action, 'detail': detail[:2000], 'created_at': now()})
        recipients = {project['owner_id']}
        if project.get('workspace_id'):
            recipients.update(m['user_id'] for m in self.db.memberships.find({'workspace_id': project['workspace_id']}))
            w = self.db.workspaces.find_one({'_id': ObjectId(project['workspace_id'])})
            if w:
                recipients.add(w['owner_id'])
        for recipient in recipients - {actor}:
            self.db.notifications.insert_one({'user_id': recipient, 'project_id': str(project['_id']), 'message': f"{project['name']}: {action}", 'read': False, 'created_at': now()})


@lru_cache
def get_store():
    s = get_settings()
    if not s.mongodb_uri:
        raise AppError('Add MONGODB_URI to backend/.env and restart the backend.', 503, 'database_configuration')
    try:
        client = MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=15000)
    except InvalidURI:
        raise AppError('Check MONGODB_URI in backend/.env.', 503, 'database_configuration') from None
    except Exception:
        raise AppError('MongoDB connection discovery failed. Check DNS/network access and the Atlas connection settings, then retry.', 503, 'database_unavailable') from None
    return Store(client[s.mongodb_database])
