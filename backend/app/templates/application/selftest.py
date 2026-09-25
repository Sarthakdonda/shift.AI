"""Executable acceptance checks shipped with each generated application."""
import importlib.util
import copy
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch


class ApplicationAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.environment = patch.dict(os.environ, {'DATABASE_PATH': str(Path(cls.temp.name) / 'app.db'),
            'ADMIN_EMAIL': 'admin@example.test', 'ADMIN_PASSWORD': 'test-only-password-123', 'COOKIE_SECURE': 'false', 'APP_ORIGIN': 'http://test.local'})
        cls.environment.start()
        definition = importlib.util.spec_from_file_location('generated_runtime', Path(__file__).with_name('server.py'))
        cls.runtime = importlib.util.module_from_spec(definition)
        definition.loader.exec_module(cls.runtime)
        cls.runtime.migrate()
        cls.server = cls.runtime.ThreadingHTTPServer(('127.0.0.1', 0), cls.runtime.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.cookie = ''
        code, _, cookie = cls.call('/api/login', {'email': 'admin@example.test', 'password': 'test-only-password-123'})
        assert code == 200
        cls.cookie = cookie
        with cls.runtime.connection() as db:
            pending = list(cls.runtime.SPEC['entities'])
            inserted = set()
            while pending:
                creatable = [e for e in pending if all(f['kind'] != 'reference' or not f['required'] or f['reference'] in inserted for f in e['fields'])]
                assert creatable, 'Required relationship cycle prevents valid seed records'
                for entity in creatable:
                    values = {f['name']: ('reference-' + f['reference'] if f['reference'] in inserted else None) if f['kind'] == 'reference' else
                        1 if f['kind'] in ('number', 'boolean') else 'sample@example.test' if f['kind'] == 'email' else '2026-09-23' if f['kind'] == 'date' else f['options'][0] if f['kind'] == 'select' else 'Fixture'
                        for f in entity['fields']}
                    names = ','.join('"' + k + '"' for k in values)
                    marks = ','.join('?' for _ in values)
                    db.execute(f'INSERT INTO "e_{entity["name"]}" (id,created_at,updated_at,{names}) VALUES (?,?,?,{marks})', ('reference-' + entity['name'], time.time(), time.time(), *values.values()))
                    inserted.add(entity['name']); pending.remove(entity)
            db.execute('INSERT INTO users VALUES (?,?,?,?)', ('outsider', 'outsider@example.test', cls.runtime.password_hash('test-only-password-123'), 'no_access'))
            for index, role in enumerate(cls.runtime.SPEC['roles']):
                db.execute('INSERT INTO users VALUES (?,?,?,?)', ('role-' + str(index), 'role-' + role + '@example.test', cls.runtime.password_hash('test-only-password-123'), role))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.environment.stop()
        cls.temp.cleanup()

    @classmethod
    def call(cls, path, body=None, method=None, cookie=None, origin='http://test.local'):
        client = HTTPConnection('127.0.0.1', cls.server.server_port, timeout=10)
        headers = {'Origin': origin, 'Cookie': cls.cookie if cookie is None else cookie}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        client.request(method or ('POST' if body is not None else 'GET'), path,
                       json.dumps(body) if body is not None else None, headers)
        response = client.getresponse()
        data = json.loads(response.read())
        result = response.status, data, (response.getheader('Set-Cookie') or '').split(';')[0]
        client.close()
        return result

    def values(self, entity):
        return {f['name']: {'text': 'Example', 'email': 'sample@example.test', 'number': 42,
                           'date': '2026-09-23', 'boolean': True, 'select': (f['options'] or [''])[0],
                           'reference': 'reference-' + str(f['reference'])}[f['kind']] for f in entity['fields']}

    def test_health_and_authentication(self):
        self.assertEqual(self.call('/health')[1]['build_id'], self.runtime.IDENTITY['build_id'])
        self.assertEqual(self.call('/api/spec', cookie='')[0], 401)
        self.assertEqual(self.call('/api/login', {'email': 'admin@example.test', 'password': 'wrong'})[0], 401)
        self.assertEqual(self.call('/api/users', {'email': 'x'}, origin='https://evil.test')[0], 403)
        self.assertEqual(self.call('/api/spec')[1]['user']['role'], 'admin')

    def test_role_enforcement(self):
        _, _, cookie = self.call('/api/login', {'email': 'outsider@example.test', 'password': 'test-only-password-123'})
        self.assertEqual(self.call('/api/users', cookie=cookie)[0], 403)
        for entity in self.runtime.SPEC['entities']:
            path = '/api/records/' + entity['name']
            self.assertEqual(self.call(path, cookie=cookie)[0], 403)
            self.assertEqual(self.call(path, self.values(entity), cookie=cookie)[0], 403)
        for role in self.runtime.SPEC['roles']:
            _, _, cookie = self.call('/api/login', {'email': 'role-' + role + '@example.test', 'password': 'test-only-password-123'})
            for entity in self.runtime.SPEC['entities']:
                path = '/api/records/' + entity['name']
                self.assertEqual(self.call(path, cookie=cookie)[0], 200 if role == 'admin' or role in entity['read_roles'] else 403)
                if role != 'admin' and role not in entity['write_roles']:
                    self.assertEqual(self.call(path, self.values(entity), cookie=cookie)[0], 403)

    def test_crud_workflow_relationships_and_persistence(self):
        for entity in self.runtime.SPEC['entities']:
            with self.subTest(entity=entity['name']):
                path = '/api/records/' + entity['name']
                values = self.values(entity)
                code, created, _ = self.call(path, values)
                self.assertEqual(code, 200, created)
                rid = created['id']
                rows = self.call(path)[1]
                self.assertTrue(any(row['id'] == rid for row in rows))
                # Unknown fields and workflow bypass must be rejected by the backend.
                self.assertEqual(self.call(path, {**values, '__unexpected': 'x'})[0], 400)
                self.assertEqual(self.call(path + '/' + rid, values)[0], 200)
                for index, transition in enumerate(entity['transitions']):
                    with self.runtime.connection() as db:
                        db.execute(f'UPDATE "e_{entity["name"]}" SET "{transition["field"]}"=? WHERE id=?', (transition['from_value'], rid))
                    changed = self.call(path + '/' + rid + '/transition', {'transition': index})
                    self.assertEqual(changed[0], 200, changed[1])
                    with self.runtime.connection() as db:
                        self.assertEqual(db.execute(f'SELECT "{transition["field"]}" FROM "e_{entity["name"]}" WHERE id=?', (rid,)).fetchone()[0], transition['to_value'])
                for field in entity['fields']:
                    if field['kind'] == 'reference':
                        self.assertEqual(self.call(path, {**values, field['name']: 'missing-reference'})[0], 409)
                # Re-running migrations must preserve the record, not recreate the database.
                self.runtime.migrate()
                with self.runtime.connection() as db:
                    self.assertIsNotNone(db.execute(f'SELECT id FROM "e_{entity["name"]}" WHERE id=?', (rid,)).fetchone())
                self.assertEqual(self.call(path + '/' + rid, method='DELETE')[0], 200)

    def test_upgrade_and_unsafe_rollback(self):
        original_spec = self.runtime.SPEC
        original_identity = self.runtime.IDENTITY
        upgraded = copy.deepcopy(original_spec)
        entity = upgraded['entities'][0]
        entity['fields'].append({'name':'shift_verification_note','label':'Upgrade verification','kind':'text','required':False,'options':[],'reference':None})
        try:
            with self.runtime.connection() as db:
                before = db.execute(f'SELECT count(*) FROM "e_{entity["name"]}"').fetchone()[0]
            self.runtime.SPEC = upgraded
            self.runtime.IDENTITY = {**original_identity, 'build_id': original_identity['build_id'] + '-upgrade'}
            self.runtime.migrate()
            with self.runtime.connection() as db:
                self.assertEqual(db.execute(f'SELECT count(*) FROM "e_{entity["name"]}"').fetchone()[0], before)
            self.assertTrue(list(self.runtime.DB_PATH.parent.glob('backup-*.db')))
            self.runtime.SPEC = original_spec
            self.runtime.IDENTITY = original_identity
            with self.assertRaisesRegex(RuntimeError, 'Unsafe migration blocked'):
                self.runtime.migrate()
        finally:
            self.runtime.SPEC = original_spec
            self.runtime.IDENTITY = original_identity


if __name__ == '__main__':
    unittest.main()
