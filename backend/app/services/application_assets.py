"""Derived diagrams, schema and executable API contract for generated applications."""
import html
import json


def assets(spec, build_id):
    schema = []
    mermaid = ['erDiagram']
    svg = []
    positions = {}
    y = 24
    for entity in spec['entities']:
        name = entity['name']; table = 'e_' + name
        columns = ['id TEXT PRIMARY KEY', 'created_at REAL NOT NULL', 'updated_at REAL NOT NULL']
        mermaid.append(f'  {table} {{\n    string id PK\n    real created_at\n    real updated_at')
        height = 110 + len(entity['fields']) * 22
        positions[name] = (24, y, height)
        svg.append(f'<rect x="24" y="{y}" width="430" height="{height}" rx="8" fill="#fff" stroke="#64748b"/><text x="40" y="{y+26}" font-weight="bold">{html.escape(table)}</text><text x="40" y="{y+50}">id: TEXT PK · created_at / updated_at</text>')
        for index, field in enumerate(entity['fields']):
            kind = 'REAL' if field['kind'] == 'number' else 'INTEGER' if field['kind'] == 'boolean' else 'TEXT'
            reference = f' REFERENCES "e_{field["reference"]}"(id) ON DELETE RESTRICT' if field['kind'] == 'reference' else ''
            columns.append(f'"{field["name"]}" {kind}' + (' NOT NULL' if field['required'] else '') + reference)
            mermaid.append(f'    {kind.lower()} {field["name"]}' + (' FK' if reference else ''))
            label = field['name'] + ': ' + kind + (' FK → e_' + str(field['reference']) + '.id' if reference else '')
            svg.append(f'<text x="40" y="{y+76+index*22}">{html.escape(label)}</text>')
        mermaid.append('  }')
        schema.append(f'CREATE TABLE IF NOT EXISTS "{table}" (\n  ' + ',\n  '.join(columns) + '\n);')
        y += height + 34
    edge = 0
    for entity in spec['entities']:
        for field in entity['fields']:
            if field['kind'] == 'reference':
                mermaid.append(f'  e_{field["reference"]} |o--o{{ e_{entity["name"]} : {field["name"]}')
                _, a, ah = positions[entity['name']]; _, b, bh = positions[field['reference']]
                lane = 480 + (edge % 12) * 14; edge += 1
                svg.append(f'<path d="M454 {a+ah/2} H{lane} V{b+bh/2} H454" fill="none" stroke="#d97706" marker-end="url(#arrow)"/>')
    files = {'migrations/001_schema.sql': 'PRAGMA foreign_keys=ON;\n' + '\n'.join(schema),
             'schema.mmd': '\n'.join(mermaid),
             'schema.svg': f'<svg xmlns="http://www.w3.org/2000/svg" width="680" height="{y}" viewBox="0 0 680 {y}" role="img" aria-label="Entity relationship diagram"><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker></defs><g font-family="sans-serif" font-size="13">'+''.join(svg)+'</g></svg>'}
    responses = {'200': {'description': 'Operation completed'}, '400': {'description': 'Invalid data'}, '401': {'description': 'Sign-in required'}, '403': {'description': 'Role or Origin rejected'}, '409': {'description': 'Relationship or workflow conflict'}}
    json_body = lambda shape: {'required': True, 'content': {'application/json': {'schema': shape}}}
    paths = {'/health': {'get': {'security': [], 'responses': {'200': {'description': 'SQLite health and build_id/spec_hash identity'}}}},
             '/api/login': {'post': {'security': [], 'requestBody': json_body({'type': 'object', 'required': ['email', 'password'], 'properties': {'email': {'type': 'string', 'format': 'email'}, 'password': {'type': 'string'}}}), 'responses': responses}},
             '/api/logout': {'post': {'responses': responses}},
             '/api/spec': {'get': {'responses': responses}},
             '/api/users': {'get': {'description': 'Administrator only', 'responses': responses}, 'post': {'description': 'Administrator only', 'requestBody': json_body({'type': 'object', 'required': ['email', 'password', 'role'], 'properties': {'email': {'type': 'string', 'format': 'email'}, 'password': {'type': 'string', 'minLength': 12}, 'role': {'type': 'string', 'enum': spec['roles']}}}), 'responses': {'201': {'description': 'Account created'}, **responses}}}}
    for entity in spec['entities']:
        props = {f['name']: {'type': 'number' if f['kind'] == 'number' else 'boolean' if f['kind'] == 'boolean' else 'string',
                           'nullable': not f['required'], **({'enum': f['options']} if f['kind'] == 'select' else {})} for f in entity['fields']}
        shape = {'type': 'object', 'properties': props, 'required': [f['name'] for f in entity['fields'] if f['required']], 'additionalProperties': False}
        base = '/api/records/' + entity['name']
        paths[base] = {'get': {'description': 'Read roles: admin, ' + ', '.join(entity['read_roles']), 'parameters': [{'in': 'query', 'name': 'q', 'schema': {'type': 'string'}}, {'in': 'query', 'name': 'offset', 'schema': {'type': 'integer'}}], 'responses': {'200': {'description': 'At most 100 records', 'content': {'application/json': {'schema': {'type': 'array', 'items': {'type': 'object', 'properties': {'id': {'type': 'string'}, **props}}}}}}, **{k:v for k,v in responses.items() if k != '200'}}},
                       'post': {'description': 'Write roles: admin, ' + ', '.join(entity['write_roles']), 'requestBody': json_body(shape), 'responses': responses}}
        parameter = [{'in': 'path', 'name': 'id', 'required': True, 'schema': {'type': 'string'}}]
        paths[base+'/{id}'] = {'parameters': parameter, 'post': {'summary': 'Update record', 'requestBody': json_body(shape), 'responses': responses}, 'delete': {'responses': responses}}
        if entity['transitions']:
            paths[base+'/{id}/transition'] = {'parameters': parameter, 'post': {'description': 'Zero-based transition index; source state and role enforced.', 'requestBody': json_body({'type': 'object', 'required': ['transition'], 'properties': {'transition': {'type': 'integer', 'minimum': 0, 'maximum': len(entity['transitions'])-1}}}), 'responses': responses}}
    files['openapi.json'] = json.dumps({'openapi': '3.0.3', 'info': {'title': spec['name'], 'version': build_id, 'description': 'Writes require the exact APP_ORIGIN in the Origin header. Admin has global module access.'},
        'security': [{'session': []}], 'components': {'securitySchemes': {'session': {'type': 'apiKey', 'in': 'cookie', 'name': 'app_session'}}}, 'paths': paths}, ensure_ascii=False, indent=2)
    files['traceability.json'] = json.dumps([{'requirement': r, 'modules': [e['name'] for e in spec['entities'] if r['id'] in e['requirement_ids']], 'validation': 'Not executed by compilation; see build validation results.'} for r in spec['requirements']], ensure_ascii=False, indent=2)
    return files
