import logging
from urllib.parse import urljoin
import time
from typing import Any

from app.providers.base import (
    ProviderCapability,
    ProviderEpisode,
    ProviderPlayback,
    ProviderSeries,
)
from app.providers.http import ProviderSession
from app.services.normalize import normalize_title

logger = logging.getLogger('dramawave-api.providers.goodshort')

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

class GoodShortProvider:
    name = 'goodshort'
    
    capabilities = {
        ProviderCapability.SEARCH: True,
        ProviderCapability.SERIES: True,
        ProviderCapability.EPISODES: True,
        ProviderCapability.PLAYBACK: True,
        ProviderCapability.FREE_STATE: True,
    }

    def __init__(self) -> None:
        self.health = _Health()
        self.session = ProviderSession(impersonate="chrome", timeout=15, name="goodshort")
        self.base_url = "https://www.goodshort.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.goodshort.com",
            "Referer": "https://www.goodshort.com/",
            "currentlanguage": "en",
            "platform": "WEB"
        }

    async def _post_json(self, path: str, payload: dict) -> dict:
        start = time.time()
        url = urljoin(self.base_url, path)
        try:
            resp = await self.session.request("POST", url, headers=self.headers, json_data=payload)
            data = resp.json()
            self.health.record_success(time.time() - start)
            return data
        except Exception as e:
            self.health.record_failure(str(e))
            raise e

    async def search(self, query: str) -> list[ProviderSeries]:
        try:
            data = await self._post_json("/hwycreels/book/search/suggest", {"keyword": query})
            books = data.get('data', {}).get('suggest', [])
            result = []
            for b in books:
                b_id = str(b.get('bookId'))
                title = b.get('bookName', '')
                if not b_id or not title: continue
                result.append(ProviderSeries(
                    provider=self.name,
                    provider_series_id=b_id,
                    title=title,
                    cover_url=b.get('cover'),
                    episode_count=b.get('chapterCount', 0),
                    aliases=[normalize_title(title)],
                ))
            return result
        except Exception as e:
            logger.warning('GoodShort search failed: %s', e)
            return []

    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        try:
            data = await self._post_json("/hwycreels/book/detail", {"bookId": provider_series_id})
            b = data.get('data', {}).get('book')
            if not b: return None
            title = b.get('bookName', '')
            return ProviderSeries(
                provider=self.name,
                provider_series_id=str(b.get('bookId')),
                title=title,
                cover_url=b.get('cover'),
                episode_count=b.get('chapterCount', 0),
                aliases=[normalize_title(title)],
            )
        except Exception as e:
            logger.warning('GoodShort get_series failed: %s', e)
            return None

    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        try:
            # GoodShort pages episodes, we can request a large pageSize
            data = await self._post_json("/hwycreels/chapter/page", {
                "bookId": provider_series_id,
                "pageNum": 1,
                "pageSize": 500
            })
            records = data.get('data', {}).get('records', [])
            
            episodes = []
            for ep in records:
                ch_id = str(ep.get('id'))
                # serial number / index
                ep_num = ep.get('index', 0) + 1
                
                m3u8 = ep.get('m3u8Path')
                is_free = bool(m3u8)
                
                # if free, we store the m3u8 in provider_episode_id since resolve doesn't have it natively
                # or we can just encode it
                # Wait, if we encode m3u8 in provider_episode_id it will be huge.
                # Actually, resolve_playback can just call /hwycreels/chapter/page again, or we can encode just the chapterId. 
                # But wait, chapter/detail didn't return m3u8!
                # Since we have it here, and the only way to get it is /chapter/page, we should just encode it!
                # Wait, M3U8 URL is quite long: 170+ chars. It's fine for provider_episode_id string.
                
                pid = f"{ch_id}|{m3u8}" if is_free else f"{ch_id}|LOCKED"
                
                episodes.append(ProviderEpisode(
                    provider=self.name,
                    provider_series_id=provider_series_id,
                    provider_episode_id=pid,
                    episode_number=ep_num,
                    title=f"Episode {ep_num}",
                    free=is_free,
                    locked=not is_free,
                    playback_available=is_free
                ))
                
            return episodes
        except Exception as e:
            logger.warning('GoodShort list_episodes failed: %s', e)
            return []

    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        try:
            parts = provider_episode_id.split('|', 1)
            if len(parts) != 2:
                return None
            ch_id, m3u8 = parts
            
            if m3u8 == "LOCKED" or not m3u8:
                return None
                
            return ProviderPlayback(
                provider=self.name,
                provider_episode_id=provider_episode_id,
                type='hls' if '.m3u8' in m3u8 else 'mp4',
                url=m3u8,
                quality='720p',
                headers=self.headers
            )
        except Exception as e:
            logger.warning('GoodShort resolve_playback failed: %s', e)
            return None

    def health_check(self) -> _Health:
        return self.health

