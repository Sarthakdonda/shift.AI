"""Compile validated, approved data into a fixed, reviewable runtime."""
import ast
import hashlib
import io
import json
import zipfile
import html
from pathlib import Path
from app.models.application import ApplicationSpec
from app.templates.application.schema_contract import compatibility
from app.services.application_assets import assets
from app.services.application_locale import localize

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'application'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


STACK = 'shift-python-runtime-v1'


def deployment_manifest(spec, build_id, application_id):
    """What the compiled source actually is, so deployment never guesses."""
    integrations = sorted({a['name'] for e in spec['entities'] for a in e.get('integrations', [])})
    return {
        'schema_version': 1, 'stack': STACK, 'application_id': application_id, 'build_id': build_id,
        'spec_hash': digest(spec), 'name': spec['name'],
        'backend': {'runtime': 'python', 'python_version': '3.13', 'entry': 'server.py',
                    'build_command': 'pip install -r requirements.txt', 'start_command': 'python server.py',
                    'health_check_path': '/health', 'port_env': 'PORT', 'instances': 1},
        'frontend': {'type': 'static', 'directory': 'public', 'entry': 'public/index.html',
                     'api_prefix': '/api', 'public_pages': [p['slug'] for p in spec.get('public_pages', [])],
                     'public_env': []},
        'database': {'engine': 'mongodb', 'required': bool(spec['entities']),
                     'collections': ['users', 'sessions', 'audit', 'integration_outbox'] + ['e_' + e['name'] for e in spec['entities']]},
        'environment': {
            'backend_secret': ['MONGODB_URI', 'ADMIN_PASSWORD'] + [f'INTEGRATION_{n.upper()}_TOKEN' for n in integrations],
            'backend_plain': ['DATABASE_BACKEND', 'MONGODB_DATABASE', 'ADMIN_EMAIL', 'APP_ORIGIN', 'COOKIE_SECURE', 'FRONTEND_ORIGINS']
                             + [f'INTEGRATION_{n.upper()}_URL' for n in integrations]},
    }


def compile_application(spec, build_id, application_id=None):
    spec = ApplicationSpec.model_validate(spec).model_dump()
    if spec['storage_mode'] != 'shared_server':
        from app.services.portable_generator import compile_portable
        return compile_portable(spec, build_id, application_id or build_id)
    files = {str(p.relative_to(TEMPLATE)).replace('\\', '/'): p.read_text(encoding='utf-8')
             for p in TEMPLATE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    files['spec.json'] = json.dumps(spec, ensure_ascii=False, indent=2)
    files['release.json'] = json.dumps({'build_id': build_id, 'spec_hash': digest(spec)})
    files['business_functions.json'] = json.dumps({e['name']: e['logic']['code'] for e in spec['entities'] if e.get('logic')}, ensure_ascii=False)
    navigation = ''.join('<a href="/site/' + page['slug'] + '">' + html.escape(page['title']) + '</a> ' for page in spec.get('public_pages', []))
    for page in spec.get('public_pages', []):
        sections = ''.join('<section><h2>' + html.escape(section['heading']) + '</h2><p>' + html.escape(section['text']).replace('\n', '<br>') + '</p></section>' for section in page['sections'])
        contact = '<a href="mailto:' + html.escape(page['contact_email'], quote=True) + '">Contact us</a>' if page['contact_email'] else ''
        files['public/site/' + page['slug'] + '.html'] = ('<!doctype html><html lang="' + html.escape(spec['language'], quote=True) + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(page['title']) + '</title><meta name="description" content="' + html.escape(page['description'], quote=True) + '"><link rel="stylesheet" href="/style.css"></head><body><header><h1>' + html.escape(spec['name']) + '</h1><a href="/workspace">Workspace sign in</a></header><main><nav>' + navigation + '</nav><h1>' + html.escape(page['title']) + '</h1><p>' + html.escape(page['description']) + '</p>' + sections + contact + '</main></body></html>')
    files.update(assets(spec, build_id))
    files['public/style.css'] += '\nbutton:hover{border-color:' + spec['accent'] + '}\n'
    localize(files, spec)
    files['Dockerfile'] = ('FROM python:3.13-slim\nWORKDIR /app\nCOPY . /app\n'
                           'RUN mkdir -p /app/data && chown -R 10001:10001 /app\n'
                           'USER 10001:10001\nENV PORT=8080 DATABASE_PATH=/app/data/application.db PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n'
                           'EXPOSE 8080\nCMD ["python", "server.py"]\n')
    files['.dockerignore'] = 'data\n.env\n.git\n__pycache__\n*.db\n'
    # Cloud deployment (Render native Python runtime + MongoDB). Pinned, tested versions.
    files['requirements.txt'] = 'pymongo[srv]==4.18.0\n'
    files['.python-version'] = '3.13\n'
    files['.gitignore'] = '.env\n.env.*\n!.env.example\ndata/\n*.db\n__pycache__/\n*.pyc\n'
    files['deploy.json'] = json.dumps(deployment_manifest(spec, build_id, application_id or build_id), indent=2)
    files['.env.example'] = ('ADMIN_EMAIL=\nADMIN_PASSWORD=\nAPP_ORIGIN=https://your-service.onrender.com\nCOOKIE_SECURE=true\nPORT=8080\n'
                             '# SQLite (single instance, persistent disk)\nDATABASE_PATH=/app/data/application.db\n'
                             '# MongoDB (cloud deployment); the URI is a secret supplied by the host\nDATABASE_BACKEND=\nMONGODB_URI=\nMONGODB_DATABASE=\n'
                             '# Additional allowed browser origins for writes, comma separated\nFRONTEND_ORIGINS=\n')
    for action in sorted({a['name'] for e in spec['entities'] for a in e.get('integrations', [])}):
        files['.env.example'] += f'INTEGRATION_{action.upper()}_URL=\nINTEGRATION_{action.upper()}_TOKEN=\n'
    files['README.md'] = f'''# {spec['name']}

Generated by shift.AI from an explicitly approved application specification.

Requires Python 3.13. SQLite mode needs no third-party packages; MongoDB mode
needs `pip install -r requirements.txt` (pymongo). Set ADMIN_EMAIL and
ADMIN_PASSWORD (12+ characters) in the process environment before first startup.
Set APP_ORIGIN to the exact public HTTPS origin; serve behind a TLS reverse proxy.
Run `python server.py`. For local use only, set COOKIE_SECURE=false and
APP_ORIGIN=http://localhost:8080. Environment files are examples, not auto-loaded.

Cloud deployment (deploy.json describes it): build `pip install -r requirements.txt`,
start `python server.py`, health check `/health`. Set DATABASE_BACKEND=mongodb,
MONGODB_URI (a secret, database-scoped credential) and MONGODB_DATABASE on the
backend host only. Never put the URI in the repository or a frontend.

The administrator creates team accounts in the application. Public signup is disabled.
Database: SQLite on a persistent disk at DATABASE_PATH. Keep one service instance.
Never use an ephemeral filesystem for production. Back up the disk independently.
On a new application release the runtime saves a consistent SQLite backup before
applying additive schema changes. Old tables/columns and business records are retained.
Restoring code does not undo data edits; restore database backups as a separate,
operator-reviewed action. Do not scale horizontally with this SQLite runtime.

Render: deploy this Docker image to an image-backed web service with a persistent
disk mounted at /app/data (writable by UID 10001), PORT=8080, COOKIE_SECURE=true,
APP_ORIGIN, ADMIN_EMAIL and ADMIN_PASSWORD as secret service environment values.
Health check: /health. Never put passwords in the image or source repository.

`python -m unittest selftest -v` runs isolated auth, roles, CRUD, relation,
workflow and persistence contract checks. The platform records separately whether
these tests actually ran. Requirements marked manual are NOT implemented.

Runtime scope: relational CRUD, forms, search, roles, finite-state transitions,
public pages and bounded pure Python business calculations with frozen examples.
Calculated fields are evaluated on the server; historical records are not silently
recalculated. Review payroll rules and rates before use. Passing examples do not
establish statutory compliance or universal algorithm correctness.

Explicit integration actions enqueue a durable SQLite outbox. Configure each
INTEGRATION_NAME_URL and optional INTEGRATION_NAME_TOKEN in the deployment environment.
Only public HTTPS port 443 is accepted. Delivery retries at most five times; receivers
must honor Idempotency-Key because a crash can cause redelivery. Preview containers
have no outbound network. Integration status is visible under Integration deliveries.

Automatic repair can change business_functions.json while keeping approved acceptance
examples fixed. Review repair_history.json when present. No built-in email transport,
provider-specific OAuth connectors, arbitrary server code, or mobile binaries.
See spec.json for assumptions and limitations. Shared labels can be model-translated;
review translations before publishing, especially legal and payroll terminology.
'''
    findings = []
    for requirement in spec['requirements']:
        if requirement['implementation'] == 'manual':
            findings.append({'severity': 'high', 'component': requirement['id'], 'issue': requirement['description'],
                             'evidence': 'Requirement is marked manual in the approved specification.',
                             'correction': 'Implement and validate the required adapter or custom workflow.', 'status': 'open'})
    for path, content in files.items():
        if path.endswith('.py'):
            ast.parse(content, filename=path)
    manifest = {path: hashlib.sha256(content.encode()).hexdigest() for path, content in files.items()}
    return files, manifest, findings


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path, content in files.items():
            bundle.writestr(path, content)
    return output.getvalue()
