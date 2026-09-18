"""DramaBox provider stub (research only, no production capability claimed)."""

from __future__ import annotations

import logging

from app.providers.base import (
    DramaProvider,
    ProviderCapability,
    ProviderEpisode,
    ProviderPlayback,
    ProviderSeries,
)


logger = logging.getLogger('dramawave-api.providers.dramabox')


class DramaBoxProvider(DramaProvider):
    name = 'dramabox'

    def __init__(self) -> None:
        super().__init__()
        self.capabilities = {
            ProviderCapability.SEARCH: False,
            ProviderCapability.SERIES: False,
            ProviderCapability.EPISODES: False,
            ProviderCapability.PLAYBACK: False,
            ProviderCapability.FREE_STATE: False,
        }

    async def search(self, query: str) -> list[ProviderSeries]:
        raise NotImplementedError('DramaBox provider not implemented')

    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        raise NotImplementedError('DramaBox provider not implemented')

    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        raise NotImplementedError('DramaBox provider not implemented')

    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        raise NotImplementedError('DramaBox provider not implemented')
