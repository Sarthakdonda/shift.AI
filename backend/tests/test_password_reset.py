"""Password reset: hashed single-use tokens, expiry, session revocation, and no account disclosure."""
from datetime import timedelta
from app.core import auth
from app.core.passwords import verify_password
from app.repositories.store import now

PASSWORD = 'test-only-password-123'
REPLACEMENT = 'another-test-passphrase-456'


def register(client, email='reset-owner@example.com', name='Reset Owner'):
    client.headers['Origin'] = 'http://localhost:3000'
    response = client.post('/api/auth/signup', json={'name': name, 'email': email, 'password': PASSWORD})
    assert response.status_code == 201, response.text
    return response.json(), client.cookies.get('shift_session')


def forgot(client, email='reset-owner@example.com'):
    return client.post('/api/auth/password/forgot', json={'email': email})


def test_local_link_reset_replaces_the_password_and_revokes_sessions(setup):
    client, store, _, _ = setup
    account, session = register(client)
    requested = forgot(client, ' RESET-OWNER@EXAMPLE.COM ')
    assert requested.status_code == 200, requested.text
    body = requested.json()
    assert body['delivery'] == 'local_link' and body['reset_link'].startswith('http://localhost:3000/reset-password?token=')
    token = body['reset_link'].split('token=')[1]
    stored = store.db.password_resets.find_one({'email': account['email']})
    assert token not in str(stored) and len(stored['token_hash']) == 64 and stored['used_at'] is None
    assert client.post('/api/auth/password/verify', json={'token': token}).status_code == 200
    reset = client.post('/api/auth/password/reset', json={'token': token, 'password': REPLACEMENT})
    assert reset.status_code == 200 and reset.json()['email'] == account['email']
    record = store.db.users.find_one({'email': account['email']})
    assert verify_password(REPLACEMENT, record['password_hash']) and record['session_version'] == 1
    assert store.db.password_resets.count_documents({'user_id': str(record['_id'])}) == 0
    client.cookies.set('shift_session', session)
    assert client.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/login', json={'email': account['email'], 'password': PASSWORD}).status_code == 401
    assert client.post('/api/auth/login', json={'email': account['email'], 'password': REPLACEMENT}).status_code == 200


def test_tokens_are_single_use_expire_and_are_replaced_by_a_new_request(setup):
    client, store, _, _ = setup
    account, _ = register(client)
    first = forgot(client).json()['reset_link'].split('token=')[1]
    second = forgot(client).json()['reset_link'].split('token=')[1]
    assert first != second and store.db.password_resets.count_documents({}) == 1
    assert client.post('/api/auth/password/verify', json={'token': first}).status_code == 400
    store.db.password_resets.update_one({'token_hash': auth.token_digest(second)}, {'$set': {'expires_at': now() - timedelta(minutes=1)}})
    expired = client.post('/api/auth/password/reset', json={'token': second, 'password': REPLACEMENT})
    assert expired.status_code == 400 and expired.json()['code'] == 'reset_invalid'
    third = forgot(client).json()['reset_link'].split('token=')[1]
    assert client.post('/api/auth/password/reset', json={'token': third, 'password': REPLACEMENT}).status_code == 200
    reused = client.post('/api/auth/password/reset', json={'token': third, 'password': 'yet-another-passphrase-789'})
    assert reused.status_code == 400 and reused.json()['code'] == 'reset_invalid'
    assert verify_password(REPLACEMENT, store.db.users.find_one({'email': account['email']})['password_hash'])


def test_unknown_email_and_disabled_accounts_get_the_same_answer(setup):
    client, store, _, _ = setup
    account, _ = register(client)
    unknown = forgot(client, 'nobody@example.com')
    assert unknown.status_code == 200 and 'reset_link' not in unknown.json()
    assert store.db.password_resets.count_documents({}) == 0
    store.db.users.update_one({'email': account['email']}, {'$set': {'disabled': True}})
    disabled = forgot(client)
    assert disabled.status_code == 200 and 'reset_link' not in disabled.json()
    assert disabled.json()['message'] == unknown.json()['message']
    assert store.db.password_resets.count_documents({}) == 0


def test_configured_email_delivery_never_returns_the_link(setup, monkeypatch):
    client, _, _, settings = setup
    account, _ = register(client)
    sent = []
    monkeypatch.setattr(auth, 'email_configured', lambda: True)
    monkeypatch.setattr(auth, 'send_email', lambda to, subject, body: sent.append((to, subject, body)))
    response = forgot(client)
    assert response.status_code == 200 and response.json()['delivery'] == 'email' and 'reset_link' not in response.json()
    assert len(sent) == 1 and sent[0][0] == account['email'] and 'reset-password?token=' in sent[0][2]
    assert forgot(client, 'nobody@example.com').json()['delivery'] == 'email' and len(sent) == 1


def test_reset_is_unavailable_when_neither_email_nor_local_link_is_allowed(setup, monkeypatch):
    client, store, _, settings = setup
    register(client)
    monkeypatch.setattr(settings, 'password_reset_local_link', False)
    blocked = forgot(client)
    assert blocked.status_code == 503 and blocked.json()['code'] == 'email_unavailable'
    assert store.db.password_resets.count_documents({}) == 0


def test_reset_requests_are_validated_and_rate_limited(setup):
    client, _, _, _ = setup
    client.headers['Origin'] = 'http://localhost:3000'
    assert client.post('/api/auth/password/forgot', json={'email': 'not-an-email'}).status_code == 422
    assert client.post('/api/auth/password/reset', json={'token': 'short', 'password': REPLACEMENT}).status_code == 422
    assert client.post('/api/auth/password/reset', json={'token': 'x' * 40, 'password': 'short'}).status_code == 422
    for _ in range(10):
        assert forgot(client, 'flooded@example.com').status_code == 200
    assert forgot(client, 'flooded@example.com').status_code == 429
