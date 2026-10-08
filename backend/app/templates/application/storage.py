"""Storage selection for the generated runtime.

SQLite serves previews, container validation and single-instance hosting.
MongoDB serves cloud deployments: set DATABASE_BACKEND=mongodb, MONGODB_URI
and optionally MONGODB_DATABASE in the backend host's environment. The URI is
never part of the source tree.
"""
import os
from pathlib import Path


class Conflict(Exception):
    """A uniqueness, relationship or restricted-delete rule was violated."""


class Unavailable(Exception):
    """The database could not be reached."""


def open_store(root):
    # Explicit opt-in: a stray host-wide MONGODB_URI must never redirect storage.
    if os.environ.get('DATABASE_BACKEND', '').strip().lower() == 'mongodb':
        uri = os.environ.get('MONGODB_URI', '').strip()
        if not uri:
            raise RuntimeError('DATABASE_BACKEND=mongodb requires MONGODB_URI in the process environment.')
        from storage_mongo import MongoStore
        return MongoStore(uri, os.environ.get('MONGODB_DATABASE', '').strip())
    from storage_sqlite import SqliteStore
    return SqliteStore(Path(os.environ.get('DATABASE_PATH', str(Path(root) / 'data' / 'application.db'))))
