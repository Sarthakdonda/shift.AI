from typing import Literal
from pydantic import BaseModel, Field, model_validator
import yaml

KINDS = ('business', 'architecture', 'process', 'ux', 'data_api', 'planning', 'transformation')
LANGUAGES = {'en': 'English', 'hi': 'Hindi', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'ar': 'Arabic', 'pt': 'Portuguese', 'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean', 'it': 'Italian', 'bn': 'Bengali', 'ta': 'Tamil', 'te': 'Telugu', 'mr': 'Marathi', 'ur': 'Urdu', 'ru': 'Russian', 'id': 'Indonesian', 'tr': 'Turkish', 'vi': 'Vietnamese'}


class Table(BaseModel):
    title: str = Field(max_length=200)
    columns: list[str] = Field(min_length=1, max_length=15)
    rows: list[list[str]] = Field(max_length=100)

    @model_validator(mode='after')
    def rectangular(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError('Each table row must match its columns.')
        return self


class Section(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(max_length=16000)
    items: list[str] = Field(max_length=50)
    tables: list[Table] = Field(max_length=8)


class DiagramNode(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,49}$')
    label: str = Field(min_length=1, max_length=300)
    lane: str = Field(max_length=100)
    kind: Literal['start', 'task', 'decision', 'end', 'entity', 'component']


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str = Field(max_length=200)


class Diagram(BaseModel):
    title: str = Field(max_length=200)
    kind: Literal['workflow', 'bpmn', 'swimlane', 'decision_tree', 'architecture', 'er', 'data_flow']
    nodes: list[DiagramNode] = Field(min_length=1, max_length=30)
    edges: list[DiagramEdge] = Field(max_length=60)

    @model_validator(mode='after')
    def references(self):
        ids = {n.id for n in self.nodes}
        if len(ids) != len(self.nodes) or any(e.source not in ids or e.target not in ids for e in self.edges):
            raise ValueError('Diagram node IDs must be unique and edges must refer to existing nodes.')
        return self


class ScreenControl(BaseModel):
    label: str = Field(max_length=150)
    kind: Literal['text', 'input', 'button', 'table', 'metric', 'select', 'navigation']
    detail: str = Field(max_length=600)


class Screen(BaseModel):
    name: str = Field(max_length=150)
    persona: str = Field(max_length=200)
    purpose: str = Field(max_length=1000)
    controls: list[ScreenControl] = Field(min_length=1, max_length=20)


class CodeAsset(BaseModel):
    filename: str = Field(pattern=r'^[A-Za-z0-9_-]+\.(yaml|json|sql|md)$')
    language: Literal['yaml', 'json', 'sql', 'markdown']
    content: str = Field(min_length=1, max_length=40000)


class Assessment(BaseModel):
    dimension: Literal['digital_maturity','ai_readiness','implementation_readiness','solution_quality','automation_opportunity']
    rating: Literal['unknown','emerging','developing','established','optimized']
    reason: str = Field(min_length=1,max_length=2000)
    evidence: list[str] = Field(min_length=1,max_length=10)


class Deliverable(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    sections: list[Section] = Field(min_length=1, max_length=20)
    diagrams: list[Diagram] = Field(max_length=8)
    screens: list[Screen] = Field(max_length=8)
    code_assets: list[CodeAsset] = Field(max_length=8)
    assumptions: list[str] = Field(max_length=30)
    validation_steps: list[str] = Field(min_length=1, max_length=30)
    assessments: list[Assessment] = Field(default_factory=list, max_length=5)


class GenerateInput(BaseModel):
    language: str = Field(default='en', max_length=50)
    instructions: str = Field(default='', max_length=4000)


class EditInput(BaseModel):
    base_version: int = Field(ge=0)
    content: Deliverable
    note: str = Field(default='Manual revision', max_length=1000)


class CommentInput(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    artifact_kind: str = Field(default='', max_length=40)


class ReviewInput(BaseModel):
    version: int = Field(ge=1)
    decision: Literal['approved', 'changes_requested']
    note: str = Field(min_length=1, max_length=2000)


def validate_coverage(kind, content):
    if kind in ('business','transformation'):
        required_assessments={'digital_maturity'} if kind=='business' else {'digital_maturity','ai_readiness','implementation_readiness','solution_quality','automation_opportunity'}
        if not required_assessments.issubset({a.dimension for a in content.assessments}):
            raise ValueError('Include evidence-based maturity/readiness assessments, using unknown where evidence is missing.')
    diagrams = {d.kind for d in content.diagrams}
    required = {'architecture': {'architecture','data_flow'}, 'process': {'bpmn','swimlane','decision_tree'},
                'data_api': {'er','data_flow'}}.get(kind, set())
    if not required.issubset(diagrams):
        raise ValueError('Required diagrams are missing: ' + ', '.join(sorted(required - diagrams)))
    if kind == 'ux' and len(content.screens) < 3:
        raise ValueError('UX design needs at least three screen wireframes.')
    if kind == 'data_api' and not {'sql','yaml'}.issubset({a.language for a in content.code_assets}):
        raise ValueError('Database/API design needs SQL DDL and an OpenAPI YAML asset.')
    if kind == 'data_api':
        valid_spec=False
        for asset in content.code_assets:
            if asset.language!='yaml': continue
            try:
                spec=yaml.safe_load(asset.content)
                valid_spec=isinstance(spec,dict) and str(spec.get('openapi','')).startswith('3.') and isinstance(spec.get('info'),dict) and bool(spec.get('paths')) and isinstance(spec['paths'],dict) and all(isinstance(path,str) and path.startswith('/') for path in spec['paths'])
                if valid_spec: break
            except (yaml.YAMLError,RecursionError): pass
        if not valid_spec: raise ValueError('Provide parseable OpenAPI 3 YAML with info and nonempty REST paths.')
