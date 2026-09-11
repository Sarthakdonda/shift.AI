from fastapi import APIRouter, Depends, Response
from app.core.auth import user
from app.core.errors import AppError
from app.repositories.store import get_store
from app.services.export_service import export, MIME

router = APIRouter(prefix='/api', tags=['Exports'])


@router.get('/projects/{pid}/export/{kind}/{fmt}')
def download(pid: str, kind: str, fmt: str, version: int | None = None, account=Depends(user)):
    s = get_store(); p = s.project(pid, account['id'])
    if kind == 'blueprint':
        if p['status'] != 'BLUEPRINT_READY': raise AppError('Complete analysis first.', 409)
        query = {'project_id': pid}
        if version is not None: query['version'] = version
        item = s.db.blueprints.find_one(query, sort=[('version', -1)])
    else:
        query = {'project_id': pid, 'kind': kind}
        if version is not None: query['version'] = version
        item = s.db.artifacts.find_one(query, sort=[('version', -1)])
    if not item: raise AppError('No saved deliverable is available.', 404)
    content = item['content']
    payload = export(content.get('final_report', {}).get('title', content.get('title', p['name'])), content, fmt)
    # Use a constant ASCII stem to avoid header/path injection.
    return Response(payload, media_type=MIME[fmt], headers={'Content-Disposition': f'attachment; filename="shift-ai-deliverable-v{item["version"]}.{fmt}"'})
