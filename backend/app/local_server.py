"""Local launcher: use this project's .env, not unrelated inherited app settings."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
import uvicorn


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--no-reload',action='store_true')
    parser.add_argument('--lan', action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    load_dotenv(root/'.env',override=True)
    discovery = None
    if args.lan:
        from app.lan import APP_PORT, lan_origins, start_discovery
        os.environ['LAN_ACCESS'] = 'true'
        discovery = start_discovery(api_port=args.port)
        for origin in lan_origins():
            if origin.endswith(f':{APP_PORT}'):
                print(f'Phone app address: {origin}', flush=True)
    try:
        uvicorn.run(
            'app.main:app',
            host='0.0.0.0' if args.lan else '127.0.0.1',
            port=args.port,
            reload=not args.no_reload,
            reload_dirs=[str(root)] if not args.no_reload else None,
            reload_includes=['.env'] if not args.no_reload else None,
            reload_excludes=[str(root / '.venv'), str(root / 'tests')] if not args.no_reload else None,
        )
    finally:
        if discovery:
            discovery.close()


if __name__ == '__main__':
    main()
elif __name__ == '__mp_main__':
    # Uvicorn spawns each reload worker with the supervisor's old environment.
    # Refresh it before the worker imports the app and caches its Settings.
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)
