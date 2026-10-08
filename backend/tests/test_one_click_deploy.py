"""One-click deployment orchestration with every provider mocked. Nothing reaches the network."""
import json
from urllib.parse import parse_qs, urlsplit
import httpx
import pytest
from bson import ObjectId
from app.api import deployments
from app.core.errors import AppError
from app.repositories.store import now
from app.services import atlas_provisioning as atlas, github_app as gh, launch_service, render_provisioning as render, vercel_provisioning as vercel
from app.services.application_generator import compile_application
from tests.builder_fixtures import specification

CLUSTER = 'mongodb+srv://owner:ownerpass@appcluster.abcde.mongodb.net/?appName=APP'


class Providers:
    def __init__(self):
        self.calls, self.fail, self.env = [], {}, {}
        self.access = ['136.233.130.145/32']
        self.service, self.vercel_errors, self.frontend, self.pushed = None, set(), [], {}

    def hit(self, name, detail=''):
        self.calls.append((name, str(detail)))
        if self.fail.get(name):
            self.fail[name] -= 1
            raise AppError(name + ' failed in this test.', 502, 'provider_test')

    def count(self, name, suffix=''):
        return sum(1 for n, d in self.calls if n == name and d.endswith(suffix))


def add_build(store, project, description=None):
    bid = ObjectId()
    spec = specification()
    if description:
        spec['description'] = description
    files, manifest, _ = compile_application(spec, str(bid))
    store.db.application_builds.insert_one({'_id': bid, 'project_id': project, 'request_id': project + ':' + str(bid),
                                            'status': 'ready', 'spec': spec,
                                            'files': files, 'manifest': manifest, 'created_at': now()})
    return str(bid)


@pytest.fixture
def env(setup, project, monkeypatch):
    client, store, _, settings = setup
    monkeypatch.setattr(deployments, 'get_store', lambda: store)
    for name, value in {'app_atlas_uri': CLUSTER, 'atlas_public_key': 'pk', 'atlas_private_key': 'sk', 'atlas_project_id': 'p1',
                        'atlas_cluster_name': 'AppCluster', 'atlas_service_client_id': '', 'atlas_service_client_secret': ''}.items():
        monkeypatch.setattr(settings, name, value)
    p = Providers()

    def atlas_api(method, path, body=None):
        p.hit('atlas.' + method, path)
        if method == 'POST' and path.endswith('/databaseUsers'):
            return {'username': body['username']}
        if method == 'GET' and '/accessList' in path:
            return {'results': [{'cidrBlock': c} for c in p.access]}
        if method == 'POST' and path.endswith('/accessList'):
            p.access += [item['cidrBlock'] for item in body]
        return {}

    monkeypatch.setattr(atlas, 'api', atlas_api)
    monkeypatch.setattr(atlas, 'initialise', lambda uri, database, indexes=(): p.hit('atlas.initialise', database))
    monkeypatch.setattr(gh, 'requirements', lambda: [])
    monkeypatch.setattr(gh, 'user_token', lambda db, account: 'ghu_testUserToken0001')
    repos = set()

    def ensure_repository(name, description='', user_access_token=None):
        p.hit('github.ensure', name)
        created = name not in repos
        repos.add(name)
        return {'full_name': 'octo/' + name, 'html_url': 'https://github.com/octo/' + name, 'default_branch': 'main',
                'private': True, 'created': created}

    def push_source(full_name, files, message=''):
        p.hit('github.push', full_name)
        p.pushed = files
        return {'commit': 'c0ffee' + str(p.count('github.push')), 'branch': 'main', 'files': len(files), 'changed': True}

    monkeypatch.setattr(gh, 'ensure_repository', ensure_repository)
    monkeypatch.setattr(gh, 'push_source', push_source)

    def create_service(name, repo, branch, variables, manifest):
        p.hit('render.create', repo)
        p.env = dict(variables)
        p.service = {'id': 'srv-test12345', 'name': name, 'serviceDetails': {'url': 'https://' + name + '.onrender.com'}}
        return p.service, 'dep-initial'

    def set_env(service_id, variables):
        p.hit('render.env', service_id)
        p.env.update(variables)

    def trigger_deploy(service_id, commit):
        p.hit('render.deploy', commit)
        return 'dep-' + commit

    monkeypatch.setattr(render, 'requirements', lambda: [])
    monkeypatch.setattr(render, 'find_service', lambda name: p.hit('render.find', name) or p.service)
    monkeypatch.setattr(render, 'get_service', lambda sid, name: p.hit('render.get', sid) or p.service)
    monkeypatch.setattr(render, 'create_service', create_service)
    monkeypatch.setattr(render, 'set_env', set_env)
    monkeypatch.setattr(render, 'trigger_deploy', trigger_deploy)
    monkeypatch.setattr(render, 'deploy_status', lambda sid, did: (p.hit('render.status', did) or 'live', None))
    monkeypatch.setattr(render, 'outbound_ips', lambda sid: p.hit('render.ips', sid) or ['74.220.52.0/24', '74.220.60.0/24'])

    def create_deployment(name, files, meta):
        p.hit('vercel.deploy', name)
        p.frontend = files
        return 'dpl_' + str(p.count('vercel.deploy'))

    monkeypatch.setattr(vercel, 'requirements', lambda: [])
    monkeypatch.setattr(vercel, 'ensure_project', lambda name: p.hit('vercel.project', name) or {'name': name})
    monkeypatch.setattr(vercel, 'create_deployment', create_deployment)
    monkeypatch.setattr(vercel, 'deployment_state', lambda did: 'ERROR' if did in p.vercel_errors else 'READY')
    monkeypatch.setattr(vercel, 'production_url', lambda name: 'https://' + name + '.vercel.app')

    def verify(frontend, build_id, spec, email, password):
        p.hit('verify', frontend)
        p.admin = {'email': email, 'password': password}
        return {'checks': ['frontend release identity', 'frontend-to-backend health', 'sign-in', 'create and read', 'update', 'delete'], 'module': 'companies'}

    monkeypatch.setattr(launch_service, 'verify_live', verify)
    monkeypatch.setattr(launch_service, 'sleep', lambda seconds: None)
    p.build_id = add_build(store, project)
    monkeypatch.setattr(httpx, 'get', lambda url, **kwargs: httpx.Response(
        200, json={'status': 'ok', 'build_id': p.build_id, 'database': 'mongodb'}, request=httpx.Request('GET', url)))
    return client, store, p, project


def deploy(client, project, build_id):
    return client.post(f'/api/projects/{project}/deploy', json={'build_id': build_id})


def launch(client, project, lid):
    return client.get(f'/api/projects/{project}/deploy/{lid}').json()


def test_one_click_deploy_goes_live_with_isolated_secrets(env):
    client, store, p, project = env
    response = deploy(client, project, p.build_id)
    assert response.status_code == 202, response.text
    result = launch(client, project, response.json()['id'])
    assert result['status'] == 'live', result.get('error')
    assert [s['status'] for s in result['stages']] == ['done'] * len(launch_service.STAGES)
    assert result['frontend_url'].endswith('.vercel.app') and result['backend_url'].endswith('.onrender.com')
    # The backend alone receives a URI scoped to its own database user.
    assert p.env['DATABASE_BACKEND'] == 'mongodb' and p.env['MONGODB_URI'].startswith('mongodb+srv://app_')
    assert 'owner:ownerpass' not in p.env['MONGODB_URI'] and p.env['MONGODB_DATABASE'].startswith('shift_app_')
    stored = json.dumps(store.db.application_launches.find_one({'project_id': project}), default=str)
    for text in (stored, json.dumps(result), client.get(f'/api/projects/{project}/deploy').text, json.dumps(p.frontend)):
        assert 'mongodb+srv' not in text and p.env['ADMIN_PASSWORD'] not in text
    proxy = next(f['data'] for f in p.frontend if f['file'] == 'api/proxy.mjs')
    assert json.dumps(result['backend_url']) in proxy
    assert '.env' not in p.pushed and 'deploy.json' in p.pushed
    assert '74.220.60.0/24' in p.access and '0.0.0.0/0' not in p.access and '136.233.130.145/32' in p.access
    assert client.post(f'/api/projects/{project}/deploy/credentials').json() == p.admin
    site = client.get(f'/api/projects/{project}/deploy').json()['site']
    assert site['live']['build_id'] == p.build_id and 'admin_password' not in site


def test_retry_after_backend_failure_reuses_repository_and_database(env):
    client, _, p, project = env
    p.fail['render.create'] = 1
    lid = deploy(client, project, p.build_id).json()['id']
    failed = launch(client, project, lid)
    assert failed['status'] == 'failed' and failed['error']['stage'] == 'backend'
    assert [s['status'] for s in failed['stages'][:4]] == ['done', 'done', 'done', 'failed']
    assert client.post(f'/api/projects/{project}/deploy/{lid}/retry').status_code == 202
    assert launch(client, project, lid)['status'] == 'live'
    assert p.count('github.ensure') == 1 and p.count('github.push') == 1
    assert p.count('atlas.POST', '/databaseUsers') == 1 and p.count('render.create') == 2


def test_retry_after_frontend_failure_keeps_backend_and_database(env):
    client, _, p, project = env
    p.vercel_errors.add('dpl_1')
    lid = deploy(client, project, p.build_id).json()['id']
    assert launch(client, project, lid)['error']['stage'] == 'frontend'
    assert client.post(f'/api/projects/{project}/deploy/{lid}/retry').status_code == 202
    assert launch(client, project, lid)['status'] == 'live'
    assert p.count('vercel.deploy') == 2 and p.count('render.create') == 1 and p.count('render.deploy') == 0
    assert p.count('atlas.POST', '/databaseUsers') == 1 and p.count('github.push') == 1


def test_redeploying_a_new_version_keeps_the_same_resources(env):
    client, store, p, project = env
    assert launch(client, project, deploy(client, project, p.build_id).json()['id'])['status'] == 'live'
    second = add_build(store, project, 'Manage companies, candidates and interviews.')
    p.build_id = second
    result = launch(client, project, deploy(client, project, second).json()['id'])
    assert result['status'] == 'live', result.get('error')
    assert p.count('render.create') == 1 and p.count('render.deploy') == 1 and p.count('render.env') == 1
    assert p.count('atlas.POST', '/databaseUsers') == 1 and p.count('github.push') == 2
    site = client.get(f'/api/projects/{project}/deploy').json()['site']
    assert site['live']['build_id'] == second and len(client.get(f'/api/projects/{project}/deploy').json()['launches']) == 2


def test_concurrent_deployments_are_rejected(env):
    client, store, p, project = env
    launch_service.start(store, store.project(project, 'local-workspace', 'admin'), {'id': 'local-workspace', 'email': ''}, p.build_id)
    second = deploy(client, project, p.build_id)
    assert second.status_code == 409 and second.json()['code'] == 'deployment_active'


def test_unvalidated_builds_and_missing_configuration_are_refused(env, monkeypatch):
    client, store, p, project = env
    store.db.application_builds.update_one({'_id': ObjectId(p.build_id)}, {'$set': {'status': 'validation_required'}})
    refused = deploy(client, project, p.build_id)
    assert refused.status_code == 409 and refused.json()['code'] == 'deployment_validation'
    monkeypatch.setattr(render, 'requirements', lambda: ['RENDER_API_KEY'])
    missing = deploy(client, project, p.build_id)
    assert missing.status_code == 503 and 'RENDER_API_KEY' in missing.json()['detail']
    assert store.db.application_launches.count_documents({}) == 0


def test_viewers_watch_but_cannot_deploy_and_strangers_see_nothing(env):
    client, store, p, project = env
    workspace = store.db.workspaces.insert_one({'name': 'Team', 'owner_id': 'someone-else'}).inserted_id
    store.db.memberships.insert_one({'workspace_id': str(workspace), 'user_id': 'local-workspace', 'role': 'viewer'})
    store.db.projects.update_one({'_id': ObjectId(project)}, {'$set': {'workspace_id': str(workspace)}})
    assert client.get(f'/api/projects/{project}/deploy').json()['can_deploy'] is False
    assert deploy(client, project, p.build_id).status_code == 403
    assert client.post(f'/api/projects/{project}/deploy/credentials').status_code == 403
    store.db.projects.update_one({'_id': ObjectId(project)}, {'$set': {'workspace_id': None, 'owner_id': 'someone-else'}})
    assert client.get(f'/api/projects/{project}/deploy').status_code == 404
    assert deploy(client, project, p.build_id).status_code == 404


def test_hourly_deployment_limit(env):
    client, store, p, project = env
    store.db.application_launches.insert_many([{'project_id': 'x', 'actor': 'local-workspace', 'created_at': now(), 'status': 'failed'} for _ in range(10)])
    limited = deploy(client, project, p.build_id)
    assert limited.status_code == 429 and limited.json()['code'] == 'deployment_rate_limited'


def test_verification_failure_is_reported_at_its_stage(env, monkeypatch):
    client, _, p, project = env

    def broken(*args):
        raise AppError('Signing in through the frontend failed (HTTP 401).', 502, 'verification_failed')

    monkeypatch.setattr(launch_service, 'verify_live', broken)
    result = launch(client, project, deploy(client, project, p.build_id).json()['id'])
    assert result['status'] == 'failed' and result['error'] == {
        'stage': 'verification', 'code': 'verification_failed', 'message': 'Signing in through the frontend failed (HTTP 401).'}


def test_github_authorization_state_is_single_use_and_account_bound(env, monkeypatch):
    client, store, _, project = env
    settings = __import__('app.core.config', fromlist=['get_settings']).get_settings()
    monkeypatch.setattr(settings, 'github_client_id', 'Iv1.testclient')
    monkeypatch.setattr(settings, 'github_client_secret', 'client-secret-value')
    exchanged = []
    monkeypatch.setattr(gh, 'exchange_code', lambda db, account, code, verifier, redirect: exchanged.append((account, code, redirect)) or 'octo')
    url = client.get('/api/deploy/github/connect', params={'project_id': project}).json()['url']
    state = parse_qs(urlsplit(url).query)['state'][0]
    assert 'client-secret-value' not in url
    first = client.get('/api/deploy/github/callback', params={'code': 'abc', 'state': state}, follow_redirects=False)
    assert first.status_code == 303 and first.headers['location'].endswith('/project/' + project + '/application?github=connected')
    replay = client.get('/api/deploy/github/callback', params={'code': 'abc', 'state': state}, follow_redirects=False)
    assert replay.headers['location'].endswith('?github=failed') and len(exchanged) == 1
    forged = client.get('/api/deploy/github/callback', params={'code': 'abc', 'state': 'not-issued'}, follow_redirects=False)
    assert forged.headers['location'].endswith('?github=failed')
