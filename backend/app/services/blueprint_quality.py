"""Deterministic artifact checks. A complete proposal is not a tested application."""
import yaml
from app.models.blueprint_design import DatabaseDesign, Requirement
from app.models.deliverables import Diagram, Screen


def assess(content):
    report = content.get('final_report') or {}
    sections = {s['key']: s for s in report.get('sections', [])}
    checks = []
    def check(key, label, valid, detail):
        checks.append({'key': key, 'label': label, 'status': 'passed' if valid else 'missing',
                       'detail': '' if valid else detail})
    required = {'executive', 'context', 'stakeholders', 'current_process', 'gaps', 'scope', 'options',
                'hld', 'lld', 'future_process', 'journeys', 'data_model', 'apis', 'integrations',
                'security', 'infrastructure', 'roadmap', 'estimates', 'timeline', 'adoption',
                'readiness', 'traceability', 'explainability', 'red_team'}
    check('sections', 'Complete blueprint sections', required.issubset(sections) and
          all(s.get('narrative', '').strip() for s in sections.values()),
          'Generate all required sections. Missing: ' + ', '.join(sorted(required - sections.keys())))
    for key, label, kinds in [('hld', 'High-level architecture', {'architecture'}),
                              ('future_process', 'Workflow and decision paths', {'swimlane', 'decision_tree'}),
                              ('data_model', 'Entity relationship diagram', {'er'}),
                              ('integrations', 'Integration data flow', {'data_flow'}),
                              ('infrastructure', 'Deployment architecture', {'architecture'})]:
        section = sections.get(key, {})
        excluded = section.get('applicability') == 'not_applicable' and bool(section.get('narrative'))
        check(key, label, excluded or kinds.issubset({d['kind'] for d in section.get('diagrams', [])}),
              'Regenerate this section to include its required diagram, or document a justified exclusion.')
    diagrams = [d for s in sections.values() for d in s.get('diagrams', [])]
    try:
        for d in diagrams:
            Diagram.model_validate(d)
        visuals_valid = bool(diagrams)
    except ValueError:
        visuals_valid = False
    check('diagram_references', 'Valid diagram nodes and connections', visuals_valid,
          'A diagram has missing nodes, invalid connections or unsupported content. Edit or regenerate it.')
    ux = sections.get('journeys', {})
    try:
        for screen in ux.get('screens', []):
            Screen.model_validate(screen)
        wireframes = bool(ux.get('screens')) or ux.get('applicability') == 'not_applicable'
    except ValueError:
        wireframes = False
    check('wireframes', 'Actual screen wireframes', wireframes, 'Generate the wireframes chapter for the application screens.')
    data = content.get('data_report', {})
    db_chapter = next((c for c in data.get('chapters', []) if c['key'] == 'database'), {})
    try:
        design = DatabaseDesign.model_validate(data.get('database_design'))
        canonical = set(content.get('architecture_report', {}).get('entity_names', []))
        valid = {e.name for e in design.entities} == canonical
        # Compare the rendered ER, SQL and column catalogue against the same source.
        from app.services.blueprint_contract import database_artifacts
        artifacts = database_artifacts(design.model_dump())
        section = sections.get('data_model', {})
        valid = valid and artifacts['diagram'] in section.get('diagrams', []) and artifacts['sql'] in section.get('code_assets', [])
        valid = valid and all(t in section.get('tables', []) for t in artifacts['tables'])
    except ValueError:
        valid = False
    check('database_schema', 'Database schema, keys and ER agreement', valid or db_chapter.get('applicability') == 'not_applicable',
          'Provide a validated database_design with canonical entities, columns, PK/FK, indexes, retention and migration decisions.')
    operations = set()
    api_section = sections.get('apis', {})
    api_valid = False
    for asset in api_section.get('code_assets', []):
        if asset.get('language') not in ('yaml', 'json'):
            continue
        try:
            spec = yaml.safe_load(asset['content'])
            if not isinstance(spec, dict) or not str(spec.get('openapi', '')).startswith('3.') or not spec.get('info') or not spec.get('paths'):
                continue
            for path, methods in spec['paths'].items():
                if not isinstance(path, str) or not path.startswith('/') or not isinstance(methods, dict):
                    raise ValueError('Invalid API path')
                for method, operation in methods.items():
                    if method in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}:
                        if not isinstance(operation, dict) or not operation.get('responses'):
                            raise ValueError('API response contract missing')
                        operations.add(method.upper() + ' ' + path)
            api_valid = bool(operations)
        except (ValueError, TypeError, AttributeError, yaml.YAMLError, RecursionError):
            api_valid = False
    check('api_contract', 'OpenAPI specification', api_valid or api_section.get('applicability') == 'not_applicable',
          'Generate parseable OpenAPI 3 with paths, methods and response contracts.')
    architecture = content.get('architecture_report', {})
    try:
        requirements = [Requirement.model_validate(r) for r in architecture.get('requirements', [])]
        valid = bool(requirements) and len({r.id for r in requirements}) == len(requirements)
        for r in requirements:
            valid = valid and set(r.components).issubset(architecture.get('component_names', [])) and set(r.entities).issubset(architecture.get('entity_names', [])) and set(r.api_operations).issubset(operations)
    except ValueError:
        valid = False
    check('traceability', 'Requirement IDs and implementation traceability', valid,
          'Map unique requirements to declared components/entities/API operations and proposed acceptance tests.')
    check('red_team', 'Independent Red Team review', bool(content.get('red_team_history')) and not content.get('review_pending') and content.get('review_gate') in ('passed', 'conditional'),
          'Run Red Team review on this version and resolve its blocking findings before approval.')
    return {'complete': all(c['status'] == 'passed' for c in checks), 'checks': checks}
