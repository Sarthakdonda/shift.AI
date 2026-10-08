"""Approved application contract with statically restricted business functions."""
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
    calculation: list[str] = Field(default_factory=list, max_length=60, description='Local numeric postfix calculation: field names, constants, + - * / min max round. No code.')


def value_error(field, value):
    """Why the runtime would reject this value, or None. Mirrors the generated runtime."""
    import math
    import re
    from datetime import date, datetime
    if value is None or value == '':
        return 'is required.' if field.required else None
    if field.kind == 'boolean':
        return None if isinstance(value, bool) else 'must be true or false.'
    if field.kind == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return 'must be a finite number.'
        return None
    if not isinstance(value, str) or len(value) > 5000:
        return 'must be text of at most 5000 characters.'
    if field.kind == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        return 'must be a valid email address.'
    if field.kind == 'date':
        try:
            date.fromisoformat(value)
        except ValueError:
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return 'must be a date (2026-09-23) or a timestamp (2026-09-23T10:00:00Z).'
    if field.kind == 'select' and value not in field.options:
        return 'must be one of ' + ', '.join(field.options) + '.'
    return None


class Transition(ProviderModel):
    label: str = Field(min_length=1, max_length=100)
    field: str
    from_value: str
    to_value: str
    roles: list[str] = Field(min_length=1, max_length=10)


class LogicCase(ProviderModel):
    input_json: str = Field(max_length=12000)
    expected_json: str = Field(max_length=12000)


class BusinessLogic(ProviderModel):
    description: str = Field(min_length=1, max_length=2000)
    code: str = Field(min_length=1, max_length=12000)
    outputs: list[str] = Field(min_length=1, max_length=20)
    cases: list[LogicCase] = Field(min_length=2, max_length=12)


class PublicSection(ProviderModel):
    heading: str = Field(max_length=200)
    text: str = Field(max_length=5000)
    layout: Literal['text', 'hero', 'cards', 'gallery', 'contact'] = 'text'
    image_url: str = Field(default='', max_length=2000)
    image_alt: str = Field(default='', max_length=200)


class PublicPage(ProviderModel):
    slug: str = Field(pattern=r'^[a-z][a-z0-9-]{0,59}$')
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(max_length=500)
    sections: list[PublicSection] = Field(min_length=1, max_length=20)
    contact_email: str = Field(default='', max_length=254)
    requirement_ids: list[str] = Field(min_length=1, max_length=1000)


class ExternalAction(ProviderModel):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)
    fields: list[str] = Field(min_length=1, max_length=30)
    roles: list[str] = Field(min_length=1, max_length=10)


class Entity(ProviderModel):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=100)
    fields: list[AppField] = Field(min_length=1, max_length=30)
    read_roles: list[str] = Field(min_length=1, max_length=10)
    write_roles: list[str] = Field(min_length=1, max_length=10)
    transitions: list[Transition] = Field(default_factory=list, max_length=30)
    requirement_ids: list[str] = Field(min_length=1, max_length=1000)
    logic: BusinessLogic | None = None
    integrations: list[ExternalAction] = Field(default_factory=list, max_length=8)

    def validate_logic(self):
        """Validate calculations against the merged module, also during staging."""
        if not self.logic:
            return
        import json
        from app.templates.application.business_logic import check_source
        check_source(self.logic.code)
        fields = {field.name for field in self.fields}
        outputs = set(self.logic.outputs)
        if len(outputs) != len(self.logic.outputs) or not outputs <= fields:
            raise ValueError('Business logic outputs must name unique fields in this module.')
        if outputs & {transition.field for transition in self.transitions}:
            raise ValueError('Workflow state is controlled by transitions, not calculated fields.')
        for index, case in enumerate(self.logic.cases, 1):
            try:
                inputs, expected = json.loads(case.input_json), json.loads(case.expected_json)
            except ValueError:
                raise ValueError(f'Module {self.name}, logic test {index}: inputs and expected outputs must be valid JSON objects.') from None
            if (not isinstance(inputs, dict) or not isinstance(expected, dict)
                    or set(expected) != outputs or not set(inputs) <= fields or set(inputs) & outputs):
                raise ValueError(f'Module {self.name}, logic test {index}: input_json must be an object using only '
                                 f'non-calculated fields {sorted(fields - outputs)}; expected_json must be an object '
                                 f'containing exactly the calculated outputs {sorted(outputs)}.')
            # An example the runtime would reject can never pass its own acceptance
            # test, so such a specification must not become approvable.
            declared = {field.name: field for field in self.fields}
            for name, value in inputs.items():
                problem = value_error(declared[name], value)
                if problem:
                    raise ValueError(f'Module {self.name}, logic test {index}: {name} {problem}')


class Requirement(ProviderModel):
    id: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(max_length=2000)
    implementation: Literal['supported', 'manual']


class ApplicationDecision(ProviderModel):
    requirement_ids: list[str] = Field(min_length=1)
    decision: str = Field(min_length=1, max_length=2000)
    implementation: Literal['supported', 'manual']


class ApplicationSpec(ProviderModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=3000)
    language: str = Field(default='en', max_length=30)
    accent: str = Field(default='#FF7A00', pattern=r'^#[0-9a-fA-F]{6}$')
    roles: list[str] = Field(min_length=1, max_length=10)
    entities: list[Entity] = Field(default_factory=list, max_length=20)
    requirements: list[Requirement] = Field(min_length=1, max_length=1000)
    assumptions: list[str] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list, max_length=40)
    change_summary: str = Field(max_length=3000)
    public_pages: list[PublicPage] = Field(default_factory=list, max_length=12)
    ui_labels: dict[str, str] = Field(default_factory=dict)
    application_type: Literal['website', 'web_application', 'desktop', 'mobile'] = 'web_application'
    storage_mode: Literal['shared_server', 'local_device', 'none'] = 'shared_server'
    target_platforms: list[Literal['web', 'windows', 'macos', 'android', 'ios']] = Field(default_factory=lambda: ['web'], min_length=1, max_length=5)
    storage_reason: str = Field(default='', max_length=2000)
    questions: list[str] = Field(default_factory=list, max_length=20)
    sensitive_data: bool = False
    # Reviewable planning output; compiler/deployment contracts remain unchanged.
    generation_details: dict[Literal['database', 'api', 'frontend', 'backend', 'deployment'], list[ApplicationDecision]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def coherent(self):
        import re
        from urllib.parse import urlsplit
        if len(set(self.target_platforms)) != len(self.target_platforms):
            raise ValueError('Target platforms must be unique.')
        if self.storage_mode == 'none' and (self.entities or self.application_type != 'website'):
            raise ValueError('No database is suitable only for a website without record modules.')
        if self.application_type == 'website' and not self.public_pages:
            raise ValueError('A website needs at least one public page.')
        if self.storage_mode != 'none' and not self.entities:
            raise ValueError('A data application needs at least one module.')
        if self.storage_mode == 'local_device':
            if self.roles != ['admin']:
                raise ValueError('Local-device applications are single-user. Shared roles require a shared server.')
            if any(e.logic or e.integrations for e in self.entities):
                raise ValueError('Server Python calculations and external secret integrations require shared_server storage.')
        for page in self.public_pages:
            for section in page.sections:
                if section.image_url:
                    url = urlsplit(section.image_url)
                    if url.scheme != 'https' or not url.hostname or url.username or url.password:
                        raise ValueError('Images must use HTTPS URLs without credentials.')
        if 'admin' not in self.roles or len(set(self.roles)) != len(self.roles):
            raise ValueError('Roles must be unique and include admin.')
        if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', r) for r in self.roles):
            raise ValueError('Roles must be lowercase identifiers.')
        entities = {e.name: e for e in self.entities}
        reqs = {r.id for r in self.requirements}
        if any(not set(decision.requirement_ids) <= reqs for decisions in self.generation_details.values() for decision in decisions):
            raise ValueError('Stage decisions must reference declared requirements.')
        if len(entities) != len(self.entities) or len(reqs) != len(self.requirements):
            raise ValueError('Entity names and requirement IDs must be unique.')
        mapped = set()
        if len({page.slug for page in self.public_pages}) != len(self.public_pages):
            raise ValueError('Public page paths must be unique.')
        for page in self.public_pages:
            if not set(page.requirement_ids) <= reqs:
                raise ValueError('Unknown public-page requirement.')
            if page.contact_email and not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', page.contact_email):
                raise ValueError('Use a valid public contact email.')
            mapped.update(page.requirement_ids)
        if len(self.ui_labels) > 150 or any(len(k) > 250 or not v or len(v) > 1500 for k, v in self.ui_labels.items()):
            raise ValueError('Interface translations exceed the allowed size.')
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
            entity.validate_logic()
            if len({action.name for action in entity.integrations}) != len(entity.integrations):
                raise ValueError('Integration action names must be unique within a module.')
            for action in entity.integrations:
                if not set(action.fields) <= set(fields) or not set(action.roles) <= set(entity.write_roles):
                    raise ValueError('Integration actions must use declared fields and write roles.')
            for field in entity.fields:
                if field.calculation:
                    if self.storage_mode != 'local_device' or field.kind != 'number':
                        raise ValueError('Declarative calculations require a local numeric field.')
                    available = {f.name for f in entity.fields if not f.calculation}
                    available.update(f.name for f in entity.fields[:entity.fields.index(field)] if f.calculation)
                    depth = 0
                    for token in field.calculation:
                        if token in ('+', '-', '*', '/', 'min', 'max'):
                            depth -= 1
                            if depth < 1:
                                raise ValueError('Invalid calculation operands.')
                        elif token == 'round':
                            if depth < 1:
                                raise ValueError('Invalid calculation operands.')
                        elif token in available or re.fullmatch(r'-?\d+(\.\d+)?', token):
                            depth += 1
                        else:
                            raise ValueError('Unknown or circular calculation input.')
                    if depth != 1:
                        raise ValueError('A calculation must produce one value.')
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
            raise ValueError('Every supported requirement must map to an entity or public page.')
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
    resume_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


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
