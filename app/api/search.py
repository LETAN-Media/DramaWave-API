"""Search route."""

from fastapi import APIRouter, Depends, Query

from app.cache import cache
from app.config import settings
from app.dramawave import domain
from app.errors import DramaWaveError
from app.models import SearchItem, SearchResponse
from app.security import require_api_token

router = APIRouter(dependencies=[Depends(require_api_token)])


@router.get('/v1/search', response_model=SearchResponse)
def search(q: str = Query(min_length=1, max_length=200)) -> SearchResponse:
    key = f'search:{q.strip().lower()}'
    hit = cache.get(key)
    if hit is not None:
        return SearchResponse(items=[SearchItem(**i) for i in hit])
    try:
        items = domain.search_series(q.strip())
    except DramaWaveError as exc:
        if exc.code == 'DRAMAWAVE_SEARCH_FAILED':
            raise
        raise DramaWaveError('DRAMAWAVE_SEARCH_FAILED', exc.message)
    cache.set(key, items, settings.cache_search_ttl)
    return SearchResponse(items=[SearchItem(**i) for i in items])
