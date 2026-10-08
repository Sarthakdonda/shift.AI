"""MongoDB storage for cloud deployments: one scoped database per application.

The connection string arrives only through the backend host's environment.
Relationships are enforced in the runtime: references must exist and a record
cannot be deleted while another record points at it (as SQLite RESTRICT does).
These checks are not transactional; concurrent conflicting writes are rare for
the supported workloads but are not strictly serialized.
"""
import json
import re
import secrets
import time
from datetime import datetime, timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from schema_contract import compatibility
from storage import Conflict, Unavailable


class MongoStore:
    kind = 'mongodb'

    def __init__(self, uri, database='', client=None):
        if client is None:
            from pymongo import MongoClient
            client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000,
                                 socketTimeoutMS=20000, retryWrites=True, appname='shift-generated-app')
        self.client = client
        if not database:
            try:
                database = client.get_default_database().name
            except Exception:
                raise RuntimeError('Set MONGODB_DATABASE or include the database name in MONGODB_URI.') from None
        self.db = client[database]
        self.spec = {'entities': []}

    def migrate(self, spec, identity, initial_admin, attempts=18, delay=5):
        # Network access rules can take a minute to apply after provisioning.
        for attempt in range(attempts):
            try:
                self.db.command('ping')
                break
            except PyMongoError:
                if attempt == attempts - 1:
                    raise RuntimeError('MongoDB is unreachable. Check the database network access list and credentials.') from None
                time.sleep(delay)
        current = self.db.shift_schema.find_one({'_id': 'current'})
        if current:
            issues = compatibility(json.loads(current['spec']), spec)
            if issues:
                raise RuntimeError('Unsafe migration blocked: ' + ' '.join(issues))
        self.db.users.create_index('email', unique=True)
        self.db.sessions.create_index('expires_at', expireAfterSeconds=0)
        self.db.integration_outbox.create_index([('status', 1), ('retry_at', 1), ('created', 1)])
        for entity in spec['entities']:
            records = self.db['e_' + entity['name']]
            records.create_index([('created_at', -1)])
            for field in entity['fields']:
                if field['kind'] == 'reference':
                    records.create_index(field['name'])
        # Additive changes need no rewrite: absent fields read as null.
        self.db.shift_migrations.update_one({'_id': identity['build_id']}, {'$setOnInsert': {'applied': time.time()}}, upsert=True)
        self.db.shift_schema.replace_one({'_id': 'current'}, {'_id': 'current', 'spec': json.dumps(spec)}, upsert=True)
        if not self.db.users.find_one({}, {'_id': 1}):
            email, password = initial_admin()
            try:
                self.db.users.insert_one({'_id': secrets.token_hex(16), 'email': email, 'password': password, 'role': 'admin'})
            except DuplicateKeyError:
                pass
        self.spec = spec

    def ping(self):
        try:
            self.db.command('ping')
        except PyMongoError:
            raise Unavailable('Database unavailable.') from None

    # ---- accounts and sessions -------------------------------------------------
    @staticmethod
    def _user(doc):
        return {'id': doc['_id'], 'email': doc['email'], 'password': doc['password'], 'role': doc['role']} if doc else None

    def register_attempt(self, email):
        now = time.time()
        self.db.login_attempts.update_one({'_id': email, 'window': {'$lte': now - 900}}, {'$set': {'attempts': 0, 'window': now}})
        doc = self.db.login_attempts.find_one_and_update({'_id': email}, {'$inc': {'attempts': 1}, '$setOnInsert': {'window': now}},
                                                         upsert=True, return_document=ReturnDocument.AFTER)
        return doc['attempts'] <= 10

    def clear_attempts(self, email):
        self.db.login_attempts.delete_one({'_id': email})

    def user_by_email(self, email):
        return self._user(self.db.users.find_one({'email': email}))

    def start_session(self, token_hash, user_id, expires):
        self.db.sessions.insert_one({'_id': token_hash, 'user_id': user_id, 'expires': expires,
                                     'expires_at': datetime.fromtimestamp(expires, timezone.utc)})

    def session_user(self, token_hash):
        session = self.db.sessions.find_one({'_id': token_hash, 'expires': {'$gt': time.time()}})
        return self._user(self.db.users.find_one({'_id': session['user_id']})) if session else None

    def end_session(self, token_hash):
        self.db.sessions.delete_one({'_id': token_hash})

    def list_users(self):
        return [{'id': u['_id'], 'email': u['email'], 'role': u['role']} for u in self.db.users.find({}, {'password': 0})]

    def create_user(self, uid, email, password, role):
        try:
            self.db.users.insert_one({'_id': uid, 'email': email, 'password': password, 'role': role})
        except DuplicateKeyError:
            raise Conflict('Duplicate account.') from None

    def audit(self, user_id, action, entity, record_id):
        self.db.audit.insert_one({'user_id': user_id, 'action': action, 'entity': entity, 'record_id': record_id, 'created': time.time()})

    # ---- records ---------------------------------------------------------------
    @staticmethod
    def _row(entity, doc):
        if not doc:
            return None
        row = {'id': doc['_id'], 'created_at': doc.get('created_at'), 'updated_at': doc.get('updated_at')}
        row.update({f['name']: doc.get(f['name']) for f in entity['fields']})
        return row

    def _check_references(self, entity, values):
        for field in entity['fields']:
            value = values.get(field['name'])
            if field['kind'] == 'reference' and value is not None:
                if not self.db['e_' + field['reference']].find_one({'_id': value}, {'_id': 1}):
                    raise Conflict('Referenced record does not exist.')

    def list_records(self, entity, term, offset):
        query = {}
        if term:
            pattern = {'$regex': re.escape(term), '$options': 'i'}
            clauses = [{f['name']: pattern} for f in entity['fields'] if f['kind'] not in ('number', 'boolean')]
            try:
                clauses += [{f['name']: float(term)} for f in entity['fields'] if f['kind'] == 'number']
            except ValueError:
                pass
            query = {'$or': clauses} if clauses else {'_id': None}
        cursor = self.db['e_' + entity['name']].find(query).sort('created_at', -1).skip(offset).limit(100)
        return [self._row(entity, doc) for doc in cursor]

    def get_record(self, entity, rid):
        return self._row(entity, self.db['e_' + entity['name']].find_one({'_id': rid}))

    def insert_record(self, entity, rid, values):
        self._check_references(entity, values)
        try:
            self.db['e_' + entity['name']].insert_one({'_id': rid, 'created_at': time.time(), 'updated_at': time.time(), **values})
        except DuplicateKeyError:
            raise Conflict('Duplicate record.') from None

    def update_record(self, entity, rid, values):
        self._check_references(entity, values)
        self.db['e_' + entity['name']].update_one({'_id': rid}, {'$set': {**values, 'updated_at': time.time()}})

    def delete_record(self, entity, rid):
        for other in self.spec['entities']:
            for field in other['fields']:
                if field['kind'] == 'reference' and field['reference'] == entity['name']:
                    if self.db['e_' + other['name']].find_one({field['name']: rid}, {'_id': 1}):
                        raise Conflict('Record is referenced by another record.')
        self.db['e_' + entity['name']].delete_one({'_id': rid})

    def transition(self, entity, rid, field, from_value, to_value):
        changed = self.db['e_' + entity['name']].update_one({'_id': rid, field: from_value}, {'$set': {field: to_value, 'updated_at': time.time()}})
        return changed.matched_count == 1

    # ---- integration outbox ----------------------------------------------------
    @staticmethod
    def _delivery(doc):
        return {'id': doc['_id'], **{k: v for k, v in doc.items() if k != '_id'}} if doc else None

    def outbox_entry(self, key):
        return self._delivery(self.db.integration_outbox.find_one({'_id': key}))

    def enqueue_delivery(self, key, action, entity, record_id, user_id, payload):
        now = time.time()
        self.db.integration_outbox.update_one({'_id': key}, {'$setOnInsert': {
            'action': action, 'entity': entity, 'record_id': record_id, 'user_id': user_id, 'payload': payload,
            'status': 'queued', 'attempts': 0, 'retry_at': now, 'created': now, 'error': ''}}, upsert=True)

    def deliveries(self, user_id, admin):
        rows = self.db.integration_outbox.find({} if admin else {'user_id': user_id}, {'payload': 0, 'user_id': 0, 'retry_at': 0})
        return [self._delivery(doc) for doc in rows.sort('created', -1).limit(100)]

    def claim_delivery(self):
        now = time.time()
        self.db.integration_outbox.update_many({'status': 'sending', 'retry_at': {'$lte': now}, 'attempts': {'$gte': 5}},
                                               {'$set': {'status': 'failed', 'error': 'Delivery interrupted after five attempts.'}})
        doc = self.db.integration_outbox.find_one_and_update(
            {'status': {'$in': ['queued', 'sending']}, 'retry_at': {'$lte': now}, 'attempts': {'$lt': 5}},
            {'$set': {'status': 'sending', 'retry_at': now + 60}, '$inc': {'attempts': 1}},
            sort=[('created', 1)], return_document=ReturnDocument.AFTER)
        return self._delivery(doc)

    def finish_delivery(self, row, status, error, retry_at):
        self.db.integration_outbox.update_one({'_id': row['id'], 'attempts': row['attempts'], 'status': 'sending'},
                                              {'$set': {'status': status, 'error': error, 'retry_at': retry_at}})
