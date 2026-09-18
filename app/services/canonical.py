"""Canonical series mapping: store and match series across providers."""

from __future__ import annotations

import logging
import time
from difflib import SequenceMatcher
from typing import Any

from app.models.provider import CanonicalSeries, EpisodeSource, SeriesProviderMapping
from app.providers.base import ProviderCapability, ProviderEpisode, ProviderSeries
from app.providers.registry import all_providers, get, ordered_names
from app.services.normalize import alias_variants, normalize_title
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.canonical')

_SERIES_MATCH_THRESHOLD = 0.82


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_norm = normalize_title(a)
    b_norm = normalize_title(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def alias_similarity(a_aliases: list[str], b_title: str) -> float:
    if not a_aliases or not b_title:
        return 0.0
    b_norm = normalize_title(b_title)
    best = 0.0
    for alias in a_aliases:
        score = SequenceMatcher(None, alias, b_norm).ratio()
        if score > best:
            best = score
    return best


def score_match(
    a: ProviderSeries,
    b: ProviderSeries,
    episode_count_weight: float = 0.2,
) -> float:
    title_score = title_similarity(a.title or '', b.title or '')
    alias_score = alias_similarity(a.aliases, b.title or '')
    best_title = max(title_score, alias_score)

    ep_score = 0.0
    if a.episode_count and b.episode_count:
        diff = abs(a.episode_count - b.episode_count)
        max_ep = max(a.episode_count, b.episode_count)
        ep_score = max(0.0, 1.0 - diff / max_ep) if max_ep > 0 else 0.0

    desc_score = 0.0
    if a.description and b.description:
        desc_score = SequenceMatcher(None, a.description, b.description).ratio()

    weights = [0.5, 0.2, episode_count_weight, 0.1]
    scores = [best_title, alias_score, ep_score, desc_score]
    return sum(w * s for w, s in zip(weights, scores)) / sum(weights)


class CanonicalStore:
    def __init__(self) -> None:
        self._series: dict[str, CanonicalSeries] = {}
        self._mappings: dict[str, list[SeriesProviderMapping]] = {}
        self._episode_sources: dict[str, dict[int, list[EpisodeSource]]] = {}

    def get_series(self, canonical_id: str) -> CanonicalSeries | None:
        return self._series.get(canonical_id)

    def get_mappings(self, canonical_id: str) -> list[SeriesProviderMapping]:
        return self._mappings.get(canonical_id, [])

    def get_episode_sources(self, canonical_id: str, episode_number: int) -> list[EpisodeSource]:
        return self._episode_sources.get(canonical_id, {}).get(episode_number, [])

    def upsert_mapping(self, mapping: SeriesProviderMapping) -> None:
        cid = mapping.canonical_series_id
        if cid not in self._series:
            self._series[cid] = CanonicalSeries(id=cid)
        cs = self._series[cid]
        if mapping.provider_title and not cs.canonical_title:
            cs.canonical_title = mapping.provider_title
        if mapping.episode_count and not cs.episode_count:
            cs.episode_count = mapping.episode_count
        self._mappings.setdefault(cid, [])
        existing = [m for m in self._mappings[cid] if m.provider != mapping.provider]
        existing.append(mapping)
        self._mappings[cid] = existing

    def update_episode_sources(self, canonical_id: str, sources: list[EpisodeSource]) -> None:
        by_ep: dict[int, list[EpisodeSource]] = {}
        for s in sources:
            by_ep.setdefault(s.episode_number, []).append(s)
        for ep_num, ep_sources in by_ep.items():
            existing = self._episode_sources.get(canonical_id, {}).get(ep_num, [])
            merged = {s.provider: s for s in existing}
            for s in ep_sources:
                if s.provider in merged:
                    ms = merged[s.provider]
                    ms.locked = s.locked
                    ms.free = s.free
                    ms.playback_available = s.playback_available
                    ms.duration = s.duration or ms.duration
                    ms.quality_max = s.quality_max or ms.quality_max
                    ms.last_checked_at = s.last_checked_at
                    ms.metadata = s.metadata
                else:
                    merged[s.provider] = s
            self._episode_sources.setdefault(canonical_id, {})[ep_num] = list(merged.values())


_store = CanonicalStore()


def get_store() -> CanonicalStore:
    return _store


async def search_all(query: str) -> list[dict]:
    results: list[dict] = []
    seen_series: dict[str, ProviderSeries] = {}

    for provider in all_providers():
        if not provider.capabilities.get(ProviderCapability.SEARCH, False):
            continue
        try:
            items = await provider.search(query)
        except Exception as exc:
            logger.warning('search failed provider=%s query=%s err=%s', provider.name, query, exc)
            continue

        for item in items:
            norm = normalize_title(item.title or '')
            if not norm:
                continue
            if norm in seen_series:
                existing = seen_series[norm]
                if item.provider != existing.provider:
                    _store.upsert_mapping(SeriesProviderMapping(
                        canonical_series_id='',
                        provider=item.provider,
                        provider_series_id=item.provider_series_id,
                        provider_title=item.title,
                        episode_count=item.episode_count,
                    ))
                continue
            seen_series[norm] = item
            canonical_id = f'cw:{norm}'
            cs = CanonicalSeries(
                id=canonical_id,
                canonical_title=item.title or '',
                aliases=item.aliases or alias_variants(item.title or ''),
                cover_url=item.cover_url,
                episode_count=item.episode_count,
                language=item.language,
            )
            _store._series[canonical_id] = cs
            _store.upsert_mapping(SeriesProviderMapping(
                canonical_series_id=canonical_id,
                provider=item.provider,
                provider_series_id=item.provider_series_id,
                provider_title=item.title,
                episode_count=item.episode_count,
                match_score=1.0,
                verified=True,
            ))

    for canonical_id, cs in _store._series.items():
        mappings = _store.get_mappings(canonical_id)
        usable = _count_usable_episodes(canonical_id)
        results.append({
            'canonical_series_id': canonical_id,
            'canonical_title': cs.canonical_title,
            'aliases': cs.aliases,
            'episode_count': cs.episode_count,
            'usable_episode_count': usable,
            'providers': [
                {
                    'provider': m.provider,
                    'provider_series_id': m.provider_series_id,
                    'title': m.provider_title,
                    'episode_count': m.episode_count,
                    'match_score': m.match_score,
                }
                for m in mappings
            ],
        })
    return results


async def get_canonical_series(canonical_id: str) -> dict | None:
    cs = _store.get_series(canonical_id)
    if not cs:
        return None
    mappings = _store.get_mappings(canonical_id)
    usable = _count_usable_episodes(canonical_id)
    locked = _count_locked_episodes(canonical_id)
    return {
        'canonical_series_id': cs.id,
        'canonical_title': cs.canonical_title,
        'description': cs.description,
        'cover_url': cs.cover_url,
        'episode_count': cs.episode_count,
        'usable_episode_count': usable,
        'locked_episode_count': locked,
        'aliases': cs.aliases,
        'providers': [
            {
                'provider': m.provider,
                'provider_series_id': m.provider_series_id,
                'provider_title': m.provider_title,
                'episode_count': m.episode_count,
                'match_score': m.match_score,
                'verified': m.verified,
            }
            for m in mappings
        ],
    }


async def get_episode_sources(canonical_id: str, episode_number: int) -> list[dict]:
    sources = _store.get_episode_sources(canonical_id, episode_number)
    out = []
    for s in sources:
        out.append({
            'provider': s.provider,
            'provider_series_id': s.provider_series_id,
            'provider_episode_id': s.provider_episode_id,
            'locked': s.locked,
            'free': s.free,
            'playback_available': s.playback_available,
            'duration': s.duration,
            'quality_max': s.quality_max,
            'last_checked_at': s.last_checked_at.isoformat(),
        })
    return out


async def resolve_best_source(
    canonical_id: str,
    episode_number: int,
    quality: str = 'best',
) -> dict | None:
    sources = _store.get_episode_sources(canonical_id, episode_number)
    if not sources:
        return None
    priority = ordered_names()
    def sort_key(s):
        try:
            return priority.index(s.provider)
        except ValueError:
            return len(priority)
    sorted_sources = sorted(sources, key=sort_key)
    for s in sorted_sources:
        if s.locked or not s.free or not s.playback_available:
            continue
        provider = get(s.provider)
        if provider is None:
            continue
        pb = await provider.resolve_playback(s.provider_episode_id, s.provider_series_id, quality)
        if pb and pb.url:
            return {
                'selected_provider': s.provider,
                'provider_series_id': s.provider_series_id,
                'provider_episode_id': s.provider_episode_id,
                'episode_number': episode_number,
                'playback': pb,
            }
    return None


def _count_usable_episodes(canonical_id: str) -> int:
    by_ep = _store._episode_sources.get(canonical_id, {})
    count = 0
    for ep_num, sources in by_ep.items():
        if any(s.playback_available and not s.locked and s.free for s in sources):
            count += 1
    return count


def _count_locked_episodes(canonical_id: str) -> int:
    by_ep = _store._episode_sources.get(canonical_id, {})
    count = 0
    for ep_num, sources in by_ep.items():
        if not any(not s.locked and s.free and s.playback_available for s in sources):
            count += 1
    return count


async def refresh_series_sources(canonical_id: str) -> None:
    mappings = _store.get_mappings(canonical_id)
    for m in mappings:
        provider = get(m.provider)
        if not provider:
            continue
        try:
            episodes = await provider.list_episodes(m.provider_series_id)
        except Exception as exc:
            logger.warning('list_episodes failed provider=%s series=%s err=%s', m.provider, m.provider_series_id, exc)
            continue
        sources = []
        for ep in episodes:
            sources.append(EpisodeSource(
                canonical_series_id=canonical_id,
                episode_number=ep.episode_number,
                provider=m.provider,
                provider_series_id=m.provider_series_id,
                provider_episode_id=ep.provider_episode_id,
                locked=ep.locked,
                free=ep.free,
                playback_available=ep.playback_available,
                duration=ep.duration,
                metadata=ep.metadata,
            ))
        _store.update_episode_sources(canonical_id, sources)
