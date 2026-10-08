"""Runs only in the document conversion container, without network or secrets."""
import json
import re
import subprocess
import sys
from pathlib import Path


def command(*args, timeout=90):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError('Document conversion failed; check format, OCR languages and encryption.')
    return result.stdout


def main():
    ext = sys.argv[1]
    language = sys.argv[2]
    if ext not in ('.doc', '.ppt', '.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff') or not re.fullmatch(r'[a-z_+]{3,100}', language):
        raise ValueError('Invalid conversion parameters.')
    data = sys.stdin.buffer.read(16 * 1024 * 1024)
    source = Path('/tmp/source' + ext); source.write_bytes(data)
    if ext in ('.doc', '.ppt'):
        command('libreoffice', '-env:UserInstallation=file:///tmp/lo-profile', '--headless', '--convert-to', 'pdf', '--outdir', '/tmp', str(source))
        source = Path('/tmp/source.pdf')
        if not source.exists():
            raise ValueError('Office conversion did not produce a PDF.')
    pages = []
    if source.suffix == '.pdf':
        info = command('pdfinfo', str(source)).decode('utf-8', errors='replace')
        match = re.search(r'^Pages:\s*(\d+)', info, re.M)
        if not match or int(match[1]) > 300:
            raise ValueError('PDF conversion supports up to 300 pages.')
        text = command('pdftotext', '-layout', str(source), '-').decode('utf-8', errors='replace').split('\f')
        missing = 0
        for index in range(int(match[1])):
            content = text[index] if index < len(text) else ''
            if not content.strip():
                missing += 1
                if missing > 30:
                    raise ValueError('Split scanned documents into batches of 30 pages or fewer.')
                prefix = '/tmp/page-' + str(index)
                command('pdftoppm', '-f', str(index + 1), '-l', str(index + 1), '-singlefile', '-scale-to', '2400', '-png', str(source), prefix, timeout=20)
                content = command('tesseract', prefix + '.png', 'stdout', '-l', language, timeout=25).decode('utf-8', errors='replace')
                Path(prefix + '.png').unlink(missing_ok=True)
            pages.append([index + 1, content])
    else:
        content = command('tesseract', str(source), 'stdout', '-l', language, timeout=25).decode('utf-8', errors='replace')
        pages = [[1, content]]
    if sum(len(text) for _, text in pages) > 500000:
        raise ValueError('Extracted text is too large. Split this document.')
    print(json.dumps({'pages': pages}, ensure_ascii=False))


try:
    main()
except Exception as exc:
    print(json.dumps({'error': str(exc) if isinstance(exc, ValueError) else 'Document conversion timed out or failed.'}))
    sys.exit(1)
