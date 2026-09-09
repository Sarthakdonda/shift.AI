import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool
from app.api.routes import router
from app.api.workspaces import router as workspace_router
from app.api.deliverables import router as deliverable_router
from app.api.exports import router as export_router
from app.api.portability import router as portability_router
from app.api.outcomes import router as outcome_router
from app.api.localization import router as localization_router
from app.api.integrations import router as integration_router
from app.core.auth import router as auth_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import get_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    try:
        await run_in_threadpool(lambda: get_store().indexes())
    except Exception as exc:
        logger.warning('Database initialization unavailable (%s). Check backend/.env and Atlas network access.', type(exc).__name__)
    yield


app = FastAPI(title='shift.AI API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_credentials=True, allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'], allow_headers=['Content-Type'])


@app.middleware('http')
async def protect_requests(request: Request, call_next):
    if request.method in ('POST', 'DELETE', 'PUT', 'PATCH'):
        origin = request.headers.get('origin')
        if origin and origin not in get_settings().origins:
            return JSONResponse({'detail': 'This request origin is not allowed.'}, status_code=403)
        if request.cookies.get('shift_session') and not origin:
            return JSONResponse({'detail': 'An Origin header is required for authenticated changes.'}, status_code=403)
        length = request.headers.get('content-length', '0')
        if length.isdigit() and int(length) > (get_settings().max_upload_mb + 1) * 1024 * 1024:
            return JSONResponse({'detail': 'The upload is too large.'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(AppError)
async def app_error(request, exc):
    return JSONResponse({'detail': exc.message, 'code': exc.code}, status_code=exc.status)


@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    logger.warning('Database request failed (%s)', type(exc).__name__)
    return JSONResponse({'detail': 'MongoDB is unavailable. Check the Atlas IP access list, database credentials, and network connection.', 'code': 'database_unavailable'}, status_code=503)


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.error('Request failed (%s)', type(exc).__name__)
    return JSONResponse({'detail': 'Something went wrong. Please retry; your saved work is preserved.'}, status_code=500)


app.include_router(auth_router)
app.include_router(router)
app.include_router(workspace_router)
app.include_router(deliverable_router)
app.include_router(export_router)
app.include_router(portability_router)
app.include_router(outcome_router)
app.include_router(localization_router)
app.include_router(integration_router)
