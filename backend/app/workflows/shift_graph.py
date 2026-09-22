from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from app.models.schemas import WorkflowAnalysis, RootCause, Necessity, Solution, RedTeam, BusinessValue, Conclusion
from app.agents import prompts
from app.agents import report_prompts
from app.models.final_report import Option, DecisionMatrix, OptionDecision, PART_SCHEMAS, validate_consistency
from app.workflows.review import (REVIEW_INSTRUCTION, DESIGN_KEYS, reconcile, revision_plan,
                                  target_parts, review_gate, record_changes)


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
    review_ledger: list[dict]
    revision_plan: list[dict]
    review_gate: str
    review_run_cycle: int
    revision_base: dict
    review_responses: list[dict]
    source_revision: int


def needs_revision(state):
    return state.get('review_run_cycle', state['red_team_cycle']) < 3 and bool(revision_plan(state))


def build_graph(ai, progress, resume=False):
    graph = StateGraph(ShiftState)

    def node(key, stage, instruction, schema):
        def run(state):
            progress(stage, state)
            payload = {k: v for k, v in state.items() if k not in {'revision_base', 'design_changes', 'solution_history', 'red_team_history'}}
            result = ai.generate_structured(instruction, payload, schema).model_dump()
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
        data = {k: v for k, v in state.items() if k not in PART_SCHEMAS and k not in {'solution_history', 'red_team_history', 'revision_base', 'design_changes'}}
        targets = target_parts(state)
        parts = {k: state[k] for k in PART_SCHEMAS if k not in targets}
        for key, schema in PART_SCHEMAS.items():
            if key not in targets:
                continue
            progress('SOLUTION_GENERATION', state)
            parts[key] = ai.generate_structured(report_prompts.part_instruction(key) +
                '\nApply revision_plan. Preserve unaffected chapters and controls. A user answer is evidence, not a request to ignore risks.',
                {**data, **parts, 'previous_part': state.get(key)}, schema).model_dump()
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
        if state.get('revision_base'):
            changes.append(record_changes(state['revision_base'], {**state, **parts},
                                          state.get('revision_plan', []), state.get('red_team_cycle', 0) + 1))
        return {**parts, 'design_changes': changes}

    def review(state):
        progress('RED_TEAM_REVIEW', state)
        # Do not send duplicated full diffs and snapshots into every model call.
        context = {k: v for k, v in state.items() if k not in {'revision_base', 'solution_history', 'red_team_history', 'design_changes'}}
        context['recent_changes'] = [{k: v for k, v in c.items() if k != 'diffs'} for c in state.get('design_changes', [])[-2:]]
        result = ai.generate_structured(prompts.RED_TEAM + '\n' + REVIEW_INSTRUCTION, context, RedTeam).model_dump()
        ledger = reconcile(state, result)
        return {'red_team': result, 'red_team_cycle': state.get('red_team_cycle', 0) + 1,
                'review_run_cycle': state.get('review_run_cycle', 0) + 1,
                'red_team_history': [*state.get('red_team_history', []), result],
                'review_ledger': ledger, 'review_gate': review_gate(ledger)}

    def prepare_revision(state):
        return {'revision_base': {k: state[k] for k in DESIGN_KEYS if k in state},
                'revision_plan': revision_plan(state)}

    def revision_route(state):
        if any(p['action'] == 'reconsider_solution' for p in state['revision_plan']):
            return 'necessity'
        requested = {s for p in state['revision_plan'] for s in p['sections']}
        return 'architect' if not requested or requested.intersection({'solution', 'option_decision', 'ai_necessity'}) else 'implementation'

    def options(state):
        # A combined three-option schema exceeds some providers' schema budgets.
        # Generate each path with the same compact contract, then compare them.
        state = {k: v for k, v in state.items() if k not in {'revision_base', 'design_changes', 'solution_history', 'red_team_history'}}
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
    graph.add_node('review', review)
    graph.add_node('prepare_revision', prepare_revision)
    graph.add_node('value', node('business_value', 'BUSINESS_VALUE', prompts.VALUE, BusinessValue))
    graph.add_node('finalize', node('conclusion', 'BUSINESS_VALUE', prompts.BLUEPRINT, Conclusion))
    graph.add_edge(START, 'review' if resume else 'workflow')
    graph.add_edge('workflow', 'root')
    graph.add_edge('root', 'necessity')
    graph.add_edge('necessity', 'options')
    graph.add_edge('options', 'architect')
    graph.add_edge('architect', 'implementation')
    graph.add_edge('implementation', 'review')
    graph.add_conditional_edges('review', lambda s: 'prepare_revision' if needs_revision(s) else 'value')
    graph.add_conditional_edges('prepare_revision', revision_route)
    graph.add_edge('value', 'finalize')
    graph.add_edge('finalize', END)
    return graph.compile()
