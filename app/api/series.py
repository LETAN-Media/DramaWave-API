"""Series routes."""

from fastapi import APIRouter, Depends

from app.cache import cache
from app.config import settings
from app.dramawave import domain
from app.models import SeriesResponse
from app.security import require_api_token

router = APIRouter(dependencies=[Depends(require_api_token)])


@router.get('/v1/series/{series_id}', response_model=SeriesResponse)
def get_series(series_id: str) -> SeriesResponse:
    key = f'series:{series_id}'
    hit = cache.get(key)
    if isinstance(hit, dict):
        return SeriesResponse(**hit)
    info = domain.get_series(series_id)
    cache.set(key, info, settings.cache_series_ttl)
    return SeriesResponse(**info)
