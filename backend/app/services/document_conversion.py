import json
import re
import secrets
import subprocess
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.application_runner import docker, docker_environment


def convert(data, ext):
    settings = get_settings()
    if not re.fullmatch(r'[a-z_+]{3,100}', settings.document_ocr_languages):
        raise AppError('Configure valid Tesseract DOCUMENT_OCR_LANGUAGES.', 503, 'document_configuration')
    name = 'shift-document-' + secrets.token_hex(8)
    try:
        docker('image', 'inspect', settings.document_converter_image, timeout=10)
        result = subprocess.run(['docker', 'run', '--rm', '-i', '--name', name, '--network=none',
            '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=768m', '--memory-swap=768m',
            '--cpus=1', '--pids-limit=128', '--tmpfs', '/tmp:rw,noexec,nosuid,size=384m,uid=10001,gid=10001',
            settings.document_converter_image, ext, settings.document_ocr_languages], input=data,
            capture_output=True, timeout=150, env=docker_environment())
        if len(result.stdout) > 4 * 1024 * 1024:
            raise AppError('Converted document is too large. Split it into smaller files.', 413)
        output = json.loads(result.stdout)
        if result.returncode or 'error' in output:
            raise AppError(str(output.get('error', 'Document conversion failed.'))[:1000], 422)
        return [(page, text) for page, text in output['pages']]
    except AppError as exc:
        if exc.code == 'sandbox_unavailable':
            raise AppError('Legacy Office and OCR processing require the document converter image on the worker. Build backend/containers/documents first.', 503, 'document_configuration') from None
        raise
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        raise AppError('Document conversion failed or exceeded its time limit. Try a smaller file.', 422) from None
    finally:
        try:
            docker('rm', '-f', name, timeout=10)
        except AppError:
            pass
