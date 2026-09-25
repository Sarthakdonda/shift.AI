"""shift.AI trusted relational application runtime (Python standard library only)."""
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager, closing
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from schema_contract import compatibility

ROOT = Path(__file__).resolve().parent
SPEC = json.loads((ROOT / 'spec.json').read_text(encoding='utf-8'))
IDENTITY = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
DB_PATH = Path(os.environ.get('DATABASE_PATH', str(ROOT / 'data' / 'application.db')))
ENTITIES = {e['name']: e for e in SPEC['entities']}
SECURE = os.environ.get('COOKIE_SECURE', 'true').lower() == 'true'


@contextmanager
def connection():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()


def migrate():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS migrations (version TEXT PRIMARY KEY, applied REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, user_id TEXT, action TEXT, entity TEXT, record_id TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS login_attempts (email TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS schema_state (id INTEGER PRIMARY KEY CHECK(id=1), spec TEXT NOT NULL);
        ''')
        current = db.execute('SELECT spec FROM schema_state WHERE id=1').fetchone()
        if current:
            issues = compatibility(json.loads(current['spec']), SPEC)
            if issues:
                raise RuntimeError('Unsafe migration blocked: ' + ' '.join(issues))
        version = IDENTITY['build_id']
        if not db.execute('SELECT 1 FROM migrations WHERE version=?', (version,)).fetchone():
            # SQLite backup is consistent even when another connection has been writing.
            if db.execute('SELECT 1 FROM migrations LIMIT 1').fetchone():
                backup = DB_PATH.with_name('backup-' + version + '.db')
                with closing(sqlite3.connect(backup)) as target:
                    db.backup(target)
            for entity in SPEC['entities']:
                table = 'e_' + entity['name']
                columns = ['id TEXT PRIMARY KEY', 'created_at REAL NOT NULL', 'updated_at REAL NOT NULL']
                for field in entity['fields']:
                    kind = 'REAL' if field['kind'] == 'number' else 'INTEGER' if field['kind'] == 'boolean' else 'TEXT'
                    reference = f' REFERENCES "e_{field["reference"]}"(id) ON DELETE RESTRICT' if field['kind'] == 'reference' else ''
                    columns.append(f'"{field["name"]}" {kind}' + (' NOT NULL' if field['required'] else '') + reference)
                db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({",".join(columns)})')
                existing = {row['name'] for row in db.execute(f'PRAGMA table_info("{table}")')}
                for field in entity['fields']:
                    if field['name'] not in existing:
                        kind = 'REAL' if field['kind'] == 'number' else 'INTEGER' if field['kind'] == 'boolean' else 'TEXT'
                        reference = f' REFERENCES "e_{field["reference"]}"(id) ON DELETE RESTRICT' if field['kind'] == 'reference' else ''
                        db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{field["name"]}" {kind}{reference}')
                    if field['kind'] == 'reference':
                        db.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_{field["name"]}" ON "{table}"("{field["name"]}")')
            db.execute('INSERT INTO migrations VALUES (?, ?)', (version, time.time()))
        db.execute('INSERT OR REPLACE INTO schema_state VALUES (1, ?)', (json.dumps(SPEC),))
        if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            email, password = os.environ.get('ADMIN_EMAIL', '').strip().lower(), os.environ.get('ADMIN_PASSWORD', '')
            if not email or len(password) < 12:
                raise RuntimeError('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters) before first startup.')
            db.execute('INSERT INTO users VALUES (?, ?, ?, ?)', (secrets.token_hex(16), email, password_hash(password), 'admin'))


def validate(entity, data, old=None):
    allowed = {f['name'] for f in entity['fields']}
    if set(data) - allowed:
        raise ValueError('Unknown field.')
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
            value = int(value)
        elif kind == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(field['label'] + ' must be a finite number.')
        else:
            if not isinstance(value, str) or len(value) > 5000:
                raise ValueError(field['label'] + ' must be text of at most 5000 characters.')
            if kind == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
                raise ValueError('Enter a valid email address.')
            if kind == 'date':
                date.fromisoformat(value)
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

    def session(self, db):
        cookie = SimpleCookie()
        cookie.load(self.headers.get('Cookie', ''))
        token = cookie.get('app_session')
        if not token:
            return None
        hashed = hashlib.sha256(token.value.encode()).hexdigest()
        return db.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?', (hashed, time.time())).fetchone()

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
        except sqlite3.IntegrityError:
            self.respond(409, {'error': 'Duplicate value or referenced record. Check relationships before saving or deleting.'})
        except Exception:
            self.respond(500, {'error': 'The operation could not complete. Your saved data is preserved.'})

    def route(self, method):
        parsed = urlsplit(self.path)
        path = parsed.path
        if method != 'GET':
            expected = os.environ.get('APP_ORIGIN') or ('https://' if SECURE else 'http://') + self.headers.get('Host', '')
            if self.headers.get('Origin') != expected:
                return self.respond(403, {'error': 'Request origin is not allowed.'})
        if method == 'GET' and path in ('/', '/app.js', '/style.css'):
            name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
            kind = {'/': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css'}[path]
            return self.respond(200, (ROOT / 'public' / name).read_bytes(), content_type=kind)
        with connection() as db:
            if method == 'GET' and path == '/health':
                db.execute('SELECT 1').fetchone()
                return self.respond(200, {'status': 'ok', **IDENTITY})
            if method == 'POST' and path == '/api/login':
                body = self.payload()
                email = str(body.get('email', '')).strip().lower()[:254]
                attempt = db.execute('SELECT * FROM login_attempts WHERE email=?', (email,)).fetchone()
                if attempt and attempt['window'] > time.time() - 900 and attempt['attempts'] >= 10:
                    return self.respond(429, {'error': 'Too many attempts. Retry in 15 minutes.'})
                window = attempt['window'] if attempt and attempt['window'] > time.time() - 900 else time.time()
                count = attempt['attempts'] + 1 if attempt and window == attempt['window'] else 1
                db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?, ?, ?)', (email, count, window))
                account = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
                password = str(body.get('password', ''))[:1024]
                stored = account['password'] if account else password_hash('unavailable')
                valid = hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)
                if not account or not valid:
                    return self.respond(401, {'error': 'Email or password is incorrect.'})
                db.execute('DELETE FROM login_attempts WHERE email=?', (email,))
                db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
                token = secrets.token_urlsafe(32)
                db.execute('INSERT INTO sessions VALUES (?, ?, ?)', (hashlib.sha256(token.encode()).hexdigest(), account['id'], time.time() + 86400))
                return self.respond(200, {'role': account['role']}, self.cookie(token))
            account = self.session(db)
            if not account:
                return self.respond(401, {'error': 'Please sign in.'})
            role = account['role']
            if method == 'POST' and path == '/api/logout':
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                token = cookie.get('app_session')
                if token:
                    db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.value.encode()).hexdigest(),))
                return self.respond(200, {'ok': True}, self.cookie('', 0))
            if method == 'GET' and path == '/api/spec':
                visible = [e for e in SPEC['entities'] if role == 'admin' or role in e['read_roles']]
                return self.respond(200, {**SPEC, 'entities': visible, 'user': {'email': account['email'], 'role': role}})
            if path == '/api/users':
                if role != 'admin':
                    return self.respond(403, {'error': 'Administrator access required.'})
                if method == 'GET':
                    return self.respond(200, [dict(r) for r in db.execute('SELECT id,email,role FROM users')])
                if method == 'POST':
                    body = self.payload()
                    email, password, chosen = str(body['email']).strip().lower(), str(body['password']), body['role']
                    if len(password) < 12 or len(password) > 1024 or chosen not in SPEC['roles'] or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                        raise ValueError('Invalid account.')
                    uid = secrets.token_hex(16)
                    db.execute('INSERT INTO users VALUES (?, ?, ?, ?)', (uid, email, password_hash(password), chosen))
                    return self.respond(201, {'id': uid})
            parts = path.strip('/').split('/')
            if len(parts) < 3 or parts[:2] != ['api', 'records'] or parts[2] not in ENTITIES:
                return self.respond(404, {'error': 'Not found.'})
            entity = ENTITIES[parts[2]]
            permissions = entity['read_roles'] if method == 'GET' else entity['write_roles']
            if role != 'admin' and role not in permissions:
                return self.respond(403, {'error': 'Your role cannot perform this action.'})
            table = 'e_' + entity['name']
            if method == 'GET' and len(parts) == 3:
                query = parse_qs(parsed.query)
                offset = max(0, min(100000, int(query.get('offset', ['0'])[0])))
                term = query.get('q', [''])[0][:200]
                fields = [f['name'] for f in entity['fields']]
                where = ' OR '.join(f'CAST("{f}" AS TEXT) LIKE ?' for f in fields)
                values = ['%' + term + '%'] * len(fields)
                rows = db.execute(f'SELECT * FROM "{table}" WHERE {where} ORDER BY created_at DESC LIMIT 100 OFFSET ?', (*values, offset)).fetchall()
                return self.respond(200, [dict(r) for r in rows])
            rid = parts[3] if len(parts) >= 4 else secrets.token_hex(16)
            old = db.execute(f'SELECT * FROM "{table}" WHERE id=?', (rid,)).fetchone() if len(parts) >= 4 else None
            if len(parts) >= 4 and not old:
                return self.respond(404, {'error': 'Record not found.'})
            if method == 'POST' and len(parts) == 5 and parts[4] == 'transition':
                body = self.payload()
                index = int(body['transition'])
                if not 0 <= index < len(entity['transitions']):
                    raise ValueError('Unknown transition.')
                transition = entity['transitions'][index]
                if role != 'admin' and role not in transition['roles']:
                    return self.respond(403, {'error': 'Your role cannot run this workflow action.'})
                changed = db.execute(f'UPDATE "{table}" SET "{transition["field"]}"=?, updated_at=? WHERE id=? AND "{transition["field"]}"=?', (transition['to_value'], time.time(), rid, transition['from_value']))
                if changed.rowcount != 1:
                    return self.respond(409, {'error': 'The workflow state changed. Refresh the record.'})
            elif method == 'POST' and len(parts) in (3, 4):
                values = validate(entity, self.payload(), old)
                if old:
                    assignments = ','.join(f'"{key}"=?' for key in values)
                    db.execute(f'UPDATE "{table}" SET {assignments}, updated_at=? WHERE id=?', (*values.values(), time.time(), rid))
                else:
                    columns = ','.join('"' + key + '"' for key in values)
                    marks = ','.join('?' for _ in values)
                    db.execute(f'INSERT INTO "{table}" (id,created_at,updated_at,{columns}) VALUES (?,?,?,{marks})', (rid, time.time(), time.time(), *values.values()))
            elif method == 'DELETE' and len(parts) == 4:
                db.execute(f'DELETE FROM "{table}" WHERE id=?', (rid,))
            else:
                return self.respond(405, {'error': 'Method not allowed.'})
            db.execute('INSERT INTO audit(user_id,action,entity,record_id,created) VALUES (?,?,?,?,?)', (account['id'], method, entity['name'], rid, time.time()))
            return self.respond(200, {'id': rid, 'ok': True})


if __name__ == '__main__':
    migrate()
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), Handler)
    server.serve_forever()
