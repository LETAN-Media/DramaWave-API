"""Normalized provider models for canonical series resolution."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class CanonicalSeries(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    canonical_title: str = ''
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    cover_url: str | None = None
    episode_count: int | None = None
    language: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SeriesProviderMapping(BaseModel):
    canonical_series_id: str
    provider: str
    provider_series_id: str
    provider_title: str | None = None
    episode_count: int | None = None
    match_score: float = 0.0
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EpisodeSource(BaseModel):
    canonical_series_id: str
    episode_number: int
    provider: str
    provider_series_id: str
    provider_episode_id: str
    locked: bool = True
    free: bool = False
    playback_available: bool = False
    duration: float | None = None
    quality_max: str | None = None
    last_checked_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeriesSearchResultItem(BaseModel):
    canonical_series_id: str
    canonical_title: str
    aliases: list[str] = Field(default_factory=list)
    episode_count: int | None = None
    usable_episode_count: int = 0
    providers: list[dict[str, Any]] = Field(default_factory=list)


class SeriesDetailResponse(BaseModel):
    canonical_series_id: str
    canonical_title: str
    description: str | None = None
    cover_url: str | None = None
    episode_count: int | None = None
    usable_episode_count: int = 0
    locked_episode_count: int = 0
    providers: list[dict[str, Any]] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class EpisodeSourceResponse(BaseModel):
    episode_number: int
    usable: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ProviderStatusResponse(BaseModel):
    provider: str
    enabled: bool = True
    available: bool = True
    capabilities: dict[str, bool] = Field(default_factory=dict)
    latency: float = 0.0
    last_success: float | None = None
    last_failure: float | None = None
    failure_rate: float = 0.0
    consecutive_failures: int = 0
    last_error: str | None = None


class AutoPlaybackResponse(BaseModel):
    selected_provider: str
    episode_number: int
    type: str
    url: str
    master_url: str | None = None
    audio_url: str | None = None
    audio_language: str | None = None
    quality: str = 'source'
    available_qualities: list[dict[str, Any]] = Field(default_factory=list)
