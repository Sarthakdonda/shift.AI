"""Decide whether a generated build is a real, deployable web application.

Only the stack the compiler emits today is supported: the trusted Python runtime
(server.py) with static public/ assets and a MongoDB-backed cloud mode. Anything
else is rejected with a reason instead of attempting an invalid deployment.
"""
import hashlib
import json
from app.core.errors import AppError
from app.services.application_generator import STACK, digest
from app.services.github_app import FORBIDDEN, SECRET_VALUE

REQUIRED_FILES = ('server.py', 'storage.py', 'storage_mongo.py', 'schema_contract.py', 'business_logic.py',
                  'integration_delivery.py', 'spec.json', 'release.json', 'requirements.txt', '.python-version',
                  'deploy.json', 'public/index.html', 'public/app.js', 'public/style.css')


def refuse(message):
    raise AppError(message, 409, 'deployment_validation')


def validate_build(build, *, allow_manual=False):
    """Return the deployment manifest for a deployable build, or raise with the reason."""
    spec = build.get('spec') or {}
    files = build.get('files') or {}
    if build.get('status') != 'ready':
        refuse('Only builds that passed isolated runtime validation can be deployed. Start Docker and rebuild, '
               'or review the build error.')
    if spec.get('storage_mode', 'shared_server') != 'shared_server':
        refuse('This build is a ' + str(spec.get('storage_mode')) + ' application. One-click cloud deployment '
               'supports shared-server web applications; download the portable build instead.')
    if 'web' not in spec.get('target_platforms', ['web']):
        refuse('This specification does not target the web.')
    manual = [r['id'] for r in spec.get('requirements', []) if r.get('implementation') == 'manual']
    if manual and not allow_manual:
        refuse('Requirements ' + ', '.join(manual[:8]) + ' are not implemented. Resolve them before deployment.')
    missing = [name for name in REQUIRED_FILES if name not in files]
    if missing:
        refuse('The build is missing ' + ', '.join(missing[:6]) + '. Rebuild with the current generator.')
    manifest = build.get('manifest') or {}
    if set(manifest) != set(files) or any(hashlib.sha256(files[n].encode()).hexdigest() != h for n, h in manifest.items()):
        refuse('Source integrity verification failed. Generate a new build.')
    try:
        plan = json.loads(files['deploy.json'])
        release = json.loads(files['release.json'])
    except ValueError:
        refuse('The deployment manifest is unreadable. Rebuild the application.')
    if plan.get('stack') != STACK:
        refuse('Unsupported application stack "' + str(plan.get('stack')) + '". Supported: ' + STACK + '.')
    if plan.get('spec_hash') != digest(spec) or release.get('spec_hash') != digest(spec) or release.get('build_id') != str(build['_id']):
        refuse('The deployment manifest does not match this build. Rebuild the application.')
    backend = plan.get('backend', {})
    if backend.get('entry') != 'server.py' or backend.get('health_check_path') != '/health' or not backend.get('start_command'):
        refuse('The backend entry point or health check is not defined.')
    blocked = sorted(n for n, data in files.items() if FORBIDDEN.search('/' + n) or SECRET_VALUE.search(data))
    if blocked:
        refuse('Files that look like credentials were found: ' + ', '.join(blocked[:6]) + '.')
    return plan
