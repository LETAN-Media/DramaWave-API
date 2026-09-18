"""DramaWave resolver API: stateless JSON over official H5 endpoints.

No video download, no FFmpeg, no ASR, no TTS, no rendering, no database.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import canonical, episodes, health, search, series
from app.config import settings
from app.errors import DramaWaveError, dramawave_error_handler
from app.providers.dramabox.provider import DramaBoxProvider
from app.providers.dramawave.provider import DramaWaveProvider
from app.providers.netshort.provider import NetShortProvider
from app.providers.registry import register
from app.providers.shortflix.provider import ShortFlixProvider

logging.basicConfig(level=settings.log_level,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger('dramawave-api')

register(DramaWaveProvider())
register(NetShortProvider())
register(DramaBoxProvider())
register(ShortFlixProvider())

app = FastAPI(title='DramaWave Resolver API', version=settings.version)
app.add_exception_handler(DramaWaveError, dramawave_error_handler)
app.include_router(health.router)
app.include_router(search.router)
app.include_router(series.router)
app.include_router(episodes.router)
app.include_router(canonical.router)


@app.middleware('http')
async def log_requests(request: Request, call_next):
    t0 = time.monotonic()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        logger.info('%s %s status=%s latency=%.2fs',
                    request.method, request.url.path, status, time.monotonic() - t0)
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    code = 'UNAUTHORIZED' if exc.status_code == 401 else 'DRAMAWAVE_UPSTREAM_ERROR'
    return JSONResponse(status_code=exc.status_code,
                        content={'error': {'code': code, 'message': str(exc.detail)[:300]}})
