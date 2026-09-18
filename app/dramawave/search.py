"""DramaWave domain logic (official H5 API mapping)."""

from __future__ import annotations

import logging

from app.dramawave.client import api_call
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.domain')

QUALITY_HEIGHTS = {'1080p': 1080, '720p': 720, '480p': 480}


def search_series(keyword: str, limit: int = 20) -> list[dict]:
    try:
        data = api_call('POST', '/h5-api/search/drama', body={'keyword': keyword})
    except DramaWaveError as exc:
        raise DramaWaveError('DRAMAWAVE_SEARCH_FAILED', exc.message)
    items = (data.get('items') or [])[:max(1, limit)]
    out = []
    for it in items:
        if not isinstance(it, dict) or not it.get('id'):
            continue
        out.append({
            'series_id': str(it['id']),
            'title': it.get('name') or it.get('title'),
            'cover_url': it.get('cover') or it.get('coverUrl') or '',
            'episode_count': it.get('episodeCount') or it.get('episode_count'),
        })
    return out


