"""Lossless source partitioning; no discovery history or unrelated documents."""
import hashlib
import re
from app.services.token_budget import compact_json

# Superseded revisions are retained in the stored blueprint, not sent as requirements.
HISTORY = {'solution_history', 'red_team_history', 'red_team_cycle', 'retrieval_warnings'}


def canonical_content(blueprint):
    """Native reports are rendered views of the current structured design parts.

    Uploaded documents/JSON remain intact. Unknown added report sections are kept,
    even for native blueprints. Only native, matching selected-design views qualify.
    """
    content = {k: v for k, v in blueprint['content'].items() if k not in HISTORY}
    native = 'name' not in blueprint or bool((blueprint.get('source') or {}).get('blueprint_id'))
    decision = content.get('option_decision', {})
    selected = decision.get('selected') if isinstance(decision, dict) else None
    report = content.get('final_report', {})
    parts = ('architecture_report', 'experience_report', 'data_report', 'planning_report')
    canonical = (native and selected and isinstance(report, dict) and report.get('schema_version', 0) >= 2 and
                 report.get('selected_option') == selected and all(isinstance(content.get(k), dict) and
                 content[k].get('selected_option') == selected and content[k].get('chapters') for k in parts))
    if canonical:
        # These keys are assembled by report_service from the retained source parts.
        rendered = {'executive', 'problem', 'context', 'evidence', 'stakeholders', 'current_process', 'gaps',
                    'validation', 'necessity', 'options', 'matrix', 'selection', 'scope', 'stack', 'hld', 'lld',
                    'future_process', 'journeys', 'data_model', 'apis', 'integrations', 'security', 'infrastructure',
                    'operating_model', 'roadmap', 'estimates', 'timeline', 'adoption', 'value', 'readiness',
                    'traceability', 'explainability', 'risks', 'red_team', 'conclusion', 'appendix'}
        additions = [section for section in report.get('sections', []) if section.get('key') not in rendered]
        content.pop('final_report')
        if additions:
            content['report_additions'] = additions
        content['option_decision'] = {key: value for key, value in decision.items() if key != 'criteria'}
        content['option_decision']['options'] = [option for option in decision.get('options', []) if option.get('tier') == selected]
    return content


def source_units(blueprint, project, instructions, previous=None, chunk_bytes=1800):
    units, seen = [], {}

    def add(path, value):
        text = value.strip() if isinstance(value, str) else compact_json(value)
        if not text:
            return
        # Exact long repetitions in assembled reports are aliases of one source.
        # Short cells retain their field paths so repeated labels do not lose context.
        signature = text if len(text) > 120 else path + '\n' + text
        if signature in seen:
            seen[signature]['aliases'].append(path)
            return
        pieces, piece = [], ''
        for token in re.findall(r'\S+\s*|\s+', text):
            # Handles a single enormous code/URL token without discarding bytes.
            for char in token:
                if len((piece + char).encode('utf-8')) > chunk_bytes:
                    pieces.append(piece); piece = ''
                piece += char
        if piece:
            pieces.append(piece)
        group = []
        for index, part in enumerate(pieces):
            ident = 's' + hashlib.sha256((path + ':' + str(index) + ':' + part).encode()).hexdigest()[:16]
            unit = {'id': ident, 'path': path, 'part': index + 1, 'parts': len(pieces), 'text': part, 'aliases': []}
            units.append(unit); group.append(unit)
        if group:
            seen[signature] = group[0]

    def walk(value, path):
        if isinstance(value, (dict, list)) and value and len(compact_json(value).encode('utf-8')) <= chunk_bytes:
            add(path, compact_json(value))
            return
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, path + '.' + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f'{path}[{index}]')
        elif value is not None:
            add(path, value)

    for key, value in canonical_content(blueprint).items():
        walk(value, 'blueprint.' + key)
    # An approved previous contract is relevant to changes, unlike old AI drafts.
    if previous:
        walk(previous, 'previous_spec')
    add('application.modification_request', instructions)
    if not units:
        add('project.initial_problem', project.get('initial_problem', ''))
    return units


def business_context(project):
    return {key: project.get(key) for key in ('name', 'industry', 'language', 'initial_problem') if project.get(key)}


def compact_facts(facts):
    return [{k: fact[k] for k in ('id', 'description', 'stages', 'targets')} for fact in facts]
