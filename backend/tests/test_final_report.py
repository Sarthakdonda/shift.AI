import copy
import io
import json
import zipfile
import pytest
from docx import Document
from pypdf import PdfReader
from pydantic import ValidationError
from app.models.final_report import OptionDecision, Estimate, PART_SCHEMAS, validate_consistency
from app.services.export_service import export
from app.services.report_service import assemble_report
from app.workflows.shift_graph import build_graph
from tests.fakes import FakeGemini
from tests.report_fixtures import decision_fixture, estimate, part_fixture


def generated():
    context = {'project': {'name':'Invoice pilot — synthetic example', 'industry':'Business operations',
                          'initial_problem':'Reduce duplicate invoice entry using validated records.'},
               'output_language':'English', 'previous_discovery':None}
    result = build_graph(FakeGemini(), lambda *_: None).invoke({'context':context,'red_team_cycle':0,'red_team_history':[]})
    result['evidence'] = [{'category':'workflow','fact':'Manual duplicate invoice entry.','source':'Synthetic user message'}]
    result['final_report'] = assemble_report(result, context)
    return result


def test_complete_report_and_editable_exports():
    content = generated()
    report = content['final_report']
    assert len(report['sections']) == 34  # Cover + 34 ordered sections from the specification.
    assert len({s['key'] for s in report['sections']}) == 34
    assert all(s['narrative'] and s['basis'] for s in report['sections'])
    assert report['selected_option'] == 'balanced'
    text = json.dumps(report).lower()
    assert all(word not in text for word in ['hospital','hipaa','fhir','patient'])
    assert 'wireframes' in text and '0..many' in text
    for item in content['solution']['data_flow'] + content['solution']['data_requirements']:
        assert item.lower() in text
    doc = Document(io.BytesIO(export(report['title'], content, 'docx')))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert any('Three solution options' in h for h in headings)
    assert any('34. Appendix' in h for h in headings)
    assert len(doc.tables) > 30
    markdown = export(report['title'], content, 'md').decode()
    assert 'low_level_schema' not in markdown and 'component_refs' not in markdown
    assert 'Evidence / assumptions' in markdown and 'Invoice · id PK' in markdown
    archive = zipfile.ZipFile(io.BytesIO(export(report['title'], content, 'zip')))
    assert {'schema.sql','openapi.yaml','report.md','deliverable.json'}.issubset(archive.namelist())
    assert any(n.endswith('.bpmn') for n in archive.namelist())


def test_pdf_contains_complete_report_and_handles_long_table_cells():
    content = generated()
    report = content['final_report']
    report['sections'][0]['narrative'] += ' Literal <tag> & source text.'
    report['sections'][0]['tables'].append({
        'title': 'Long table', 'columns': ['Details'],
        'rows': [['Long cell content. ' * 1200 + 'END OF LONG CELL']],
    })
    payload = export(report['title'], content, 'pdf')
    assert payload.startswith(b'%PDF-')
    pdf = PdfReader(io.BytesIO(payload))
    text = '\n'.join(page.extract_text() for page in pdf.pages)
    assert len(pdf.pages) > 1
    assert pdf.metadata.title == report['title']
    for section in report['sections']:
        assert section['title'] in ' '.join(text.split())
    assert 'Literal <tag> & source text.' in text
    assert 'END OF LONG CELL' in text
    assert 'Evidence / assumptions:' in text
    assert 'schema.sql' in text


def test_pdf_supports_legacy_blueprints():
    payload = export('Legacy blueprint', {'summary': 'Original saved analysis.'}, 'pdf')
    text = PdfReader(io.BytesIO(payload)).pages[0].extract_text()
    assert 'Legacy blueprint' in text
    assert 'Original saved analysis.' in text


@pytest.mark.parametrize('change', ['weight', 'duplicate_tier', 'winner', 'duplicate_scope', 'missing_score', 'rejection'])
def test_invalid_decision_rejected(change):
    data = decision_fixture()
    if change == 'weight': data['criteria'][0]['weight'] += 1
    if change == 'duplicate_tier': data['options'][0]['tier'] = 'balanced'
    if change == 'winner': data['selected'] = 'advanced'
    if change == 'duplicate_scope': data['options'][0]['scope'] = data['options'][1]['scope']
    if change == 'missing_score': data['criteria'][0]['scores'].pop()
    if change == 'rejection': data['rejection_reasons'][0]['tier'] = 'balanced'
    with pytest.raises(ValidationError): OptionDecision.model_validate(data)


def test_scores_computed_not_model_supplied_and_unknown_estimates():
    decision = OptionDecision.model_validate(decision_fixture())
    assert decision.totals() == {'lean':76.0,'balanced':88.0,'advanced':50.0}
    assert Estimate.model_validate(estimate('Vendor cost','Unconfirmed currency')).low is None
    for updates in [{'low':10,'high':2}, {'low':None,'high':2}, {'low':None,'high':None,'confidence':'high'}]:
        with pytest.raises(ValidationError): Estimate.model_validate({**estimate('Cost','USD'),**updates})


def test_provider_schema_preserves_property_names_and_local_validation():
    schema = PART_SCHEMAS['architecture_report'].provider_json_schema()
    assert 'title' in schema['$defs']['Chapter']['properties']
    assert 'title' in schema['$defs']['Table']['properties']
    assert 'maxItems' not in schema['properties']['chapters']
    assert schema['properties']['selected_option']['enum'] == ['lean', 'balanced', 'advanced']
    def inspect(node):
        if isinstance(node, dict):
            if 'properties' in node: assert set(node.get('required',[])).issubset(node['properties'])
            for child in node.values(): inspect(child)
        if isinstance(node, list):
            for child in node: inspect(child)
    inspect(schema)
    assert PART_SCHEMAS['architecture_report'].model_fields['chapters'].metadata


@pytest.mark.parametrize('change', ['option','component','entity','integration','ai','chapter','diagram','wireframe'])
def test_cross_section_and_completeness_gates(change):
    data = generated()
    if change == 'option': data['data_report']['selected_option'] = 'lean'
    if change == 'component': data['architecture_report']['component_names'] = ['Wrong component']
    if change == 'entity': data['data_report']['chapters'][0]['entity_refs'] = ['Patient']
    if change == 'integration': data['data_report']['chapters'][0]['integration_refs'] = ['Unlisted API']
    if change == 'ai': data['solution']['components'][0]['uses_ai'] = True
    if change == 'chapter': data['planning_report']['chapters'].pop()
    if change == 'diagram': next(c for c in data['architecture_report']['chapters'] if c['key']=='hld')['diagrams'] = []
    if change == 'wireframe': next(c for c in data['experience_report']['chapters'] if c['key']=='wireframes')['screens'] = []
    with pytest.raises(ValueError): validate_consistency(data['option_decision'], data['solution'], data)


def test_process_only_can_explain_inapplicable_custom_design():
    data = part_fixture('DataReport')
    for chapter in data['chapters']:
        chapter.update(applicability='not_applicable', narrative='No custom database or integration is needed: configure the existing process.', diagrams=[],screens=[],code_assets=[],tables=[])
    PART_SCHEMAS['data_report'].model_validate(data)
    data['chapters'][0]['narrative'] = ''
    with pytest.raises(ValidationError): PART_SCHEMAS['data_report'].model_validate(data)


def test_blueprint_export_uses_requested_saved_version(setup, project):
    client, store, *_ = setup
    client.post(f'/api/projects/{project}/discovery/next')
    first = client.get(f'/api/projects/{project}/blueprint').json()
    second = copy.deepcopy(first['content'])
    second['final_report']['title'] = 'Later design'
    store.save_blueprint(project, second)
    original = client.get(f'/api/projects/{project}/export/blueprint/json?version=1')
    assert original.status_code == 200
    assert original.json()['final_report']['title'] == 'Invoice operations'
    assert client.get(f'/api/projects/{project}/export/blueprint/json?version=2').json()['final_report']['title'] == 'Later design'
    assert client.get(f'/api/projects/{project}/export/blueprint/json?version=900').status_code == 404
    pdf = client.get(f'/api/projects/{project}/export/blueprint/pdf?version=1')
    assert pdf.status_code == 200
    assert pdf.headers['content-type'] == 'application/pdf'
    assert pdf.headers['content-disposition'] == 'attachment; filename="shift-ai-deliverable-v1.pdf"'
    assert PdfReader(io.BytesIO(pdf.content)).metadata.title == 'Invoice operations'
    assert client.get(f'/api/projects/{project}/export/blueprint/pdf?version=900').status_code == 404


def test_failed_report_generation_preserves_previous_blueprint(setup, project, monkeypatch):
    client, store, ai, _ = setup
    client.post(f'/api/projects/{project}/discovery/next')
    previous = store.latest('blueprints', project)
    original = ai.generate_structured
    def invalid(instruction, context, schema):
        if schema.__name__ == 'PlanningReport': raise ValueError('Incomplete provider draft')
        return original(instruction, context, schema)
    monkeypatch.setattr(ai, 'generate_structured', invalid)
    client.post(f'/api/projects/{project}/analysis/run')
    assert store.latest('blueprints', project) == previous
    assert store.project(project, 'local-workspace')['status'] == 'ERROR'
    assert not store.project(project, 'local-workspace')['busy']


def test_red_team_repairs_only_planning_and_verifies_actual_change():
    from app.models.schemas import RedTeam
    class Reviewer(FakeGemini):
        def generate_structured(self, instruction, context, schema):
            if schema is RedTeam:
                self.calls.append('RedTeam')
                if not context.get('review_ledger'):
                    return schema.model_validate({'summary': 'Missing pilot exit gate.', 'findings': [{
                        'category': 'DELIVERY', 'severity': 'HIGH', 'issue': 'No reconciliation gate',
                        'reason': 'The pilot needs an explicit exit condition.', 'mitigation': 'Add reconciliation before rollout.',
                        'requires_revision': True, 'action': 'revise', 'affected_sections': ['timeline'],
                        'decision': 'Require reconciliation before rollout.', 'validation': 'Timeline contains a gate.'}]})
                fid = context['review_ledger'][0]['id']
                return schema.model_validate({'summary': 'The exit gate is now in the timeline.', 'findings': [],
                    'assessments': [{'finding_id': fid, 'status': 'fixed', 'rationale': 'Rollout is gated on reconciliation.',
                                     'section': 'timeline', 'quote': 'Reconcile every pilot invoice before rollout.'}]})
            result = super().generate_structured(instruction, context, schema)
            if schema.__name__ == 'PlanningReport' and context.get('revision_plan'):
                next(c for c in result.chapters if c.key == 'timeline').narrative = 'Reconcile every pilot invoice before rollout.'
            return result
    ai = Reviewer()
    result = build_graph(ai, lambda *_: None).invoke({'context': {}}, {'recursion_limit': 45})
    assert result['review_gate'] == 'passed'
    assert result['review_ledger'][0]['status'] == 'fixed'
    assert ai.calls.count('PlanningReport') == 2
    assert ai.calls.count('Solution') == ai.calls.count('ArchitectureReport') == ai.calls.count('DataReport') == 1
    change = result['design_changes'][0]
    assert change['changed_sections'] == ['timeline']
    assert change['diffs'][0]['before'] != change['diffs'][0]['after']
    assert change['finding_ids'] == [result['review_ledger'][0]['id']]


def test_red_team_omission_and_fabricated_evidence_cannot_close_findings():
    from app.models.schemas import RedTeam
    from app.workflows.review import reconcile, review_gate
    original = FakeGemini(always_revise=True).generate_structured('', {}, RedTeam).model_dump()
    state = {'red_team_cycle': 0, 'solution': {'summary': 'A real design statement exists here.'}}
    ledger = reconcile(state, original)
    state['review_ledger'] = ledger
    omitted = reconcile(state, {'findings': [], 'assessments': []})
    assert omitted[0]['status'] == 'open' and review_gate(omitted) == 'blocked'
    assessment = {'finding_id': ledger[0]['id'], 'status': 'fixed', 'rationale': 'Fixed.',
                  'section': 'solution', 'quote': 'This fabricated fix never existed.', 'residual_risk': ''}
    result = reconcile(state, {'findings': [], 'assessments': [assessment]})
    assert result[0]['status'] == 'open'
    # Even a real quote does not prove a design changed.
    assessment['quote'] = state['solution']['summary']
    assert reconcile(state, {'findings': [], 'assessments': [assessment]})[0]['status'] == 'open'

    # A later edit invalidates a prior verification until the reviewer checks it again.
    state['review_ledger'][0].update(status='fixed', verified_section='solution')
    state['design_changes'] = [{'cycle': 1, 'changed_sections': ['solution']}]
    assert reconcile(state, {'findings': [], 'assessments': []})[0]['status'] == 'open'


def test_red_team_can_reconsider_the_selected_option():
    from app.models.schemas import RedTeam
    class Reconsider(FakeGemini):
        def generate_structured(self, instruction, context, schema):
            result = super().generate_structured(instruction, context, schema)
            if schema is RedTeam:
                result.findings[0].requires_revision = not bool(context.get('revision_plan'))
                result.findings[0].action = 'reconsider_solution'
                result.findings[0].affected_sections = ['option_decision']
            elif schema.__name__ == 'DecisionMatrix' and context.get('revision_plan'):
                result.selected = 'lean'
                result.selection_reason = 'Choose the lean option after review.'
                for criterion in result.criteria:
                    for score in criterion.scores:
                        if score.tier in ('lean', 'balanced'):
                            score.tier = 'lean' if score.tier == 'balanced' else 'balanced'
                for reason in result.rejection_reasons:
                    if reason.tier == 'lean':
                        reason.tier = 'balanced'
            elif schema.__name__ in ('ArchitectureReport', 'ExperienceReport', 'DataReport', 'PlanningReport') and context.get('revision_plan'):
                result.selected_option = 'lean'
            return result
    # Keep the fixture's comparison internally valid when changing selection.
    ai = Reconsider()
    result = build_graph(ai, lambda *_: None).invoke({'context': {}}, {'recursion_limit': 45})
    assert result['option_decision']['selected'] == 'lean'
    assert ai.calls.count('Necessity') == 2
    assert ai.calls.count('Option') == 6
    assert 'option_decision' in result['design_changes'][0]['changed_sections']


def test_unresolved_review_blocks_export_even_after_cycle_limit():
    from app.services.report_service import assemble_report
    state = build_graph(FakeGemini(always_revise=True), lambda *_: None).invoke({'context': {}}, {'recursion_limit': 45})
    assert state['review_run_cycle'] == 3
    assert state['review_gate'] == 'blocked'
    report = assemble_report(state, {'project': {'name': 'Pilot', 'initial_problem': 'Invoice workflow'}, 'output_language': 'English'})
    assert 'DRAFT' in report['sections'][0]['narrative']
    assert all(f['status'] == 'open' for f in state['review_ledger'])
