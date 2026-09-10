from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import pytest
from app.core.errors import AppError
from app.services.project_service import ProjectService


def test_cancel_stops_waiting_unlocks_and_discards_late_response(setup, project, monkeypatch):
    client, store, fake, _ = setup
    started, release, finished = Event(), Event(), Event()
    original = fake.generate_structured

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(5)
        try:
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(fake, 'generate_structured', slow)
    request_id = str(uuid4())
    owner = store.db.projects.find_one() ['owner_id']
    before = len(store.related('messages', project))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(ProjectService(store, fake).chat, project, owner, 'Please help with our invoice workflow.', None, request_id)
        try:
            assert started.wait(3)
            response = client.post(f'/api/projects/{project}/generation/cancel', json={'request_id': request_id})
            assert response.status_code == 200
            with pytest.raises(AppError) as stopped:
                future.result(timeout=2)
            assert stopped.value.code == 'generation_cancelled'
            assert not store.project(project, owner)['busy']
            assert len(store.related('messages', project)) == before + 1
        finally:
            release.set()
            assert finished.wait(3)
    assert len(store.related('messages', project)) == before + 1
    monkeypatch.setattr(fake, 'generate_structured', original)
    followup = client.post(f'/api/projects/{project}/chat', json={'content': 'Continue with the workflow.', 'request_id': str(uuid4())})
    assert followup.status_code == 200


def test_cancel_before_start_does_not_start_provider(setup, project):
    client, store, fake, _ = setup
    request_id = str(uuid4())
    assert client.post(f'/api/projects/{project}/generation/cancel', json={'request_id': request_id}).status_code == 200
    response = client.post(f'/api/projects/{project}/chat', json={'content': 'Hi', 'request_id': request_id})
    assert response.json()['code'] == 'generation_cancelled'
    assert not fake.calls
    assert len(store.related('messages', project)) == 1


def test_cancel_automatic_analysis_prevents_later_stages(setup, project, monkeypatch):
    client, store, fake, _ = setup
    started, release, finished = Event(), Event(), Event()
    original = fake.generate_structured

    def slow_analysis(instruction, context, schema):
        if schema.__name__ == 'WorkflowAnalysis':
            started.set()
            assert release.wait(5)
            try:
                return original(instruction, context, schema)
            finally:
                finished.set()
        return original(instruction, context, schema)

    monkeypatch.setattr(fake, 'generate_structured', slow_analysis)
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(client.post, f'/api/projects/{project}/chat', json={
            'content': 'Fixed rules cover invoice fields; keep human exception review.', 'request_id': request_id,
        })
        try:
            assert started.wait(3)
            assert client.post(f'/api/projects/{project}/generation/cancel', json={'request_id': request_id}).status_code == 200
            assert response.result(timeout=2).status_code == 200
            state = client.get(f'/api/projects/{project}').json()
            assert not state['busy'] and state['status'] == 'DISCOVERY'
            assert state['active_generation_id'] is None
        finally:
            release.set()
            assert finished.wait(3)
    assert store.db.blueprints.count_documents({'project_id': project}) == 0
    assert 'RootCause' not in fake.calls


def test_cancel_requires_project_write_access(setup, project):
    client, store, *_ = setup
    store.db.projects.update_one({}, {'$set': {'owner_id': 'another-user'}})
    assert client.post(f'/api/projects/{project}/generation/cancel', json={'request_id': str(uuid4())}).status_code == 404
    assert store.db.generation_requests.count_documents({}) == 0


def test_usage_requires_project_access_and_returns_no_credentials(setup, project):
    client, store, *_ = setup
    result = client.get(f'/api/projects/{project}/usage')
    assert result.status_code == 200
    assert result.json()['remaining_requests'] is None
    assert result.json()['available_connections'] == 2
    store.db.projects.update_one({}, {'$set': {'owner_id': 'another-user'}})
    assert client.get(f'/api/projects/{project}/usage').status_code == 404
