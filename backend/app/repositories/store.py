from datetime import datetime, timezone, timedelta
from functools import lru_cache
from bson import ObjectId
from pymongo import MongoClient, ReturnDocument
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
        return {('id' if k == '_id' else k): serialize(v) for k, v in value.items() if k not in ('owner_id', 'lease_until')}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


class Store:
    def __init__(self, db):
        self.db = db

    def indexes(self):
        self.db.projects.create_index([('owner_id', 1), ('updated_at', -1)])
        self.db.messages.create_index([('project_id', 1), ('created_at', 1)])
        self.db.documents.create_index('project_id')
        self.db.document_chunks.create_index([('project_id', 1), ('document_id', 1)])
        self.db.analyses.create_index('project_id', unique=True)
        self.db.blueprints.create_index([('project_id', 1), ('version', -1)], unique=True)

    def project(self, pid, owner):
        if not ObjectId.is_valid(pid):
            raise AppError('Project not found.', 404)
        p = self.db.projects.find_one({'_id': ObjectId(pid), 'owner_id': owner})
        if not p:
            raise AppError('Project not found.', 404)
        if p.get('busy') and p.get('lease_until', now()).replace(tzinfo=timezone.utc) < now():
            self.update(pid, busy=False, status='ERROR', error='The previous operation was interrupted. Please retry.')
            p = self.db.projects.find_one({'_id': ObjectId(pid)})
        return p

    def create(self, data, owner):
        p = {**data, 'owner_id': owner, 'status': 'DISCOVERY', 'discovery_scores': Scores().model_dump(), 'discovery': None, 'analysis_ready': False, 'ai_necessity': None, 'busy': False, 'error': None, 'created_at': now(), 'updated_at': now()}
        p['_id'] = self.db.projects.insert_one(p).inserted_id
        self.message(str(p['_id']), 'user', data['initial_problem'])
        return p

    def update(self, pid, **values):
        self.db.projects.update_one({'_id': ObjectId(pid)}, {'$set': {**values, 'updated_at': now()}})

    def acquire(self, pid, owner):
        self.project(pid, owner)
        result = self.db.projects.find_one_and_update({'_id': ObjectId(pid), 'owner_id': owner, 'busy': {'$ne': True}}, {'$set': {'busy': True, 'lease_until': now() + timedelta(minutes=30), 'error': None}}, return_document=ReturnDocument.AFTER)
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

    def delete(self, pid, owner):
        self.acquire(pid, owner)
        for name in ['messages', 'documents', 'document_chunks', 'analyses', 'blueprints']:
            self.db[name].delete_many({'project_id': pid})
        self.db.projects.delete_one({'_id': ObjectId(pid), 'owner_id': owner})


@lru_cache
def get_store():
    s = get_settings()
    if not s.mongodb_uri:
        raise AppError('Add MONGODB_URI to backend/.env and restart the backend.', 503, 'database_configuration')
    try:
        client = MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=15000)
    except Exception:
        raise AppError('Check MONGODB_URI in backend/.env.', 503, 'database_configuration') from None
    return Store(client[s.mongodb_database])
