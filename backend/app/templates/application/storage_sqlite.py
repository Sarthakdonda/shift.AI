"""SQLite storage: previews, container validation and single-instance hosting."""
import json
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path
from schema_contract import compatibility
from storage import Conflict

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS migrations (version TEXT PRIMARY KEY, applied REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, user_id TEXT, action TEXT, entity TEXT, record_id TEXT, created REAL);
CREATE TABLE IF NOT EXISTS login_attempts (email TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window REAL NOT NULL);
CREATE TABLE IF NOT EXISTS schema_state (id INTEGER PRIMARY KEY CHECK(id=1), spec TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS integration_outbox (id TEXT PRIMARY KEY, action TEXT NOT NULL, entity TEXT NOT NULL, record_id TEXT NOT NULL, user_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL, created REAL NOT NULL, error TEXT NOT NULL DEFAULT '');
'''


def column(field):
    kind = 'REAL' if field['kind'] == 'number' else 'INTEGER' if field['kind'] == 'boolean' else 'TEXT'
    reference = f' REFERENCES "e_{field["reference"]}"(id) ON DELETE RESTRICT' if field['kind'] == 'reference' else ''
    return kind, reference


class SqliteStore:
    kind = 'sqlite'

    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        except sqlite3.IntegrityError:
            raise Conflict('Duplicate value or referenced record.') from None
        finally:
            db.close()

    def migrate(self, spec, identity, initial_admin):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript(SCHEMA)
            current = db.execute('SELECT spec FROM schema_state WHERE id=1').fetchone()
            if current:
                issues = compatibility(json.loads(current['spec']), spec)
                if issues:
                    raise RuntimeError('Unsafe migration blocked: ' + ' '.join(issues))
            version = identity['build_id']
            if not db.execute('SELECT 1 FROM migrations WHERE version=?', (version,)).fetchone():
                # SQLite backup is consistent even when another connection has been writing.
                if db.execute('SELECT 1 FROM migrations LIMIT 1').fetchone():
                    backup = self.path.with_name('backup-' + version + '.db')
                    with closing(sqlite3.connect(backup)) as target:
                        db.backup(target)
                for entity in spec['entities']:
                    table = 'e_' + entity['name']
                    columns = ['id TEXT PRIMARY KEY', 'created_at REAL NOT NULL', 'updated_at REAL NOT NULL']
                    for field in entity['fields']:
                        kind, reference = column(field)
                        columns.append(f'"{field["name"]}" {kind}' + (' NOT NULL' if field['required'] else '') + reference)
                    db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({",".join(columns)})')
                    existing = {row['name'] for row in db.execute(f'PRAGMA table_info("{table}")')}
                    for field in entity['fields']:
                        if field['name'] not in existing:
                            kind, reference = column(field)
                            db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{field["name"]}" {kind}{reference}')
                        if field['kind'] == 'reference':
                            db.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_{field["name"]}" ON "{table}"("{field["name"]}")')
                db.execute('INSERT INTO migrations VALUES (?, ?)', (version, time.time()))
            db.execute('INSERT OR REPLACE INTO schema_state VALUES (1, ?)', (json.dumps(spec),))
            if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                email, password = initial_admin()
                db.execute('INSERT INTO users VALUES (?, ?, ?, ?)', (secrets.token_hex(16), email, password, 'admin'))

    def ping(self):
        with self.connection() as db:
            db.execute('SELECT 1').fetchone()

    # ---- accounts and sessions -------------------------------------------------
    def register_attempt(self, email):
        """Record a login attempt; False when the 15-minute window is exhausted."""
        with self.connection() as db:
            attempt = db.execute('SELECT * FROM login_attempts WHERE email=?', (email,)).fetchone()
            if attempt and attempt['window'] > time.time() - 900 and attempt['attempts'] >= 10:
                return False
            window = attempt['window'] if attempt and attempt['window'] > time.time() - 900 else time.time()
            count = attempt['attempts'] + 1 if attempt and window == attempt['window'] else 1
            db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?, ?, ?)', (email, count, window))
            return True

    def clear_attempts(self, email):
        with self.connection() as db:
            db.execute('DELETE FROM login_attempts WHERE email=?', (email,))

    def user_by_email(self, email):
        with self.connection() as db:
            row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            return dict(row) if row else None

    def start_session(self, token_hash, user_id, expires):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?, ?, ?)', (token_hash, user_id, expires))

    def session_user(self, token_hash):
        with self.connection() as db:
            row = db.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?', (token_hash, time.time())).fetchone()
            return dict(row) if row else None

    def end_session(self, token_hash):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (token_hash,))

    def list_users(self):
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT id,email,role FROM users')]

    def create_user(self, uid, email, password, role):
        with self.connection() as db:
            db.execute('INSERT INTO users VALUES (?, ?, ?, ?)', (uid, email, password, role))

    def audit(self, user_id, action, entity, record_id):
        with self.connection() as db:
            db.execute('INSERT INTO audit(user_id,action,entity,record_id,created) VALUES (?,?,?,?,?)', (user_id, action, entity, record_id, time.time()))

    # ---- records ---------------------------------------------------------------
    def list_records(self, entity, term, offset):
        fields = [f['name'] for f in entity['fields']]
        where = ' OR '.join(f'CAST("{f}" AS TEXT) LIKE ?' for f in fields)
        values = ['%' + term + '%'] * len(fields)
        with self.connection() as db:
            rows = db.execute(f'SELECT * FROM "e_{entity["name"]}" WHERE {where} ORDER BY created_at DESC LIMIT 100 OFFSET ?', (*values, offset)).fetchall()
            return [dict(r) for r in rows]

    def get_record(self, entity, rid):
        with self.connection() as db:
            row = db.execute(f'SELECT * FROM "e_{entity["name"]}" WHERE id=?', (rid,)).fetchone()
            return dict(row) if row else None

    def insert_record(self, entity, rid, values):
        columns = ','.join('"' + key + '"' for key in values)
        marks = ','.join('?' for _ in values)
        with self.connection() as db:
            db.execute(f'INSERT INTO "e_{entity["name"]}" (id,created_at,updated_at,{columns}) VALUES (?,?,?,{marks})', (rid, time.time(), time.time(), *values.values()))

    def update_record(self, entity, rid, values):
        assignments = ','.join(f'"{key}"=?' for key in values)
        with self.connection() as db:
            db.execute(f'UPDATE "e_{entity["name"]}" SET {assignments}, updated_at=? WHERE id=?', (*values.values(), time.time(), rid))

    def delete_record(self, entity, rid):
        with self.connection() as db:
            db.execute(f'DELETE FROM "e_{entity["name"]}" WHERE id=?', (rid,))

    def transition(self, entity, rid, field, from_value, to_value):
        with self.connection() as db:
            changed = db.execute(f'UPDATE "e_{entity["name"]}" SET "{field}"=?, updated_at=? WHERE id=? AND "{field}"=?', (to_value, time.time(), rid, from_value))
            return changed.rowcount == 1

    # ---- integration outbox ----------------------------------------------------
    def outbox_entry(self, key):
        with self.connection() as db:
            row = db.execute('SELECT * FROM integration_outbox WHERE id=?', (key,)).fetchone()
            return dict(row) if row else None

    def enqueue_delivery(self, key, action, entity, record_id, user_id, payload):
        with self.connection() as db:
            db.execute('INSERT OR IGNORE INTO integration_outbox(id,action,entity,record_id,user_id,payload,retry_at,created) VALUES (?,?,?,?,?,?,?,?)', (key, action, entity, record_id, user_id, payload, time.time(), time.time()))

    def deliveries(self, user_id, admin):
        with self.connection() as db:
            rows = db.execute('SELECT id,action,entity,record_id,status,attempts,error,created FROM integration_outbox WHERE user_id=? OR ? ORDER BY created DESC LIMIT 100', (user_id, admin)).fetchall()
            return [dict(row) for row in rows]

    def claim_delivery(self):
        with self.connection() as db:
            db.execute("UPDATE integration_outbox SET status='failed',error='Delivery interrupted after five attempts.' WHERE status='sending' AND retry_at<=? AND attempts>=5", (time.time(),))
            row = db.execute("UPDATE integration_outbox SET status='sending', attempts=attempts+1, retry_at=? WHERE id=(SELECT id FROM integration_outbox WHERE status IN ('queued','sending') AND retry_at<=? AND attempts<5 ORDER BY created LIMIT 1) RETURNING *", (time.time() + 60, time.time())).fetchone()
            return dict(row) if row else None

    def finish_delivery(self, row, status, error, retry_at):
        with self.connection() as db:
            db.execute('UPDATE integration_outbox SET status=?,error=?,retry_at=? WHERE id=? AND attempts=? AND status=?', (status, error, retry_at, row['id'], row['attempts'], 'sending'))
