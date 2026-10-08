"""Run with python -m app.worker on a trusted builder host sharing MongoDB."""
import signal
import threading
from app.repositories.store import get_store
from app.services.job_queue import run_worker


def main():
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    get_store().indexes()
    run_worker(get_store, stop)


if __name__ == '__main__':
    main()
