"""Trusted preview relay: one fixed upstream, no HTTP CONNECT or dynamic targets."""
import ipaddress
import os
import select
import socket
import socketserver
import sys
import threading
import time

UPSTREAM = (str(ipaddress.IPv4Address(sys.argv[1])), 8080)
SLOTS = threading.BoundedSemaphore(32)


class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        if not SLOTS.acquire(blocking=False):
            return
        try:
            with socket.create_connection(UPSTREAM, timeout=5) as upstream:
                self.request.settimeout(5)
                upstream.settimeout(5)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([self.request, upstream], [], [], 2)
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.request else self.request).sendall(data)
        except OSError:
            pass
        finally:
            SLOTS.release()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 32


if __name__ == '__main__':
    # Expiry is independent of the API worker and carries no platform credentials.
    timer = threading.Timer(900, lambda: os._exit(0))
    timer.daemon = True
    timer.start()
    with Server(('0.0.0.0', 8080), Relay) as server:
        server.serve_forever()
