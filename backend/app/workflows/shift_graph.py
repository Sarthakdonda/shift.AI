from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from app.models.schemas import WorkflowAnalysis, RootCause, Necessity, Solution, RedTeam, BusinessValue, Conclusion
from app.agents import prompts
from app.agents import report_prompts
from app.models.final_report import Option, DecisionMatrix, OptionDecision, PART_SCHEMAS, validate_consistency


class ShiftState(TypedDict, total=False):
    context: dict
    workflow_analysis: dict
    root_cause: dict
    ai_necessity: dict
    solution: dict
    solution_history: list[dict]
    red_team: dict
    red_team_history: list[dict]
    red_team_cycle: int
    business_value: dict
    conclusion: dict
    option_decision: dict
    architecture_report: dict
    experience_report: dict
    data_report: dict
    planning_report: dict
    design_changes: list[dict]


def needs_revision(state):
    return state['red_team_cycle'] < 3 and any(f['requires_revision'] for f in state['red_team']['findings'])


def build_graph(ai, progress):
    graph = StateGraph(ShiftState)

    def node(key, stage, instruction, schema):
        def run(state):
            progress(stage, state)
            result = ai.generate_structured(instruction, state, schema).model_dump()
            update: dict[str, Any] = {key: result}
            if key == 'solution':
                update['solution_history'] = [*state.get('solution_history', []), result]
            if key == 'red_team':
                update['red_team_cycle'] = state.get('red_team_cycle', 0) + 1
                update['red_team_history'] = [*state.get('red_team_history', []), result]
            return update
        return run

    def implementation(state):
        # Bounded calls keep each structured output small. No saved studio artifact
        # is silently mixed in from an older discovery revision or another option.
        progress('SOLUTION_GENERATION', state)
        data = {k: v for k, v in state.items() if k not in PART_SCHEMAS and k not in {'solution_history', 'red_team_history'}}
        parts = {}
        for key, schema in PART_SCHEMAS.items():
            progress('SOLUTION_GENERATION', state)
            parts[key] = ai.generate_structured(report_prompts.part_instruction(key), {**data, **parts}, schema).model_dump()
        try:
            validate_consistency(state['option_decision'], state['solution'], parts)
        except ValueError as exc:
            # One bounded repair pass, using the concrete error and previous drafts.
            for key, schema in PART_SCHEMAS.items():
                progress('SOLUTION_GENERATION', state)
                parts[key] = ai.generate_structured(report_prompts.part_instruction(key) + '\nRepair consistency: ' + str(exc),
                    {**data, **parts}, schema).model_dump()
            validate_consistency(state['option_decision'], state['solution'], parts)
        changes = list(state.get('design_changes', []))
        if state.get('architecture_report'):
            changed = [c['title'] for key in PART_SCHEMAS for c in parts[key]['chapters']
                       if c not in state[key]['chapters']]
            changes.append({'cycle': state.get('red_team_cycle', 0) + 1, 'changed_sections': changed,
                            'review_findings': state['red_team']['findings']})
        return {**parts, 'design_changes': changes}

    def options(state):
        # A combined three-option schema exceeds some providers' schema budgets.
        # Generate each path with the same compact contract, then compare them.
        drafts = []
        for tier in ('lean', 'balanced', 'advanced'):
            progress('SOLUTION_GENERATION', state)
            draft = ai.generate_structured(report_prompts.OPTIONS + '\nFor this call return ONLY the ' + tier + ' option. Use the supplied earlier options to make its scope and approach distinct.',
                {**state, 'requested_tier': tier, 'earlier_options': drafts}, Option).model_dump()
            if draft['tier'] != tier:
                raise ValueError('Option generator returned a different tier than requested.')
            drafts.append(draft)
        progress('SOLUTION_GENERATION', state)
        data = {**state, 'options': drafts}
        matrix = ai.generate_structured(report_prompts.OPTIONS + '\nCompare the three supplied options. Return only the decision matrix and selection reasoning.', data, DecisionMatrix).model_dump()
        try:
            decision = OptionDecision.model_validate({**matrix, 'options': drafts})
        except ValueError as exc:
            matrix = ai.generate_structured(report_prompts.OPTIONS + '\nRepair the decision matrix: ' + str(exc), {**data, 'draft_matrix': matrix}, DecisionMatrix).model_dump()
            decision = OptionDecision.model_validate({**matrix, 'options': drafts})
        return {'option_decision': decision.model_dump()}

    graph.add_node('workflow', node('workflow_analysis', 'SYSTEM_ANALYSIS', prompts.WORKFLOW, WorkflowAnalysis))
    graph.add_node('root', node('root_cause', 'SYSTEM_ANALYSIS', prompts.ROOT_CAUSE, RootCause))
    graph.add_node('necessity', node('ai_necessity', 'AI_NECESSITY', prompts.NECESSITY, Necessity))
    graph.add_node('options', options)
    graph.add_node('architect', node('solution', 'SOLUTION_GENERATION', prompts.ARCHITECT + '\nImplement option_decision.selected exactly. Keep component names stable on revision. Do not switch options or introduce AI into an option with ai_usage=none.', Solution))
    graph.add_node('implementation', implementation)
    graph.add_node('review', node('red_team', 'RED_TEAM_REVIEW', prompts.RED_TEAM + '\nReview ALL implementation report parts and the option matrix. Cross-check HLD/LLD, entities/schema/API, integrations, wireframes, roadmap, estimates and ownership for contradictions, missing details, unsupported regulation claims and scenario relevance. Request revision for material inconsistencies. Do not accept a name-reference check as proof of semantic correctness.', RedTeam))
    graph.add_node('value', node('business_value', 'BUSINESS_VALUE', prompts.VALUE, BusinessValue))
    graph.add_node('finalize', node('conclusion', 'BUSINESS_VALUE', prompts.BLUEPRINT, Conclusion))
    graph.add_edge(START, 'workflow')
    graph.add_edge('workflow', 'root')
    graph.add_edge('root', 'necessity')
    graph.add_edge('necessity', 'options')
    graph.add_edge('options', 'architect')
    graph.add_edge('architect', 'implementation')
    graph.add_edge('implementation', 'review')
    graph.add_conditional_edges('review', lambda s: 'architect' if needs_revision(s) else 'value')
    graph.add_edge('value', 'finalize')
    graph.add_edge('finalize', END)
    return graph.compile()
