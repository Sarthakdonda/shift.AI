"""Opt-in: python -m tests.live_atlas_smoke. Creates and deletes only its own test project."""
import uuid
from pymongo import MongoClient
from app.core.config import get_settings
from app.repositories.store import Store, get_store


def main():
    settings = get_settings()
    owner = 'smoke-test:' + str(uuid.uuid4())
    store = get_store()
    project = store.create({'name': 'Temporary persistence verification', 'initial_problem': 'Verify project persistence across independent database connections.', 'industry': 'Test'}, owner)
    pid = str(project['_id'])
    try:
        store.message(pid, 'assistant', 'Persistence verification only.')
        with MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10000) as fresh_client:
            fresh = Store(fresh_client[settings.mongodb_database])
            assert fresh.project(pid, owner)['name'] == project['name']
            assert len(fresh.related('messages', pid)) == 2
        print('PASS: Atlas project and messages persist across independent connections.')
    finally:
        store.delete(pid, owner)
        print('Temporary verification project and related data removed.')


if __name__ == '__main__':
    main()
