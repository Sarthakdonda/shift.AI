"""Verify a deployed application through its public frontend.

Provider build status is not accepted as proof. This signs in through the
Vercel gateway, then creates, reads, updates and deletes one clearly marked
record, exercising browser -> Vercel -> Render -> MongoDB. No credential or
record content is returned.
"""
import json
import secrets
from datetime import date
import httpx
from app.core.errors import AppError


def fail(message):
    raise AppError(message, 502, 'verification_failed')


def sample_entity(spec):
    """A module that can be written without pre-existing related records."""
    return next((e for e in spec['entities'] if not any(f['kind'] == 'reference' and f['required'] for f in e['fields'])), None)


def sample_values(entity, marker):
    outputs = set((entity.get('logic') or {}).get('outputs', []))
    values = {}
    for field in entity['fields']:
        if field['name'] in outputs:
            continue
        kind = field['kind']
        values[field['name']] = {'text': marker, 'email': 'deploy-check@example.com', 'number': 1, 'boolean': True,
                                 'date': date.today().isoformat(), 'reference': None}.get(kind, (field['options'] or [''])[0])
    if entity.get('logic'):
        values.update(json.loads(entity['logic']['cases'][0]['input_json']))
    return values


def check(frontend, build_id, spec, email, password, timeout=90):
    frontend = frontend.rstrip('/')
    checks = []
    with httpx.Client(base_url=frontend, timeout=timeout, follow_redirects=False, trust_env=False) as client:
        def call(method, path, body=None, cookie=''):
            headers = {'Origin': frontend}
            if cookie:
                headers['Cookie'] = cookie
            try:
                response = client.request(method, path, json=body, headers=headers)
            except httpx.HTTPError:
                fail('The frontend did not answer ' + path + ' within ' + str(timeout) + ' seconds.')
            try:
                data = response.json()
            except ValueError:
                data = None
            return response, data

        response, release = call('GET', '/release.json')
        if response.status_code in (301, 302, 303, 307, 308, 401, 403):
            fail('The frontend URL is not public (HTTP ' + str(response.status_code) + '). Vercel Deployment Protection '
                 'may cover it; disable protection for this project\'s production domain, then retry.')
        if response.status_code != 200 or (release or {}).get('build_id') != build_id:
            fail('The frontend is not serving this build (HTTP ' + str(response.status_code) + ').')
        checks.append('frontend release identity')
        response, health = call('GET', '/health')
        if response.status_code != 200 or (health or {}).get('status') != 'ok' or health.get('build_id') != build_id:
            fail('The frontend could not reach the backend health check (HTTP ' + str(response.status_code) + ').')
        if health.get('database') != 'mongodb':
            fail('The backend is not using its MongoDB database.')
        checks.append('frontend-to-backend health')
        response, _ = call('POST', '/api/login', {'email': email, 'password': password})
        cookie = (response.headers.get('set-cookie') or '').split(';')[0]
        if response.status_code != 200 or not cookie.startswith('app_session='):
            fail('Signing in through the frontend failed (HTTP ' + str(response.status_code) + ').')
        checks.append('sign-in')
        response, profile = call('GET', '/api/spec', cookie=cookie)
        if response.status_code != 200 or (profile or {}).get('user', {}).get('role') != 'admin':
            fail('The signed-in session was not accepted (HTTP ' + str(response.status_code) + ').')
        entity = sample_entity(spec)
        if not entity:
            fail('No module can be written without related records, so CRUD could not be verified.')
        base = '/api/records/' + entity['name']
        marker = 'shift-deploy-check-' + secrets.token_hex(4)
        values = sample_values(entity, marker)
        response, created = call('POST', base, values, cookie)
        if response.status_code != 200 or not (created or {}).get('id'):
            fail('Creating a record through the frontend failed (HTTP ' + str(response.status_code) + ').')
        record = created['id']

        def listed():
            status, rows = call('GET', base, cookie=cookie)
            if status.status_code != 200 or not isinstance(rows, list):
                fail('Listing records through the frontend failed (HTTP ' + str(status.status_code) + ').')
            return next((row for row in rows if row.get('id') == record), None)

        if not listed():
            fail('A created record was not returned by the database.')
        checks.append('create and read')
        text = next((f['name'] for f in entity['fields'] if f['kind'] == 'text' and f['name'] in values), None)
        if text:
            updated = {**values, text: marker + '-updated'}
            response, _ = call('POST', base + '/' + record, updated, cookie)
            row = listed()
            if response.status_code != 200 or not row or row.get(text) != marker + '-updated':
                fail('Updating a record through the frontend did not persist (HTTP ' + str(response.status_code) + ').')
            checks.append('update')
        response, _ = call('DELETE', base + '/' + record, cookie=cookie)
        if response.status_code != 200 or listed():
            fail('Deleting the verification record failed (HTTP ' + str(response.status_code) + ').')
        checks.append('delete')
        call('POST', '/api/logout', {}, cookie)
    return {'checks': checks, 'module': entity['name']}
