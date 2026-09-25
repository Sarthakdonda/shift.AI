"""Docker boundary. Only compiler-owned files enter a build; no host secret mounts."""
import json
import os
import re
import secrets
import subprocess
import tempfile
import time
import httpx
from pathlib import Path
from app.core.errors import AppError
from app.core.config import get_settings


def docker_environment():
    return {k: v for k, v in os.environ.items() if k.upper() in {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG', 'PROGRAMFILES', 'LOCALAPPDATA', 'APPDATA'}}


def docker(*args, timeout=30, include_stderr=False):
    try:
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout, shell=False, env=docker_environment())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        raise AppError('Docker is unavailable or timed out. Start Docker Engine and retry.', 503, 'sandbox_unavailable') from None
    if result.returncode:
        # Commands contain no secrets; Docker diagnostics may mention private registry paths.
        message = (result.stderr or result.stdout or 'Docker operation failed.')[-3000:]
        raise AppError(message, 503, 'sandbox_unavailable')
    return (result.stdout + ('\n' + result.stderr if include_stderr else '')).strip()


def available():
    try:
        docker('info', '--format', '{{.ServerVersion}}', timeout=8)
        return True
    except AppError:
        return False


def image_name(build_id):
    if not re.fullmatch('[0-9a-f]{24}', build_id):
        raise AppError('Invalid build identifier.')
    return 'shift-generated:' + build_id


def build_and_test(build_id, files):
    name = image_name(build_id)
    logs = []
    # Pulling the fixed base image is an operator setup step. Builds have no egress.
    docker('image', 'inspect', 'python:3.13-slim', timeout=10)
    with tempfile.TemporaryDirectory(prefix='shift-build-') as directory:
        root = Path(directory)
        for relative, content in files.items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()):
                raise AppError('Invalid generated file path.')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        logs.append(docker('build', '--platform=linux/amd64', '--network=none', '--pull=false', '-t', name, directory, timeout=get_settings().builder_timeout_seconds, include_stderr=True)[-6000:])
    container = 'shift-test-' + build_id
    try:
        logs.append(docker('run', '--rm', '--name', container, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=256m', '--memory-swap=256m', '--cpus=1', '--pids-limit=64',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', name, 'python', '-m', 'unittest', 'selftest', '-v', timeout=120, include_stderr=True))
    finally:
        # This exact container was created by this build; never stop other containers.
        try:
            docker('rm', '-f', container, timeout=10)
        except AppError:
            pass
    return {'status': 'passed', 'checks': ['runtime_startup', 'database', 'authentication', 'authorization', 'crud', 'relationships', 'workflow', 'persistence'], 'logs': logs,
            'limitations': ['No browser, device, external integration or load tests were executed in this container.']}


def preview(build_id):
    name = image_name(build_id)
    container = 'shift-preview-' + secrets.token_hex(8)
    network = container + '-net'
    gateway = container + '-gateway'
    password = secrets.token_urlsafe(24)
    # Docker inherits only the selected preview credential; no application secrets
    # are passed to the container or placed in command-line arguments.
    command = ['docker', 'run', '-d', '--rm', '--name', container, '--network', network,
        '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=256m', '--memory-swap=256m', '--cpus=1', '--pids-limit=64',
        '--tmpfs', '/app/data:rw,noexec,nosuid,size=64m,uid=10001,gid=10001', '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m',
        '-e', 'ADMIN_EMAIL=preview@shift.local', '-e', 'ADMIN_PASSWORD', '-e', 'COOKIE_SECURE=false',
        name, 'python', '-c', 'import os,runpy,threading; t=threading.Timer(900,lambda:os._exit(0)); t.daemon=True; t.start(); runpy.run_path("server.py",run_name="__main__")']
    try:
        docker('network', 'create', '--internal', network)
        result = subprocess.run(command, env={**docker_environment(), 'ADMIN_PASSWORD': password}, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AppError('Preview failed to start. Check Docker resources and image availability.', 503)
        # Docker does not publish ports on an internal-only network. A trusted
        # relay joins both networks; generated code stays on its own internal
        # network. It cannot choose a relay destination or enable IP forwarding.
        networks = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Networks}}', container))
        address = networks[network]['IPAddress']
        relay = (Path(__file__).resolve().parents[1] / 'templates' / 'preview_gateway.py').read_text('utf-8')
        docker('run', '-d', '--rm', '--name', gateway, '--network', 'bridge',
            '--user', '10001:10001', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--sysctl', 'net.ipv4.ip_forward=0', '--memory=64m', '--memory-swap=64m', '--cpus=0.5', '--pids-limit=64',
            '-p', '127.0.0.1::8080', 'python:3.13-slim', 'python', '-B', '-c', relay, address)
        docker('network', 'connect', network, gateway)
        port = docker('port', gateway, '8080/tcp').rsplit(':', 1)[-1]
        if not port.isdigit():
            raise AppError('Preview port could not be determined.', 503)
        healthy = False
        for _ in range(10):
            try:
                response = httpx.get('http://127.0.0.1:' + port + '/health', timeout=1, trust_env=False)
                healthy = response.is_success and response.json().get('build_id') == build_id
                if healthy:
                    break
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.3)
        if not healthy:
            raise AppError('The isolated preview did not pass its startup health check.', 503, 'sandbox_unavailable')
        return {'container': container, 'url': 'http://127.0.0.1:' + port, 'email': 'preview@shift.local',
                'password': password, 'expires_in_seconds': 900}
    except Exception:
        try:
            stop_preview(container)
        except AppError:
            pass
        raise


def stop_preview(container):
    if not re.fullmatch(r'shift-preview-[0-9a-f]{16}', container):
        raise AppError('Invalid preview identifier.')
    # --rm previews can already have expired. Docker inspect must succeed before
    # removing a running one; the caller records cleanup failures for retry.
    for owned in (container + '-gateway', container):
        listed = docker('ps', '-a', '--filter', 'name=^/' + owned + '$', '--format', '{{.Names}}')
        if listed == owned:
            docker('rm', '-f', owned)
        if docker('ps', '-a', '--filter', 'name=^/' + owned + '$', '--format', '{{.Names}}'):
            raise AppError('Preview cleanup is not confirmed. Retry stopping it.', 503, 'sandbox_unavailable')
    network = container + '-net'
    if network in docker('network', 'ls', '--format', '{{.Name}}').splitlines():
        docker('network', 'rm', network)
    if network in docker('network', 'ls', '--format', '{{.Name}}').splitlines():
        raise AppError('Preview network cleanup is not confirmed. Retry stopping it.', 503, 'sandbox_unavailable')
