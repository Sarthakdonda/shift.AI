from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.models.project_context import ContextFact, Unknown, Question

Score = int
Classification = Literal['AI_REQUIRED', 'AI_OPTIONAL', 'AUTOMATION_SUFFICIENT', 'PROCESS_IMPROVEMENT', 'EXISTING_SOFTWARE_SUFFICIENT', 'HYBRID_SOLUTION']


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=100)
    initial_problem: str = Field(min_length=15, max_length=12000)
    industry: str = Field(default='', max_length=100)
    workspace_id: str | None = None
    language: str = Field(default='en', max_length=50)


class ChatInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=12000)
    request_id: str | None = Field(default=None, min_length=1, max_length=80)


class GenerationInput(BaseModel):
    request_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9-]+$')


class ModelChoice(BaseModel):
    """Per-project model and reasoning effort chosen in the composer."""
    model_config = ConfigDict(str_strip_whitespace=True, protected_namespaces=())
    # Restricted to provider model-id characters so the value cannot alter the request path.
    model: str = Field(min_length=3, max_length=80, pattern=r'^[a-z0-9][a-z0-9.\-]*$')
    effort: Literal['instant', 'low', 'medium', 'high']


class Scores(BaseModel):
    business: int = Field(default=0, ge=0, le=100)
    problem: int = Field(default=0, ge=0, le=100)
    workflow: int = Field(default=0, ge=0, le=100)
    people: int = Field(default=0, ge=0, le=100)
    technology: int = Field(default=0, ge=0, le=100)
    data: int = Field(default=0, ge=0, le=100)
    constraints: int = Field(default=0, ge=0, le=100)
    impact: int = Field(default=0, ge=0, le=100)
    integrations: int = Field(default=0, ge=0, le=100)
    outcome: int = Field(default=0, ge=0, le=100)
    overall: int = Field(default=0, ge=0, le=100)


class Fact(BaseModel):
    category: str
    fact: str
    source: str


class Discovery(BaseModel):
    collected_information: list[ContextFact]
    missing_information: list[str]
    critical_missing: list[str]
    scores: Scores
    enough_information: bool
    next_question: str
    assumptions: list[str]
    unknowns: list[Unknown]
    next_questions: list[Question] = Field(max_length=3)
    answered_topics: list[str]
    information_sufficiency: int = Field(ge=0, le=100)
    readiness_reason: str = Field(min_length=1)

    @model_validator(mode='after')
    def gate(self):
        self.scores.overall = self.information_sufficiency
        if self.critical_missing or min(self.scores.problem, self.scores.workflow, self.scores.outcome) < 60:
            self.enough_information = False
        if not self.enough_information and not self.next_questions:
            raise ValueError('A useful discovery question is required when information is missing')
        if self.enough_information:
            self.next_questions = []
            self.next_question = ''
        else:
            self.next_question = '\n\n'.join(q.question for q in self.next_questions)
        return self


class DocumentSummary(BaseModel):
    summary: str
    facts: list[Fact]


class WorkflowStep(BaseModel):
    name: str
    owner: str
    description: str
    tools: list[str]


class EvidenceItem(BaseModel):
    title: str
    description: str
    evidence: list[str]
    confidence: float = Field(ge=0, le=1)


class CurrentSystem(BaseModel):
    people: list[str]
    process: str
    technology: list[str]
    data: list[str]


class WorkflowAnalysis(BaseModel):
    business_context: str
    current_system: CurrentSystem
    workflow: list[WorkflowStep]
    bottlenecks: list[EvidenceItem]


class RootCause(BaseModel):
    user_request: str
    root_problem: str
    root_causes: list[EvidenceItem]
    assumptions: list[str]


class Necessity(BaseModel):
    classification: Classification
    score: int = Field(ge=0, le=100)
    reasoning: list[str]
    non_ai_alternative: str
    recommended_approach: str
    confidence: float = Field(ge=0, le=1)


class Component(BaseModel):
    name: str
    responsibility: str
    uses_ai: bool
    reason: str


class RoadmapStep(BaseModel):
    phase: str
    title: str
    actions: list[str]
    exit_criteria: str


class Solution(BaseModel):
    title: str
    summary: str
    solution_type: Literal['EXISTING_SOFTWARE', 'API_INTEGRATION', 'CUSTOM_AUTOMATION', 'CUSTOM_AI', 'PROCESS_IMPROVEMENT', 'HYBRID']
    components: list[Component]
    data_flow: list[str]
    data_requirements: list[str]
    integrations: list[str]
    human_in_loop: list[str]
    constraints: list[str]
    assumptions: list[str]
    complexity: Literal['LOW', 'MEDIUM', 'HIGH']
    roadmap: list[RoadmapStep]
    success_metrics: list[str]


class Finding(BaseModel):
    category: str
    severity: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    issue: str
    reason: str
    mitigation: str
    requires_revision: bool


class RedTeam(BaseModel):
    summary: str
    findings: list[Finding]


class Dimension(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


class Feasibility(BaseModel):
    technical: Dimension
    data: Dimension
    integration: Dimension
    operational: Dimension
    business: Dimension
    overall: int = Field(ge=0, le=100)


class ValueMetric(BaseModel):
    metric: str
    estimate: str
    basis: str
    is_assumption: bool


class BusinessValue(BaseModel):
    summary: str
    metrics: list[ValueMetric]
    feasibility: Feasibility
    risks: list[Finding]


class Conclusion(BaseModel):
    executive_summary: str
    recommendation: str
    next_steps: list[str]
