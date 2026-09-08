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

    def generate_structured(self, instruction, context, schema):
        self.calls.append(schema.__name__)
        finding = {'category': 'INTEGRATION', 'severity': 'HIGH', 'issue': 'Accounting API access is not confirmed', 'reason': 'The supplied workflow names an accounting tool but no available API.', 'mitigation': 'Validate API access before implementation; use a reviewed CSV import as fallback.', 'requires_revision': self.always_revise}
        evidence = {'title': 'Duplicate entry', 'description': 'Staff retype the same invoice data.', 'evidence': ['User message: invoices copied from email to spreadsheet.'], 'confidence': 0.9}
        dimension = {'score': 75, 'reason': 'Validate access in a small pilot.'}
        values = {
            'Discovery': {'collected_information': [{'category': 'workflow', 'fact': 'Staff retype invoice data', 'source': 'User message'}], 'missing_information': [], 'critical_missing': [], 'scores': {k: 80 for k in Scores.model_fields}, 'enough_information': True, 'next_question': 'We have enough context. You can run analysis now.'},
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
