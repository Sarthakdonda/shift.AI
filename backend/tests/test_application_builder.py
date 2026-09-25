import copy
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
from bson import ObjectId
from pydantic import ValidationError
from app.api import applications
from app.core.errors import AppError
from app.models.application import ApplicationSpec
from app.services import application_runner, billing_service, deployment_service
from app.services.application_generator import compile_application, compatibility, digest
from app.services.application_service import save_spec
from app.services.url_service import public_address, TextExtractor


from tests.builder_fixtures import specification


def draft(setup, pid):
    _, store, _, _ = setup
    store.update(pid, status='BLUEPRINT_READY', analysis_ready=True)
    store.save_blueprint(pid, {'review_gate': 'passed', 'requirements': ['Manage company and candidate information']})
    return save_spec(store, store.project(pid, 'local-workspace'), specification(), 'local-workspace')


def test_approval_is_version_and_context_specific(setup, project):
    client, store, *_ = setup
    draft(setup, project)
    body = {'version': 1, 'request_id': 'request-one'}
    assert client.post(f'/api/projects/{project}/application/build', json=body).status_code == 409
    assert client.post(f'/api/projects/{project}/application/approve', json={'version': 1}).status_code == 200
    changed = specification(); changed['description'] = 'Changed application scope.'
    assert client.post(f'/api/projects/{project}/application/spec', json={'base_version': 1, 'spec': changed}).status_code == 200
    assert client.post(f'/api/projects/{project}/application/build', json=body).status_code == 409
    assert client.post(f'/api/projects/{project}/application/approve', json={'version': 2}).status_code == 200
    store.invalidate(project)
    assert client.post(f'/api/projects/{project}/application/build', json={**body, 'version': 2}).status_code == 409
    assert client.get(f'/api/projects/{project}/application').json()['stale'] is True
    assert client.get('/api/billing').json()['account']['balance'] == 100


def test_build_refund_retry_download_and_no_false_preview(setup, project, monkeypatch):
    client, store, *_ = setup
    draft(setup, project)
    client.post(f'/api/projects/{project}/application/approve', json={'version': 1})
    monkeypatch.setattr(application_runner, 'build_and_test', Mock(side_effect=AppError('Docker not running', 503)))
    url = f'/api/projects/{project}/application/build'
    body = {'version': 1, 'request_id': 'request-one'}
    first = client.post(url, json=body)
    assert first.status_code == 202, first.text
    bid = first.json()['id']
    second = client.post(url, json=body)
    assert second.status_code == 202 and second.json()['id'] == bid
    build = client.get(f'/api/projects/{project}/application').json()['builds'][0]
    assert build['status'] == 'validation_required'
    assert build['validation']['checks'] == []
    assert 'files' not in build
    assert client.get('/api/billing').json()['account']['balance'] == 100
    assert store.db.application_builds.count_documents({'project_id': project}) == 1
    assert client.get(f'/api/projects/{project}/application/builds/{bid}/download').content.startswith(b'PK')
    assert client.post(f'/api/projects/{project}/application/builds/{bid}/preview').status_code == 409
    assert client.post(f'/api/projects/{project}/application/builds/{bid}/deploy').status_code == 409


def test_success_charges_once_and_schema_downgrade_blocked(setup, project, monkeypatch):
    client, store, *_ = setup
    draft(setup, project)
    client.post(f'/api/projects/{project}/application/approve', json={'version': 1})
    monkeypatch.setattr(application_runner, 'build_and_test', lambda *args: {'status': 'passed', 'checks': ['test substitute'], 'logs': []})
    body = {'version': 1, 'request_id': 'request-success'}
    for _ in range(3):
        assert client.post(f'/api/projects/{project}/application/build', json=body).status_code == 202
    assert client.get('/api/billing').json()['account']['balance'] == 90
    billing_service.settle(store, 'local-workspace', project + ':request-success', False)
    assert client.get('/api/billing').json()['account']['balance'] == 90
    current = specification(); current['entities'][1]['fields'][0]['kind'] = 'number'
    assert compatibility(specification(), current)


def test_credit_reservation_is_atomic_and_refund_idempotent(setup):
    _, store, *_ = setup
    for i in range(10):
        assert billing_service.reserve(store, 'actor', 'build-' + str(i))
    with pytest.raises(AppError):
        billing_service.reserve(store, 'actor', 'one-too-many')
    assert billing_service.reserve(store, 'actor', 'build-0') is False
    for _ in range(3):
        billing_service.settle(store, 'actor', 'build-0', False)
    assert billing_service.account(store, 'actor')['balance'] == 10


def test_spec_rejects_code_identifiers_and_broken_relations():
    for name in ['../escape', 'users; DROP TABLE users', 'a.b', 'x"']:
        data = specification(); data['entities'][0]['name'] = name
        with pytest.raises(ValidationError):
            ApplicationSpec.model_validate(data)
    data = specification(); data['entities'][1]['fields'][2]['reference'] = 'missing'
    with pytest.raises(ValidationError):
        ApplicationSpec.model_validate(data)


def test_generated_trusted_runtime_real_http_database_contract(tmp_path):
    files, manifest, findings = compile_application(specification(), str(ObjectId()))
    assert not findings and 'server.py' in manifest
    for name, content in files.items():
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding='utf-8')
    # Fixed, compiler-owned runtime only. No AI-produced Python is executed here.
    result = subprocess.run([sys.executable, '-m', 'unittest', 'selftest', '-v'], cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Ran 4 tests' in result.stderr


def test_unsafe_edits_are_not_approved(setup, project):
    client, store, *_ = setup
    draft(setup, project)
    store.db.application_builds.insert_one({'project_id':project,'status':'ready','spec':specification()})
    changed = specification()
    changed['entities'][0]['fields'][0]['kind'] = 'number'
    response = client.post(f'/api/projects/{project}/application/spec', json={'base_version': 1, 'spec': changed})
    assert response.status_code == 200
    assert response.json()['migration_issues']
    assert client.post(f'/api/projects/{project}/application/approve', json={'version': 2}).status_code == 409


def test_spec_blocks_required_cycles_and_missing_reference_permissions():
    value = specification()
    value['entities'][0]['fields'].append({'name':'candidate','label':'Candidate','kind':'reference','required':True,'reference':'candidates'})
    value['entities'][1]['fields'][2]['required'] = True
    with pytest.raises(ValidationError, match='cycles'):
        ApplicationSpec.model_validate(value)
    value = specification()
    value['entities'][0]['read_roles'] = ['admin', 'viewer']
    value['entities'][0]['write_roles'] = ['admin']
    with pytest.raises(ValidationError, match='referenced'):
        ApplicationSpec.model_validate(value)


def test_admin_permissions_idempotent_grants_and_refund_price(setup, monkeypatch):
    client, store, _, settings = setup
    body = {'account_id':'local-workspace','amount':25,'request_id':'test-grant'}
    assert client.post('/api/builder/admin/credits', json=body).status_code == 403
    monkeypatch.setattr(settings, 'builder_admin_ids', 'local-workspace')
    for _ in range(2):
        assert client.post('/api/builder/admin/credits', json=body).status_code == 200
    assert billing_service.account(store, 'local-workspace')['balance'] == 125
    billing_service.reserve(store, 'local-workspace', 'reserved-price')
    assert client.post('/api/builder/admin/plan', json={'name':'Pilot','build_cost':50,'initial_credits':200,'max_entities':10}).status_code == 200
    billing_service.settle(store, 'local-workspace', 'reserved-price', False)
    assert billing_service.account(store, 'local-workspace')['balance'] == 125
    assert client.get('/api/billing').json()['build_cost'] == 50


def test_stale_price_does_not_reserve_credits(setup, project):
    client, store, *_ = setup
    draft(setup, project)
    client.post(f'/api/projects/{project}/application/approve', json={'version':1})
    response = client.post(f'/api/projects/{project}/application/build', json={'version':1,'request_id':'stale-price-test','quoted_cost':100})
    assert response.status_code == 409
    assert billing_service.account(store, 'local-workspace')['balance'] == 100


def test_artifacts_match_runtime_and_escape_labels():
    value=specification(); value['entities'][0]['label']='<script>alert(1)</script>'
    files,manifest,_=compile_application(value,str(ObjectId()))
    contract=json.loads(files['openapi.json'])
    assert '/api/records/candidates/{id}/transition' in contract['paths']
    assert '"company" TEXT REFERENCES "e_companies"(id)' in files['migrations/001_schema.sql']
    assert 'NOT NULL' in files['migrations/001_schema.sql']
    assert '<script>' not in files['schema.svg']
    assert 'e_companies' in files['schema.mmd']
    assert json.loads(files['traceability.json'])[0]['modules']==['companies']
    assert all(len(hash_value)==64 for hash_value in manifest.values())


def test_preview_lifecycle_is_owned_and_stop_verified(setup, project, monkeypatch):
    client,store,*_=setup
    bid=ObjectId();store.db.application_builds.insert_one({'_id':bid,'project_id':project,'status':'ready'})
    stopped=[]
    monkeypatch.setattr(application_runner,'preview',lambda _: {'container':'shift-preview-1234567890abcdef','url':'http://127.0.0.1:39001','password':'temporary-secret','email':'preview@shift.local','expires_in_seconds':900})
    monkeypatch.setattr(application_runner,'stop_preview',lambda name: stopped.append(name))
    result=client.post(f'/api/projects/{project}/application/builds/{bid}/preview')
    assert result.status_code==200
    assert 'password' not in store.db.application_previews.find_one({'project_id':project})
    assert client.delete(f'/api/projects/{project}').status_code==409
    assert client.post(f'/api/projects/{project}/application/preview/stop').status_code==200
    assert stopped==['shift-preview-1234567890abcdef']


def test_expired_preview_cleanup_retries_without_claiming_success(setup, project, monkeypatch):
    from datetime import timedelta
    from app.repositories.store import now
    client, store, *_ = setup
    container = 'shift-preview-1234567890abcdef'
    key = store.db.application_previews.insert_one({'project_id': project, 'status': 'running',
        'container': container, 'expires_at': now() - timedelta(seconds=1)}).inserted_id
    cleanup = Mock(side_effect=AppError('Docker cleanup unavailable', 503))
    monkeypatch.setattr(application_runner, 'stop_preview', cleanup)
    first = client.get(f'/api/projects/{project}/application')
    assert first.status_code == 200
    assert first.json()['preview']['cleanup_error'] == 'Docker cleanup unavailable'
    assert store.db.application_previews.find_one({'_id': key})['status'] == 'running'
    cleanup.side_effect = None
    assert client.get(f'/api/projects/{project}/application').json()['preview'] is None
    saved = store.db.application_previews.find_one({'_id': key})
    assert saved['status'] == 'expired' and 'cleanup_error' not in saved
    assert cleanup.call_count == 2 and cleanup.call_args.args == (container,)


def test_vercel_never_live_without_matching_frontend_and_backend(setup, project, monkeypatch):
    from app.services import vercel_deployment
    _,store,*_=setup
    bid=ObjectId();store.db.application_builds.insert_one({'_id':bid,'project_id':project,'spec':specification()})
    row={'_id':ObjectId(),'project_id':project,'target':'vercel','provider_id':'dpl-example','candidate_url':'https://example.vercel.app','build_id':str(bid),'status':'deploying'}
    store.db.application_deployments.insert_one(row)
    monkeypatch.setattr(vercel_deployment,'api',lambda *args: {'readyState':'READY'})
    monkeypatch.setattr(vercel_deployment,'fetch_public',lambda *args,**kw: (b'{"status":"ok","build_id":"other"}','application/json',''))
    assert vercel_deployment.refresh(store,row)['status']=='health_pending'
    monkeypatch.setattr(vercel_deployment,'fetch_public',lambda *args,**kw: (json.dumps({'status':'ok','build_id':str(bid),'spec_hash':digest(specification())}).encode(),'application/json',''))
    assert vercel_deployment.refresh(store,row)['status']=='live'


def test_vercel_gateway_origin_cookie_path_and_size(tmp_path):
    import shutil
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to verify the Vercel gateway')
    template = Path(__file__).resolve().parents[1] / 'app/templates/vercel_proxy.mjs'
    gateway = tmp_path / 'proxy.mjs'
    gateway.write_text(template.read_text('utf-8').replace('__UPSTREAM__', '"https://backend.onrender.com"'), encoding='utf-8')
    script = '''
import assert from 'node:assert/strict';
const gateway = (await import(process.argv[1])).default;
const calls=[];
globalThis.fetch=async (url, options) => { calls.push({url:String(url),options});return new Response('{"ok":true}',{headers:{'set-cookie':'app_session=generated; HttpOnly; Secure; SameSite=Strict'}}); };
const url='https://front.vercel.app/api/proxy?route=records/clients';
let result=await gateway.fetch(new Request(url,{method:'POST',headers:{origin:'https://evil.test'},body:'{}'}));
assert.equal(result.status,403);assert.equal(calls.length,0);
result=await gateway.fetch(new Request('https://front.vercel.app/api/proxy?route=../../secret'));
assert.equal(result.status,404);assert.equal(calls.length,0);
result=await gateway.fetch(new Request(url,{method:'POST',headers:{origin:'https://front.vercel.app',cookie:'shift_session=platform-secret; app_session=testtoken'},body:'{}'}));
assert.equal(result.status,200);assert.equal(calls[0].options.headers.Cookie,'app_session=testtoken');
assert.equal(calls[0].options.headers.Origin,'https://backend.onrender.com');
assert.equal(calls[0].url,'https://backend.onrender.com/api/records/clients');
assert.match(result.headers.get('set-cookie'),/^app_session=/);
result=await gateway.fetch(new Request(url,{method:'POST',headers:{origin:'https://front.vercel.app'},body:'x'.repeat(65537)}));
assert.equal(result.status,413);assert.equal(calls.length,1);
'''
    result = subprocess.run([node, '--input-type=module', '-e', script, gateway.as_uri()], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_orphan_refund_and_language_assets(setup):
    from datetime import timedelta
    from app.repositories.store import now
    _,store,*_=setup
    billing_service.reserve(store,'orphan-account','orphan-build')
    store.db.credit_accounts.update_one({'_id':'orphan-account'},{'$set':{'entries.0.created_at':now()-timedelta(minutes=40)}})
    for _ in range(2):billing_service.recover_orphans(store,'orphan-account')
    assert billing_service.account(store,'orphan-account')['balance']==100
    for language, label in [('hi','रिकॉर्ड जोड़ें'),('gu','રેકોર્ડ ઉમેરો')]:
        value=specification();value['language']=language
        files,_,_=compile_application(value,str(ObjectId()))
        assert f'lang="{language}"' in files['public/index.html']
        assert label in files['public/app.js']


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', '0.0.0.0', '192.168.1.1'])
def test_url_blocks_private_and_metadata_addresses(monkeypatch, address):
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', (address, 443))])
    with pytest.raises(AppError):
        public_address('example.test', 443)


def test_html_extraction_excludes_scripts():
    parser = TextExtractor(); parser.feed('<h1>Business</h1><script>steal secrets</script><p>We recruit candidates.</p>')
    assert 'Business' in ''.join(parser.parts) and 'steal' not in ''.join(parser.parts)


def test_deployment_requires_exact_health_identity(setup, project, monkeypatch):
    _, store, *_ = setup
    bid = ObjectId()
    store.db.application_builds.insert_one({'_id': bid, 'project_id': project, 'spec': specification()})
    doc = {'_id': ObjectId(), 'project_id': project, 'build_id': str(bid), 'service_id': 'srv-testservice', 'provider_id': 'dep-example', 'status': 'deploying'}
    store.db.application_deployments.insert_one(doc)
    monkeypatch.setattr(deployment_service, 'render_api', lambda method, path: {'status': 'live'} if '/deploys/' in path else {'serviceDetails': {'url': 'https://example.onrender.com'}})
    monkeypatch.setattr(deployment_service, 'fetch_public', lambda *a, **kw: (json.dumps({'status': 'ok', 'build_id': 'wrong'}).encode(), 'application/json', ''))
    result = deployment_service.refresh(store, doc)
    assert result['status'] == 'health_pending' and 'live_url' not in result
    monkeypatch.setattr(deployment_service, 'fetch_public', lambda *a, **kw: (json.dumps({'status': 'ok', 'build_id': str(bid), 'spec_hash': digest(specification())}).encode(), 'application/json', ''))
    result = deployment_service.refresh(store, result)
    assert result['status'] == 'live'


def test_build_endpoints_enforce_project_roles(setup, project):
    client, store, *_ = setup
    doc = draft(setup, project)
    # The existing project permission implementation is authoritative at every route.
    original = store.project
    def restricted(pid, actor, permission='read'):
        if permission != 'read':
            raise AppError('Viewer cannot write.', 403)
        return original(pid, actor, permission)
    store.project = restricted
    assert client.post(f'/api/projects/{project}/application/approve', json={'version': 1}).status_code == 403
    assert client.post(f'/api/projects/{project}/application/build', json={'version': 1, 'request_id': 'viewer-test'}).status_code == 403
    assert client.post(f'/api/projects/{project}/application/spec', json={'base_version': 1, 'spec': doc['spec']}).status_code == 403
