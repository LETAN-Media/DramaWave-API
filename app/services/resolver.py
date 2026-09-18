"""Episode resolver: find best free source across providers."""

from __future__ import annotations

import logging

from app.errors import DramaWaveError
from app.services.canonical import get_store, refresh_series_sources, resolve_best_source

logger = logging.getLogger('dramawave-api.resolver')


class EpisodeResolver:
    def __init__(self) -> None:
        self._store = get_store()

    async def resolve(
        self,
        canonical_id: str,
        episode_number: int,
        quality: str = 'best',
        force_refresh: bool = False,
    ) -> dict | None:
        if force_refresh:
            await refresh_series_sources(canonical_id)
        result = await resolve_best_source(canonical_id, episode_number, quality)
        if result is None:
            raise DramaWaveError('NO_FREE_SOURCE', f'episode {episode_number}')
        return result

    async def resolve_with_fallback(
        self,
        canonical_id: str,
        episode_number: int,
        quality: str = 'best',
        preferred_provider: str | None = None,
    ) -> dict | None:
        result = await resolve_best_source(canonical_id, episode_number, quality)
        if result:
            return result
        await refresh_series_sources(canonical_id)
        result = await resolve_best_source(canonical_id, episode_number, quality)
        if result:
            return result
        raise DramaWaveError('NO_FREE_SOURCE', f'episode {episode_number}')
