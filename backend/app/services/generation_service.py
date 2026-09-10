"""Cooperative cancellation across API workers, with no late project writes.

Only the provider call runs in the detached thread. The request thread owns all
project persistence and stops waiting immediately when cancellation is recorded.
An already submitted provider call may still consume quota; later retries stop.
"""
import copy
import queue
import threading
from datetime import timedelta
from app.core.errors import AppError
from app.repositories.store import now


class Generation:
    def __init__(self, store, pid, request_id):
        self.collection = store.db.generation_requests
        self.key = {'_id': f'{pid}:{request_id}'}
        self.cancelled = threading.Event()
        self.collection.update_one(self.key, {'$setOnInsert': {
            'project_id': pid, 'cancelled': False, 'expires_at': now() + timedelta(days=1),
        }}, upsert=True)

    def check(self):
        if self.cancelled.is_set() or self.collection.find_one({**self.key, 'cancelled': True}):
            self.cancelled.set()
            raise AppError('Response stopped. Your message is saved.', 409, 'generation_cancelled')

    def cancel(self):
        self.collection.update_one(self.key, {'$set': {'cancelled': True}})
        self.cancelled.set()

    def call(self, operation):
        self.check()
        result = queue.Queue(maxsize=1)

        def run():
            try:
                result.put((True, operation()))
            except Exception as exc:
                result.put((False, exc))

        threading.Thread(target=run, daemon=True, name='cancellable-provider').start()
        while True:
            self.check()
            try:
                ok, value = result.get(timeout=0.15)
            except queue.Empty:
                continue
            self.check()
            if not ok:
                raise value
            return value


class CancellableAI:
    def __init__(self, inner, generation):
        self.inner = copy.copy(inner)
        self.generation = generation
        self.inner.check_cancelled = generation.check

    def __copy__(self):
        return CancellableAI(self.inner, self.generation)

    @property
    def settings(self):
        return self.inner.settings

    @settings.setter
    def settings(self, value):
        self.inner.settings = value

    def require(self):
        self.generation.check()
        return self.inner.require()

    def generate_structured(self, *args, **kwargs):
        return self.generation.call(lambda: self.inner.generate_structured(*args, **kwargs))

    def embed(self, *args, **kwargs):
        return self.generation.call(lambda: self.inner.embed(*args, **kwargs))
