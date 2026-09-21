"""Start the servers the Android app needs: the API and the app frontend.

The website in ../frontend is a separate surface and is intentionally not
started here; run it yourself when you want it.
"""
from pathlib import Path
import os
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
APP_PORT = 3100
API_PORT = 8000


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def main():
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    children = []
    try:
        for port, cwd, command in [
            (API_PORT, ROOT / 'backend', [sys.executable, 'run.py', '--lan']),
            (APP_PORT, ROOT / 'appfrontend',
             [npm, 'run', 'dev', '--', '--hostname', '0.0.0.0', '--port', str(APP_PORT)]),
        ]:
            if listening(port):
                print(f'Port {port} is already running; leaving that server alone.', flush=True)
                if port == API_PORT:
                    print('If the phone cannot connect, restart that backend yourself with: python run.py --lan', flush=True)
            else:
                if port == APP_PORT and not (ROOT / 'appfrontend/node_modules').is_dir():
                    print('Install the app frontend first: cd appfrontend && npm.cmd ci', flush=True)
                    return 1
                flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                children.append(subprocess.Popen(command, cwd=cwd, creationflags=flags))
        print('\nKeep this window open. Connect the phone to the same Wi-Fi, then open Shift AI.\n'
              'The Android app reconnects automatically, even if your computer address changes. Ctrl+C stops servers started here.\n', flush=True)
        while children and all(child.poll() is None for child in children):
            time.sleep(1)
        return 0 if not children else 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                # Only the process trees created by this launcher are stopped.
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
                else:
                    child.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
