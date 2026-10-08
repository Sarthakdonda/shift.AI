"""Dedicated trusted native build host. Run python -m app.native_worker."""
import signal
import threading
from app.core.config import get_settings
from app.repositories.store import get_store
from app.services.job_queue import run_worker
from app.services.native_packaging import capability


def main():
    targets=[t.strip() for t in get_settings().native_worker_targets.split(',') if t.strip()]
    if not targets:raise SystemExit('Set NATIVE_WORKER_TARGETS to this host\'s provisioned platforms.')
    for target in targets:
        reason=capability(target)
        if reason:raise SystemExit(target+': '+reason)
    stop=threading.Event()
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    get_store().indexes()
    run_worker(get_store,stop,targets)


if __name__=='__main__':main()
