"""Abstract base provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderCapability(str, Enum):
    SEARCH = 'search'
    SERIES = 'series'
    EPISODES = 'episodes'
    PLAYBACK = 'playback'
    FREE_STATE = 'free_state'


class ProviderHealth:
    def __init__(self) -> None:
        self.available: bool = True
        self.success_count: int = 0
        self.failure_count: int = 0
        self.total_latency: float = 0.0
        self.last_success: float | None = None
        self.last_failure: float | None = None
        self.last_error: str | None = None
        self.consecutive_failures: int = 0

    @property
    def average_latency(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.total_latency / self.success_count

    @property
    def failure_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.failure_count / total

    def record_success(self, latency: float) -> None:
        self.success_count += 1
        self.total_latency += latency
        self.last_success = __import__('time').time()
        self.consecutive_failures = 0
        self.last_error = None

    def record_failure(self, error: str) -> None:
        self.failure_count += 1
        self.last_failure = __import__('time').time()
        self.last_error = error
        self.consecutive_failures += 1


@dataclass
class ProviderSeries:
    provider: str
    provider_series_id: str
    title: str | None = None
    aliases: list[str] = field(default_factory=list)
    description: str | None = None
    cover_url: str | None = None
    episode_count: int | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderEpisode:
    provider: str
    provider_series_id: str
    provider_episode_id: str
    episode_number: int
    title: str | None = None
    duration: float | None = None
    locked: bool = False
    free: bool = False
    playback_available: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderPlayback:
    provider: str
    provider_episode_id: str
    type: str = 'hls'
    url: str = ''
    master_url: str | None = None
    audio_url: str | None = None
    audio_language: str | None = None
    codec: str = 'h264'
    quality: str = 'source'
    available_qualities: list[dict[str, Any]] = field(default_factory=list)
    expires_at: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class DramaProvider(ABC):
    name: str = ''

    capabilities: dict[ProviderCapability, bool] = {
        ProviderCapability.SEARCH: True,
        ProviderCapability.SERIES: True,
        ProviderCapability.EPISODES: True,
        ProviderCapability.PLAYBACK: True,
        ProviderCapability.FREE_STATE: True,
    }

    def __init__(self) -> None:
        self.health = ProviderHealth()

    @abstractmethod
    async def search(self, query: str) -> list[ProviderSeries]:
        ...

    @abstractmethod
    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        ...

    @abstractmethod
    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        ...

    @abstractmethod
    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        ...

    def health_check(self) -> ProviderHealth:
        return self.health
