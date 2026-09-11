from types import SimpleNamespace
from app.models.schemas import *


class FakeGemini:
    """Deterministic provider used only by tests, never by the application."""
    settings = SimpleNamespace(vector_search_enabled=False)
    def __init__(self, always_revise=False):
        self.calls = []
        self.always_revise = always_revise

    def require(self):
        return self

    def availability(self, model=None):
        return {'model': model, 'configured_connections': 2, 'available_connections': 2, 'status': 'available',
                'retry_after_seconds': None, 'retry_at': None, 'remaining_requests': None, 'request_limit': None,
                'reset_at': None, 'quota_note': 'Exact remaining requests and quota resets are not reported by this API. View your project limits in Google AI Studio.',
                'quota_url': 'https://aistudio.google.com/usage?tab=rate-limit'}

    def generate_structured(self, instruction, context, schema):
        self.calls.append(schema.__name__)
        from tests.report_fixtures import decision_fixture, part_fixture
        if schema.__name__ == 'OptionDecision': return schema.model_validate(decision_fixture())
        if schema.__name__ == 'Option': return schema.model_validate(next(o for o in decision_fixture()['options'] if o['tier'] == context['requested_tier']))
        if schema.__name__ == 'DecisionMatrix': return schema.model_validate(decision_fixture())
        if schema.__name__ in ('ArchitectureReport', 'ExperienceReport', 'DataReport', 'PlanningReport'):
            return schema.model_validate(part_fixture(schema.__name__))
        if schema.__name__ == 'Deliverable':
            return schema.model_validate(deliverable_fixture())
        if schema.__name__ == 'TranslationOutput':
            return schema.model_validate({'translations':['Translated: '+text for text in context]})
        finding = {'category': 'INTEGRATION', 'severity': 'HIGH', 'issue': 'Accounting API access is not confirmed', 'reason': 'The supplied workflow names an accounting tool but no available API.', 'mitigation': 'Validate API access before implementation; use a reviewed CSV import as fallback.', 'requires_revision': self.always_revise}
        evidence = {'title': 'Duplicate entry', 'description': 'Staff retype the same invoice data.', 'evidence': ['User message: invoices copied from email to spreadsheet.'], 'confidence': 0.9}
        dimension = {'score': 75, 'reason': 'Validate access in a small pilot.'}
        source_id = context.get('latest_user_message', {}).get('id', 'test-message') if isinstance(context, dict) else 'test-message'
        values = {
            'Discovery': {'collected_information': [{'category': 'workflow', 'topic': 'workflow.entry', 'fact': 'Staff retype invoice data', 'source': 'User message', 'source_ids': [source_id]}], 'missing_information': [], 'critical_missing': [], 'scores': {k: 80 for k in Scores.model_fields}, 'enough_information': True, 'next_question': '', 'next_questions': [], 'assumptions': [], 'unknowns': [], 'answered_topics': [], 'information_sufficiency': 80, 'readiness_reason': 'Test fixture supplies the workflow, problem and outcome.'},
            'DocumentSummary': {'summary': 'Invoice processing uses email and a shared spreadsheet.', 'facts': [{'category': 'technology', 'fact': 'A shared spreadsheet tracks invoices', 'source': 'workflow.txt, page 1'}]},
            'WorkflowAnalysis': {'business_context': 'The operations team processes invoices.', 'current_system': {'people': ['Operations staff'], 'process': 'Copy invoice details, review, then import.', 'technology': ['Email', 'Spreadsheet'], 'data': ['Invoice records']}, 'workflow': [{'name': 'Receive invoice', 'owner': 'Operations staff', 'description': 'Read incoming email.', 'tools': ['Email']}, {'name': 'Record details', 'owner': 'Operations staff', 'description': 'Retype invoice details.', 'tools': ['Spreadsheet']}], 'bottlenecks': [evidence]},
            'RootCause': {'user_request': 'Use AI for invoices', 'root_problem': 'Duplicate entry between disconnected tools', 'root_causes': [evidence], 'assumptions': ['API access requires validation.']},
            'Necessity': {'classification': 'AUTOMATION_SUFFICIENT', 'score': 15, 'reasoning': ['The supplied workflow follows fixed rules.'], 'non_ai_alternative': 'Validate and import structured invoice records using deterministic rules.', 'recommended_approach': 'Automate validated imports with human exception review.', 'confidence': 0.85},
            'Solution': {'title': 'A simpler invoice workflow', 'summary': 'Replace duplicate entry with reviewed imports.', 'solution_type': 'CUSTOM_AUTOMATION', 'components': [{'name': 'Invoice importer', 'responsibility': 'Validate and import structured records.', 'uses_ai': False, 'reason': 'Fields follow deterministic rules.'}], 'data_flow': ['Invoice arrives', 'Validate fields', 'Human approves', 'Import accounting record'], 'data_requirements': ['Structured invoice records'], 'integrations': ['Accounting API access to be validated'], 'human_in_loop': ['Review exceptions and approve imports'], 'constraints': ['Do not automate payments'], 'assumptions': ['CSV import is supported; validate before implementation'], 'complexity': 'LOW', 'roadmap': [{'phase': '01', 'title': 'Validate a small pilot', 'actions': ['Confirm import format', 'Test duplicate handling'], 'exit_criteria': 'Pilot imports reconcile with source invoices'}], 'success_metrics': ['Track duplicate entry count before and after pilot']},
            'RedTeam': {'summary': 'Confirm integration access before building.', 'findings': [finding]},
            'BusinessValue': {'summary': 'Less duplicate entry; savings must be measured.', 'metrics': [{'metric': 'Manual entry', 'estimate': 'Potential reduction, not yet quantified', 'basis': 'No measured time baseline was supplied.', 'is_assumption': True}], 'feasibility': {**{k: dimension for k in ['technical', 'data', 'integration', 'operational', 'business']}, 'overall': 75}, 'risks': [finding]},
            'Conclusion': {'executive_summary': 'The bottleneck is duplicate entry, not reasoning complexity.', 'recommendation': 'Pilot deterministic imports with staff review.', 'next_steps': ['Confirm integration access', 'Measure the current workload']},
        }
        return schema.model_validate(values[schema.__name__])


def deliverable_fixture():
    """Schema-rich fixture for renderer/export tests, not evidence of model quality."""
    nodes=[{'id':'receive','label':'Receive invoice','lane':'Operations','kind':'start'},
           {'id':'review','label':'Approve invoice?','lane':'Reviewer','kind':'decision'},
           {'id':'record','label':'Record approved invoice','lane':'Operations','kind':'end'}]
    edges=[{'source':'receive','target':'review','label':'Validate'}, {'source':'review','target':'record','label':'Approved'}]
    return {'title':'Invoice transformation design','summary':'Replace duplicate entry with reviewed structured imports.',
        'sections':[{'title':'Current and future state','narrative':'Current: manual retyping. Future: validated import with human review.',
                     'items':['Measure entry time before estimating savings.'],
                     'tables':[{'title':'Estimate assumptions','columns':['Work item','Days'], 'rows':[['Pilot validation','5 (assumption)']]}]}],
        'diagrams':[{'title':kind.replace('_',' ').title(),'kind':kind,'nodes':nodes,'edges':edges} for kind in ['architecture','data_flow','bpmn','swimlane','decision_tree','er']],
        'screens':[{'name':name,'persona':'Operations reviewer','purpose':'Review invoice records.',
                    'controls':[{'label':'Review queue','kind':'table','detail':'Invoice, amount, status'}, {'label':'Approve','kind':'button','detail':'Confirm a validated import'}]} for name in ['Overview','Review invoice','Import history']],
        'code_assets':[{'filename':'schema.sql','language':'sql','content':'CREATE TABLE invoice (id INTEGER PRIMARY KEY, status VARCHAR(20) NOT NULL);'},
                       {'filename':'openapi.yaml','language':'yaml','content':'openapi: 3.0.3\ninfo:\n  title: Invoice pilot\n  version: 1.0.0\npaths:\n  /invoices:\n    get:\n      responses:\n        "200":\n          description: Invoice list\n'}],
        'assessments':[{'dimension':d,'rating':'unknown','reason':'No validated baseline supplied.','evidence':['Source message describes manual entry, without a measured baseline.']} for d in ['digital_maturity','ai_readiness','implementation_readiness','solution_quality','automation_opportunity']],
        'assumptions':['API access and five-day pilot estimate require validation.'],
        'validation_steps':['Reconcile imports against source invoices and test duplicate rejection.']}
