import json
from app.lan import PROTOCOL, discovery_response
from app.core.config import Settings


def test_discovery_echoes_nonce_without_exposing_credentials():
    reply = json.loads(discovery_response(json.dumps({'service': PROTOCOL, 'nonce': 'test-123'}), '192.168.1.20'))
    assert reply['nonce'] == 'test-123'
    assert reply['port'] == 3000
    assert reply['api_port'] == 8000
    assert set(reply) == {'service', 'nonce', 'port', 'api_port', 'name'}


def test_discovery_ignores_unrelated_malformed_and_public_requests():
    valid = json.dumps({'service': PROTOCOL, 'nonce': 'test'})
    assert discovery_response(valid, '8.8.8.8') is None
    for payload in [b'bad', b'\xff', b'[]', b'{}', json.dumps({'service': PROTOCOL, 'nonce': 'x' * 65})]:
        assert discovery_response(payload, '192.168.1.20') is None


def test_lan_origins_follow_address_changes_only_when_enabled(monkeypatch):
    monkeypatch.setattr('app.lan.lan_addresses', lambda: ['192.168.1.10'])
    settings = Settings(_env_file=None, lan_access=True)
    assert 'http://192.168.1.10:3000' in settings.origins
    monkeypatch.setattr('app.lan.lan_addresses', lambda: ['192.168.2.20'])
    assert 'http://192.168.2.20:3000' in settings.origins
    assert 'http://192.168.1.10:3000' not in settings.origins
    assert 'http://192.168.2.20:3000' not in Settings(_env_file=None, lan_access=False).origins
