import pytest
import mongomock
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.repositories.store import Store
from tests.fakes import FakeGemini


@pytest.fixture
def setup(monkeypatch):
    from app import main
    from app.api import routes
    settings = get_settings()
    monkeypatch.setattr(settings, 'google_client_id', '')
    monkeypatch.setattr(settings, 'mongodb_uri', '')
    monkeypatch.setattr(settings, 'gemini_api_key', '')
    monkeypatch.setattr(settings, 'allow_local_access', True)
    monkeypatch.setattr(settings, 'session_secret', 'test-secret-that-is-at-least-thirty-two-characters')
    monkeypatch.setattr(settings, 'vector_search_enabled', False)
    store = Store(mongomock.MongoClient().test_shift_ai)
    fake = FakeGemini()
    monkeypatch.setattr(routes, 'get_store', lambda: store)
    monkeypatch.setattr(main, 'get_store', lambda: store)
    monkeypatch.setattr(routes, 'get_gemini', lambda: fake)
    with TestClient(main.app) as client:
        yield client, store, fake, settings


@pytest.fixture
def project(setup):
    client, *_ = setup
    response = client.post('/api/projects', json={'name': 'Invoice operations', 'initial_problem': 'We manually copy invoice fields from email to spreadsheets.'})
    assert response.status_code == 201
    return response.json()['id']
