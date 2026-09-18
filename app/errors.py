"""Error codes + structured JSON error responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class DramaWaveError(Exception):
    def __init__(self, code: str, message: str = '', status: int | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.status = status


# code -> (message, http status)
ERRORS: dict[str, tuple[str, int]] = {
    'DRAMAWAVE_AUTH_FAILED': ('Guest authentication failed', 502),
    'DRAMAWAVE_SEARCH_FAILED': ('Search failed', 502),
    'DRAMAWAVE_SERIES_NOT_FOUND': ('Series not found', 404),
    'DRAMAWAVE_EPISODES_NOT_FOUND': ('Episodes not found', 404),
    'DRAMAWAVE_EPISODE_NOT_FOUND': ('Episode not found', 404),
    'DRAMAWAVE_EPISODE_LOCKED': ('Episode is locked', 403),
    'DRAMAWAVE_PLAYBACK_NOT_FOUND': ('Playback not found', 404),
    'DRAMAWAVE_RATE_LIMITED': ('Upstream rate limited', 429),
    'DRAMAWAVE_UPSTREAM_ERROR': ('Upstream error', 502),
    'UNAUTHORIZED': ('Invalid API token', 401),
}


def error_response(code: str, message: str = '', status: int | None = None) -> JSONResponse:
    default_message, default_status = ERRORS.get(code, ('Upstream error', 502))
    return JSONResponse(
        status_code=status or default_status,
        content={'error': {'code': code, 'message': message or default_message}},
    )


async def dramawave_error_handler(_request: Request, exc: DramaWaveError) -> JSONResponse:
    _, default_status = ERRORS.get(exc.code, ('Upstream error', 502))
    return JSONResponse(
        status_code=exc.status or default_status,
        content={'error': {'code': exc.code, 'message': exc.message}},
    )
