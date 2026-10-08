"""Explicit external actions with a durable outbox and pinned public HTTPS peers."""
import http.client
import ipaddress
import os
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit


def deliver(action, payload, key):
    prefix = 'INTEGRATION_' + action.upper()
    parsed = urlsplit(os.environ.get(prefix + '_URL', ''))
    token = os.environ.get(prefix + '_TOKEN', '')
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError('Configure a public HTTPS integration endpoint.')
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Integration addresses must be publicly routable.')
    address = addresses[0][4][0]
    class Pinned(http.client.HTTPSConnection):
        def connect(self):
            self.sock = self._context.wrap_socket(socket.create_connection((address, 443), timeout=self.timeout), server_hostname=self.host)
    connection = Pinned(parsed.hostname, timeout=10, context=ssl.create_default_context())
    try:
        headers = {'Content-Type': 'application/json', 'Idempotency-Key': key}
        if token:
            if '\r' in token or '\n' in token:
                raise ValueError('Invalid integration credential.')
            headers['Authorization'] = 'Bearer ' + token
        connection.request('POST', (parsed.path or '/') + ('?' + parsed.query if parsed.query else ''), body=payload.encode(), headers=headers)
        response = connection.getresponse()
        response.read(65536)
        if not 200 <= response.status < 300:
            raise ValueError('Integration returned HTTP ' + str(response.status) + '.')
    finally:
        connection.close()


def process_one(store):
    row = store.claim_delivery()
    if not row:
        return False
    try:
        deliver(row['action'], row['payload'], row['id'])
        status, error = 'delivered', ''
    except Exception:
        status = 'failed' if row['attempts'] >= 5 else 'queued'
        error = 'Delivery failed. Check the configured endpoint and credentials.'
    store.finish_delivery(row, status, error, time.time() + min(300, 2 ** row['attempts'] * 5))
    return True


def start_worker(store):
    def run():
        while True:
            try:
                process_one(store)
            except Exception:
                pass
            time.sleep(2)
    threading.Thread(target=run, daemon=True).start()
