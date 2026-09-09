"""Selectable Gemini text models and reasoning-effort levels.

The catalog is read from the configured API keys so the list always reflects the
models the account can actually use. Results are cached briefly because listing
models is a network call. Listing never consumes generation quota.
"""
import logging
import re
import threading
import time

logger = logging.getLogger(__name__)

# Reasoning effort offered in the composer, fastest first.
EFFORTS = [
    {'id': 'instant', 'label': 'Instant', 'description': 'Fastest answers, minimal reasoning.'},
    {'id': 'low', 'label': 'Fast', 'description': 'Quick answers with light reasoning.'},
    {'id': 'medium', 'label': 'Balanced', 'description': 'More thorough reasoning, slower.'},
    {'id': 'high', 'label': 'Thorough', 'description': 'Deepest reasoning for hard problems.'},
]
EFFORT_IDS = [effort['id'] for effort in EFFORTS]
DEFAULT_EFFORT = 'low'
PREFERRED_MODEL = 'gemini-3.6-flash'

# Text generation only: image, audio, embedding and research models cannot answer discovery.
_EXCLUDED = (
    'embedding', 'image', 'tts', 'transcribe', 'audio', 'robotics', 'lyria', 'veo',
    'imagen', 'nano-banana', 'deep-research', 'computer-use', 'omni', 'antigravity',
    'customtools', 'gemma', 'learnlm', 'aqa',
)
# Fallback used when the provider cannot be reached, so the picker still works.
_FALLBACK = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3-flash-preview', 'gemini-2.5-flash', 'gemini-2.5-pro']

_cache: dict = {}
_lock = threading.Lock()
_TTL = 600.0


def model_version(model: str) -> float | None:
    """Numeric Gemini family version, used to choose the thinking API."""
    match = re.match(r'^(?:models/)?gemini-(\d+(?:\.\d+)?)', model or '')
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _label(model: str) -> str:
    words = []
    for part in model.split('-'):
        if re.fullmatch(r'\d+(\.\d+)?', part):
            words.append(part)
        elif part == 'ai':
            words.append('AI')
        else:
            words.append(part.capitalize())
    return ' '.join(words).replace('Gemini', 'Gemini')


def _describe(model: str, provider_description: str = '') -> str:
    text = (provider_description or '').strip().split('\n')[0]
    # Providers often repeat the display name; that tells the user nothing.
    repeats_name = text.replace('-', ' ').lower() in (_label(model).lower(), model.replace('-', ' ').lower())
    if text and len(text) <= 120 and not repeats_name:
        return text
    if 'pro' in model:
        return 'Deepest reasoning for complex strategy work.'
    if 'lite' in model:
        return 'Fastest and lightest for quick answers.'
    if 'flash' in model:
        return 'Efficient for everyday discovery and analysis.'
    return 'General purpose text model.'


def _sort_key(model: dict):
    version = model_version(model['id']) or 0
    tier = 0 if 'lite' in model['id'] else 1 if 'flash' in model['id'] else 2
    preview = 1 if 'preview' in model['id'] else 0
    return (-version, preview, -tier, model['id'])


def _from_provider(service) -> list[str]:
    client = service.require()
    found = []
    for item in client.models.list():
        name = str(getattr(item, 'name', '') or '').removeprefix('models/')
        actions = [str(a) for a in (getattr(item, 'supported_actions', None) or [])]
        if not name.startswith('gemini-') or any(word in name for word in _EXCLUDED):
            continue
        if actions and not any('generateContent' in action for action in actions):
            continue
        found.append((name, str(getattr(item, 'description', '') or '')))
    return found


def catalog(service, default_model: str) -> dict:
    """Selectable models and efforts, with the project default resolved."""
    with _lock:
        cached = _cache.get('models')
        fresh = cached and cached[0] > time.monotonic()
    if fresh:
        entries = cached[1]
    else:
        try:
            entries = _from_provider(service)
        except Exception as exc:  # noqa: BLE001 - the picker must still render
            logger.warning('Model listing unavailable (%s); using the built-in list.', type(exc).__name__)
            entries = [(name, '') for name in _FALLBACK]
        with _lock:
            _cache['models'] = (time.monotonic() + _TTL, entries)
    ids = {name for name, _ in entries}
    for extra in {default_model, PREFERRED_MODEL} - ids:
        if extra:
            entries = [*entries, (extra, '')]
    models = [{'id': name, 'label': _label(name), 'description': _describe(name, description),
               'supports_effort': (model_version(name) or 0) >= 2.5}
              for name, description in dict(entries).items()]
    models.sort(key=_sort_key)
    return {'models': models, 'default_model': default_model, 'efforts': EFFORTS, 'default_effort': DEFAULT_EFFORT}
