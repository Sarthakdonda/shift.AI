"""Generated runtime on the MongoDB store (the cloud deployment path), offline via mongomock."""
import importlib.util
import json
import sys
import threading
from http.client import HTTPConnection
import mongomock
import pytest
from bson import ObjectId
from app.services.application_generator import compile_application
from tests.builder_fixtures import specification

MODULES = ('server_under_test', 'storage', 'storage_sqlite', 'storage_mongo', 'schema_contract', 'business_logic', 'integration_delivery')


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    files, _, _ = compile_application(specification(), str(ObjectId()))
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    for name in ('DATABASE_BACKEND', 'MONGODB_URI', 'FRONTEND_ORIGINS', 'RENDER_EXTERNAL_URL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'unused.db'))
    monkeypatch.setenv('ADMIN_EMAIL', 'owner@example.test')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-only-password-123')
    monkeypatch.setenv('APP_ORIGIN', 'https://inventory.example.test')
    monkeypatch.setenv('COOKIE_SECURE', 'false')
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in MODULES:
        sys.modules.pop(name, None)
    definition = importlib.util.spec_from_file_location('server_under_test', tmp_path / 'server.py')
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    from storage_mongo import MongoStore
    client = mongomock.MongoClient()
    module.STORE = MongoStore('mongodb://unused/app', 'shift_app_test', client=client)
    module.migrate()
    server = module.ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield module, server, client['shift_app_test']
    server.shutdown()
    server.server_close()
    for name in MODULES:
        sys.modules.pop(name, None)


def call(server, path, body=None, method=None, cookie='', origin='https://inventory.example.test'):
    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    headers = {'Origin': origin, 'Cookie': cookie}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    connection.request(method or ('POST' if body is not None else 'GET'), path, json.dumps(body) if body is not None else None, headers)
    response = connection.getresponse()
    data = json.loads(response.read())
    session = (response.getheader('Set-Cookie') or '').split(';')[0]
    connection.close()
    return response.status, data, session


def login(server):
    status, body, cookie = call(server, '/api/login', {'email': 'owner@example.test', 'password': 'test-only-password-123'})
    assert status == 200 and body['role'] == 'admin'
    return cookie


def test_health_reports_mongodb_and_admin_is_seeded_once(runtime):
    module, server, db = runtime
    status, health, _ = call(server, '/health')
    assert status == 200 and health['database'] == 'mongodb' and health['build_id'] == module.IDENTITY['build_id']
    module.migrate()
    assert db.users.count_documents({}) == 1
    assert db.shift_schema.find_one({'_id': 'current'})


def test_crud_search_references_and_restricted_delete(runtime):
    _, server, db = runtime
    cookie = login(server)
    status, company, _ = call(server, '/api/records/companies', {'name': 'Acme Supplies'}, cookie=cookie)
    assert status == 200
    candidate = {'name': 'Asha', 'email': 'asha@example.test', 'company': company['id'], 'stage': 'new'}
    status, created, _ = call(server, '/api/records/candidates', candidate, cookie=cookie)
    assert status == 200
    assert db.e_candidates.find_one({'_id': created['id']})['company'] == company['id']
    assert call(server, '/api/records/candidates?q=ash', cookie=cookie)[1][0]['id'] == created['id']
    assert call(server, '/api/records/candidates?q=zzz', cookie=cookie)[1] == []
    assert call(server, '/api/records/candidates', {**candidate, 'company': 'missing'}, cookie=cookie)[0] == 409
    # A referenced company cannot be deleted (RESTRICT semantics).
    assert call(server, '/api/records/companies/' + company['id'], method='DELETE', cookie=cookie)[0] == 409
    updated = call(server, '/api/records/candidates/' + created['id'], {**candidate, 'name': 'Asha Rao'}, cookie=cookie)
    assert updated[0] == 200 and db.e_candidates.find_one({'_id': created['id']})['name'] == 'Asha Rao'
    assert call(server, '/api/records/candidates/' + created['id'] + '/transition', {'transition': 0}, cookie=cookie)[0] == 200
    assert db.e_candidates.find_one({'_id': created['id']})['stage'] == 'interview'
    assert call(server, '/api/records/candidates/' + created['id'] + '/transition', {'transition': 0}, cookie=cookie)[0] == 409
    assert call(server, '/api/records/candidates/' + created['id'], method='DELETE', cookie=cookie)[0] == 200
    assert call(server, '/api/records/companies/' + company['id'], method='DELETE', cookie=cookie)[0] == 200
    assert db.audit.count_documents({}) >= 5


def test_sessions_origins_roles_and_duplicate_accounts(runtime):
    _, server, _ = runtime
    assert call(server, '/api/spec')[0] == 401
    cookie = login(server)
    assert call(server, '/api/records/companies', {'name': 'X'}, cookie=cookie, origin='https://evil.example')[0] == 403
    account = {'email': 'viewer@example.test', 'password': 'viewer-password-123', 'role': 'viewer'}
    assert call(server, '/api/users', account, cookie=cookie)[0] == 201
    assert call(server, '/api/users', account, cookie=cookie)[0] == 409
    status, _, viewer = call(server, '/api/login', {'email': 'viewer@example.test', 'password': 'viewer-password-123'})
    assert status == 200
    assert call(server, '/api/records/companies', cookie=viewer)[0] == 200
    assert call(server, '/api/records/companies', {'name': 'Y'}, cookie=viewer)[0] == 403
    assert call(server, '/api/logout', {}, cookie=cookie)[0] == 200
    assert call(server, '/api/spec', cookie=cookie)[0] == 401


def test_login_throttle_and_frontend_origin_allowlist(runtime, monkeypatch):
    _, server, _ = runtime
    for _ in range(10):
        assert call(server, '/api/login', {'email': 'owner@example.test', 'password': 'wrong'})[0] == 401
    assert call(server, '/api/login', {'email': 'owner@example.test', 'password': 'wrong'})[0] == 429
    monkeypatch.setenv('FRONTEND_ORIGINS', 'https://inventory-web.example.test')
    assert call(server, '/api/login', {'email': 'x@example.test', 'password': 'y'}, origin='https://inventory-web.example.test')[0] == 401
