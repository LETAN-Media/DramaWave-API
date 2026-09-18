"""DramaWave domain logic (official H5 API mapping)."""

from __future__ import annotations

import logging

from app.dramawave.client import api_call
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.domain')


def get_series(series_id: str) -> dict:
    try:
        data = api_call('GET', '/h5-api/drama/info', params={'series_id': series_id})
    except DramaWaveError as exc:
        if exc.code == 'DRAMAWAVE_SERIES_NOT_FOUND':
            raise DramaWaveError('DRAMAWAVE_SERIES_NOT_FOUND', series_id[:32])
        raise DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', exc.message)
    info = data.get('info') or {}
    if not info:
        raise DramaWaveError('DRAMAWAVE_SERIES_NOT_FOUND', series_id[:32])
    return {
        'series_id': str(info.get('id') or series_id),
        'title': info.get('name'),
        'description': info.get('desc'),
        'cover_url': info.get('cover'),
        'episode_count': info.get('episodeCount') or info.get('episode_count'),
        'metadata': {
            'labels': info.get('labels'),
            'content_tags': info.get('content_tags'),
            'original_audio_language': info.get('original_audio_language'),
            'free': info.get('free'),
            'finish_status': info.get('finish_status'),
        },
    }


