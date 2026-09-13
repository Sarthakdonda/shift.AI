"""Start the ordinary development servers for the Android Wi-Fi app."""
from pathlib import Path
import os
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def main():
    children = []
    try:
        for port, cwd, command in [
            (8000, ROOT / 'backend', [sys.executable, 'run.py', '--lan']),
            (3000, ROOT / 'frontend', ['npm.cmd' if os.name == 'nt' else 'npm', 'run', 'dev', '--', '--hostname', '0.0.0.0', '--port', '3000']),
        ]:
            if listening(port):
                print(f'Port {port} is already running; leaving that server alone.', flush=True)
                if port == 8000:
                    print('If the phone cannot connect, restart that backend yourself with: python run.py --lan', flush=True)
            else:
                flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                children.append(subprocess.Popen(command, cwd=cwd, creationflags=flags))
        print('\nKeep this window open. Connect the phone to the same Wi-Fi, then open Shift AI.\n'
              'Use Find server in the app if your computer address changes. Ctrl+C stops servers started here.\n', flush=True)
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
