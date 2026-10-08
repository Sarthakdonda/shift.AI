"""Blueprint intake preserves structured documents; never replaces discovery."""
import hashlib
import json
from pathlib import PurePosixPath
from bson import ObjectId
from app.core.errors import AppError
from app.repositories.store import now
from app.services.document_service import validate_file, extract


def parse_upload(filename, data):
    name = PurePosixPath((filename or '').replace('\\', '/')).name[:180]
    ext = PurePosixPath(name).suffix.lower()
    if not data or len(data) > 10 * 1024 * 1024:
        raise AppError('Choose a nonempty blueprint up to 10 MB.', 413)
    if ext not in ('.pdf', '.docx', '.md', '.json'):
        raise AppError('Blueprints support PDF, DOCX, Markdown and structured JSON.', 415)
    if ext in ('.md', '.json'):
        try:
            text = data.decode('utf-8-sig')
            if '\x00' in text or len(text) > 300000:
                raise ValueError()
            content = json.loads(text) if ext == '.json' else {'document_text': text}
            if not isinstance(content, dict) or not content:
                raise ValueError()
        except (UnicodeError, ValueError, RecursionError):
            raise AppError('Use a valid UTF-8 blueprint; JSON must contain a nonempty object under 300,000 characters.') from None
    else:
        validate_file(name, data, 10)
        content = {'document_chunks': extract(data, ext)}
    return name, content, hashlib.sha256(data).hexdigest()


def attach(store, project, actor, content, name, sha, source=None):
    pid = str(project['_id'])
    current = selected(store, project)
    if current and current.get('source') == source and current['content'] == content:
        # Selecting the same blueprint again must not hide an unfinished run.
        return current
    row = {'project_id': pid, 'version': store.db.application_blueprints.count_documents({'project_id': pid}) + 1,
           'content': content, 'name': name, 'file_hash': sha, 'source': source,
           'actor': actor, 'created_at': now()}
    row['_id'] = store.db.application_blueprints.insert_one(row).inserted_id
    store.update(pid, application_source=str(row['_id']), application_job=None)
    store.activity(project, actor, 'Application blueprint selected', name)
    return row


def selected(store, project):
    key = project.get('application_source')
    if not key:
        return None
    row = store.db.application_blueprints.find_one({'_id': ObjectId(key), 'project_id': str(project['_id'])})
    if not row:
        raise AppError('The selected application blueprint is unavailable. Select it again.', 409)
    return row
