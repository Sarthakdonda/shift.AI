"""Validated, scenario-independent contract for the final implementation report."""
from typing import Literal, ClassVar
from pydantic import BaseModel, Field, model_validator
from app.models.deliverables import Section, Diagram, Screen, CodeAsset

Tier = Literal['lean', 'balanced', 'advanced']


class ReportModel(BaseModel):
    @classmethod
    def provider_json_schema(cls):
        """Send shape/enums; enforce size/range/relationship constraints locally.

        Nested collection bounds can exhaust a provider's schema compilation
        budget even when the actual requested document is small.
        """
        def compact(value):
            if isinstance(value, dict):
                return {k: ({name: compact(child) for name, child in v.items()} if k in {'properties', '$defs'} else compact(v)) for k, v in value.items() if k not in {
                    'title', 'minItems', 'maxItems', 'minLength', 'maxLength', 'minimum', 'maximum', 'pattern'}}
            if isinstance(value, list): return [compact(v) for v in value]
            return value
        return compact(cls.model_json_schema())


class Estimate(BaseModel):
    label: str = Field(min_length=1)
    low: float | None = Field(ge=0)
    high: float | None = Field(ge=0)
    unit: str = Field(min_length=1, description='Person-days, weeks, or currency and billing period.')
    basis: str = Field(min_length=1, description='Source, arithmetic, or why the amount is unknown.')
    assumptions: list[str] = Field(min_length=1)
    confidence: Literal['low', 'medium', 'high', 'unknown']

    @model_validator(mode='after')
    def range_check(self):
        if (self.low is None) != (self.high is None):
            raise ValueError('Both range bounds must be supplied or both unknown.')
        if self.low is not None and self.low > self.high:
            raise ValueError('Estimate lower bound exceeds upper bound.')
        if self.low is None and self.confidence != 'unknown':
            raise ValueError('Unknown amounts must have unknown confidence.')
        return self


class Option(ReportModel):
    tier: Tier
    title: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    included: list[str] = Field(min_length=1)
    excluded: list[str] = Field(min_length=1)
    ai_usage: Literal['none', 'optional', 'required']
    ai_reason: str = Field(min_length=1)
    approach: str = Field(min_length=1)
    integrations_and_data: list[str] = Field(min_length=1)
    security_and_governance: str = Field(min_length=1)
    effort: Estimate
    cost: Estimate
    duration: Estimate
    team_and_ownership: list[str] = Field(min_length=1)
    benefits: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    risks_and_mitigations: list[str] = Field(min_length=1)
    scalability: str = Field(min_length=1)
    best_fit: str = Field(min_length=1)
    avoid_when: str = Field(min_length=1)


class OptionScore(BaseModel):
    tier: Tier
    score: int = Field(ge=1, le=5, description='5 is best, including lowest cost/risk for cost/risk fit.')
    reason: str = Field(min_length=1)


class Criterion(BaseModel):
    name: str = Field(min_length=1)
    weight: int = Field(ge=1, le=100)
    basis: str = Field(min_length=1, description='Discovered priority source or explicitly assumed weight.')
    scores: list[OptionScore] = Field(min_length=3, max_length=3)


class DecisionMatrix(ReportModel):
    criteria: list[Criterion] = Field(min_length=3, max_length=12)
    selected: Tier
    selection_reason: str = Field(min_length=1)
    rejection_reasons: list[OptionScore] = Field(min_length=2, max_length=2,
        description='One reason for rejecting each non-selected tier; score is its overall qualitative fit, 1-5.')
    decision_sensitivities: list[str] = Field(min_length=1)


class OptionDecision(DecisionMatrix):
    options: list[Option] = Field(min_length=3, max_length=3)

    def totals(self):
        return {tier: round(sum(c.weight * next(s.score for s in c.scores if s.tier == tier)
                               for c in self.criteria) / 5, 2)
                for tier in ('lean', 'balanced', 'advanced')}

    @model_validator(mode='after')
    def decision_check(self):
        tiers = {'lean', 'balanced', 'advanced'}
        if {o.tier for o in self.options} != tiers:
            raise ValueError('Provide exactly one Lean, Balanced and Advanced option.')
        if len({o.scope.strip().casefold() for o in self.options}) != 3 or len({o.approach.strip().casefold() for o in self.options}) != 3:
            raise ValueError('The three options must have distinct scope and implementation approaches.')
        if sum(c.weight for c in self.criteria) != 100:
            raise ValueError('Decision weights must total 100 percent.')
        if any({s.tier for s in c.scores} != tiers for c in self.criteria):
            raise ValueError('Each criterion must score all three options exactly once.')
        if len({c.name.casefold() for c in self.criteria}) != len(self.criteria):
            raise ValueError('Decision criteria must be unique.')
        if {r.tier for r in self.rejection_reasons} != tiers - {self.selected}:
            raise ValueError('Explain why each alternative was rejected.')
        totals = self.totals()
        if totals[self.selected] != max(totals.values()):
            raise ValueError('The recommendation must match the highest weighted total; explain any tie.')
        return self


class Chapter(Section):
    key: str = Field(min_length=1)
    applicability: Literal['applicable', 'not_applicable']
    basis: str = Field(min_length=1, description='Evidence source(s), inferred design assumptions and items to validate.')
    diagrams: list[Diagram] = Field(max_length=3)
    screens: list[Screen] = Field(max_length=5)
    code_assets: list[CodeAsset] = Field(max_length=3)
    component_refs: list[str]
    entity_refs: list[str]
    integration_refs: list[str]

    @model_validator(mode='after')
    def meaningful(self):
        if not self.narrative.strip():
            raise ValueError('Every chapter needs content, or an explicit not-applicable reason.')
        if any(not t.rows for t in self.tables):
            raise ValueError('Do not include empty placeholder tables.')
        if self.applicability == 'not_applicable' and (self.diagrams or self.screens or self.code_assets):
            raise ValueError('Not-applicable chapters must explain exclusion without fabricated artifacts.')
        return self


class ReportPart(ReportModel):
    required_keys: ClassVar[set[str]] = set()
    selected_option: Tier
    chapters: list[Chapter] = Field(min_length=1, max_length=10)

    @model_validator(mode='after')
    def coverage(self):
        keys = [c.key for c in self.chapters]
        if set(keys) != self.required_keys or len(keys) != len(set(keys)):
            raise ValueError('Required chapter keys, exactly once: ' + ', '.join(sorted(self.required_keys)))
        for c in self.chapters:
            if c.applicability == 'not_applicable':
                if c.key in {'scope', 'stakeholders', 'estimates', 'resources', 'timeline', 'releases', 'readiness', 'operating_model'}:
                    raise ValueError(c.key + ' must be addressed for every solution, including process changes.')
                continue
            expected = {'hld': {'architecture'}, 'future_process': {'swimlane', 'decision_tree'},
                        'journeys': {'workflow'}, 'data_model': {'er'}, 'integrations': {'data_flow'}}.get(c.key, set())
            if not expected.issubset({d.kind for d in c.diagrams}):
                raise ValueError(c.key + ' requires diagrams: ' + ', '.join(expected))
            if c.key == 'wireframes' and not c.screens:
                raise ValueError('An applicable UX chapter requires actual screen wireframes.')
            if c.key in {'stack', 'lld', 'database', 'apis', 'resources', 'timeline', 'releases', 'readiness'} and not c.tables:
                raise ValueError(c.key + ' requires a concrete catalogue/planning table.')
        return self


class ArchitectureReport(ReportPart):
    required_keys = {'scope', 'stack', 'hld', 'lld', 'security', 'infrastructure', 'deployment', 'operating_model'}
    component_names: list[str] = Field(min_length=1)
    entity_names: list[str]
    integration_names: list[str]


class ExperienceReport(ReportPart):
    required_keys = {'stakeholders', 'future_process', 'journeys', 'wireframes'}


class DataReport(ReportPart):
    required_keys = {'data_model', 'database', 'apis', 'integrations'}


class ReportRisk(BaseModel):
    risk: str = Field(min_length=1)
    severity: Literal['low', 'medium', 'high', 'critical']
    likelihood: Literal['low', 'medium', 'high', 'unknown']
    impact: str = Field(min_length=1)
    mitigation: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    validation_action: str = Field(min_length=1)
    residual_concern: str = Field(min_length=1)


class PlanningReport(ReportPart):
    required_keys = {'estimates', 'resources', 'timeline', 'releases', 'adoption', 'readiness'}
    estimates: list[Estimate] = Field(min_length=3, description='Separate phase/module effort, elapsed duration, setup costs and recurring costs. Unknowns remain null.')
    risks: list[ReportRisk] = Field(min_length=1)
    unresolved_items: list[str]
    glossary: list[str]


def validate_consistency(decision, solution, parts):
    """Check identifiers and coverage; prose/semantic checks belong to independent review."""
    decision = OptionDecision.model_validate(decision)
    models = [schema.model_validate(parts[key]) for key, schema in PART_SCHEMAS.items()]
    architecture = models[0]
    if any(p.selected_option != decision.selected for p in models):
        raise ValueError('Every design part must implement the selected option.')
    if set(architecture.component_names) != {c['name'] for c in solution['components']}:
        raise ValueError('HLD/LLD component catalogue must match the selected solution components.')
    for attr in ('component_names', 'entity_names', 'integration_names'):
        names = getattr(architecture, attr)
        if len(names) != len(set(names)):
            raise ValueError('Catalogue names must be unique: ' + attr)
    for part in models:
        for chapter in part.chapters:
            for refs, names in [('component_refs', 'component_names'), ('entity_refs', 'entity_names'), ('integration_refs', 'integration_names')]:
                if not set(getattr(chapter, refs)).issubset(getattr(architecture, names)):
                    raise ValueError(chapter.key + ': unknown ' + refs)
            if chapter.applicability == 'applicable':
                for keys, refs, names in [({'hld', 'lld'}, 'component_refs', 'component_names'),
                                         ({'data_model', 'database'}, 'entity_refs', 'entity_names'),
                                         ({'integrations'}, 'integration_refs', 'integration_names')]:
                    if chapter.key in keys and set(getattr(chapter, refs)) != set(getattr(architecture, names)):
                        raise ValueError(chapter.key + ' must cover the complete shared ' + names + ' catalogue.')
    option = next(o for o in decision.options if o.tier == decision.selected)
    if option.ai_usage == 'none' and any(c['uses_ai'] for c in solution['components']):
        raise ValueError('A no-AI option cannot introduce AI components.')
    if option.ai_usage == 'required' and not any(c['uses_ai'] for c in solution['components']):
        raise ValueError('An AI-required option must identify its justified AI component.')


PART_SCHEMAS = {'architecture_report': ArchitectureReport, 'experience_report': ExperienceReport,
                'data_report': DataReport, 'planning_report': PlanningReport}
