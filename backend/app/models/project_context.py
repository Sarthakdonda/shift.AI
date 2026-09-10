"""Persistent discovery memory and the provider's evidence/question contracts."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class ContextFact(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    category: str = Field(min_length=1)
    topic: str = Field(min_length=1, description='Stable, specific information key, reused across paraphrases, e.g. organization.size')
    fact: str = Field(min_length=1)
    source: str = Field(min_length=1, description='Human-readable citation including document page/chunk when applicable')
    source_ids: list[str] = Field(min_length=1, description='Exact IDs of supporting user messages or current documents; never assistant messages')
    replaces_existing: bool = Field(default=False, description='True only for an explicit user correction of prior facts on this topic')


class Unknown(BaseModel):
    topic: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    priority: Literal['high', 'medium', 'low']


class Question(BaseModel):
    question: str = Field(min_length=5, max_length=1200)
    topic: str = Field(min_length=1, description='Specific unknown to resolve; reuse known fact and historical question topic keys')
    reason: str = Field(min_length=1)
    priority: Literal['high', 'medium', 'low']


class ProjectContext(BaseModel):
    version: int = 1
    stated_request: str
    known_facts: list[ContextFact] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[Unknown] = Field(default_factory=list)
    document_findings: list[ContextFact] = Field(default_factory=list)
    questions_asked: list[Question] = Field(default_factory=list)
    answered_topics: list[str] = Field(default_factory=list)
    processed_message_ids: list[str] = Field(default_factory=list)
    information_sufficiency: int = Field(default=0, ge=0, le=100)
    ready_for_analysis: bool = False
    readiness_reason: str = ''
