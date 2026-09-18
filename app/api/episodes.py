"""Episode + playback routes."""

from fastapi import APIRouter, Depends, Query

from app.cache import cache
from app.config import settings
from app.dramawave import domain
from app.models import EpisodeItem, PlaybackResponse, QualityVariant
from app.security import require_api_token

router = APIRouter(dependencies=[Depends(require_api_token)])

_EP_KEYS = ('episode_id', 'episode_number', 'title', 'duration', 'episode_price', 'locked', 'cover')


@router.get('/v1/series/{series_id}/episodes')
def list_episodes(series_id: str):
    key = f'episodes:{series_id}'
    hit = cache.get(key)
    if isinstance(hit, list):
        eps = hit
    else:
        eps = [{k: e[k] for k in _EP_KEYS if k in e} for e in domain.list_episodes(series_id)]
        cache.set(key, eps, settings.cache_episodes_ttl)
    return {'series_id': series_id, 'total': len(eps),
            'episodes': [EpisodeItem(**e).model_dump() for e in eps]}


@router.get('/v1/episodes/{episode_id}')
def get_episode(episode_id: str, series_id: str = Query(description='Parent series id')) -> dict:
    ep = domain.get_episode(series_id, episode_id)
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
    pb = domain.get_playback(series_id, episode_id, quality)
    out = {**pb, 'available_qualities': [QualityVariant(**v).model_dump() for v in pb['available_qualities']]}
    cache.set(key, out, settings.cache_playback_ttl)
    return PlaybackResponse(**out)
