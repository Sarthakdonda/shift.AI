"""Start the backend with `python run.py`, using its local virtual environment."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-reload', action='store_true')
    parser.add_argument('--check', action='store_true', help='Verify dependencies without starting a server')
    args = parser.parse_args()
    backend = Path(__file__).resolve().parent
    python = backend / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.is_file():
        print('Create the backend environment first:\n  python -m venv .venv')
        print('Then install dependencies with the virtual environment Python:\n  <venv-python> -m pip install -r requirements.lock.txt')
        return 1
    if args.check:
        command = [str(python), '-c', "from app.main import app; print('Backend dependencies OK; virtual environment selected correctly.')"]
    else:
        command = [str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.port)]
        if not args.no_reload:
            command += ['--reload', '--reload-dir', str(backend / 'app')]
        print(f'Starting backend at http://localhost:{args.port} (Ctrl+C to stop)', flush=True)
    try:
        return subprocess.call(command, cwd=backend)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
