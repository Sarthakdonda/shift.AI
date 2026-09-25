"""Declarative application contract. No executable model output is accepted."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.provider_schema import ProviderModel

Identifier = str


class AppField(ProviderModel):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=100)
    kind: Literal['text', 'email', 'number', 'date', 'boolean', 'select', 'reference'] = 'text'
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=40)
    reference: str | None = None


class Transition(ProviderModel):
    label: str = Field(min_length=1, max_length=100)
    field: str
    from_value: str
    to_value: str
    roles: list[str] = Field(min_length=1, max_length=10)


class Entity(ProviderModel):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=100)
    fields: list[AppField] = Field(min_length=1, max_length=30)
    read_roles: list[str] = Field(min_length=1, max_length=10)
    write_roles: list[str] = Field(min_length=1, max_length=10)
    transitions: list[Transition] = Field(default_factory=list, max_length=30)
    requirement_ids: list[str] = Field(min_length=1, max_length=30)


class Requirement(ProviderModel):
    id: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(max_length=2000)
    implementation: Literal['supported', 'manual']


class ApplicationSpec(ProviderModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=3000)
    language: str = Field(default='en', max_length=30)
    accent: str = Field(default='#FF7A00', pattern=r'^#[0-9a-fA-F]{6}$')
    roles: list[str] = Field(min_length=1, max_length=10)
    entities: list[Entity] = Field(min_length=1, max_length=20)
    requirements: list[Requirement] = Field(min_length=1, max_length=100)
    assumptions: list[str] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list, max_length=40)
    change_summary: str = Field(max_length=3000)

    @model_validator(mode='after')
    def coherent(self):
        import re
        if 'admin' not in self.roles or len(set(self.roles)) != len(self.roles):
            raise ValueError('Roles must be unique and include admin.')
        if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', r) for r in self.roles):
            raise ValueError('Roles must be lowercase identifiers.')
        entities = {e.name: e for e in self.entities}
        reqs = {r.id for r in self.requirements}
        if len(entities) != len(self.entities) or len(reqs) != len(self.requirements):
            raise ValueError('Entity names and requirement IDs must be unique.')
        mapped = set()
        for entity in self.entities:
            fields = {f.name: f for f in entity.fields}
            if entity.name.startswith(('sqlite_', 'shift_')):
                raise ValueError('Entity name uses a reserved prefix.')
            if len(fields) != len(entity.fields) or set(fields) & {'id', 'created_at', 'updated_at'}:
                raise ValueError('Field names must be unique and cannot use reserved columns.')
            if not set(entity.read_roles + entity.write_roles) <= set(self.roles):
                raise ValueError('Unknown role in entity permissions.')
            if not (set(entity.write_roles) - {'admin'}) <= set(entity.read_roles):
                raise ValueError('Writers must have read access to their modules.')
            if not set(entity.requirement_ids) <= reqs:
                raise ValueError('Unknown requirement reference.')
            mapped.update(entity.requirement_ids)
            for field in entity.fields:
                if field.name.startswith('shift_'):
                    raise ValueError('Field name uses a reserved prefix.')
                if field.kind == 'reference' and field.reference not in entities:
                    raise ValueError('Reference fields must point to an entity.')
                if field.kind == 'reference' and not (set(entity.write_roles) - {'admin'}) <= set(entities[field.reference].read_roles):
                    raise ValueError('Writers must be able to read referenced modules.')
                if field.kind == 'select' and (not field.options or len(set(field.options)) != len(field.options)):
                    raise ValueError('Select fields need unique options.')
                if any(not value or len(value) > 200 for value in field.options):
                    raise ValueError('Options must be nonempty and at most 200 characters.')
            for transition in entity.transitions:
                field = fields.get(transition.field)
                if not field or field.kind != 'select' or not {transition.from_value, transition.to_value} <= set(field.options):
                    raise ValueError('Transitions must use existing select values.')
                if not set(transition.roles) <= set(entity.write_roles):
                    raise ValueError('Transition roles must have write permission.')
        if any(r.implementation == 'supported' and r.id not in mapped for r in self.requirements):
            raise ValueError('Every supported requirement must map to an entity.')
        pending = set(entities)
        while pending:
            creatable = {name for name in pending if not any(f.kind == 'reference' and f.required and f.reference in pending for f in entities[name].fields)}
            if not creatable:
                raise ValueError('Required reference cycles prevent initial records. Make at least one relationship optional.')
            pending -= creatable
        return self


class PlanInput(BaseModel):
    instructions: str = Field(default='', max_length=6000)
    base_version: int = Field(default=0, ge=0)


class SpecEdit(BaseModel):
    base_version: int = Field(ge=1)
    spec: ApplicationSpec


class VersionInput(BaseModel):
    version: int = Field(ge=1)


class BuildInput(VersionInput):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    quoted_cost: int | None = Field(default=None, ge=0, le=10000)


class TargetInput(BaseModel):
    service_id: str = Field(pattern=r'^srv-[a-zA-Z0-9]{5,80}$')
    image_repository: str = Field(pattern=r'^[a-z0-9][a-z0-9.:-]*/[a-z0-9/_-]+$', max_length=200)


class DeployInput(BuildInput):
    target: Literal['render', 'vercel'] = 'render'


class CreditGrant(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0, le=100000)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


class PlanConfig(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    build_cost: int = Field(ge=0, le=10000)
    max_entities: int = Field(ge=1, le=20)
    initial_credits: int = Field(ge=0, le=100000)
