"""Optional API-token gate. /health stays public."""

from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger('dramawave-api.auth')


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    expected = (settings.api_token or '').strip()
    if not expected:
        return
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Invalid API token')
    if not secrets.compare_digest(authorization[len('Bearer '):].strip(), expected):
        logger.warning('invalid api token attempt')
        raise HTTPException(status_code=401, detail='Invalid API token')
