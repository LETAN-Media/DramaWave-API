"""Canonical + multi-provider search API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.cache import cache
from app.config import settings
from app.providers.registry import get_status
from app.services.canonical import (
    get_canonical_series,
    get_episode_sources,
    refresh_series_sources,
    search_all,
)
from app.services.resolver import EpisodeResolver
from app.security import require_api_token
from app.errors import DramaWaveError

router = APIRouter(dependencies=[Depends(require_api_token)])


@router.get('/v1/search-all')
async def search_all_route(q: str = Query(min_length=1, max_length=200)):
    key = f'search-all:{q.strip().lower()}'
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        items = await search_all(q.strip())
    except Exception as exc:
        raise DramaWaveError('MULTI_SEARCH_FAILED', str(exc))
    out = {'query': q.strip(), 'items': [i.model_dump() if hasattr(i, 'model_dump') else i for i in items]}
    cache.set(key, out, settings.cache_search_ttl)
    return out


@router.get('/v1/providers')
def list_providers():
    return {'providers': get_status()}


@router.get('/v1/providers/status')
def provider_status():
    return {'providers': get_status()}


@router.get('/v1/series/{series_id}/episodes/{episode_number}/playback')
async def auto_playback(
    series_id: str,
    episode_number: int,
    quality: str = Query(default='best'),
    provider: str = Query(default='auto'),
):
    canonical_id = series_id if series_id.startswith('cw:') else f'cw:{series_id}'
    if not series_id.startswith('cw:'):
        existing = await get_canonical_series(canonical_id)
        if existing is None:
            from app.providers.registry import get as get_provider
            dw = get_provider('dramawave')
            if dw:
                try:
                    s = await dw.get_series(series_id)
                    if s:
                        from app.models.provider import CanonicalSeries, SeriesProviderMapping
                        from app.services.canonical import _store
                        cs = CanonicalSeries(id=canonical_id, canonical_title=s.title or '', cover_url=s.cover_url, episode_count=s.episode_count, language=s.language, aliases=s.aliases)
                        _store._series[canonical_id] = cs
                        _store.upsert_mapping(SeriesProviderMapping(canonical_series_id=canonical_id, provider='dramawave', provider_series_id=series_id, provider_title=s.title, episode_count=s.episode_count, match_score=1.0, verified=True))
                except Exception:
                    pass
    resolver = EpisodeResolver()
    try:
        if provider == 'auto':
            result = await resolver.resolve_with_fallback(canonical_id, episode_number, quality)
        else:
            result = await resolver.resolve(canonical_id, episode_number, quality)
    except DramaWaveError as exc:
        if exc.code == 'NO_FREE_SOURCE':
            return {'error': {'code': 'NO_FREE_SOURCE', 'message': exc.message}}
        raise
    pb = result['playback']
    return {
        'selected_provider': result['selected_provider'],
        'provider_series_id': result['provider_series_id'],
        'provider_episode_id': result['provider_episode_id'],
        'episode_number': result['episode_number'],
        'type': pb.type,
        'url': pb.url,
        'master_url': pb.master_url,
        'audio_url': pb.audio_url,
        'audio_language': pb.audio_language,
        'quality': pb.quality,
        'available_qualities': pb.available_qualities,
    }
