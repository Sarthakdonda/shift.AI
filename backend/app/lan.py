"""Opt-in local network discovery; no credentials or project data are broadcast."""
import ipaddress
import json
import socket
import threading

DISCOVERY_PORT = 45831
PROTOCOL = 'shift-ai-discover-v1'
# The Android shell loads appfrontend; the website keeps its own port.
APP_PORT = 3100
WEB_PORTS = (3000, 3001)


def lan_addresses():
    return sorted({entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                   if not ipaddress.ip_address(entry[4][0]).is_loopback})


def lan_origins():
    return [f'http://{host}:{port}' for host in [*lan_addresses(), socket.gethostname(), socket.gethostname() + '.local']
            for port in (*WEB_PORTS, APP_PORT)]


def discovery_response(data, peer, api_port=8000):
    address = ipaddress.ip_address(peer)
    if not address.is_private or address.is_unspecified or address.is_multicast:
        return None
    try:
        request = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(request, dict) or request.get('service') != PROTOCOL:
        return None
    nonce = request.get('nonce')
    if not isinstance(nonce, str) or not 1 <= len(nonce) <= 64:
        return None
    # 'port' stays the website port for older installed apps; 'app_port' is the
    # phone app that the current shell looks for.
    return json.dumps({'service': PROTOCOL, 'nonce': nonce, 'name': socket.gethostname(),
                       'port': WEB_PORTS[0], 'app_port': APP_PORT, 'api_port': api_port}).encode()


def start_discovery(api_port=8000):
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        listener.bind(('0.0.0.0', DISCOVERY_PORT))
    except OSError:
        listener.close()
        print('Wi-Fi discovery is unavailable; enter the phone server address manually.', flush=True)
        return None

    def serve():
        while True:
            try:
                data, peer = listener.recvfrom(2048)
                response = discovery_response(data, peer[0], api_port)
                if response:
                    listener.sendto(response, peer)
            except OSError:
                break

    threading.Thread(target=serve, daemon=True, name='shift-wifi-discovery').start()
    return listener
