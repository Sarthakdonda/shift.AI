from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from app.models.schemas import WorkflowAnalysis, RootCause, Necessity, Solution, RedTeam, BusinessValue, Conclusion
from app.agents import prompts


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

    graph.add_node('workflow', node('workflow_analysis', 'SYSTEM_ANALYSIS', prompts.WORKFLOW, WorkflowAnalysis))
    graph.add_node('root', node('root_cause', 'SYSTEM_ANALYSIS', prompts.ROOT_CAUSE, RootCause))
    graph.add_node('necessity', node('ai_necessity', 'AI_NECESSITY', prompts.NECESSITY, Necessity))
    graph.add_node('architect', node('solution', 'SOLUTION_GENERATION', prompts.ARCHITECT, Solution))
    graph.add_node('review', node('red_team', 'RED_TEAM_REVIEW', prompts.RED_TEAM, RedTeam))
    graph.add_node('value', node('business_value', 'BUSINESS_VALUE', prompts.VALUE, BusinessValue))
    graph.add_node('finalize', node('conclusion', 'BUSINESS_VALUE', prompts.BLUEPRINT, Conclusion))
    graph.add_edge(START, 'workflow')
    graph.add_edge('workflow', 'root')
    graph.add_edge('root', 'necessity')
    graph.add_edge('necessity', 'architect')
    graph.add_edge('architect', 'review')
    graph.add_conditional_edges('review', lambda s: 'architect' if needs_revision(s) else 'value')
    graph.add_edge('value', 'finalize')
    graph.add_edge('finalize', END)
    return graph.compile()
