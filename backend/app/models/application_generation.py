"""Small contracts for checkpointed application planning."""
from typing import Literal
from pydantic import Field, create_model
from app.models.provider_schema import ProviderModel
from app.models.application import ApplicationSpec, ApplicationDecision

Stage = Literal['core', 'database', 'api', 'frontend', 'backend', 'deployment']


class Fact(ProviderModel):
    description: str = Field(min_length=1, max_length=1600)
    stages: list[Stage] = Field(min_length=1)
    targets: list[str] = Field(default_factory=list, description='Stable lowercase module/page names this requirement concerns; empty for global constraints.')
    source_ids: list[str] = Field(min_length=1)


class SourceDisposition(ProviderModel):
    source_id: str
    reason: str = Field(min_length=1, description='Why this source fragment has no application requirement (e.g. heading, repeated evidence, historical observation).')


class ExtractedContext(ProviderModel):
    requirements: list[Fact]
    non_requirements: list[SourceDisposition]


class Scope(ProviderModel):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str
    requirement_ids: list[str]


CORE_FIELDS = ['name', 'description', 'language', 'accent', 'roles', 'assumptions', 'limitations',
               'change_summary', 'application_type', 'storage_mode', 'target_platforms',
               'storage_reason', 'questions', 'sensitive_data']
CoreApplication = create_model('CoreApplication', __base__=ProviderModel,
    **{name: (ApplicationSpec.model_fields[name].annotation, ApplicationSpec.model_fields[name]) for name in CORE_FIELDS},
    modules=(list[Scope], Field(default_factory=list, max_length=20)),
    pages=(list[Scope], Field(default_factory=list, max_length=12)))


class StageSpecification(ProviderModel):
    decisions: list[ApplicationDecision]


class SingleRequirementAssessment(ProviderModel):
    implementation: Literal['supported', 'manual']
    reason: str = Field(min_length=1, max_length=1000)


class RequirementAssessment(ProviderModel):
    requirement_id: str
    implementation: Literal['supported', 'manual']
    reason: str = Field(min_length=1, max_length=1000)


class CoverageReview(ProviderModel):
    assessments: list[RequirementAssessment]
