"""shift.AI trusted relational application runtime (standard library; pymongo only for MongoDB)."""
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import time
from datetime import date, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from business_logic import run_logic
from storage import Conflict, Unavailable, open_store

ROOT = Path(__file__).resolve().parent
SPEC = json.loads((ROOT / 'spec.json').read_text(encoding='utf-8'))
IDENTITY = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
ENTITIES = {e['name']: e for e in SPEC['entities']}
SECURE = os.environ.get('COOKIE_SECURE', 'true').lower() == 'true'
FUNCTIONS = json.loads((ROOT / 'business_functions.json').read_text('utf-8')) if (ROOT / 'business_functions.json').exists() else {}
STORE = open_store(ROOT)
# SQLite helpers remain importable for the shipped acceptance tests.
DB_PATH = getattr(STORE, 'path', None)
connection = getattr(STORE, 'connection', None)


def app_origin(host=''):
    configured = os.environ.get('APP_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL', '')
    return configured.rstrip('/') or ('https://' if SECURE else 'http://') + host


def allowed_origins(host=''):
    extra = {o.strip().rstrip('/') for o in os.environ.get('FRONTEND_ORIGINS', '').split(',') if o.strip()}
    return {app_origin(host)} | extra


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()


def initial_admin():
    email, password = os.environ.get('ADMIN_EMAIL', '').strip().lower(), os.environ.get('ADMIN_PASSWORD', '')
    if not email or len(password) < 12:
        raise RuntimeError('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters) before first startup.')
    return email, password_hash(password)


def migrate():
    STORE.migrate(SPEC, IDENTITY, initial_admin)


def validate(entity, data, old=None, calculated=False):
    allowed = {f['name'] for f in entity['fields']}
    if set(data) - allowed:
        raise ValueError('Unknown field.')
    logic = entity.get('logic')
    if logic and not calculated:
        outputs = set(logic['outputs'])
        inputs = validate({**entity, 'logic': None, 'fields': [f for f in entity['fields'] if f['name'] not in outputs]},
                          {k: v for k, v in data.items() if k not in outputs}, old)
        result = run_logic(FUNCTIONS.get(entity['name'], logic['code']), inputs)
        if set(result) != outputs:
            raise ValueError('Business function returned unexpected fields.')
        return validate(entity, {**inputs, **result}, old, calculated=True)
    result = {}
    for field in entity['fields']:
        name = field['name']
        value = data.get(name)
        if value is None or value == '':
            if field['required']:
                raise ValueError(field['label'] + ' is required.')
            result[name] = None
            continue
        kind = field['kind']
        if kind == 'boolean':
            if not isinstance(value, bool):
                raise ValueError(field['label'] + ' must be true or false.')
            value = bool(value)
        elif kind == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(field['label'] + ' must be a finite number.')
        else:
            if not isinstance(value, str) or len(value) > 5000:
                raise ValueError(field['label'] + ' must be text of at most 5000 characters.')
            if kind == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
                raise ValueError('Enter a valid email address.')
            if kind == 'date':
                try:
                    date.fromisoformat(value)
                except ValueError:
                    # Business data often carries a time as well; keep the value as given.
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
            if kind == 'select' and value not in field['options']:
                raise ValueError('Choose an available option.')
        result[name] = value
    for field_name in {t['field'] for t in entity['transitions']}:
        field = next(f for f in entity['fields'] if f['name'] == field_name)
        if old and result[field_name] != old[field_name]:
            raise ValueError('Use the workflow action to change ' + field['label'] + '.')
        if not old and result[field_name] != field['options'][0]:
            raise ValueError('New records must start with ' + field['options'][0] + '.')
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'Application'

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, fmt, *args):
        # Never log bodies, passwords, sessions, or query strings.
        pass

    def respond(self, status, body, cookie=None, content_type='application/json'):
        raw = json.dumps(body, ensure_ascii=False).encode() if content_type == 'application/json' else body
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(raw)

    def payload(self):
        if not self._raw_body:
            raise ValueError('Provide a JSON body smaller than 64 KB.')
        body = json.loads(self._raw_body)
        if not isinstance(body, dict):
            raise ValueError('Expected an object.')
        return body

    def session_token(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get('Cookie', ''))
        token = cookie.get('app_session')
        return hashlib.sha256(token.value.encode()).hexdigest() if token else None

    def cookie(self, token, age=86400):
        return f'app_session={token}; HttpOnly; Path=/; SameSite=Strict; Max-Age={age}' + ('; Secure' if SECURE else '')

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def do_DELETE(self):
        self.handle_request('DELETE')

    def handle_request(self, method):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 65536:
                raise ValueError('Request too large.')
            self._raw_body = self.rfile.read(length) if length else b''
            self.route(method)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.respond(400, {'error': 'Invalid input. Check required fields, formats, and workflow state.'})
        except Conflict:
            self.respond(409, {'error': 'Duplicate value or referenced record. Check relationships before saving or deleting.'})
        except Unavailable:
            self.respond(503, {'error': 'The operation could not complete. Your saved data is preserved.'})
        except Exception:
            self.respond(500, {'error': 'The operation could not complete. Your saved data is preserved.'})

    def route(self, method):
        parsed = urlsplit(self.path)
        path = parsed.path
        if method != 'GET' and self.headers.get('Origin') not in allowed_origins(self.headers.get('Host', '')):
            return self.respond(403, {'error': 'Request origin is not allowed.'})
        pages = SPEC.get('public_pages', [])
        if method == 'GET' and (path == '/' and pages or path in ['/site/' + page['slug'] for page in pages]):
            slug = pages[0]['slug'] if path == '/' else path.rsplit('/', 1)[1]
            return self.respond(200, (ROOT / 'public' / 'site' / (slug + '.html')).read_bytes(), content_type='text/html')
        if method == 'GET' and path in ('/', '/workspace', '/app.js', '/style.css'):
            name = {'/': 'index.html', '/workspace': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
            kind = {'/': 'text/html', '/workspace': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css'}[path]
            return self.respond(200, (ROOT / 'public' / name).read_bytes(), content_type=kind)
        if method == 'GET' and path == '/health':
            try:
                STORE.ping()
            except Exception:
                return self.respond(503, {'status': 'unavailable', 'database': STORE.kind, **IDENTITY})
            return self.respond(200, {'status': 'ok', 'database': STORE.kind, **IDENTITY})
        if method == 'POST' and path == '/api/login':
            body = self.payload()
            email = str(body.get('email', '')).strip().lower()[:254]
            if not STORE.register_attempt(email):
                return self.respond(429, {'error': 'Too many attempts. Retry in 15 minutes.'})
            account = STORE.user_by_email(email)
            password = str(body.get('password', ''))[:1024]
            stored = account['password'] if account else password_hash('unavailable')
            valid = hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)
            if not account or not valid:
                return self.respond(401, {'error': 'Email or password is incorrect.'})
            STORE.clear_attempts(email)
            token = secrets.token_urlsafe(32)
            STORE.start_session(hashlib.sha256(token.encode()).hexdigest(), account['id'], time.time() + 86400)
            return self.respond(200, {'role': account['role']}, self.cookie(token))
        token = self.session_token()
        account = STORE.session_user(token) if token else None
        if not account:
            return self.respond(401, {'error': 'Please sign in.'})
        role = account['role']
        if method == 'POST' and path == '/api/logout':
            STORE.end_session(token)
            return self.respond(200, {'ok': True}, self.cookie('', 0))
        if method == 'GET' and path == '/api/spec':
            visible = [e for e in SPEC['entities'] if role == 'admin' or role in e['read_roles']]
            return self.respond(200, {**SPEC, 'entities': visible, 'user': {'email': account['email'], 'role': role}})
        if method == 'GET' and path == '/api/deliveries':
            return self.respond(200, STORE.deliveries(account['id'], role == 'admin'))
        if path == '/api/users':
            if role != 'admin':
                return self.respond(403, {'error': 'Administrator access required.'})
            if method == 'GET':
                return self.respond(200, STORE.list_users())
            if method == 'POST':
                body = self.payload()
                email, password, chosen = str(body['email']).strip().lower(), str(body['password']), body['role']
                if len(password) < 12 or len(password) > 1024 or chosen not in SPEC['roles'] or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                    raise ValueError('Invalid account.')
                uid = secrets.token_hex(16)
                STORE.create_user(uid, email, password_hash(password), chosen)
                return self.respond(201, {'id': uid})
        parts = path.strip('/').split('/')
        if len(parts) < 3 or parts[:2] != ['api', 'records'] or parts[2] not in ENTITIES:
            return self.respond(404, {'error': 'Not found.'})
        entity = ENTITIES[parts[2]]
        permissions = entity['read_roles'] if method == 'GET' else entity['write_roles']
        if role != 'admin' and role not in permissions:
            return self.respond(403, {'error': 'Your role cannot perform this action.'})
        if method == 'GET' and len(parts) == 3:
            query = parse_qs(parsed.query)
            offset = max(0, min(100000, int(query.get('offset', ['0'])[0])))
            term = query.get('q', [''])[0][:200]
            return self.respond(200, STORE.list_records(entity, term, offset))
        rid = parts[3] if len(parts) >= 4 else secrets.token_hex(16)
        old = STORE.get_record(entity, rid) if len(parts) >= 4 else None
        if len(parts) >= 4 and not old:
            return self.respond(404, {'error': 'Record not found.'})
        if method == 'POST' and len(parts) == 6 and parts[4] == 'integrations':
            action = next((action for action in entity.get('integrations', []) if action['name'] == parts[5]), None)
            if not action or (role != 'admin' and role not in action['roles']):
                return self.respond(403, {'error': 'Your role cannot run this integration.'})
            key = str(self.payload().get('request_id', ''))
            if not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', key):
                raise ValueError('A unique integration request ID is required.')
            previous = STORE.outbox_entry(key)
            if previous and (previous['user_id'] != account['id'] or previous['entity'] != entity['name'] or previous['record_id'] != rid or previous['action'] != action['name']):
                return self.respond(409, {'error': 'Request ID belongs to another delivery.'})
            payload = json.dumps({name: old[name] for name in action['fields']}, ensure_ascii=False)
            STORE.enqueue_delivery(key, action['name'], entity['name'], rid, account['id'], payload)
            return self.respond(202, {'id': key, 'status': previous['status'] if previous else 'queued'})
        if method == 'POST' and len(parts) == 5 and parts[4] == 'transition':
            body = self.payload()
            index = int(body['transition'])
            if not 0 <= index < len(entity['transitions']):
                raise ValueError('Unknown transition.')
            transition = entity['transitions'][index]
            if role != 'admin' and role not in transition['roles']:
                return self.respond(403, {'error': 'Your role cannot run this workflow action.'})
            if not STORE.transition(entity, rid, transition['field'], transition['from_value'], transition['to_value']):
                return self.respond(409, {'error': 'The workflow state changed. Refresh the record.'})
        elif method == 'POST' and len(parts) in (3, 4):
            values = validate(entity, self.payload(), old)
            if old:
                STORE.update_record(entity, rid, values)
            else:
                STORE.insert_record(entity, rid, values)
        elif method == 'DELETE' and len(parts) == 4:
            STORE.delete_record(entity, rid)
        else:
            return self.respond(405, {'error': 'Method not allowed.'})
        STORE.audit(account['id'], method, entity['name'], rid)
        return self.respond(200, {'id': rid, 'ok': True})


if __name__ == '__main__':
    migrate()
    from integration_delivery import start_worker
    start_worker(STORE)
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), Handler)
    server.serve_forever()
