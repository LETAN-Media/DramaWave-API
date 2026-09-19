"""Episode + playback routes: supports canonical and legacy DramaWave IDs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.cache import cache
from app.config import settings
from app.dramawave import domain as dw_domain
from app.errors import DramaWaveError
from app.models import AudioTrack, EpisodeItem, PlaybackResponse, QualityVariant
from app.security import require_api_token
from app.services.canonical import get_episode_sources, refresh_series_sources

router = APIRouter(dependencies=[Depends(require_api_token)])

_EP_KEYS = ('episode_id', 'episode_number', 'title', 'duration', 'episode_price', 'locked', 'cover')


def _is_canonical(series_id: str) -> bool:
    return series_id.startswith('cw:')


@router.get('/v1/series/{series_id}/episodes')
def list_episodes(series_id: str):
    if _is_canonical(series_id):
        import asyncio
        from app.services.canonical import get_store
        store = get_store()
        mappings = store.get_mappings(series_id)
        if not mappings:
            raise DramaWaveError('SERIES_NOT_FOUND', series_id[:64])
        key = f'canonical-episodes:{series_id}'
        hit = cache.get(key)
        if isinstance(hit, list):
            return {'series_id': series_id, 'total': len(hit), 'episodes': hit}
        
        all_eps: dict[int, dict] = {}
        # Make sure we use the correct providers!
        asyncio.get_event_loop().run_until_complete(refresh_series_sources(series_id))
        sources_map = store.get_episode_sources(series_id, None) or {}
        # Wait, get_episode_sources takes episode_number!
        # It's better to access _episode_sources map directly:
        sources_map = store._episode_sources.get(series_id, {})
        for ep_num, sources in sources_map.items():
            all_eps[ep_num] = {'episode_number': ep_num, 'sources': []}
            for s in sources:
                all_eps[ep_num]['sources'].append({
                    'provider': s.provider,
                    'status': 'free' if s.free else 'locked',
                    'locked': s.locked or not s.playback_available,
                })

        eps_out = sorted(all_eps.values(), key=lambda x: x['episode_number'])
        cache.set(key, eps_out, settings.cache_episodes_ttl)
        return {'series_id': series_id, 'total': len(eps_out), 'episodes': eps_out}
    key = f'episodes:{series_id}'
    hit = cache.get(key)
    if isinstance(hit, list):
        eps = hit
    else:
        eps = [{k: e[k] for k in _EP_KEYS if k in e} for e in dw_domain.list_episodes(series_id)]
        cache.set(key, eps, settings.cache_episodes_ttl)
    return {'series_id': series_id, 'total': len(eps),
            'episodes': [EpisodeItem(**e).model_dump() for e in eps]}


@router.get('/v1/episodes/{episode_id}')
def get_episode(episode_id: str, series_id: str = Query(description='Parent series id')) -> dict:
    ep = dw_domain.get_episode(series_id, episode_id)
    return {'episode_id': ep['episode_id'], 'episode_number': ep['episode_number'],
            'title': ep.get('title'), 'duration': ep.get('duration'),
            'episode_price': ep.get('episode_price'), 'locked': ep['locked']}


@router.get('/v1/episodes/{episode_id}/playback', response_model=PlaybackResponse)
def get_playback(episode_id: str, series_id: str = Query(description='Parent series id'),
                 quality: str = Query(default='best')) -> PlaybackResponse:
    key = f'playback:{series_id}:{episode_id}:{quality}'
    hit = cache.get(key)
    if isinstance(hit, dict):
        return PlaybackResponse(**hit)
    pb = dw_domain.get_playback(series_id, episode_id, quality)
    from app.models import AudioTrack

    out = {**pb,
           'audio_tracks': [AudioTrack(**t).model_dump() for t in pb.get('audio_tracks', [])],
           'available_qualities': [QualityVariant(**v).model_dump() for v in pb['available_qualities']]}
    cache.set(key, out, settings.cache_playback_ttl)
    return PlaybackResponse(**out)
