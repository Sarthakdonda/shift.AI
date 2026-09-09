"""Explicit browser-test server; never used by normal app startup."""
import mongomock
from app.core.config import get_settings
from app.repositories.store import Store
from app.api import routes
from app import main
from app.core import auth
from app.api import workspaces, deliverables, exports, portability, outcomes, localization, integrations
from tests.fakes import FakeGemini

settings = get_settings()
settings.mongodb_uri = ''
settings.gemini_api_key = 'browser-tests-only'
settings.gemini_api_keys = ''
settings.google_client_id = ''
settings.allow_local_access = True
store = Store(mongomock.MongoClient().browser_test_shift_ai)
fake = FakeGemini()
routes.get_store = lambda: store
routes.get_gemini = lambda: fake
main.get_store = lambda: store
auth.get_store = lambda: store
workspaces.get_store = lambda: store
deliverables.get_store = lambda: store
exports.get_store = lambda: store
portability.get_store = lambda: store
deliverables.get_gemini = lambda: fake
for module in (outcomes, localization, integrations):
    module.get_store = lambda: store
for module in (localization, integrations):
    module.get_gemini = lambda: fake
app = main.app
