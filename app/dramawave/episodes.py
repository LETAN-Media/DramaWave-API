"""DramaWave domain logic (official H5 API mapping)."""

from __future__ import annotations

import logging

from app.dramawave.client import api_call
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.domain')


def list_episodes(series_id: str) -> list[dict]:
    try:
        data = api_call('GET', '/h5-api/drama/info', params={'series_id': series_id})
    except DramaWaveError as exc:
        if exc.code == 'DRAMAWAVE_SERIES_NOT_FOUND':
            raise DramaWaveError('DRAMAWAVE_SERIES_NOT_FOUND', series_id[:32])
        raise DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', exc.message)
    raw_eps = (data.get('info') or {}).get('episode_list') or []
    if not raw_eps:
        raise DramaWaveError('DRAMAWAVE_EPISODES_NOT_FOUND', series_id[:32])
    episodes = []
    for index, raw in enumerate(raw_eps):
        if not isinstance(raw, dict):
            continue
        episodes.append({
            'episode_id': str(raw.get('id') or f'ep{index + 1}'),
            'episode_number': index + 1,
            'title': raw.get('name'),
            'duration': raw.get('duration'),
            'episode_price': raw.get('episode_price'),
            'locked': not bool(raw.get('unlock')),
            'cover': raw.get('cover'),
            '_raw': raw,
        })
    return episodes


def get_episode(series_id: str, episode_id: str) -> dict:
    for ep in list_episodes(series_id):
        if ep['episode_id'] == episode_id:
            return ep
    raise DramaWaveError('DRAMAWAVE_EPISODE_NOT_FOUND', episode_id[:32])


