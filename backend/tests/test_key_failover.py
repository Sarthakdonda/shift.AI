from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from google.genai import errors
from app.core.errors import AppError
from app.core.config import Settings
from app.models.schemas import Necessity
from app.services.gemini_service import GeminiService


def api_error(code, message='Provider rejected request', details=None):
    return errors.APIError(code, {'error': {'code': code, 'message': message, 'details': details or []}})


def make_pool(setup, monkeypatch, failures, count=2):
    monkeypatch.setattr(setup[3], 'gemini_api_key', 'primary-secret')
    monkeypatch.setattr(setup[3], 'gemini_api_keys', ','.join(f'backup-secret-{i}' for i in range(count - 1)))
    ai = GeminiService()
    valid = SimpleNamespace(text=setup[2].generate_structured('', {}, Necessity).model_dump_json())
    calls = []
    for i in range(count):
        call = Mock(side_effect=failures.get(i), return_value=valid)
        ai._clients[i] = SimpleNamespace(models=SimpleNamespace(generate_content=call, embed_content=call))
        calls.append(call)
    return ai, calls


@pytest.mark.parametrize('failure', [api_error(429), api_error(401), api_error(403), api_error(400, 'API key not valid'), api_error(503), httpx.ReadTimeout('Request timed out')])
def test_failover_and_cooldown_skip_failed_key(setup, monkeypatch, failure):
    ai, calls = make_pool(setup, monkeypatch, {0: failure})
    assert ai.generate_structured('Decide', {}, Necessity).classification == 'AUTOMATION_SUFFICIENT'
    assert calls[0].call_count == calls[1].call_count == 1
    ai.generate_structured('Decide again', {}, Necessity)
    assert calls[0].call_count == 1 and calls[1].call_count == 2


def test_all_keys_exhausted_is_safe_and_bounded(setup, monkeypatch):
    ai, calls = make_pool(setup, monkeypatch, {i: api_error(429, 'primary-secret') for i in range(6)}, count=6)
    with pytest.raises(AppError) as result:
        ai.generate_structured('Decide', {}, Necessity)
    assert result.value.code == 'provider_unavailable'
    assert 'primary-secret' not in result.value.message
    assert sum(c.call_count for c in calls) == 4


def test_missing_model_rotates_keys_because_projects_differ(setup, monkeypatch):
    """A 404 means this key's project lacks the model; another key may still serve it."""
    ai, calls = make_pool(setup, monkeypatch, {0: api_error(404)})
    assert ai.generate_structured('Decide', {}, Necessity).classification == 'AUTOMATION_SUFFICIENT'
    assert calls[0].call_count == 1 and calls[1].call_count == 1
    # The key is still usable for models it does have.
    assert ai._cooldowns.get(0, 0) == 0


def test_missing_model_on_all_keys_reports_the_model(setup, monkeypatch):
    ai, calls = make_pool(setup, monkeypatch, {0: api_error(404), 1: api_error(404)})
    with pytest.raises(AppError) as result:
        ai.generate_structured('Decide', {}, Necessity)
    assert result.value.code == 'model_unavailable'
    assert calls[0].call_count == 1 and calls[1].call_count == 1


def test_malformed_request_does_not_rotate_keys(setup, monkeypatch):
    ai, calls = make_pool(setup, monkeypatch, {0: api_error(400, 'Invalid JSON payload')})
    with pytest.raises(AppError) as result:
        ai.generate_structured('Decide', {}, Necessity)
    assert result.value.code == 'gemini_configuration'
    assert calls[1].call_count == 0


def test_failover_then_json_repair(setup, monkeypatch):
    ai, calls = make_pool(setup, monkeypatch, {0: api_error(429)})
    valid = calls[1].return_value
    calls[1].side_effect = [SimpleNamespace(text='bad json'), valid]
    ai.generate_structured('Decide', {}, Necessity)
    assert calls[0].call_count == 1 and calls[1].call_count == 2


def test_embeddings_use_backup(setup, monkeypatch):
    ai, calls = make_pool(setup, monkeypatch, {0: api_error(429)})
    calls[1].return_value = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
    assert ai.embed('Invoice processing') == [0.1, 0.2]
    assert calls[0].call_count == calls[1].call_count == 1


def test_cooldown_expires_and_retry_info_is_honored(setup, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr('app.services.gemini_service.time.monotonic', lambda: clock[0])
    failure = api_error(429, details=[{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '120s'}])
    ai, calls = make_pool(setup, monkeypatch, {0: failure})
    ai.generate_structured('Decide', {}, Necessity)
    assert ai._cooldowns[0] == 220
    calls[0].side_effect = None
    clock[0] = 221
    ai.generate_structured('Decide', {}, Necessity)
    assert calls[0].call_count == 2


def test_keys_deduplicated_and_backup_only_health(setup, monkeypatch):
    config = Settings(_env_file=None, gemini_api_key=' first ', gemini_api_keys='second,first, ,AQ.valid-format\nthird')
    assert config.gemini_keys == ['first', 'second', 'AQ.valid-format', 'third']
    monkeypatch.setattr(setup[3], 'gemini_api_keys', 'only-backup-secret')
    response = setup[0].get('/api/health')
    assert response.json()['gemini_configured']
    assert 'only-backup-secret' not in response.text
