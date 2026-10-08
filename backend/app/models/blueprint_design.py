"""Reviewable database and requirement contracts; never execute generated SQL."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Identifier = str


class Column(BaseModel):
    name: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,49}$')
    data_type: Literal['uuid', 'text', 'integer', 'bigint', 'boolean', 'numeric', 'timestamp', 'date', 'jsonb']
    nullable: bool
    primary_key: bool
    unique: bool
    description: str = Field(min_length=1, max_length=1000)


class Index(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=8)
    unique: bool
    reason: str = Field(min_length=1, max_length=500)


class Entity(BaseModel):
    name: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,49}$')
    description: str = Field(min_length=1, max_length=1000)
    columns: list[Column] = Field(min_length=1, max_length=50)
    indexes: list[Index] = Field(max_length=10)
    retention: str = Field(min_length=1, max_length=1000)


class Relationship(BaseModel):
    source_entity: str
    source_columns: list[str] = Field(min_length=1, max_length=8)
    target_entity: str
    target_columns: list[str] = Field(min_length=1, max_length=8)
    on_delete: Literal['RESTRICT', 'CASCADE', 'SET NULL']
    description: str = Field(min_length=1, max_length=120)


class DatabaseDesign(BaseModel):
    dialect: Literal['PostgreSQL']
    entities: list[Entity] = Field(min_length=1, max_length=30)
    relationships: list[Relationship] = Field(max_length=60)
    normalization: str = Field(min_length=1, max_length=2000)
    migration: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def integrity(self):
        entities = {e.name: e for e in self.entities}
        if len(entities) != len(self.entities):
            raise ValueError('Database entity names must be unique.')
        for entity in self.entities:
            names = {c.name for c in entity.columns}
            if len(names) != len(entity.columns) or not any(c.primary_key for c in entity.columns):
                raise ValueError(entity.name + ' requires unique column names and a primary key.')
            if any(c.primary_key and c.nullable for c in entity.columns):
                raise ValueError('Primary keys cannot be nullable: ' + entity.name)
            for index in entity.indexes:
                if not set(index.columns).issubset(names) or len(set(index.columns)) != len(index.columns):
                    raise ValueError('Invalid index columns in ' + entity.name)
        seen = set()
        for rel in self.relationships:
            identity = (rel.source_entity, tuple(rel.source_columns), rel.target_entity, tuple(rel.target_columns))
            if identity in seen:
                raise ValueError('Duplicate foreign-key relationship.')
            seen.add(identity)
            if rel.source_entity not in entities or rel.target_entity not in entities:
                raise ValueError('Foreign keys must reference declared entities.')
            source, target = entities[rel.source_entity], entities[rel.target_entity]
            src, dst = {c.name: c for c in source.columns}, {c.name: c for c in target.columns}
            if (len(rel.source_columns) != len(rel.target_columns) or
                len(set(rel.source_columns)) != len(rel.source_columns) or
                len(set(rel.target_columns)) != len(rel.target_columns) or
                not set(rel.source_columns).issubset(src) or not set(rel.target_columns).issubset(dst)):
                raise ValueError('Foreign-key columns must exist with matching arity.')
            if any(src[a].data_type != dst[b].data_type for a, b in zip(rel.source_columns, rel.target_columns)):
                raise ValueError('Foreign-key column types must agree.')
            if not unique_key(target, rel.target_columns):
                raise ValueError('Foreign keys must reference a complete primary or unique key.')
            if rel.on_delete == 'SET NULL' and any(not src[c].nullable for c in rel.source_columns):
                raise ValueError('SET NULL requires nullable foreign-key columns.')
        return self


def unique_key(entity, columns):
    keys = [{c.name for c in entity.columns if c.primary_key}]
    keys += [{c.name} for c in entity.columns if c.unique]
    keys += [set(i.columns) for i in entity.indexes if i.unique]
    return set(columns) in keys


class Requirement(BaseModel):
    id: str = Field(pattern=r'^REQ-[A-Za-z0-9_-]{1,40}$')
    objective: str = Field(min_length=1, max_length=1000)
    description: str = Field(min_length=1, max_length=2000)
    kind: Literal['functional', 'non_functional']
    user_story: str = Field(min_length=1, max_length=1500)
    acceptance: list[str] = Field(min_length=1, max_length=10)
    modules: list[str] = Field(min_length=1, max_length=10)
    components: list[str] = Field(min_length=1, max_length=10)
    entities: list[str] = Field(max_length=30)
    api_operations: list[str] = Field(max_length=20, description='Exact METHOD /path operations, or empty for non-API work.')
    test_cases: list[str] = Field(min_length=1, max_length=15, description='Test ID and concrete scenario; proposed tests, not execution results.')
    evidence: list[str] = Field(min_length=1, max_length=15, description='User answer/document reference, or explicitly unconfirmed assumption.')
    assumptions: list[str] = Field(max_length=15)
