"""Pydantic response models (OpenAPI-visible, no auth data)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchItem(BaseModel):
    series_id: str
    title: str | None = None
    cover_url: str | None = None
    episode_count: int | None = None


class SearchResponse(BaseModel):
    items: list[SearchItem] = Field(default_factory=list)


class SeriesResponse(BaseModel):
    series_id: str
    title: str | None = None
    description: str | None = None
    cover_url: str | None = None
    episode_count: int | None = None
    metadata: dict = Field(default_factory=dict)


class EpisodeItem(BaseModel):
    episode_id: str
    episode_number: int
    title: str | None = None
    duration: float | None = None
    episode_price: int | None = None
    locked: bool = False
    cover: str | None = None


class EpisodeListResponse(BaseModel):
    series_id: str
    total: int
    episodes: list[EpisodeItem] = Field(default_factory=list)


class QualityVariant(BaseModel):
    quality: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    url: str


class AudioTrack(BaseModel):
    language: str | None = None
    name: str | None = None
    default: bool = False
    url: str


class PlaybackResponse(BaseModel):
    episode_id: str
    duration: float | None = None
    type: str
    codec: str
    quality: str
    url: str
    master_url: str | None = None
    audio_url: str | None = None
    audio_language: str | None = None
    audio_tracks: list[AudioTrack] = Field(default_factory=list)
    available_qualities: list[QualityVariant] = Field(default_factory=list)


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str
    guest_auth: dict = Field(default_factory=dict)
