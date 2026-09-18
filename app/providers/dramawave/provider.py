"""DramaWave provider: wraps existing domain logic into the new provider interface."""

from __future__ import annotations

import logging
import time

from app.config import settings
from app.dramawave import domain as dw_domain
from app.dramawave.auth import get_guest_credentials
from app.errors import DramaWaveError
from app.providers.base import (
    DramaProvider,
    ProviderCapability,
    ProviderEpisode,
    ProviderPlayback,
    ProviderSeries,
)
from app.services.normalize import normalize_title

logger = logging.getLogger('dramawave-api.providers.dramawave')


class DramaWaveProvider(DramaProvider):
    name = 'dramawave'

    def __init__(self) -> None:
        super().__init__()
        self.capabilities = {
            ProviderCapability.SEARCH: True,
            ProviderCapability.SERIES: True,
            ProviderCapability.EPISODES: True,
            ProviderCapability.PLAYBACK: True,
            ProviderCapability.FREE_STATE: True,
        }

    async def search(self, query: str) -> list[ProviderSeries]:
        t0 = time.monotonic()
        try:
            items = dw_domain.search_series(query)
            result = [
                ProviderSeries(
                    provider=self.name,
                    provider_series_id=str(it['series_id']),
                    title=it.get('title'),
                    cover_url=it.get('cover_url'),
                    episode_count=it.get('episode_count'),
                    aliases=[normalize_title(it['title'])] if it.get('title') else [],
                )
                for it in items
            ]
            self.health.record_success(time.monotonic() - t0)
            return result
        except Exception as exc:
            self.health.record_failure(str(exc))
            raise

    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        t0 = time.monotonic()
        try:
            info = dw_domain.get_series(provider_series_id)
            result = ProviderSeries(
                provider=self.name,
                provider_series_id=provider_series_id,
                title=info.get('title'),
                description=info.get('description'),
                cover_url=info.get('cover_url'),
                episode_count=info.get('episode_count'),
                aliases=[normalize_title(info['title'])] if info.get('title') else [],
                metadata=info.get('metadata', {}),
            )
            self.health.record_success(time.monotonic() - t0)
            return result
        except DramaWaveError as exc:
            self.health.record_failure(exc.message)
            if exc.code == 'DRAMAWAVE_SERIES_NOT_FOUND':
                return None
            raise
        except Exception as exc:
            self.health.record_failure(str(exc))
            raise

    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        t0 = time.monotonic()
        try:
            raw_eps = dw_domain.list_episodes(provider_series_id)
            result = []
            for ep in raw_eps:
                locked = bool(ep.get('locked', False))
                result.append(
                    ProviderEpisode(
                        provider=self.name,
                        provider_series_id=provider_series_id,
                        provider_episode_id=str(ep.get('episode_id', '')),
                        episode_number=int(ep.get('episode_number', 0)),
                        title=ep.get('title'),
                        duration=ep.get('duration'),
                        locked=locked,
                        free=not locked,
                        playback_available=not locked,
                        metadata=ep.get('_raw', {}),
                    )
                )
            self.health.record_success(time.monotonic() - t0)
            return result
        except Exception as exc:
            self.health.record_failure(str(exc))
            raise

    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        t0 = time.monotonic()
        try:
            pb = dw_domain.get_playback(provider_series_id, provider_episode_id, quality)
            result = ProviderPlayback(
                provider=self.name,
                provider_episode_id=provider_episode_id,
                type=pb.get('type', 'hls'),
                url=pb.get('url', ''),
                master_url=pb.get('master_url'),
                audio_url=pb.get('audio_url'),
                audio_language=pb.get('audio_language'),
                codec=pb.get('codec', 'h264'),
                quality=pb.get('quality', 'source'),
                available_qualities=pb.get('available_qualities', []),
            )
            self.health.record_success(time.monotonic() - t0)
            return result
        except DramaWaveError as exc:
            self.health.record_failure(exc.message)
            if exc.code == 'DRAMAWAVE_EPISODE_LOCKED':
                return None
            if exc.code in ('DRAMAWAVE_PLAYBACK_NOT_FOUND', 'DRAMAWAVE_EPISODE_NOT_FOUND'):
                return None
            raise
        except Exception as exc:
            self.health.record_failure(str(exc))
            raise
