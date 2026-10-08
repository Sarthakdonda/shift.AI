"""Large-input budgets, coverage, stage persistence and provider error semantics."""
import json
from unittest.mock import Mock

import httpx
import mongomock
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import AppError
from app.models.application import ApplicationSpec
from app.models.application_generation import CORE_FIELDS
from app.repositories.store import Store
from app.services import groq_service
from app.services.application_context import source_units, canonical_content
from app.services.application_planning import ApplicationPlanner
from app.services.application_service import plan_job
from app.services.token_budget import estimate_tokens


class TextResult(BaseModel):
    text: str


def transport(monkeypatch, responses, **options):
    settings = Settings(_env_file=None, groq_api_keys='test-first,test-second', groq_cooldown_wait_seconds=0, **options)
    monkeypatch.setattr(groq_service, 'get_settings', lambda: settings)
    requests = []
    values = iter(responses)
    def handler(request):
        requests.append(request)
        return next(values)
    client = httpx.Client
    monkeypatch.setattr(groq_service.httpx, 'Client', lambda **kw: client(transport=httpx.MockTransport(handler), **kw))
    return groq_service.GroqService(), requests


def ok(text='done'):
    return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'text': text})}, 'finish_reason': 'stop'}]})


def test_estimator_includes_multilingual_content_and_schema():
    assert estimate_tokens('账单' * 1000) > estimate_tokens('ab' * 1000)


def test_oversized_preflight_never_calls_provider(monkeypatch):
    ai, calls = transport(monkeypatch, [])
    with pytest.raises(AppError) as caught:
        ai.generate_structured('Return text', {'blueprint': 'x' * 100000}, TextResult)
    assert caught.value.code == 'groq_request_budget' and not calls


@pytest.mark.parametrize('status,body,expected', [
    (413, {'message': 'Request too large on tokens per minute: Limit 8000, Requested 70929', 'code': 'rate_limit_exceeded'}, 'groq_request_budget'),
    (429, {'message': 'Request too large: Limit 8000, Requested 12000', 'code': 'rate_limit_exceeded'}, 'groq_request_budget'),
    (400, {'message': 'maximum context length exceeded', 'code': 'context_length_exceeded'}, 'groq_context_length'),
])
def test_nonretryable_limits_do_not_rotate_keys(monkeypatch, status, body, expected):
    ai, calls = transport(monkeypatch, [httpx.Response(status, headers={'retry-after': '472'}, json={'error': body})])
    with pytest.raises(AppError) as caught:
        ai.generate_structured('Return text', {}, TextResult)
    assert caught.value.code == expected and len(calls) == 1


def test_retryable_rate_limit_rotates_and_honors_cooldown(monkeypatch):
    ai, calls = transport(monkeypatch, [httpx.Response(429, headers={'retry-after': '90'}, json={'error': {'message': 'Rate limit reached for tokens per minute: Limit 8000, Used 7500, Requested 1000. Visit https://console.groq.com/settings/billing', 'code': 'rate_limit_exceeded'}}), ok()])
    assert ai.generate_text('Return text', {}) == 'done'
    assert len(calls) == 2
    assert ai._cooldowns[0] > groq_service.time.monotonic() + 85


def test_daily_quota_never_retries_exhausted_connection(monkeypatch):
    exhausted = httpx.Response(429, json={'error': {'message': 'tokens per day quota exhausted'}})
    ai, calls = transport(monkeypatch, [exhausted, exhausted])
    with pytest.raises(AppError) as caught:
        ai.generate_text('Return text', {})
    assert caught.value.code == 'groq_quota_exhausted' and len(calls) == 2
    assert len({call.headers['authorization'] for call in calls}) == 2


def test_output_clamps_to_model_limit_and_detects_truncation(monkeypatch):
    ai, calls = transport(monkeypatch, [httpx.Response(200, json={'choices': [{'message': {'content': '{}'}, 'finish_reason': 'length'}]})], groq_model_output_limit=512)
    with pytest.raises(AppError) as caught:
        ai.generate_text('Return text', {})
    assert caught.value.code == 'groq_output_limit'
    assert json.loads(calls[0].content)['max_completion_tokens'] == 512


def test_actual_provider_header_reduces_future_budget(monkeypatch):
    response = ok(); response.headers['x-ratelimit-limit-tokens'] = '4000'
    ai, _ = transport(monkeypatch, [response])
    ai.generate_text('Return text', {})
    assert ai.token_limits()['request'] == 3600


def test_remaining_token_headers_prevent_a_known_exhausted_request(monkeypatch):
    first = ok(); first.headers.update({'x-ratelimit-remaining-tokens': '1', 'x-ratelimit-reset-tokens': '1m30s'})
    ai, calls = transport(monkeypatch, [first, ok()])
    ai.generate_text('First', {})
    ai.generate_text('Second', {})
    assert [r.headers['authorization'] for r in calls] == ['Bearer test-first', 'Bearer test-second']


@pytest.mark.parametrize('report_version', [2, 3])
def test_native_report_projection_preserves_canonical_and_custom_requirements(report_version):
    content = {'option_decision': {'selected': 'lean', 'options': [{'tier': 'lean', 'feature': 'keep'}, {'tier': 'advanced', 'feature': 'rejected'}]},
        'final_report': {'schema_version': report_version, 'selected_option': 'lean', 'sections': [{'key': 'apis', 'narrative': 'Rendered APIs'}, {'key': 'custom_requirement', 'narrative': 'Unique requirement'}]}}
    for key in ('architecture_report', 'experience_report', 'data_report', 'planning_report'):
        content[key] = {'selected_option': 'lean', 'chapters': [{'key': 'apis', 'narrative': 'Canonical requirement including all APIs'}]}
    projected = canonical_content({'content': content})
    assert 'final_report' not in projected
    assert projected['option_decision']['options'] == [{'tier': 'lean', 'feature': 'keep'}]
    assert projected['report_additions'][0]['narrative'] == 'Unique requirement'
    assert all(projected[key] == content[key] for key in ('architecture_report', 'experience_report', 'data_report', 'planning_report'))
    uploaded = canonical_content({'name': 'external.json', 'source': None, 'content': content})
    assert uploaded == content


def test_lossless_partition_and_history_exclusion():
    text = '账单规则 must retain exact amounts and relationships. ' * 3000 + 'CRITICAL LAST REQUIREMENT'
    blueprint = {'content': {'document_text': text, 'solution_history': ['obsolete'], 'red_team_history': ['old']}}
    units = source_units(blueprint, {}, '')
    assert ''.join(u['text'] for u in units if u['path'] == 'blueprint.document_text') == text
    assert all(len(u['text'].encode()) <= 1800 for u in units)
    assert not any('history' in u['path'] for u in units)


class StagedFake(groq_service.GroqService):
    def __init__(self, fail_stage=None):
        super().__init__()
        self.settings = Settings(_env_file=None, groq_api_key='test', groq_tokens_per_minute=8000)
        self._keys = ['test']
        self._observed_token_limit = 8000
        self.calls = []
        self.fail_stage = fail_stage

    def generate_structured(self, instruction, context, schema, **kwargs):
        payload = self.make_payload(instruction, context, schema)
        self._preflight(payload)
        self.calls.append((schema.__name__, context, self.request_size(instruction, context, schema)))
        if context.get('stage') == self.fail_stage and self.fail_stage:
            self.fail_stage = None
            raise AppError('Temporary rate limit; saved stages can resume.', 429, 'rate_limited')
        items = context.get('items', [])
        ids = [f['id'] for f in items]
        if schema.__name__ == 'ExtractedContext':
            return schema.model_validate({'requirements': [{'description': 'Invoice rule ' + str(index) + ': ' + item['text'][:160],
                'stages': ['core', 'database', 'api', 'frontend', 'backend', 'deployment'],
                'targets': ['invoices'], 'source_ids': [item['id']]} for index, item in enumerate(items)], 'non_requirements': []})
        if schema.__name__ == 'CoreApplication':
            return schema.model_validate({'name': 'Invoice operations', 'description': 'Manage invoice records.', 'roles': ['admin'],
                'change_summary': 'Initial specification.', 'application_type': 'web_application', 'storage_mode': 'shared_server',
                'modules': [{'name': 'invoices', 'label': 'Invoices', 'requirement_ids': ids}], 'pages': []})
        if schema.__name__ == 'Entity':
            return schema.model_validate({'name': 'invoices', 'label': 'Invoices', 'fields': [{'name': 'title', 'label': 'Title'}],
                'read_roles': ['admin'], 'write_roles': ['admin'], 'requirement_ids': ids})
        if schema.__name__ == 'StageSpecification':
            return schema.model_validate({'decisions': [{'requirement_ids': ids, 'decision': 'Use the existing approved runtime and delivery architecture.', 'implementation': 'supported'}]})
        if schema.__name__ == 'CoverageReview':
            return schema.model_validate({'assessments': [{'requirement_id': ident, 'implementation': 'supported', 'reason': 'Mapped to the invoice module.'} for ident in ids]})
        raise AssertionError(schema.__name__)


def workspace(large=False):
    store = Store(mongomock.MongoClient().generation)
    project = store.create({'name': 'Invoices', 'initial_problem': 'Manual invoice work', 'language': 'en'}, 'owner')
    pid = str(project['_id'])
    content = {'requirements': [{'id': f'F{i}', 'rule': f'Invoice rule {i} keeps its unique acceptance criteria and exact tax threshold {i}. ' + ('Detailed business constraints. ' * 50 if large else '')} for i in range(70 if large else 4)]}
    store.save_blueprint(pid, {'review_gate': 'passed', **content})
    return store, project, pid


def test_large_blueprint_multi_stage_success_and_budgets():
    store, project, pid = workspace(large=True)
    ai = StagedFake()
    plan_job(store, ai, pid, 'owner', 'Build the website with all required invoice features.', 0)
    job = store.project(pid, 'owner')['application_job']
    assert job['status'] == 'complete', job
    spec = ApplicationSpec.model_validate(store.latest('application_specs', pid)['spec'])
    assert len(spec.requirements) >= 70
    assert all(size <= 7200 for _, _, size in ai.calls)
    stages = {row['stage'] for row in store.db.application_generation_steps.find({'status': 'complete'})}
    assert {'requirements', 'core', 'database', 'api', 'frontend', 'backend', 'deployment', 'review'} <= stages
    assert all(r.implementation == 'supported' for r in spec.requirements)


def test_long_conversations_and_unrelated_documents_are_not_sent():
    store, project, pid = workspace()
    for i in range(30):
        store.message(pid, 'user', 'UNRELATED_HISTORY_SECRET_' + str(i) + (' unrelated words' * 3000))
    store.db.documents.insert_one({'project_id': pid, 'content': 'UNRELATED_DOCUMENT_SECRET' * 10000})
    ai = StagedFake()
    plan_job(store, ai, pid, 'owner', 'Build invoices.', 0)
    assert store.project(pid, 'owner')['application_job']['status'] == 'complete'
    assert 'UNRELATED_HISTORY_SECRET' not in json.dumps(ai.calls)
    assert 'UNRELATED_DOCUMENT_SECRET' not in json.dumps(ai.calls)


def test_partial_failure_resumes_completed_steps_without_regeneration():
    store, project, pid = workspace()
    ai = StagedFake(fail_stage='api')
    plan_job(store, ai, pid, 'owner', 'Build invoices.', 0)
    job = store.project(pid, 'owner')['application_job']
    assert job['status'] == 'failed' and job['resumable'] and job['completed_steps'] > 0
    assert not store.latest('application_specs', pid)
    before = len([name for name, _, _ in ai.calls if name in ('ExtractedContext', 'CoreApplication', 'Entity')])
    plan_job(store, ai, pid, 'owner', 'Build invoices.', 0, job['generation_id'])
    assert store.project(pid, 'owner')['application_job']['status'] == 'complete'
    # Only the backend entity call remains; extraction/core/database are reused.
    after = len([name for name, _, _ in ai.calls if name in ('ExtractedContext', 'CoreApplication', 'Entity')])
    assert after == before + 1


def test_changed_blueprint_cannot_resume_old_generation():
    store, project, pid = workspace()
    ai = StagedFake(fail_stage='api')
    plan_job(store, ai, pid, 'owner', 'Build invoices.', 0)
    old = store.project(pid, 'owner')['application_job']['generation_id']
    store.save_blueprint(pid, {'review_gate': 'passed', 'requirements': ['Changed requirements']})
    plan_job(store, ai, pid, 'owner', 'Build invoices.', 0, old)
    job = store.project(pid, 'owner')['application_job']
    assert job['code'] == 'application_resume_stale'
    assert not store.latest('application_specs', pid)


def test_missing_source_coverage_blocks_generation():
    store, project, pid = workspace()
    ai = StagedFake()
    original = ai.generate_structured
    def incomplete(instruction, context, schema, **kwargs):
        if schema.__name__ == 'ExtractedContext':
            return schema.model_validate({'requirements': [], 'non_requirements': []})
        return original(instruction, context, schema, **kwargs)
    ai.generate_structured = incomplete
    plan_job(store, ai, pid, 'owner', '', 0)
    assert store.project(pid, 'owner')['application_job']['code'] == 'application_stage_coverage'
    assert not store.latest('application_specs', pid)


@pytest.mark.parametrize('code', ['groq_request_budget', 'groq_output_limit'])
def test_provider_size_failure_splits_batch_instead_of_replaying_it(code):
    store, project, pid = workspace()
    ai = StagedFake()
    original = ai.generate_structured
    failed_sizes = []
    def oversized(instruction, context, schema, **kwargs):
        if schema.__name__ == 'ExtractedContext' and len(context['items']) > 1:
            failed_sizes.append(len(context['items']))
            raise AppError('Provider actual limit requires smaller batch', 413, code)
        return original(instruction, context, schema, **kwargs)
    ai.generate_structured = oversized
    plan_job(store, ai, pid, 'owner', 'Build invoices', 0)
    assert store.project(pid, 'owner')['application_job']['status'] == 'complete'
    assert failed_sizes
    assert all(len(ctx['items']) == 1 for name, ctx, _ in ai.calls if name == 'ExtractedContext')


def test_resume_route_uses_saved_request_and_checks_project_access(setup, project, monkeypatch):
    from app.api import applications
    client, store, _, _ = setup
    store.save_blueprint(project, {'review_gate': 'passed', 'requirements': ['Invoice records']})
    ai = StagedFake(fail_stage='api')
    monkeypatch.setattr(applications, 'get_builder_ai', lambda: ai)
    assert client.post(f'/api/projects/{project}/application/plan', json={'instructions': 'Original invoice request'}).status_code == 202
    job = store.project(project, 'local-workspace')['application_job']
    assert job['resumable']
    response = client.post(f'/api/projects/{project}/application/plan', json={'resume_id': job['generation_id']})
    assert response.status_code == 202
    assert store.project(project, 'local-workspace')['application_job']['status'] == 'complete'
    assert client.post(f'/api/projects/{project}/application/plan', json={'resume_id': job['generation_id']}).status_code == 409
