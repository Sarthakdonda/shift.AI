"""Per-project model and reasoning-effort selection."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.models.schemas import Necessity
from app.services import model_catalog
from app.services.gemini_service import GeminiService
from app.services.project_service import ProjectService


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    model_catalog._cache.clear()
    yield
    model_catalog._cache.clear()


def fake_listing(*names):
    models = [SimpleNamespace(name=f'models/{n}', description='', supported_actions=['generateContent']) for n in names]
    return SimpleNamespace(models=SimpleNamespace(list=lambda: models))


# ---------- catalog ----------

def test_catalog_lists_text_models_and_excludes_other_modalities():
    service = SimpleNamespace(require=lambda: fake_listing(
        'gemini-3.6-flash', 'gemini-2.5-pro', 'gemini-3.1-flash-image', 'gemini-embedding-001', 'gemini-3.5-transcribe'))
    result = model_catalog.catalog(service, 'gemini-3.6-flash')
    ids = [m['id'] for m in result['models']]
    assert 'gemini-3.6-flash' in ids and 'gemini-2.5-pro' in ids
    assert not any('image' in i or 'embedding' in i or 'transcribe' in i for i in ids)
    assert result['default_model'] == 'gemini-3.6-flash'
    assert [e['id'] for e in result['efforts']] == ['instant', 'low', 'medium', 'high']


def test_catalog_falls_back_when_the_provider_cannot_be_reached():
    def unavailable():
        raise RuntimeError('no key')
    result = model_catalog.catalog(SimpleNamespace(require=unavailable), 'gemini-3.6-flash')
    assert 'gemini-3.6-flash' in [m['id'] for m in result['models']]


def test_catalog_orders_newest_first_and_is_cached():
    listing = Mock(return_value=fake_listing('gemini-2.5-flash', 'gemini-3.6-flash'))
    service = SimpleNamespace(require=listing)
    first = model_catalog.catalog(service, 'gemini-3.6-flash')
    assert first['models'][0]['id'] == 'gemini-3.6-flash'
    model_catalog.catalog(service, 'gemini-3.6-flash')
    assert listing.call_count == 1


@pytest.mark.parametrize('model,expected', [
    ('gemini-3.6-flash', 3.6), ('models/gemini-2.5-pro', 2.5), ('gemini-3-flash-preview', 3.0), ('other', None)])
def test_model_version_parsing(model, expected):
    assert model_catalog.model_version(model) == expected


# ---------- effort maps to the API the model supports ----------

@pytest.mark.parametrize('model,effort,attribute,value', [
    ('gemini-3.6-flash', 'instant', 'thinking_level', 'MINIMAL'),
    ('gemini-3.6-flash', 'high', 'thinking_level', 'HIGH'),
    ('gemini-2.5-flash', 'instant', 'thinking_budget', 0),
    ('gemini-2.5-flash', 'medium', 'thinking_budget', 4096),
])
def test_effort_selects_the_thinking_api_for_the_model(model, effort, attribute, value):
    ai = GeminiService()
    ai.settings = Settings(_env_file=None, gemini_model=model, gemini_effort=effort)
    config = ai._thinking()
    assert getattr(config, attribute) == value


def test_older_models_receive_no_thinking_option():
    ai = GeminiService()
    ai.settings = Settings(_env_file=None, gemini_model='gemini-1.5-flash', gemini_effort='high')
    assert ai._thinking() is None


def test_generation_retries_without_thinking_when_the_model_rejects_it(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'gemini_api_key', 'test-primary')
    monkeypatch.setattr(setup[3], 'gemini_model', 'gemini-3.6-flash')
    ai = GeminiService()
    valid = setup[2].generate_structured('', {}, Necessity).model_dump_json()
    from google.genai import errors as genai_errors
    rejection = genai_errors.APIError(400, {'message': 'thinking_level is not supported'})
    generate = Mock(side_effect=[rejection, SimpleNamespace(text=valid)])
    ai._clients[0] = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    assert ai.generate_structured('Decide', {}, Necessity).classification == 'AUTOMATION_SUFFICIENT'
    assert generate.call_count == 2
    assert generate.call_args.kwargs['config'].thinking_config is None


# ---------- the stored choice reaches generation ----------

def test_project_choice_overrides_model_and_effort_for_generation(setup):
    _, store, _, _ = setup
    ai = SimpleNamespace(settings=Settings(_env_file=None, gemini_model='gemini-2.5-flash', gemini_effort='high',
                                           gemini_thinking_level='high'))
    project = store.create({'name': 'Charging visibility', 'initial_problem': 'Drivers cannot see free chargers at peak times.'}, 'email:1')
    pid = str(project['_id'])
    store.update(pid, model='gemini-3.6-flash', effort='instant')
    service = ProjectService(store, ai)
    service.context(pid, 'email:1')
    assert service.ai.settings.gemini_model == 'gemini-3.6-flash'
    assert service.ai.settings.gemini_effort == 'instant'
    # A stored effort replaces a fixed environment thinking level.
    assert service.ai.settings.gemini_thinking_level is None
    assert service.ai.settings.gemini_model != ai.settings.gemini_model


def test_a_key_without_model_access_falls_through_to_one_that_has_it(setup, monkeypatch):
    """Keys can belong to different Google projects, so 404 must try the next key."""
    monkeypatch.setattr(setup[3], 'gemini_api_key', 'first')
    monkeypatch.setattr(setup[3], 'gemini_api_keys', 'second')
    monkeypatch.setattr(setup[3], 'gemini_model', 'gemini-2.5-flash')
    ai = GeminiService()
    valid = setup[2].generate_structured('', {}, Necessity).model_dump_json()
    from google.genai import errors as genai_errors
    missing = genai_errors.APIError(404, {'message': 'models/gemini-2.5-flash is not found'})
    ai._clients[0] = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=missing)))
    ai._clients[1] = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(text=valid))))
    assert ai.generate_structured('Decide', {}, Necessity).classification == 'AUTOMATION_SUFFICIENT'
    # The key that lacked the model is not put on a long cooldown; it stays usable.
    assert ai._cooldowns.get(0, 0) == 0


def test_model_missing_on_every_key_is_reported_as_a_model_problem(setup, monkeypatch):
    monkeypatch.setattr(setup[3], 'gemini_api_key', 'only')
    monkeypatch.setattr(setup[3], 'gemini_api_keys', '')
    ai = GeminiService()
    from google.genai import errors as genai_errors
    missing = genai_errors.APIError(404, {'message': 'model not found'})
    ai._clients[0] = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=missing)))
    with pytest.raises(Exception) as raised:
        ai.generate_structured('Decide', {}, Necessity)
    assert raised.value.code == 'model_unavailable'


# ---------- API ----------

def test_models_endpoint_returns_catalog(setup, monkeypatch):
    client, _, _, settings = setup
    monkeypatch.setattr('app.api.routes.catalog', lambda service, default: {
        'models': [{'id': 'gemini-3.6-flash', 'label': 'Gemini 3.6 Flash', 'description': 'x', 'supports_effort': True}],
        'default_model': default, 'efforts': model_catalog.EFFORTS, 'default_effort': 'low'})
    body = client.get('/api/models').json()
    assert body['models'][0]['id'] == 'gemini-3.6-flash'
    assert body['default_effort'] == 'low'


def test_choosing_a_model_persists_it_on_the_project(setup, project, monkeypatch):
    client, store, _, _ = setup
    monkeypatch.setattr('app.api.routes.catalog', lambda service, default: {
        'models': [{'id': 'gemini-3.6-flash'}, {'id': 'gemini-2.5-flash'}], 'default_model': default,
        'efforts': model_catalog.EFFORTS, 'default_effort': 'low'})
    response = client.post(f'/api/projects/{project}/model', json={'model': 'gemini-2.5-flash', 'effort': 'high'})
    assert response.status_code == 200
    saved = client.get(f'/api/projects/{project}').json()
    assert saved['model'] == 'gemini-2.5-flash' and saved['effort'] == 'high'


def test_unavailable_model_and_invalid_effort_are_rejected(setup, project, monkeypatch):
    client, *_ = setup
    monkeypatch.setattr('app.api.routes.catalog', lambda service, default: {
        'models': [{'id': 'gemini-3.6-flash'}], 'default_model': default,
        'efforts': model_catalog.EFFORTS, 'default_effort': 'low'})
    denied = client.post(f'/api/projects/{project}/model', json={'model': 'other-model', 'effort': 'high'})
    assert denied.status_code == 400 and denied.json()['code'] == 'model_unavailable'
    assert client.post(f'/api/projects/{project}/model', json={'model': 'gemini-3.6-flash', 'effort': 'turbo'}).status_code == 422
    assert client.post(f'/api/projects/{project}/model', json={'model': 'BAD MODEL', 'effort': 'high'}).status_code == 422
