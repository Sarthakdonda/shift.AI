"""Local launcher: use this project's .env, not unrelated inherited app settings."""
import argparse
from pathlib import Path
from dotenv import load_dotenv
import uvicorn


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--no-reload',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    load_dotenv(root/'.env',override=True)
    uvicorn.run('app.main:app',host='127.0.0.1',port=args.port,reload=not args.no_reload,reload_dirs=[str(root/'app')] if not args.no_reload else None)


if __name__=='__main__':main()
