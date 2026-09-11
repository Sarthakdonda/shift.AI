"""Assemble one ordered, reviewable report from validated generation stages."""
from app.models.final_report import OptionDecision, PART_SCHEMAS, validate_consistency


def table(title, columns, rows):
    return {'title': title, 'columns': columns, 'rows': [[str(v) for v in row] for row in rows]}


def chapter(key, title, narrative, items=None, tables=None, diagrams=None, basis='Proposed design / advisory analysis; validate against the evidence register.'):
    return {'key': key, 'title': title, 'narrative': narrative, 'items': items or [], 'tables': tables or [],
            'diagrams': diagrams or [], 'screens': [], 'code_assets': [], 'basis': basis,
            'applicability': 'applicable', 'component_refs': [], 'entity_refs': [], 'integration_refs': []}


def estimate_text(e):
    amount = 'Unknown — requires validation' if e['low'] is None else f"{e['low']:g}–{e['high']:g} {e['unit']}"
    return f"{amount}. Basis: {e['basis']} Confidence: {e['confidence']}. Assumptions: {'; '.join(e['assumptions'])}"


def finding_tables(findings):
    return [table(f['issue'], ['Review field', 'Assessment'], [
        ['Category / severity', f"{f['category']} / {f['severity']}"], ['Finding / impact', f['reason']],
        ['Mitigation', f['mitigation']], ['Status', 'Requires further attention' if f['requires_revision'] else 'Mitigation proposed; validate before implementation'],
    ]) for f in findings]


def merge_chapters(title, *chapters):
    merged = dict(chapters[0])
    merged['title'] = title
    merged['applicability'] = 'not_applicable' if all(c['applicability'] == 'not_applicable' for c in chapters) else 'applicable'
    merged['narrative'] = '\n\n'.join(c['title'] + (' — Not applicable' if c['applicability'] == 'not_applicable' else '') + ': ' + c['narrative'] for c in chapters)
    merged['basis'] = '\n'.join(c['title'] + ': ' + c['basis'] for c in chapters)
    for key in ('items', 'tables', 'diagrams', 'screens', 'code_assets', 'component_refs', 'entity_refs', 'integration_refs'):
        merged[key] = [value for c in chapters for value in c[key]]
    return merged


def assemble_report(content, context):
    validate_consistency(content['option_decision'], content['solution'], content)
    project = context['project']
    decision = OptionDecision.model_validate(content['option_decision'])
    generated = {c['key']: c for key in PART_SCHEMAS for c in content[key]['chapters']}
    w, r, s, n, v = (content[k] for k in ('workflow_analysis', 'root_cause', 'solution', 'ai_necessity', 'business_value'))
    conclusion, planning = content['conclusion'], content['planning_report']
    evidence = content.get('evidence', [])
    # Preserve the original reviewed solution detail as well as the richer design.
    generated['hld'] = {**generated['hld'], 'items': [*generated['hld']['items'], *['Data flow: ' + x for x in s['data_flow']]],
        'tables': [*generated['hld']['tables'], table('Reviewed solution components', ['Component', 'Responsibility / rationale'],
            [[c['name'], f"{c['responsibility']} Why: {c['reason']} ({'AI' if c['uses_ai'] else 'Non-AI'} component)"] for c in s['components']])]}
    for key, values in [('data_model', s['data_requirements']), ('integrations', s['integrations']), ('operating_model', s['human_in_loop'])]:
        generated[key] = {**generated[key], 'items': list(dict.fromkeys([*generated[key]['items'], *values]))}
    out = []
    add = out.append
    add(chapter('executive', 'Executive summary', conclusion['executive_summary']))
    add(chapter('problem', 'Original request and underlying problem', project['initial_problem'],
                [f"Normalized problem: {r['root_problem']}", f"Requested solution: {r['user_request']}"]))
    add(chapter('context', 'Business context, objectives and success definition', w['business_context'], s['success_metrics']))
    add(chapter('evidence', 'Evidence register and confidence policy',
        'Source-backed facts are attributed below. Proposed designs are recommendations, inferred assumptions are not confirmed facts, and estimates are planning ranges. Unknown facts, vendor access and applicable regulations require validation. Readiness scores are advisory heuristics.',
        content.get('retrieval_warnings', []), [table('Source register', ['Category', 'Fact', 'Source'],
            [[f.get('category', f.get('topic', 'Evidence')), f['fact'], f['source']] for f in evidence])] if evidence else [],
        basis='User messages and uploaded documents. No independent verification is implied.'))
    stakeholders = dict(generated['stakeholders'])
    stakeholders['title'] = 'Stakeholders and current system'
    stakeholders['tables'] = [*stakeholders['tables'], table('People, process, technology and data', ['Aspect', 'Current state'],
        [[k.title(), '; '.join(val) if isinstance(val, list) else val] for k, val in w['current_system'].items()])]
    add(stakeholders)
    steps = w['workflow']
    diagram = {'title': 'Current-state process map', 'kind': 'workflow',
        'nodes': [{'id': f'step_{i}', 'label': x['name'], 'lane': x['owner'], 'kind': 'task'} for i, x in enumerate(steps)],
        'edges': [{'source': f'step_{i}', 'target': f'step_{i+1}', 'label': 'Next step'} for i in range(len(steps)-1)]}
    add(chapter('current_process', 'Current-state workflow', w['current_system']['process'],
        tables=[table('Current activities', ['Step / owner', 'Activity / tools'],
            [[f"{i+1}. {x['name']} — {x['owner']}", x['description'] + ' Tools: ' + ', '.join(x['tools'])] for i, x in enumerate(steps)])] if steps else [],
        diagrams=[diagram] if steps else []))
    add(chapter('gaps', 'Bottlenecks, gaps and root causes', r['root_problem'], tables=[
        table(x['title'], ['Analysis', 'Detail'], [['Finding', x['description']], ['Evidence', '; '.join(x['evidence'])],
            ['Confidence', f"{round(x['confidence']*100)}% advisory"]]) for x in [*w['bottlenecks'], *r['root_causes']]]))
    discovery = context.get('previous_discovery') or {}
    unresolved = list(dict.fromkeys([*r['assumptions'], *discovery.get('missing_information', []), *planning['unresolved_items']]))
    add(chapter('validation', 'Validation gaps and unanswered questions',
        'Resolve these items with the named stakeholders before committing to implementation.' if unresolved else 'No additional unanswered questions were recorded; proposed designs still require stakeholder validation.', unresolved))
    add(chapter('necessity', 'AI necessity and automation opportunities', n['recommended_approach'],
        [f"Decision: {n['classification']} · AI necessity {n['score']}/100 · confidence {round(n['confidence']*100)}%",
         *n['reasoning'], 'Non-AI alternative: ' + n['non_ai_alternative']]))
    option_tables = []
    for option in decision.options:
        d = option.model_dump()
        rows = [[label, '\n'.join(d[key]) if isinstance(d[key], list) else str(d[key])] for key, label in [
            ('scope', 'Problem coverage / scope'), ('included', 'Included'), ('excluded', 'Excluded'),
            ('approach', 'Technology / implementation'), ('integrations_and_data', 'Integrations / data'),
            ('security_and_governance', 'Security / privacy / governance'), ('team_and_ownership', 'Team / ownership'),
            ('benefits', 'Benefits / outcomes'), ('limitations', 'Limitations / trade-offs'),
            ('risks_and_mitigations', 'Risks / mitigations'), ('scalability', 'Scalability'), ('best_fit', 'Best fit'), ('avoid_when', 'Do not select when')]]
        rows.insert(3, ['AI usage', f"{d['ai_usage']}: {d['ai_reason']}"])
        rows.extend([[label, estimate_text(d[key])] for key, label in [('effort', 'Effort estimate'), ('cost', 'Cost estimate'), ('duration', 'Delivery range')]])
        option_tables.append(table(option.tier.title() + ': ' + option.title, ['Comparison field', 'Option detail'], rows))
    add(chapter('options', 'Three solution options', 'Compare scope, cost, delivery and operating trade-offs before selecting the implementation path.', tables=option_tables))
    matrix = [table('Weighted scores', ['Criterion / weight', 'Lean', 'Balanced', 'Advanced'], [
        [f'{c.name} ({c.weight}%)', *[str(next(x.score for x in c.scores if x.tier == t)) for t in ('lean','balanced','advanced')]] for c in decision.criteria] +
        [['Total / 100', *[str(decision.totals()[t]) for t in ('lean','balanced','advanced')]]])]
    matrix.extend(table(c.name, ['Decision basis', 'Explanation'], [['Weight basis', c.basis],
        *[[x.tier.title(), f'{x.score}/5 — {x.reason}'] for x in c.scores]]) for c in decision.criteria)
    add(chapter('matrix', 'Option comparison and weighted decision matrix',
        'Weights total 100%. Scores run from 1 (weakest fit) to 5 (best fit). Total = sum(weight × score) ÷ 5, calculated by shift.AI. Scores and assumed priorities require stakeholder validation.', tables=matrix))
    add(chapter('selection', 'Recommended option and rejected alternatives', decision.selected.title() + ': ' + decision.selection_reason,
        [s['title'] + ': ' + s['summary'], f"Solution type: {s['solution_type']} · Complexity: {s['complexity']}",
         *[x.tier.title() + ' rejected: ' + x.reason for x in decision.rejection_reasons], *['Decision sensitivity: ' + x for x in decision.decision_sensitivities]]))
    for key in ('scope','stack','hld','lld','future_process'):
        add(generated[key])
    ux = merge_chapters('User journeys, navigation and wireframes', generated['journeys'], generated['wireframes'])
    add(ux)
    data = merge_chapters('Data model, ER diagram and database schema', generated['data_model'], generated['database'])
    add(data)
    for key in ('apis', 'integrations', 'security'):
        add(generated[key])
    infra = merge_chapters('Infrastructure, cloud and deployment architecture', generated['infrastructure'], generated['deployment'])
    add(infra)
    add(generated['operating_model'])
    add(chapter('roadmap', 'Implementation roadmap', s['summary'], tables=[
        table(p['phase'] + ': ' + p['title'], ['Actions', 'Ready when'], [['\n'.join(p['actions']), p['exit_criteria']]]) for p in s['roadmap']]))
    estimates = merge_chapters('Effort, cost and resource estimates', generated['estimates'], generated['resources'])
    estimates['items'] = [*estimates['items'], *[e['label'] + ': ' + estimate_text(e) for e in planning['estimates']]]
    add(estimates)
    timeline = merge_chapters('Timeline, milestones and sprint / release plan', generated['timeline'], generated['releases'])
    add(timeline)
    add(generated['adoption'])
    add(chapter('value', 'Success KPIs and business value', v['summary'], s['success_metrics'],
        [table('Business value estimates', ['Metric', 'Estimate / basis'], [[m['metric'],
            f"{m['estimate']} — {m['basis']} ({'Assumption / estimate' if m['is_assumption'] else 'Based on supplied inputs'})"] for m in v['metrics']])] if v['metrics'] else []))
    ready = dict(generated['readiness'])
    ready['title'] = 'Feasibility and readiness assessment'
    ready['tables'] = [*ready['tables'], table('Feasibility (advisory)', ['Dimension', 'Score / reason'],
        [[k.title(), f"{d['score']}/100 — {d['reason']}"] for k, d in v['feasibility'].items() if k != 'overall'] + [['Overall', str(v['feasibility']['overall']) + '/100']])]
    add(ready)
    add(chapter('risks', 'Risk register and mitigations', 'Mitigations are proposed controls; residual risks and validation actions remain visible.',
        tables=[table(risk['risk'], ['Risk field', 'Assessment'], [[k.replace('_', ' ').title(), val] for k, val in risk.items() if k != 'risk']) for risk in planning['risks']] + finding_tables(v['risks'])))
    review_tables = []
    for i, review in enumerate(content['red_team_history']):
        review_tables.append(table(f'Red Team cycle {i+1}', ['Summary', 'Review scope'], [[review['summary'], 'Selected solution and all implementation design parts']]))
        review_tables.extend(finding_tables(review['findings']))
    changes = [f"Cycle {x['cycle']} changed sections: {', '.join(x['changed_sections']) or 'No section content changed; findings remain subject to review.'}" for x in content.get('design_changes', [])]
    changes += [f"Proposal {i+1}: {p['summary']} Components: " + '; '.join(c['name'] + ': ' + c['responsibility'] for c in p['components']) +
                ' Human controls: ' + '; '.join(p['human_in_loop']) + ' Integrations: ' + '; '.join(p['integrations']) for i, p in enumerate(content['solution_history'])]
    add(chapter('red_team', 'Independent Red Team review and design changes', content['red_team']['summary'], changes, review_tables))
    add(chapter('conclusion', 'Final recommendation and immediate next actions', conclusion['recommendation'], conclusion['next_steps']))
    add(chapter('appendix', 'Appendix: assumptions, unresolved items, glossary and artifact index',
        'Validate these assumptions and unresolved items before implementation. Design artifacts are proposals for review.',
        list(dict.fromkeys([*s['constraints'], *s['assumptions'], *unresolved, *planning['glossary']])),
        [table('Generated artifact index', ['Section', 'Artifact'], [[c['title'], x.get('title', x.get('name', x.get('filename', '')))]
            for c in out for key in ('diagrams','screens','code_assets') for x in c[key]])]
        if any(c[k] for c in out for k in ('diagrams','screens','code_assets')) else []))
    # Generated chapters are validated individually before merging. Merged sections
    # can legitimately contain more tables than one generation-stage chapter.
    return {'schema_version': 2, 'title': project['name'], 'industry': project.get('industry') or 'Not specified',
            'language': context['output_language'], 'source_revision': project.get('context_revision', 0),
            'selected_option': decision.selected, 'sections': out}
