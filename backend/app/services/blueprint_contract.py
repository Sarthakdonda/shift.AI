"""Derive diagrams, field catalogues and SQL from ONE validated database design."""
import copy
from app.models.blueprint_design import DatabaseDesign, unique_key


def database_artifacts(value):
    design = DatabaseDesign.model_validate(value)
    entities = {e.name: e for e in design.entities}
    ids = {e.name: 'entity_' + str(i) for i, e in enumerate(design.entities)}
    foreign = {(r.source_entity, c) for r in design.relationships for c in r.source_columns}
    nodes, edges, tables, statements = [], [], [], []
    quote = lambda name: '"' + name + '"'
    for entity in design.entities:
        fields, rows, ddl = [], [], []
        for column in entity.columns:
            keys = (' PK' if column.primary_key else '') + (' FK' if (entity.name, column.name) in foreign else '')
            fields.append(f'{column.name} {column.data_type}{keys}')
            rows.append([column.name, column.data_type, 'Yes' if column.nullable else 'No',
                         (keys.strip() + (' UNIQUE' if column.unique else '')).strip() or '—', column.description])
            ddl.append(f'  {quote(column.name)} {column.data_type.upper()}' + ('' if column.nullable else ' NOT NULL') + (' UNIQUE' if column.unique else ''))
        ddl.append('  PRIMARY KEY (' + ', '.join(quote(c.name) for c in entity.columns if c.primary_key) + ')')
        statements.append('CREATE TABLE ' + quote(entity.name) + ' (\n' + ',\n'.join(ddl) + '\n);')
        nodes.append({'id': ids[entity.name], 'label': entity.name + '\n' + '\n'.join(fields), 'kind': 'entity', 'lane': ''})
        tables.append({'title': entity.name + ' — ' + entity.description, 'columns': ['Column', 'Type', 'Nullable', 'Keys', 'Meaning'], 'rows': rows})
        for i, index in enumerate(entity.indexes):
            statements.append('CREATE ' + ('UNIQUE ' if index.unique else '') + 'INDEX ' + quote('idx_' + entity.name[:40] + '_' + str(i)) + ' ON ' + quote(entity.name) + ' (' + ', '.join(map(quote, index.columns)) + ');')
    # Unique indexes exist before referenced foreign keys; cycles are supported.
    for i, rel in enumerate(design.relationships):
        source = entities[rel.source_entity]
        nullable = any(c.nullable for c in source.columns if c.name in rel.source_columns)
        parent, child = ('0..1' if nullable else '1'), ('0..1' if unique_key(source, rel.source_columns) else '0..*')
        label = f'{parent} to {child}: {rel.source_entity}.{",".join(rel.source_columns)} -> {rel.target_entity}.{",".join(rel.target_columns)}; {rel.description}'
        edges.append({'source': ids[rel.target_entity], 'target': ids[rel.source_entity], 'label': label})
        statements.append('ALTER TABLE ' + quote(rel.source_entity) + ' ADD CONSTRAINT ' + quote('fk_' + str(i+1)) + ' FOREIGN KEY (' + ', '.join(map(quote, rel.source_columns)) + ') REFERENCES ' + quote(rel.target_entity) + ' (' + ', '.join(map(quote, rel.target_columns)) + ') ON DELETE ' + rel.on_delete + ';')
    governance = {'title': 'Indexes, retention and migration', 'columns': ['Entity / concern', 'Decision'], 'rows':
        [[e.name + ' retention', e.retention] for e in design.entities] +
        [[e.name + ' index', ', '.join(i.columns) + (' UNIQUE' if i.unique else '') + ': ' + i.reason] for e in design.entities for i in e.indexes] +
        [['Normalization', design.normalization], ['Migration', design.migration]]}
    return {'diagram': {'title': 'Entity relationship diagram', 'kind': 'er', 'nodes': nodes, 'edges': edges},
            'tables': tables + [governance], 'sql': {'filename': 'schema.sql', 'language': 'sql', 'content': '\n\n'.join(statements)}}


def materialize(parts):
    """Keep raw proposals/version history; authoritative rendered schema is derived."""
    result = copy.deepcopy(parts)
    data = result.get('data_report', {})
    if not data.get('database_design'):
        return result
    artifacts = database_artifacts(data['database_design'])
    for section in data['chapters']:
        if section['key'] == 'data_model':
            section['diagrams'] = [d for d in section['diagrams'] if d['kind'] != 'er'] + [artifacts['diagram']]
        elif section['key'] == 'database':
            # Free-text tables remain in the saved source part, while the published
            # column catalogue and SQL are rendered from the validated contract.
            section['tables'] = artifacts['tables']
            section['code_assets'] = [a for a in section['code_assets'] if a['language'] != 'sql'] + [artifacts['sql']]
    return result
