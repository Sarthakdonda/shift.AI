import pytest


@pytest.mark.parametrize('origin', ['http://localhost:3000', 'http://localhost:3001'])
@pytest.mark.parametrize('path', ['/api/health', '/api/projects'])
def test_dashboard_preflight_and_reads(setup, origin, path):
    client, *_ = setup
    response = client.options(path, headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    assert response.headers['access-control-allow-credentials'] == 'true'
    response = client.get(path, headers={'Origin': origin})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin


def test_project_write_from_port_3001(setup):
    client, *_ = setup
    origin = 'http://localhost:3001'
    response = client.options('/api/projects', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 200
    response = client.post('/api/projects', headers={'Origin': origin}, json={
        'name': 'Alternate frontend port',
        'initial_problem': 'Verify that the frontend can create projects from port 3001.',
    })
    assert response.status_code == 201
    assert response.headers['access-control-allow-origin'] == origin


def test_validation_error_is_readable_from_port_3001(setup):
    client, *_ = setup
    response = client.post('/api/projects', headers={'Origin': 'http://localhost:3001'}, json={})
    assert response.status_code == 422
    assert response.headers['access-control-allow-origin'] == 'http://localhost:3001'


def test_unlisted_origins_remain_blocked(setup):
    client, *_ = setup
    origin = 'http://localhost:3001.evil.example'
    response = client.options('/api/projects', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
    response = client.post('/api/projects', headers={'Origin': origin}, json={})
    assert response.status_code == 403
