"""GitHub source delivery: auth, idempotent repositories, and secret refusal."""
import base64
import httpx
import pytest
from app.core.errors import AppError
from app.services import github_app as gh

PEM = None


def key_material():
    """A throwaway RSA key generated in-process; never a real credential."""
    global PEM
    if PEM is None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        PEM = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()).decode()
    return PEM


class Recorder:
    """Scripted GitHub transport: (method, path) -> (status, body)."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, **kwargs):
        path = url.replace(gh.API, '')
        self.calls.append((method, path, kwargs.get('json'),
                           kwargs.get('headers', {}).get('Authorization', '')))
        for (want_method, want_path), (status, body) in self.routes.items():
            if method == want_method and path == want_path:
                return httpx.Response(status, json=body, request=httpx.Request(method, url))
        return httpx.Response(404, json={'message': 'Not Found'}, request=httpx.Request(method, url))


@pytest.fixture
def app_env(setup, monkeypatch):
    settings = setup[3]
    monkeypatch.setattr(settings, 'github_app_id', '5076803')
    monkeypatch.setattr(settings, 'github_app_private_key', key_material())
    monkeypatch.setattr(settings, 'github_app_private_key_path', '')
    monkeypatch.setattr(settings, 'github_installation_id', '165001444')
    monkeypatch.setattr(settings, 'github_owner', 'octoperson')
    monkeypatch.setattr(settings, 'github_pat', '')
    monkeypatch.setitem(gh._token, 'value', '')
    monkeypatch.setitem(gh._token, 'expires', 0.0)
    return settings


def install(owner_type='User'):
    return {('GET', '/app/installations/165001444'): (200, {
        'account': {'login': 'octoperson', 'type': owner_type},
        'permissions': {'contents': 'write', 'administration': 'write'},
        'repository_selection': 'all'})}


def token_route():
    return {('POST', '/app/installations/165001444/access_tokens'): (200, {'token': 'ghs_installation'})}


def test_missing_configuration_is_reported_precisely(setup, monkeypatch):
    for name in ('github_app_id', 'github_app_private_key', 'github_app_private_key_path',
                 'github_installation_id'):
        monkeypatch.setattr(setup[3], name, '')
    assert gh.configured() is False
    assert gh.requirements() == ['GITHUB_APP_ID',
                                 'GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH',
                                 'GITHUB_INSTALLATION_ID']
    with pytest.raises(AppError) as failure:
        gh.require()
    assert failure.value.code == 'github_configuration'


def test_app_jwt_is_signed_rs256_with_the_app_as_issuer(app_env):
    import json
    token = gh.app_jwt()
    header, claims, signature = token.split('.')
    pad = lambda s: s + '=' * (-len(s) % 4)
    assert json.loads(base64.urlsafe_b64decode(pad(header)))['alg'] == 'RS256'
    body = json.loads(base64.urlsafe_b64decode(pad(claims)))
    assert body['iss'] == '5076803' and body['exp'] - body['iat'] == 540
    assert signature


def test_installation_token_is_cached(app_env, monkeypatch):
    recorder = Recorder({**install(), **token_route()})
    monkeypatch.setattr(httpx, 'request', recorder)
    assert gh.installation_token() == 'ghs_installation'
    assert gh.installation_token() == 'ghs_installation'
    mints = [c for c in recorder.calls if c[1].endswith('/access_tokens')]
    assert len(mints) == 1


def test_existing_repository_is_reused_not_recreated(app_env, monkeypatch):
    recorder = Recorder({**install(), **token_route(), ('GET', '/repos/octoperson/shift-app-1'): (200, {
        'full_name': 'octoperson/shift-app-1', 'default_branch': 'main',
        'html_url': 'https://github.com/octoperson/shift-app-1'})})
    monkeypatch.setattr(httpx, 'request', recorder)
    result = gh.ensure_repository('shift-app-1')
    assert result['created'] is False and result['full_name'] == 'octoperson/shift-app-1'
    assert not [c for c in recorder.calls if c[0] == 'POST' and 'repos' in c[1] and 'access_tokens' not in c[1]]


def test_personal_account_without_user_authorization_explains_the_real_limitation(app_env, monkeypatch):
    monkeypatch.setattr(httpx, 'request', Recorder({**install('User'), **token_route()}))
    with pytest.raises(AppError) as failure:
        gh.ensure_repository('shift-app-2')
    assert failure.value.code == 'github_authorization'
    assert 'Connect GitHub' in failure.value.message and 'GITHUB_PAT' in failure.value.message


def test_organization_installation_creates_through_the_app(app_env, monkeypatch):
    recorder = Recorder({**install('Organization'), **token_route(),
                         ('POST', '/orgs/octoperson/repos'): (201, {
                             'full_name': 'octoperson/shift-app-3', 'default_branch': 'main',
                             'html_url': 'https://github.com/octoperson/shift-app-3'})})
    monkeypatch.setattr(httpx, 'request', recorder)
    result = gh.ensure_repository('shift-app-3')
    assert result['created'] is True
    body = next(c[2] for c in recorder.calls if c[1] == '/orgs/octoperson/repos')
    assert body['private'] is True and body['auto_init'] is False


@pytest.mark.parametrize('credential, source', [('ghu_userAccessToken0001', 'user'), ('ghp_useronly', 'pat')])
def test_personal_account_creates_with_a_user_credential(app_env, monkeypatch, credential, source):
    if source == 'pat':
        monkeypatch.setattr(app_env, 'github_pat', credential)
    recorder = Recorder({**install('User'), **token_route(), ('GET', '/user'): (200, {'login': 'OctoPerson'}),
                         ('POST', '/user/repos'): (201, {
                             'full_name': 'octoperson/shift-app-4', 'default_branch': 'main', 'private': True,
                             'html_url': 'https://github.com/octoperson/shift-app-4'})})
    monkeypatch.setattr(httpx, 'request', recorder)
    result = gh.ensure_repository('shift-app-4', user_access_token=credential if source == 'user' else None)
    assert result['created'] is True and result['private'] is True
    auth = next(c[3] for c in recorder.calls if c[1] == '/user/repos')
    assert auth == 'Bearer ' + credential
    assert next(c[2] for c in recorder.calls if c[1] == '/user/repos')['private'] is True


def test_repository_is_never_created_under_a_different_user(app_env, monkeypatch):
    recorder = Recorder({**install('User'), **token_route(), ('GET', '/user'): (200, {'login': 'someone-else'})})
    monkeypatch.setattr(httpx, 'request', recorder)
    with pytest.raises(AppError) as failure:
        gh.ensure_repository('shift-app-5', user_access_token='ghu_otherUsersToken0001')
    assert failure.value.code == 'github_authorization' and 'someone-else' in failure.value.message
    assert not [c for c in recorder.calls if c[1] == '/user/repos']


@pytest.mark.parametrize('name, data', [
    ('.env', 'ADMIN_PASSWORD=hunter2'),
    ('deploy/key.pem', '-----BEGIN RSA PRIVATE KEY-----\nx\n-----END RSA PRIVATE KEY-----'),
    ('config.py', 'URI = "mongodb+srv://u:p@cluster.mongodb.net/db"'),
    ('ci.yml', 'token: ghp_abcdefghijklmnopqrstuvwxyz'),
])
def test_credential_shaped_files_are_never_committed(app_env, monkeypatch, name, data):
    monkeypatch.setattr(httpx, 'request', Recorder({**install(), **token_route()}))
    with pytest.raises(AppError) as failure:
        gh.push_source('octoperson/shift-app-1', {'server.py': 'print(1)', name: data})
    assert failure.value.code == 'github_secret_blocked' and name in failure.value.message


def test_push_commits_a_full_snapshot_and_moves_the_branch(app_env, monkeypatch):
    base = '/repos/octoperson/shift-app-1'
    recorder = Recorder({**install(), **token_route(),
        ('GET', base): (200, {'default_branch': 'main'}),
        ('GET', base + '/git/ref/heads/main'): (200, {'object': {'sha': 'parent-sha'}}),
        ('GET', base + '/git/commits/parent-sha'): (200, {'tree': {'sha': 'base-tree'}}),
        ('POST', base + '/git/trees'): (201, {'sha': 'tree-sha'}),
        ('POST', base + '/git/commits'): (201, {'sha': 'commit-sha'}),
        ('PATCH', base + '/git/refs/heads/main'): (200, {'object': {'sha': 'commit-sha'}})})
    monkeypatch.setattr(httpx, 'request', recorder)
    result = gh.push_source('octoperson/shift-app-1',
                            {'server.py': 'print(1)', 'public/index.html': '<p>hi</p>'})
    assert result == {'commit': 'commit-sha', 'branch': 'main', 'files': 2, 'changed': True}
    tree = next(c[2] for c in recorder.calls if c[1] == base + '/git/trees')
    assert 'base_tree' not in tree
    assert {entry['path'] for entry in tree['tree']} == {'server.py', 'public/index.html'}
    assert all(entry['mode'] == '100644' and 'content' in entry for entry in tree['tree'])
    commit = next(c[2] for c in recorder.calls if c[1] == base + '/git/commits')
    assert commit['parents'] == ['parent-sha']


def test_identical_retry_creates_no_new_commit(app_env, monkeypatch):
    base = '/repos/octoperson/shift-app-1'
    recorder = Recorder({**install(), **token_route(),
        ('GET', base): (200, {'default_branch': 'main'}),
        ('GET', base + '/git/ref/heads/main'): (200, {'object': {'sha': 'parent-sha'}}),
        ('GET', base + '/git/commits/parent-sha'): (200, {'tree': {'sha': 'same-tree'}}),
        ('POST', base + '/git/trees'): (201, {'sha': 'same-tree'})})
    monkeypatch.setattr(httpx, 'request', recorder)
    result = gh.push_source('octoperson/shift-app-1', {'server.py': 'print(1)'})
    assert result == {'commit': 'parent-sha', 'branch': 'main', 'files': 1, 'changed': False}
    assert not [c for c in recorder.calls if c[1] == base + '/git/commits' and c[0] == 'POST']


def test_first_push_initializes_an_empty_repository(app_env, monkeypatch):
    base = '/repos/octoperson/shift-app-1'
    state = {'initialized': False}
    routes = {**install(), **token_route(),
              ('GET', base): (200, {'default_branch': 'main'}),
              ('GET', base + '/git/commits/init-sha'): (200, {'tree': {'sha': 'init-tree'}}),
              ('POST', base + '/git/trees'): (201, {'sha': 'tree-sha'}),
              ('POST', base + '/git/commits'): (201, {'sha': 'commit-sha'}),
              ('PATCH', base + '/git/refs/heads/main'): (200, {'object': {'sha': 'commit-sha'}})}
    recorder = Recorder(routes)

    def transport(method, url, **kwargs):
        path = url.replace(gh.API, '')
        if path == base + '/git/ref/heads/main':
            recorder.calls.append((method, path, None, ''))
            if state['initialized']:
                return httpx.Response(200, json={'object': {'sha': 'init-sha'}}, request=httpx.Request(method, url))
            return httpx.Response(409, json={'message': 'Git Repository is empty.'}, request=httpx.Request(method, url))
        if method == 'PUT' and path == base + '/contents/.gitignore':
            state['initialized'] = True
            recorder.calls.append((method, path, kwargs.get('json'), ''))
            return httpx.Response(201, json={'commit': {'sha': 'init-sha'}}, request=httpx.Request(method, url))
        return recorder(method, url, **kwargs)

    monkeypatch.setattr(httpx, 'request', transport)
    result = gh.push_source('octoperson/shift-app-1', {'server.py': 'print(1)', '.gitignore': '.env\n'})
    assert result['commit'] == 'commit-sha' and result['changed'] is True
    assert any(c[0] == 'PUT' and c[1].endswith('/contents/.gitignore') for c in recorder.calls)
    commit = next(c[2] for c in recorder.calls if c[1] == base + '/git/commits')
    assert commit['parents'] == ['init-sha']


def test_repository_names_are_deterministic_and_valid():
    import re
    first = gh.repository_name('0123456789abcdef01234567', 'Inventory Management!')
    assert first == gh.repository_name('0123456789abcdef01234567', 'Inventory Management!')
    assert first != gh.repository_name('ffffffffffffffffffffffff', 'Inventory Management!')
    for app_id, name in (('abc', ''), ('', 'x' * 80), ('ZZ--99', 'Ünïcødé  app')):
        value = gh.repository_name(app_id, name)
        assert re.fullmatch(r'[A-Za-z0-9-]{1,90}', value), value


@pytest.mark.parametrize('text, hidden', [
    ('token ghp_abcdefghijklmnopqrstuvwxyz', 'ghp_abcdefghijklmnopqrstuvwxyz'),
    ('uri mongodb+srv://u:p@c.mongodb.net/d', 'mongodb+srv://u:p@c.mongodb.net/d'),
    ('sa mdb_sa_sk_AAAAAAAAAAAA', 'mdb_sa_sk_AAAAAAAAAAAA'),
    ('render rnd_AAAAAAAAAAAAAAAAAAAAAAAA', 'rnd_AAAAAAAAAAAAAAAAAAAAAAAA'),
])
def test_log_redaction_removes_credentials(text, hidden):
    assert hidden not in gh.redact(text) and '[redacted]' in gh.redact(text)


def test_rate_limit_is_surfaced_as_a_retryable_error(app_env, monkeypatch):
    monkeypatch.setattr(httpx, 'request', lambda method, url, **kwargs: httpx.Response(
        403, json={'message': 'API rate limit exceeded'}, request=httpx.Request(method, url)))
    with pytest.raises(AppError) as failure:
        gh.installation()
    assert failure.value.status == 429 and failure.value.code == 'github_rate_limited'



def test_user_token_is_exchanged_encrypted_and_refreshed(app_env, setup, monkeypatch):
    store = setup[1]
    monkeypatch.setattr(app_env, 'github_client_id', 'Iv1.testclient')
    monkeypatch.setattr(app_env, 'github_client_secret', 'client-secret-value')
    grants = []

    def token_post(url, data=None, **kwargs):
        grants.append(dict(data))
        if data.get('grant_type') == 'refresh_token':
            body = {'access_token': 'ghu_refreshedAccessToken01', 'expires_in': 28800,
                    'refresh_token': 'ghr_secondRefreshToken0001', 'refresh_token_expires_in': 15897600}
        else:
            body = {'access_token': 'ghu_firstAccessToken00001', 'expires_in': 28800,
                    'refresh_token': 'ghr_firstRefreshToken00001', 'refresh_token_expires_in': 15897600}
        return httpx.Response(200, json=body, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', token_post)
    monkeypatch.setattr(httpx, 'request', Recorder({('GET', '/user'): (200, {'login': 'octoperson'})}))
    login = gh.exchange_code(store.db, 'email:abc', 'code-123', 'verifier-xyz', 'http://localhost:8000/cb')
    assert login == 'octoperson'
    assert grants[0]['code_verifier'] == 'verifier-xyz' and grants[0]['client_secret'] == 'client-secret-value'
    row = store.db.github_user_tokens.find_one({'_id': 'email:abc'})
    assert 'ghu_' not in row['access'] and 'ghr_' not in row['refresh']
    assert gh.user_token(store.db, 'email:abc') == 'ghu_firstAccessToken00001'
    assert gh.user_link(store.db, 'email:abc') == {'connected': True, 'login': 'octoperson'}
    store.db.github_user_tokens.update_one({'_id': 'email:abc'}, {'$set': {'access_expires': 0}})
    assert gh.user_token(store.db, 'email:abc') == 'ghu_refreshedAccessToken01'
    assert grants[-1]['grant_type'] == 'refresh_token' and grants[-1]['refresh_token'] == 'ghr_firstRefreshToken00001'
    store.db.github_user_tokens.update_one({'_id': 'email:abc'}, {'$set': {'access_expires': 0, 'refresh_expires': 0}})
    assert gh.user_token(store.db, 'email:abc') is None
    assert gh.user_token(store.db, 'email:nobody') is None


def test_rejected_code_exchange_is_reported_without_secrets(app_env, setup, monkeypatch):
    monkeypatch.setattr(app_env, 'github_client_id', 'Iv1.testclient')
    monkeypatch.setattr(app_env, 'github_client_secret', 'client-secret-value')
    monkeypatch.setattr(httpx, 'post', lambda url, **kwargs: httpx.Response(
        200, json={'error': 'bad_verification_code'}, request=httpx.Request('POST', url)))
    with pytest.raises(AppError) as failure:
        gh.exchange_code(setup[1].db, 'email:abc', 'code', 'verifier', 'http://localhost:8000/cb')
    assert failure.value.code == 'github_authorization' and 'client-secret-value' not in failure.value.message
    url = gh.authorize_url('state-1', 'challenge-1', 'http://localhost:8000/cb')
    assert 'code_challenge_method=S256' in url and 'client_secret' not in url
