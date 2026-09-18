"""Series routes: supports both canonical (cw:...) and legacy DramaWave IDs."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.cache import cache
from app.config import settings
from app.dramawave import domain as dw_domain
from app.errors import DramaWaveError
from app.models import SeriesResponse
from app.security import require_api_token
from app.services.canonical import get_canonical_series, get_store

router = APIRouter(dependencies=[Depends(require_api_token)])


def _is_canonical(series_id: str) -> bool:
    return series_id.startswith('cw:')


@router.get('/v1/series/{series_id}')
def get_series(series_id: str):
    if _is_canonical(series_id):
        key = f'canonical-series:{series_id}'
        hit = cache.get(key)
        if isinstance(hit, dict):
            return hit
        import asyncio
        data = asyncio.get_event_loop().run_until_complete(get_canonical_series(series_id))
        if data is None:
            raise DramaWaveError('SERIES_NOT_FOUND', series_id[:64])
        cache.set(key, data, settings.cache_series_ttl)
        return data
    key = f'series:{series_id}'
    hit = cache.get(key)
    if isinstance(hit, dict):
        return SeriesResponse(**hit)
    info = dw_domain.get_series(series_id)
    cache.set(key, info, settings.cache_series_ttl)
    return SeriesResponse(**info)
