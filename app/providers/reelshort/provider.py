import re
import logging
from typing import Any
from urllib.parse import quote
import time

from app.providers.base import (
    ProviderCapability,
    ProviderEpisode,
    ProviderPlayback,
    ProviderSeries,
)
from app.providers.http import ProviderSession, HTTPError
from app.services.normalize import normalize_title

logger = logging.getLogger('dramawave-api.providers.reelshort')

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
        self.success_count += 1
        self.total_latency += latency
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.last_error = None

    def record_failure(self, error: str) -> None:
        self.failure_count += 1
        self.last_failure = time.time()
        self.last_error = error
        self.consecutive_failures += 1


class ReelShortProvider:
    name = 'reelshort'
    
    capabilities = {
        ProviderCapability.SEARCH: True,
        ProviderCapability.SERIES: True,
        ProviderCapability.EPISODES: True,
        ProviderCapability.PLAYBACK: True,
        ProviderCapability.FREE_STATE: True,
    }

    def __init__(self) -> None:
        self.health = _Health()
        self.session = ProviderSession(impersonate="chrome", timeout=15, name="reelshort")
        self.build_id = "1789719981533"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.reelshort.com/"
        }

    async def _update_build_id(self) -> None:
        start = time.time()
        try:
            resp = await self.session.request("GET", "https://www.reelshort.com/", headers=self.headers)
            match = re.search(r'"buildId":"([^"]+)"', resp.text)
            if match:
                self.build_id = match.group(1)
            self.health.record_success(time.time() - start)
        except Exception as e:
            self.health.record_failure(str(e))
            logger.warning("ReelShort failed to update build ID: %s", e)

    async def _fetch_json(self, url: str) -> dict:
        start = time.time()
        try:
            resp = await self.session.request("GET", url, headers=self.headers)
            if 'text/html' in resp.headers.get('Content-Type', ''):
                await self._update_build_id()
                url = re.sub(r'/_next/data/[^/]+/', f'/_next/data/{self.build_id}/', url)
                resp = await self.session.request("GET", url, headers=self.headers)
            data = resp.json()
            self.health.record_success(time.time() - start)
            return data
        except Exception as e:
            self.health.record_failure(str(e))
            raise e

    async def search(self, query: str) -> list[ProviderSeries]:
        await self._update_build_id()
        url = f"https://www.reelshort.com/_next/data/{self.build_id}/en/search.json?keywords={quote(query)}"
        try:
            data = await self._fetch_json(url)
            books = data.get('pageProps', {}).get('books', [])
            result = []
            for b in books:
                b_id = str(b.get('_id'))
                title = b.get('book_title', '')
                if not b_id or not title: continue
                result.append(ProviderSeries(
                    provider=self.name,
                    provider_series_id=b_id,
                    title=title,
                    cover_url=b.get('book_pic'),
                    episode_count=b.get('chapter_count', 0),
                    aliases=[normalize_title(title)],
                ))
            return result
        except Exception as e:
            logger.warning('ReelShort search failed: %s', e)
            return []

    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        return None

    async def _get_slug(self, book_id: str) -> str | None:
        url = f"https://www.reelshort.com/_next/data/{self.build_id}/en/movie/a-{book_id}.json?slug=a-{book_id}"
        data = await self._fetch_json(url)
        redir = data.get('pageProps', {}).get('__N_REDIRECT')
        if redir:
            return redir.split('/')[-1]
        return None

    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        try:
            slug = await self._get_slug(provider_series_id)
            if not slug:
                return []
                
            url = f"https://www.reelshort.com/_next/data/{self.build_id}/en/movie/{slug}.json?slug={slug}"
            data = await self._fetch_json(url)
            online_base = data.get('pageProps', {}).get('data', {}).get('online_base', [])
            
            episodes = []
            for ep in online_base:
                ch_id = ep.get('chapter_id')
                ep_num = ep.get('serial_number')
                if ch_id is None or ep_num is None: continue
                
                # ReelShort API returns playable URLs for all episodes as seen in research.
                # So they are technically free for our purpose unless we find a strict block.
                # ReelShort episodes might not be 1-indexed for serial_number, so we index by list order
                
                # provider_episode_id format: slug|chapter_id|serial_number
                pid = f"{slug}|{ch_id}|{ep_num}"
                
                episodes.append(ProviderEpisode(
                    provider=self.name,
                    provider_series_id=provider_series_id,
                    provider_episode_id=pid,
                    episode_number=ep_num,
                    title=f"Episode {ep_num}",
                    free=True,
                    locked=False,
                    playback_available=True
                ))
                
            # Filter out teaser if it has serial_number 0
            episodes = [e for e in episodes if e.episode_number > 0]
            
            return episodes
        except Exception as e:
            logger.warning('ReelShort list_episodes failed: %s', e)
            return []

    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        try:
            parts = provider_episode_id.split('|')
            if len(parts) != 3:
                return None
            slug, chapter_id, ep_num = parts
            
            url = f"https://www.reelshort.com/_next/data/{self.build_id}/en/episodes/episode-{ep_num}-{slug}-{chapter_id}.json?play_time=1&slug=episode-{ep_num}-{slug}-{chapter_id}"
            data = await self._fetch_json(url)
            ep_data = data.get('pageProps', {}).get('data', {})
            video_url = ep_data.get('video_url')
            
            if not video_url:
                return None
                
            return ProviderPlayback(
                provider=self.name,
                provider_episode_id=provider_episode_id,
                type='hls' if '.m3u8' in video_url else 'mp4',
                url=video_url,
                quality='1080p' if '1080' in video_url else '720p',
                headers=self.headers
            )
        except Exception as e:
            logger.warning('ReelShort resolve_playback failed: %s', e)
            return None

    def health_check(self) -> _Health:
        return self.health
