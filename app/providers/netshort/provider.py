"""NetShort provider implementation via public website data.

Research findings:
- Encrypted mobile API (appsecapi.netshort.com) requires RSA/AES encryption.
  Current login attempts return 500/401; endpoint/auth flow may have changed.
- Public website (netshort.com) embeds search/series JSON in HTML RSC payload.
- Episode list and playback URL sources were not found in public HTML.
- Third-party wrappers (netshort.sansekai.my.id, api-drama.dobda.id) are
  currently unavailable or blocked.

Capabilities:
- search: true  (via netshort.com HTML parsing)
- series: true  (via netshort.com HTML parsing)
- episodes: false (no verified public source)
- playback: false (no verified public source)
- free_state: false (depends on episodes/playback)
"""

from __future__ import annotations

import codecs
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any

from app.providers.base import (
    ProviderCapability,
    ProviderEpisode,
    ProviderPlayback,
    ProviderSeries,
)
from app.services.normalize import normalize_title

logger = logging.getLogger('dramawave-api.providers.netshort')

_BASE = 'https://netshort.com'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def _get(path: str) -> bytes:
    url = urllib.parse.urljoin(_BASE, path)
    req = urllib.request.Request(url, headers={
        'User-Agent': _UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _parse_rsc_chunks(html: str) -> list[Any]:
    pattern = r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)'
    chunks = re.findall(pattern, html)
    results = []
    for chunk in chunks:
        try:
            unescaped = codecs.decode(chunk, 'unicode_escape')
            if ':' in unescaped[:10]:
                parts = unescaped.split(':', 1)
                if len(parts) == 2 and parts[0].isdigit():
                    unescaped = parts[1]
            data = json.loads(unescaped)
            results.append(data)
        except Exception:
            continue
    return results


def _extract_short_plays(obj: Any, out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if isinstance(obj, dict):
        if 'shortPlayId' in obj and 'shortPlayName' in obj:
            out.append(obj)
        for v in obj.values():
            _extract_short_plays(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _extract_short_plays(item, out)
    return out


def _to_provider_series(item: dict[str, Any]) -> ProviderSeries:
    labels = item.get('labelList') or []
    return ProviderSeries(
        provider='netshort',
        provider_series_id=str(item.get('shortPlayId', '')),
        title=item.get('shortPlayName'),
        cover_url=item.get('shortPlayCover'),
        episode_count=item.get('totalEpisode'),
        language=item.get('language'),
        aliases=[normalize_title(item['shortPlayName'])] if item.get('shortPlayName') else [],
        metadata={
            'description': item.get('shotIntroduce'),
            'labels': [l.get('labelName') for l in labels if isinstance(l, dict)],
        },
    )


class NetShortProvider:
    name = 'netshort'

    capabilities = {
        ProviderCapability.SEARCH: True,
        ProviderCapability.SERIES: True,
        ProviderCapability.EPISODES: False,
        ProviderCapability.PLAYBACK: False,
        ProviderCapability.FREE_STATE: False,
    }

    def __init__(self) -> None:
        self.health = _Health()

    async def search(self, query: str) -> list[ProviderSeries]:
        try:
            raw = _get(f'/api/search?q={urllib.parse.quote(query)}')
            html = raw.decode('utf-8', 'replace')
            chunks = _parse_rsc_chunks(html)
            items: list[dict[str, Any]] = []
            for chunk in chunks:
                items.extend(_extract_short_plays(chunk))
            seen: set[str] = set()
            result: list[ProviderSeries] = []
            for item in items:
                sid = str(item.get('shortPlayId', ''))
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                result.append(_to_provider_series(item))
            self.health.record_success(0.0)
            return result[:50]
        except Exception as exc:
            logger.warning('netshort search failed: %s', exc)
            self.health.record_failure(str(exc))
            return []

    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        try:
            raw = _get(f'/api/drama/{provider_series_id}')
            html = raw.decode('utf-8', 'replace')
            chunks = _parse_rsc_chunks(html)
            items = []
            for chunk in chunks:
                items.extend(_extract_short_plays(chunk))
            for item in items:
                if str(item.get('shortPlayId', '')) == str(provider_series_id):
                    self.health.record_success(0.0)
                    return _to_provider_series(item)
            self.health.record_success(0.0)
            return None
        except Exception as exc:
            logger.warning('netshort get_series failed: %s', exc)
            self.health.record_failure(str(exc))
            return None

    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        raise NotImplementedError('NetShort episode list is not publicly available')

    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        raise NotImplementedError('NetShort playback is not publicly available')

    def health_check(self) -> _Health:
        return self.health


class _Health:
    available: bool = True
    success_count: int = 0
    failure_count: int = 0
    total_latency: float = 0.0
    last_success: float | None = None
    last_failure: float | None = None
    last_error: str | None = None
    consecutive_failures: int = 0

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
        import time
        self.success_count += 1
        self.total_latency += latency
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.last_error = None

    def record_failure(self, error: str) -> None:
        import time
        self.failure_count += 1
        self.last_failure = time.time()
        self.last_error = error
        self.consecutive_failures += 1
