import io
from datetime import timedelta
from unittest.mock import patch
import pytest
from app.core.auth import signer
from app.repositories.store import now
from app.core.errors import AppError
from app.services.gemini_service import GeminiService


def test_health_boots_without_keys(setup):
    client, _, _, settings = setup
    assert client.get('/api/health').json()['gemini_configured'] is False
    settings.gemini_api_key = 'configured-test-value'
    assert client.get('/api/health').json()['gemini_configured'] is True
    assert 'gemini_api_key' not in client.get('/api/health').text


def test_project_crud_and_isolation(setup, project):
    client, store, _, _ = setup
    p2 = client.post('/api/projects', json={'name': 'Another project', 'initial_problem': 'A different unrelated business problem.'}).json()['id']
    assert len(client.get('/api/projects').json()) == 2
    assert client.get(f'/api/projects/{project}').json()['name'] == 'Invoice operations'
    assert 'invoice' not in client.get(f'/api/projects/{p2}/messages').text.lower()
    assert client.get('/api/projects/not-an-id').status_code == 404
    for c in ['documents', 'document_chunks', 'analyses', 'blueprints']:
        store.db[c].insert_one({'project_id': project})
    assert client.delete(f'/api/projects/{project}').status_code == 200
    for c in ['messages', 'documents', 'document_chunks', 'analyses', 'blueprints']:
        assert store.db[c].count_documents({'project_id': project}) == 0
    assert client.get(f'/api/projects/{p2}').status_code == 200


def test_discovery_to_blueprint_end_to_end(setup, project):
    client, store, ai, _ = setup
    assert client.post(f'/api/projects/{project}/analysis/run').status_code == 409
    response = client.post(f'/api/projects/{project}/chat', json={'content': 'Two staff manually review every row. We want fewer duplicate entries. No AI is required; the fields have fixed rules.'})
    assert response.status_code == 200
    assert response.json()['analysis_ready']
    assert client.get(f'/api/projects/{project}/messages').json()[-1]['role'] == 'assistant'
    assert client.post(f'/api/projects/{project}/analysis/run').status_code == 202
    p = client.get(f'/api/projects/{project}').json()
    assert p['status'] == 'BLUEPRINT_READY' and p['busy'] is False
    bp = client.get(f'/api/projects/{project}/blueprint').json()
    assert bp['content']['ai_necessity']['classification'] == 'AUTOMATION_SUFFICIENT'
    assert bp['content']['solution']['components'][0]['uses_ai'] is False
    assert bp['content']['business_value']['metrics'][0]['is_assumption']
    assert ai.calls == ['Discovery', 'WorkflowAnalysis', 'RootCause', 'Necessity', 'Solution', 'RedTeam', 'BusinessValue', 'Conclusion']
    assert client.post(f'/api/projects/{project}/blueprint/generate').json()['version'] == 1
    # Reload from a fresh repository instance: results live in Mongo collections.
    from app.repositories.store import Store
    assert Store(store.db).project(project, 'local-workspace')['status'] == 'BLUEPRINT_READY'
    client.post(f'/api/projects/{project}/chat', json={'content': 'Correction: the data now has many exceptional cases.'})
    assert client.get(f'/api/projects/{project}/blueprint').json() is None
    assert client.get(f'/api/projects/{project}/analysis').json() is None


def test_red_team_bounded_and_findings_retained(setup, project):
    client, _, ai, _ = setup
    ai.always_revise = True
    client.post(f'/api/projects/{project}/discovery/next')
    client.post(f'/api/projects/{project}/analysis/run')
    bp = client.get(f'/api/projects/{project}/blueprint').json()['content']
    assert bp['red_team_cycle'] == 3
    assert len(bp['red_team_history']) == 3
    assert bp['red_team']['findings'][0]['requires_revision']
    assert ai.calls.count('Solution') == 3
    assert ai.calls.count('RedTeam') == 3


def test_missing_gemini_preserves_project(setup, project, monkeypatch):
    from app.api import routes
    client, store, _, _ = setup
    monkeypatch.setattr(routes, 'get_gemini', GeminiService)
    r = client.post(f'/api/projects/{project}/chat', json={'content': 'Hello again'})
    assert r.status_code == 503
    assert 'GEMINI_API_KEY' in r.json()['detail']
    assert store.project(project, 'local-workspace')['busy'] is False


def test_failed_chat_saves_answer_and_allows_retry(setup, project, monkeypatch):
    client, store, ai, _ = setup
    original = ai.generate_structured
    monkeypatch.setattr(ai, 'generate_structured', lambda *args: (_ for _ in ()).throw(AppError('Quota reached', 503)))
    assert client.post(f'/api/projects/{project}/chat', json={'content': 'A new fact to preserve'}).status_code == 503
    assert store.related('messages', project)[-1]['content'] == 'A new fact to preserve'
    assert not store.project(project, 'local-workspace')['busy']
    monkeypatch.setattr(ai, 'generate_structured', original)
    assert client.post(f'/api/projects/{project}/discovery/next').status_code == 200
    assert len([m for m in store.related('messages', project) if m['content'] == 'A new fact to preserve']) == 1


def test_busy_project_rejects_concurrent_mutations_and_expired_lease_recovers(setup, project):
    client, store, *_ = setup
    store.acquire(project, 'local-workspace')
    assert client.post(f'/api/projects/{project}/chat', json={'content': 'Concurrent request'}).status_code == 409
    assert client.delete(f'/api/projects/{project}').status_code == 409
    store.update(project, lease_until=now() - timedelta(seconds=1))
    p = client.get(f'/api/projects/{project}').json()
    assert p['busy'] is False and p['status'] == 'ERROR'


def test_document_processing_and_delete(setup, project):
    client, store, ai, _ = setup
    r = client.post(f'/api/projects/{project}/documents', files={'file': ('../../workflow.txt', b'Invoices arrive via email and are tracked in a shared spreadsheet.', 'text/plain')})
    assert r.status_code == 202
    did = r.json()['id']
    d = client.get(f'/api/projects/{project}/documents').json()[0]
    assert d['status'] == 'processed' and d['filename'] == 'workflow.txt'
    assert d['summary'] and d['facts']
    assert store.db.document_chunks.count_documents({'project_id': project}) > 0
    assert ai.calls == ['DocumentSummary', 'Discovery']
    assert client.delete(f'/api/projects/{project}/documents/{did}').status_code == 200
    assert store.db.document_chunks.count_documents({'project_id': project}) == 0
    assert client.get(f'/api/projects/{project}').json()['discovery'] is None


def test_document_validation_and_failure(setup, project):
    client, store, _, settings = setup
    for name, body in [('bad.exe', b'abc'), ('bad.pdf', b'Not PDF'), ('bad.docx', b'Not Office'), ('empty.txt', b'')]:
        assert client.post(f'/api/projects/{project}/documents', files={'file': (name, body)}).status_code in (400, 415)
    settings.max_upload_mb = 1
    assert client.post(f'/api/projects/{project}/documents', files={'file': ('big.txt', b'x' * (1024 * 1024 + 1))}).status_code == 413
    r = client.post(f'/api/projects/{project}/documents', files={'file': ('corrupt.txt', b'\xff\xfe\x00')})
    assert r.status_code == 202
    assert client.get(f'/api/projects/{project}/documents').json()[0]['status'] == 'failed'
    assert not store.project(project, 'local-workspace')['busy']


def test_authentication_ownership_csrf_and_signout(setup, project):
    client, store, _, settings = setup
    settings.google_client_id = 'test-client.apps.googleusercontent.com'
    assert client.get('/api/projects').status_code == 401
    # Signed session A may not access local or another account's projects.
    client.cookies.set('shift_session', signer().dumps({'id': 'google:a', 'name': 'A', 'email': 'a@example.com', 'local': False}))
    assert client.get(f'/api/projects/{project}').status_code == 404
    assert client.post('/api/projects', json={'name': 'Owned', 'initial_problem': 'Account-specific business challenge.'}).status_code == 403
    r = client.post('/api/projects', json={'name': 'Owned', 'initial_problem': 'Account-specific business challenge.'}, headers={'Origin': 'http://localhost:3000'})
    assert r.status_code == 201
    owned = r.json()['id']
    assert client.get(f'/api/projects/{owned}').status_code == 200
    client.cookies.set('shift_session', signer().dumps({'id': 'google:b', 'name': 'B'}))
    for path in ['', '/messages', '/documents', '/analysis', '/blueprint']:
        assert client.get(f'/api/projects/{owned}{path}').status_code == 404
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/auth/logout', headers={'Origin': 'http://localhost:3000'}).status_code == 200


def test_google_token_verified_with_nonce(setup):
    client, _, _, settings = setup
    settings.google_client_id = 'test-client'
    nonce = client.get('/api/auth/nonce').json()['nonce']
    with patch('app.core.auth.id_token.verify_oauth2_token', return_value={'sub': '123', 'email': 'test@example.com', 'name': 'Test', 'email_verified': True, 'nonce': nonce}) as verify:
        r = client.post('/api/auth/google', json={'credential': 'test-token-at-least-twenty-characters'}, headers={'Origin': 'http://localhost:3000'})
        assert r.status_code == 200
        assert verify.call_args.args[2] == 'test-client'
        assert 'HttpOnly' in r.headers['set-cookie']
        assert client.get('/api/auth/me').json()['id'] == 'google:123'
    # A stale or missing nonce must reject a token.
    client.cookies.clear()
    assert client.post('/api/auth/google', json={'credential': 'test-token-at-least-twenty-characters'}).status_code == 401
