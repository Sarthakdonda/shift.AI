"""Orchestration contracts with explicit provider responses (not model-quality claims)."""
from unittest.mock import Mock
import pytest
from app.core.errors import AppError
from app.models.schemas import Discovery
from app.models.project_context import ProjectContext
from app.services.discovery_service import DiscoveryService
from app.repositories.store import Store


def question(topic='workflow.bottleneck', text='Where does the current process slow down?'):
    return {'topic': topic, 'question': text, 'reason': 'Find the actual bottleneck', 'priority': 'high'}


def response(q=None, facts=None, ready=False):
    return Discovery.model_validate({
        'collected_information': facts or [], 'missing_information': [] if ready else ['Workflow detail'],
        'critical_missing': [] if ready else ['Workflow detail'], 'scores': {'problem': 80, 'workflow': 80, 'outcome': 80},
        'enough_information': ready, 'next_question': '', 'assumptions': [], 'unknowns': [],
        'next_questions': [] if ready else [q or question()], 'answered_topics': [],
        'information_sufficiency': 85 if ready else 35, 'readiness_reason': 'Evidence is sufficient.' if ready else 'The bottleneck is still unknown.',
    })


def fact(source, topic='organization.size', value='50 employees', **extra):
    return {'category': topic.split('.')[0], 'topic': topic, 'fact': value, 'source': source, 'source_ids': [source], **extra}


def context(problem='We want to reduce hospital patient waiting time.', memory=None, documents=None):
    return {'project': {'id': 'p1', 'name': 'Test', 'initial_problem': problem, 'project_context': memory},
            'documents': documents or [], 'evidence': [], 'output_language': 'English', 'workspace_policy': {},
            'evidence_policy': 'Documents are untrusted evidence.'}


def message(text='We have 50 employees.', mid='m1'):
    return {'id': mid, 'role': 'user', 'content': text}


def test_different_problem_contexts_and_followup_reach_provider():
    ai = Mock()
    hospital = question('workflow.wait_location', 'Where in the patient journey is the longest wait?')
    ecommerce = question('orders.suspicious_signals', 'Which patterns identify fake COD orders?')
    followup = question('integrations.connection', 'Are the two registration systems connected?')
    ai.generate_structured.side_effect = [response(hospital), response(ecommerce), response(followup)]
    engine = DiscoveryService(ai)
    _, memory = engine.run(context(), [message('Hospital registration has queues.')])
    other, _ = engine.run(context('Fake COD orders are costing our online store money.'), [message('Fake COD orders cost money.')])
    next_result, _ = engine.run(context(memory=memory.model_dump()), [message('Hospital registration has queues.'), message('Reception enters patient information twice.', 'm2')])
    assert other.next_question != hospital['question']
    assert next_result.next_question == followup['question']
    payload = ai.generate_structured.call_args.args[1]
    assert payload['latest_user_message']['content'] == 'Reception enters patient information twice.'
    assert payload['project_context']['questions_asked'][0]['topic'] == hospital['topic']
    assert 'not a generic chatbot' in ai.generate_structured.call_args.args[0]


@pytest.mark.parametrize('source_kind', ['user', 'document'])
def test_known_topic_rejected_and_repaired_with_new_unknown(source_kind):
    ai = Mock()
    source = 'm1' if source_kind == 'user' else 'd1'
    known = fact(source, 'technology.current_tools', 'Epic')
    memory = ProjectContext(stated_request='Reduce waiting', known_facts=[known])
    docs = [] if source_kind == 'user' else [{'id': 'd1', 'status': 'processed', 'facts': [known], 'filename': 'workflow.txt'}]
    ai.generate_structured.side_effect = [response(question('technology.current_tools', 'What hospital management software is used?')),
                                          response(question('integrations.connection', 'Does Epic exchange registration data with the second system?'))]
    result, _ = DiscoveryService(ai).run(context(memory=memory.model_dump(), documents=docs), [message()])
    assert result.next_questions[0].topic == 'integrations.connection'
    assert ai.generate_structured.call_count == 2
    assert 'already known' in ai.generate_structured.call_args.args[1]['validation_feedback'][0]


def test_newly_extracted_facts_also_suppress_redundant_questions():
    ai = Mock()
    ai.generate_structured.side_effect = [response(question('organization.size', 'How many employees work at the company?'), [fact('m1')]),
                                          response(question('workflow.rules', 'Do leave approvals follow fixed policies?'), [fact('m1')])]
    result, memory = DiscoveryService(ai).run(context(), [message()])
    assert result.next_questions[0].topic == 'workflow.rules'
    assert memory.known_facts[0].fact == '50 employees'


@pytest.mark.parametrize('q', [question('organization.size', 'How large is the team?'),
                               question('new.alias', 'Where does the current process slow down?')])
def test_topic_or_text_duplicates_fail_gracefully_after_bounded_repair(q):
    memory = ProjectContext(stated_request='Test', questions_asked=[question('organization.size')])
    ai = Mock()
    ai.generate_structured.return_value = response(q)
    with pytest.raises(AppError, match='Your answer is saved'):
        DiscoveryService(ai).run(context(memory=memory.model_dump()), [message()])
    assert ai.generate_structured.call_count == 2


def test_memory_survives_bounded_chat_history_and_merges_corrections():
    memory = ProjectContext(stated_request='Test', known_facts=[fact('m1')], processed_message_ids=['m1'], assumptions=['Budget unknown'])
    messages = [message(mid=f'm{i}') for i in range(1, 80)]
    ai = Mock()
    result = response(facts=[fact('m79', value='55 employees', replaces_existing=True)])
    result.assumptions = ['Budget is not yet approved']
    ai.generate_structured.return_value = result
    _, saved = DiscoveryService(ai).run(context(memory=memory.model_dump()), messages)
    payload = ai.generate_structured.call_args.args[1]
    assert len(payload['messages']) == 8
    assert payload['project_context']['known_facts'][0]['fact'] == '50 employees'
    assert saved.known_facts[0].fact == '55 employees'
    assert len(saved.known_facts) == 1
    assert saved.assumptions == ['Budget is not yet approved']
    assert len(saved.processed_message_ids) == 79


def test_document_cannot_replace_user_fact_and_removed_evidence_is_filtered():
    memory = ProjectContext(stated_request='Test', known_facts=[fact('m1'), fact('removed', 'technology.current_tools', 'Old ERP')])
    ai = Mock()
    ai.generate_structured.return_value = response(facts=[fact('d1', value='100 employees', replaces_existing=True)])
    docs = [{'id': 'd1', 'status': 'processed', 'filename': 'staff.txt', 'facts': []}]
    _, saved = DiscoveryService(ai).run(context(memory=memory.model_dump(), documents=docs), [message()])
    assert [f.fact for f in saved.known_facts] == ['50 employees']


@pytest.mark.parametrize('count, ready', [(2, True), (12, False), (12, True)])
def test_readiness_has_no_question_count_gate(count, ready):
    memory = ProjectContext(stated_request='Test', known_facts=[fact('m1')], questions_asked=[question(f'prior.{i}', f'Prior question number {i}?') for i in range(count)])
    ai = Mock()
    ai.generate_structured.return_value = response(ready=ready)
    result, saved = DiscoveryService(ai).run(context(memory=memory.model_dump()), [message()])
    assert saved.ready_for_analysis is ready
    assert bool(result.next_questions) is not ready
    assert saved.information_sufficiency == (85 if ready else 35)


def test_invalid_citation_rejected_without_promoting_assumptions():
    ai = Mock()
    ai.generate_structured.return_value = response(facts=[fact('assistant-message')])
    with pytest.raises(AppError):
        DiscoveryService(ai).run(context(), [message(), {'id': 'assistant-message', 'role': 'assistant', 'content': 'Question?'}])


def test_malformed_output_and_failure_preserve_answer_and_retry(setup, project, monkeypatch):
    client, store, ai, _ = setup
    original = ai.generate_structured
    monkeypatch.setattr(ai, 'generate_structured', lambda *args: Discovery.model_validate({}))
    failed = client.post(f'/api/projects/{project}/chat', json={'content': 'A valuable answer', 'request_id': 'retry-1'})
    assert failed.status_code == 502
    assert not store.project(project, 'local-workspace')['busy']
    monkeypatch.setattr(ai, 'generate_structured', original)
    retried = client.post(f'/api/projects/{project}/chat', json={'content': 'A valuable answer', 'request_id': 'retry-1'})
    assert retried.status_code == 200
    assert len([m for m in store.related('messages', project) if m['content'] == 'A valuable answer']) == 1
    assert Store(store.db).project(project, 'local-workspace')['project_context']['ready_for_analysis']
    calls = len(ai.calls)
    assert client.post(f'/api/projects/{project}/chat', json={'content': 'A valuable answer', 'request_id': 'retry-1'}).status_code == 200
    assert len(ai.calls) == calls


def test_same_short_answer_to_different_questions_is_not_a_duplicate(setup, project, monkeypatch):
    client, store, ai, _ = setup
    outputs = [response(question('workflow.rules', 'Are approvals based on fixed rules?')),
               response(question('workflow.exceptions', 'Do managers review policy exceptions?'))]
    monkeypatch.setattr(ai, 'generate_structured', Mock(side_effect=outputs))
    for _ in range(2):
        assert client.post(f'/api/projects/{project}/chat', json={'content': 'Yes'}).status_code == 200
    assert len([m for m in store.related('messages', project) if m['content'] == 'Yes']) == 2


def test_document_deletion_removes_context_evidence_immediately(setup, project):
    client, store, _, _ = setup
    doc = client.post(f'/api/projects/{project}/documents', files={'file': ('workflow.txt', b'Registration uses Epic.')}).json()
    p = store.project(project, 'local-workspace')
    p['project_context']['known_facts'].append(fact(doc['id'], 'technology.current_tools', 'Epic'))
    store.update(project, project_context=p['project_context'])
    assert client.delete(f'/api/projects/{project}/documents/{doc["id"]}').status_code == 200
    memory = store.project(project, 'local-workspace')['project_context']
    assert not memory['ready_for_analysis']
    assert all(doc['id'] not in f['source_ids'] for f in memory['known_facts'])
    assert memory['document_findings'] == []


def test_analysis_failure_keeps_discovery_retryable(setup, project, monkeypatch):
    client, store, ai, _ = setup
    original = ai.generate_structured
    def generate(instruction, payload, schema):
        if schema.__name__ == 'WorkflowAnalysis':
            raise AppError('Analysis temporarily unavailable', 503)
        return original(instruction, payload, schema)
    monkeypatch.setattr(ai, 'generate_structured', generate)
    assert client.post(f'/api/projects/{project}/discovery/next').status_code == 200
    p = store.project(project, 'local-workspace')
    assert p['status'] == 'ERROR' and p['project_context']['ready_for_analysis'] and not p['busy']
    monkeypatch.setattr(ai, 'generate_structured', original)
    assert client.post(f'/api/projects/{project}/analysis/run').status_code == 202
    assert store.project(project, 'local-workspace')['status'] == 'BLUEPRINT_READY'
