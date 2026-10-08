"""Per-application Atlas provisioning: isolation, idempotency and honest refusal."""
import re
import httpx
import pytest
from app.core.errors import AppError
from app.services import atlas_provisioning as atlas

CLUSTER = 'mongodb+srv://owner:ownerpass@appcluster.abcde.mongodb.net/?appName=APP'


@pytest.fixture(autouse=True)
def offline(setup, monkeypatch):
    """No test may reach Atlas: clear real credentials and the token cache."""
    for name in ('atlas_service_client_id', 'atlas_service_client_secret',
                 'atlas_public_key', 'atlas_private_key', 'atlas_project_id', 'atlas_cluster_name'):
        monkeypatch.setattr(setup[3], name, '')
    monkeypatch.setattr(setup[3], 'app_atlas_uri', '')
    monkeypatch.setitem(atlas._token, 'value', '')
    monkeypatch.setitem(atlas._token, 'expires', 0.0)


@pytest.fixture
def ready(setup, monkeypatch):
    """Fully configured provisioning with the Atlas API and driver faked out."""
    client, store, _, settings = setup
    monkeypatch.setattr(settings, 'app_atlas_uri', CLUSTER)
    monkeypatch.setattr(settings, 'app_atlas_database_prefix', 'shift_app_')
    monkeypatch.setattr(settings, 'atlas_public_key', 'public-key')
    monkeypatch.setattr(settings, 'atlas_private_key', 'private-key')
    monkeypatch.setattr(settings, 'atlas_project_id', '65f0000000000000000000aa')
    monkeypatch.setattr(settings, 'atlas_cluster_name', 'AppCluster')
    calls = []

    def fake_api(method, path, body=None):
        calls.append((method, path, body))
        if method == 'POST' and path.endswith('/databaseUsers'):
            return {'username': body['username']}
        return {}

    connected = []
    monkeypatch.setattr(atlas, 'api', fake_api)
    monkeypatch.setattr(atlas, 'initialise', lambda uri, database, indexes=(): connected.append((uri, database, list(indexes))))
    return store, calls, connected


def test_refuses_without_admin_api_credentials(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'app_atlas_uri', CLUSTER)
    assert atlas.configured() is False
    assert atlas.requirements() == ['ATLAS_SERVICE_CLIENT_ID or ATLAS_PUBLIC_KEY',
                                    'ATLAS_SERVICE_CLIENT_SECRET or ATLAS_PRIVATE_KEY',
                                    'ATLAS_PROJECT_ID', 'ATLAS_CLUSTER_NAME']
    with pytest.raises(AppError) as failure:
        atlas.provision(setup[1].db, 'app-1')
    assert failure.value.status == 503 and failure.value.code == 'atlas_configuration'
    # The powerful cluster credential is never handed out as a fallback.
    assert 'ownerpass' not in failure.value.message


def test_a_service_account_satisfies_the_credential_requirement(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'app_atlas_uri', CLUSTER)
    monkeypatch.setattr(setup[3], 'atlas_service_client_id', 'mdb_sa_id_test')
    monkeypatch.setattr(setup[3], 'atlas_service_client_secret', 'mdb_sa_sk_test')
    monkeypatch.setattr(setup[3], 'atlas_project_id', '65f0000000000000000000aa')
    monkeypatch.setattr(setup[3], 'atlas_cluster_name', 'AppCluster')
    assert atlas.requirements() == [] and atlas.configured() is True


def test_service_account_token_is_cached_and_sent_as_a_bearer(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'atlas_service_client_id', 'mdb_sa_id_test')
    monkeypatch.setattr(setup[3], 'atlas_service_client_secret', 'mdb_sa_sk_test')
    posts = []

    def fake_post(url, **kwargs):
        posts.append(url)
        return httpx.Response(200, json={'access_token': 'tok-123', 'expires_in': 3600},
                              request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', fake_post)
    assert atlas._auth_kwargs()['headers']['Authorization'] == 'Bearer tok-123'
    atlas._auth_kwargs()
    assert len(posts) == 1 and posts[0] == atlas.TOKEN_URL


def test_service_account_rejection_is_reported_without_the_secret(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'atlas_service_client_id', 'mdb_sa_id_test')
    monkeypatch.setattr(setup[3], 'atlas_service_client_secret', 'mdb_sa_sk_supersecret')
    monkeypatch.setattr(httpx, 'post', lambda url, **kwargs: httpx.Response(
        401, json={'error': 'invalid_client'}, request=httpx.Request('POST', url)))
    with pytest.raises(AppError) as failure:
        atlas._bearer()
    assert failure.value.code == 'atlas_provider'
    assert 'mdb_sa_sk_supersecret' not in failure.value.message


def test_rejects_a_connection_string_with_a_space(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'app_atlas_uri', CLUSTER.replace('@', ' @'))
    with pytest.raises(AppError) as failure:
        atlas._cluster_host()
    assert 'space' in failure.value.message and failure.value.code == 'atlas_configuration'


def test_provisioned_user_is_scoped_to_its_own_database(ready):
    store, calls, connected = ready
    result = atlas.provision(store.db, '0123456789abcdef01234567',
                             indexes=[('records', [('owner_id', 1)], False)])
    assert result['status'] == 'ready'
    assert result['database'] == 'shift_app_cdef01234567'
    assert result['username'] == 'app_cdef01234567'
    create = next(body for method, path, body in calls if method == 'POST' and path.endswith('/databaseUsers'))
    # readWrite on exactly one database, restricted to one cluster, no admin rights.
    assert create['roles'] == [{'databaseName': 'shift_app_cdef01234567', 'roleName': 'readWrite'}]
    assert create['scopes'] == [{'name': 'AppCluster', 'type': 'CLUSTER'}]
    assert create['databaseName'] == 'admin'
    assert len(create['password']) == 40
    # Requested indexes are created with the scoped credential, not the owner one.
    uri, database, indexes = connected[0]
    assert database == 'shift_app_cdef01234567' and indexes == [('records', [('owner_id', 1)], False)]
    assert uri.startswith('mongodb+srv://app_cdef01234567:') and '@appcluster.abcde.mongodb.net/' in uri
    assert 'owner:ownerpass' not in uri


def test_uri_is_encrypted_at_rest_and_never_public(ready):
    store, _, _ = ready
    atlas.provision(store.db, 'aaaaaaaaaaaaaaaaaaaaaaaa')
    row = store.db.application_databases.find_one({'_id': 'aaaaaaaaaaaaaaaaaaaaaaaa'})
    assert 'mongodb+srv' not in row['uri']
    assert atlas.uri_of(store.db, 'aaaaaaaaaaaaaaaaaaaaaaaa').startswith('mongodb+srv://app_')
    assert set(atlas.public(row)) == {'database', 'username', 'cluster', 'status', 'created_at', 'rotated_at'}


def test_provisioning_is_idempotent(ready):
    store, calls, _ = ready
    first = atlas.provision(store.db, 'bbbbbbbbbbbbbbbbbbbbbbbb')
    creates = len([1 for method, path, _ in calls if method == 'POST' and path.endswith('/databaseUsers')])
    second = atlas.provision(store.db, 'bbbbbbbbbbbbbbbbbbbbbbbb')
    assert second == first
    assert len([1 for method, path, _ in calls if method == 'POST' and path.endswith('/databaseUsers')]) == creates


def test_rotation_replaces_the_password_and_keeps_the_database(ready):
    store, calls, _ = ready
    atlas.provision(store.db, 'cccccccccccccccccccccccc')
    before = atlas.uri_of(store.db, 'cccccccccccccccccccccccc')
    rotated = atlas.rotate(store.db, 'cccccccccccccccccccccccc')
    after = atlas.uri_of(store.db, 'cccccccccccccccccccccccc')
    assert rotated['database'] == 'shift_app_cccccccccccc' and rotated['username'] == 'app_cccccccccccc'
    assert before != after
    assert any(method == 'PATCH' for method, _, _ in calls)


def test_deprovision_removes_the_credential(ready):
    store, calls, _ = ready
    atlas.provision(store.db, 'dddddddddddddddddddddddd')
    atlas.deprovision(store.db, 'dddddddddddddddddddddddd')
    assert any(method == 'DELETE' and path.endswith('/databaseUsers/admin/app_dddddddddddd') for method, path, _ in calls)
    row = store.db.application_databases.find_one({'_id': 'dddddddddddddddddddddddd'})
    assert row['status'] == 'removed' and 'uri' not in row
    with pytest.raises(AppError):
        atlas.uri_of(store.db, 'dddddddddddddddddddddddd')


def test_generated_identifiers_are_atlas_safe(ready):
    for value in ('0123456789abcdef01234567', 'Weird-ID!!', '', 'a' * 60):
        database, username = atlas.identifiers(value)
        assert re.fullmatch(r'[a-z0-9_]{6,38}', database), database
        assert re.fullmatch(r'[a-z0-9_]{6,38}', username), username


@pytest.mark.parametrize('status, expected', [(401, 'atlas_provider'), (403, 'atlas_provider'),
                                             (404, 'atlas_provider'), (500, 'atlas_provider')])
def test_provider_failures_are_reported_without_leaking_keys(setup, monkeypatch, status, expected):
    monkeypatch.setattr(setup[3], 'atlas_public_key', 'public-key')
    monkeypatch.setattr(setup[3], 'atlas_private_key', 'private-key-secret')
    monkeypatch.setattr(setup[3], 'atlas_project_id', 'p1')
    monkeypatch.setattr(setup[3], 'atlas_cluster_name', 'AppCluster')

    def fake_request(*args, **kwargs):
        return httpx.Response(status, json={'detail': 'atlas said no'}, request=httpx.Request('POST', 'https://x'))

    monkeypatch.setattr(httpx, 'request', fake_request)
    with pytest.raises(AppError) as failure:
        atlas.api('POST', '/groups/p1/databaseUsers', {'username': 'u'})
    assert failure.value.code == expected
    assert 'private-key-secret' not in failure.value.message



def fake_access_api(monkeypatch, existing):
    posts = []

    def fake_api(method, path, body=None):
        if method == 'GET' and '/accessList' in path:
            return {'results': [{'cidrBlock': c} if '/' in c else {'ipAddress': c} for c in existing]}
        if method == 'POST' and path.endswith('/accessList'):
            posts.append(body)
            existing.extend(item['cidrBlock'] for item in body)
            return {}
        return {}

    monkeypatch.setattr(atlas, 'api', fake_api)
    return posts


def test_render_ranges_are_added_once_and_existing_entries_are_preserved(ready, monkeypatch):
    existing = ['136.233.130.145', '74.220.52.0/24']
    posts = fake_access_api(monkeypatch, existing)
    result = atlas.ensure_access(['74.220.52.0/24', '74.220.60.0/24'], 'shift app abc')
    assert result == {'added': ['74.220.60.0/24'], 'present': ['74.220.52.0/24']}
    assert posts == [[{'cidrBlock': '74.220.60.0/24', 'comment': 'shift app abc'}]]
    # A second run is a no-op: nothing duplicated, nothing removed.
    assert atlas.ensure_access(['74.220.52.0/24', '74.220.60.0/24'], 'shift app abc')['added'] == []
    assert len(posts) == 1 and '136.233.130.145' in existing


def test_ranges_covered_by_a_broader_entry_are_not_added(ready, monkeypatch):
    posts = fake_access_api(monkeypatch, ['74.220.0.0/16'])
    assert atlas.ensure_access(['74.220.60.0/24'], 'x')['added'] == []
    assert posts == []


@pytest.mark.parametrize('entry', ['0.0.0.0/0', '10.0.0.0/8', '::/0'])
def test_open_internet_ranges_are_refused(ready, monkeypatch, entry):
    posts = fake_access_api(monkeypatch, [])
    with pytest.raises(AppError) as failure:
        atlas.ensure_access([entry], 'x')
    assert failure.value.code == 'atlas_network' and posts == []
