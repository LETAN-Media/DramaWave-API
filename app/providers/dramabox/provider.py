import json
import logging
import time
import uuid
import random
import base64
from typing import Any
from urllib.parse import quote

from curl_cffi.requests import AsyncSession
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

from app.providers.base import (
    ProviderCapability,
    ProviderEpisode,
    ProviderPlayback,
    ProviderSeries,
)
from app.services.normalize import normalize_title

logger = logging.getLogger('dramawave-api.providers.dramabox')

# PKCS8 Key
_PEM_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC9Q4Y5QX5j08Hr
nbY3irfKdkEllAU2OORnAjlXDyCzcm2Z6ZRrGvtTZUAMelfU5PWS6XGEm3d4kJEK
bXi4Crl8o2E/E3YJPk1lQD1d0JTdrvZleETN1ViHZFSQwS3L94Woh0E3TPebaEYq
88eExvKu1tDdjSoFjBbgMezySnas5Nc2xF28XhPuC8m15u+dectsrJl+ALGcTDX3
Lv3FURuwV/dN7WMEkgcseIKVMdJxzUB0PeSqCNftfxmdBV/U4yXFRxPhnSFSXCrk
j6uJjickiYq1pQ1aZfrQe1eLD3MB2hKq7crhMcA3kpggQlnmy1wRR4BAttmSU4fP
b/yF8D3hAgMBAAECggEBAJdru6p5RLZ3h/GLF2rud8bqv4piF51e/RWQyPFnMAGB
rkByiYT7bFI3cnvJMhYpLHRigqjWfUofV3thRDDym54lVLtTRZ91khRMxgwVwdRu
k8Fw7JNFenOwCJxbgdlq6iuAMuQclwll7qWUrm8DgMvzH93xf8o6X171cp4Sh0og
1Ra7E9GZ37dzBlX2aJBK8VBfctZntuDPx52e71nafqfbjXxZuEtpu92oJd6A9mWb
d0BZTk72ZHUmDcKcqjfcEH19SWOphMJFYkxU5FRoIEr3/zisyTO4Mt33ZmwELOrY
9PdlyAAyed7ZoH+hlTr7c025QROvb2LmqgRiUT56tMECgYEA+jH5m6iMRK6XjiBh
SUnlr3DzRybwlQrtIj5sZprWe2my5uYHG3jbViYIO7GtQvMTnDrBCxNhuM6dPrL0
cRnbsp/iBMXe3pyjT/aWveBkn4R+UpBsnbtDn28r1MZpCDtr5UNc0TPj4KFJvjnV
/e8oGoyYEroECqcw1LqNOGDiLhkCgYEAwaemNePYrXW+MVX/hatfLQ96tpxwf7yu
HdENZ2q5AFw73GJWYvC8VY+TcoKPAmeoCUMltI3TrS6K5Q/GoLd5K2BsoJrSxQNQ
Fd3ehWAtdOuPDvQ5rn/2fsvgvc3rOvJh7uNnwEZCI/45WQg+UFWref4PPc+ArNtp
9Xj2y7LndwkCgYARojIQeXmhYZjG6JtSugWZLuHGkwUDzChYcIPdW25ndluokG/R
zNvQn4+W/XfTryQjr7RpXm1VxCIrCBvYWNU2KrSYV4XUtL+B5ERNj6In6AOrOAif
uVITy5cQQQeoD+AT4YKKMBkQfO2gnZzqb8+ox130e+3K/mufoqJPZeyrCQKBgC2f
objwhQvYwYY+DIUharri+rYrBRYTDbJYnh/PNOaw1CmHwXJt5PEDcml3+NlIMn58
I1X2U/hpDrAIl3MlxpZBkVYFI8LmlOeR7ereTddN59ZOE4jY/OnCfqA480Jf+FKf
oMHby5lPO5OOLaAfjtae1FhrmpUe3EfIx9wVuhKBAoGBAPFzHKQZbGhkqmyPW2ct
TEIWLdUHyO37fm8dj1WjN4wjRAI4ohNiKQJRh3QE11E1PzBTl9lZVWT8QtEsSjnr
A/tpGr378fcUT7WGBgTmBRaAnv1P1n/Tp0TSvh5XpIhhMuxcitIgrhYMIG3GbP9J
NAarxO/qPW6Gi0xWaF7il7Or
-----END PRIVATE KEY-----"""

_PRIVATE_KEY = RSA.import_key(_PEM_KEY)

def _sign_data(data_str: str) -> str:
    h = SHA256.new(data_str.encode('utf-8'))
    signature = pkcs1_15.new(_PRIVATE_KEY).sign(h)
    return base64.b64encode(signature).decode('utf-8')

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

class DramaBoxProvider:
    name = 'dramabox'

    capabilities = {
        ProviderCapability.SEARCH: True,
        ProviderCapability.SERIES: True,
        ProviderCapability.EPISODES: True,
        ProviderCapability.PLAYBACK: True,
        ProviderCapability.FREE_STATE: True,
    }

    def __init__(self) -> None:
        self.health = _Health()
        self._session: AsyncSession | None = None
        self._token: str | None = None
        self._device_id: str | None = None
        self._android_id: str | None = None
        self._token_expiry: float = 0

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(impersonate="chrome")
        return self._session

    async def _ensure_token(self) -> None:
        if self._token and time.time() < self._token_expiry:
            return
            
        session = await self._get_session()
        self._device_id = str(uuid.uuid4())
        self._android_id = "ffffffff" + "".join(random.choices("0123456789abcdef", k=8)) + "000000000"
        ts = int(time.time() * 1000)
        
        headers = {
            "tn": "",
            "version": "470",
            "vn": "4.7.0",
            "cid": "DAUAF1064291",
            "package-Name": "com.storymatrix.drama",
            "Apn": "1",
            "device-id": self._device_id,
            "language": "en",
            "current-Language": "en",
            "p": "48",
            "Time-Zone": "+0700",
            "md": "Redmi Note 8",
            "ov": "9",
            "over-flow": "new-fly",
            "android-id": self._android_id,
            "mf": "XIAOMI",
            "brand": "Xiaomi",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/4.10.0"
        }
        
        body = json.dumps({"distinctId": None}, separators=(',', ':'))
        sign_str = f"timestamp={ts}{body}{self._device_id}{self._android_id}"
        headers["sn"] = _sign_data(sign_str)
        
        url = f"https://sapi.dramaboxdb.com/drama-box/ap001/bootstrap?timestamp={ts}"
        resp = await session.post(url, headers=headers, data=body)
        resp.raise_for_status()
        data = resp.json()
        self._token = data['data']['user']['token']
        self._token_expiry = time.time() + 86400 # 24 hours

    async def _api_call(self, endpoint: str, payload: dict) -> dict:
        await self._ensure_token()
        session = await self._get_session()
        ts = int(time.time() * 1000)
        headers = {
            "tn": f"Bearer {self._token}",
            "version": "470",
            "vn": "4.7.0",
            "cid": "DAUAF1064291",
            "package-Name": "com.storymatrix.drama",
            "Apn": "1",
            "device-id": self._device_id,
            "language": "en",
            "current-Language": "en",
            "p": "48",
            "Time-Zone": "+0700",
            "md": "Redmi Note 8",
            "ov": "9",
            "over-flow": "new-fly",
            "android-id": self._android_id,
            "mf": "XIAOMI",
            "brand": "Xiaomi",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/4.10.0"
        }
        body = json.dumps(payload, separators=(',', ':')) if payload else "{}"
        sign_str = f"timestamp={ts}{body}{self._device_id}{self._android_id}{headers['tn']}"
        headers["sn"] = _sign_data(sign_str)
        
        url = f"https://sapi.dramaboxdb.com{endpoint}?timestamp={ts}"
        start_time = time.time()
        try:
            resp = await session.post(url, headers=headers, data=body)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise Exception(data.get("message", "API returned failure"))
            self.health.record_success(time.time() - start_time)
            return data
        except Exception as exc:
            self.health.record_failure(str(exc))
            raise

    async def search(self, query: str) -> list[ProviderSeries]:
        try:
            data = await self._api_call("/drama-box/search/suggest", {
                "keyword": query
            })
            items = data.get('data', {}).get('suggestList', [])
            result = []
            for item in items:
                book_id = str(item.get('bookId') or '')
                title = item.get('bookName', '')
                if not book_id or not title:
                    continue
                result.append(ProviderSeries(
                    provider=self.name,
                    provider_series_id=book_id,
                    title=title,
                    cover_url=item.get('cover'),
                    aliases=[normalize_title(title)],
                ))
            return result
        except Exception as exc:
            logger.warning('dramabox search failed: %s', exc)
            return []

    async def get_series(self, provider_series_id: str) -> ProviderSeries | None:
        try:
            data = await self._api_call("/drama-box/chapterv2/batch/load", {
                "boundaryIndex": 0,
                "index": target_index,
                "preLoad": False,
                "bookId": provider_series_id
            })
            d = data.get('data', {})
            if not d:
                return None
            title = d.get('bookName', '')
            if not title:
                return None
            return ProviderSeries(
                provider=self.name,
                provider_series_id=provider_series_id,
                title=title,
                episode_count=d.get('chapterCount'),
                aliases=[normalize_title(title)],
            )
        except Exception as exc:
            logger.warning('dramabox get_series failed: %s', exc)
            return None

    async def list_episodes(self, provider_series_id: str) -> list[ProviderEpisode]:
        try:
            episodes = []
            current_index = 1
            total_chapters = 1
            
            first_batch = await self._api_call("/drama-box/chapterv2/batch/load", {
                "boundaryIndex": 0,
                "index": current_index,
                "preLoad": False,
                "bookId": provider_series_id
            })
            d = first_batch.get('data', {})
            if not d:
                return []
                
            total_chapters = d.get('chapterCount') or 0
            pay_chapter_num = d.get('payChapterNum') or 0
            
            seen = set()
            
            def process_chapters(ch_list):
                for c in ch_list:
                    ch_id = str(c.get('chapterId'))
                    if ch_id in seen:
                        continue
                    seen.add(ch_id)
                    
                    ch_idx = c.get('chapterIndex', 0)
                    ch_num = ch_idx + 1
                    
                    is_free = True
                    if pay_chapter_num > 0 and ch_num >= pay_chapter_num:
                        is_free = False
                        
                    episodes.append(ProviderEpisode(
                        provider=self.name,
                        provider_series_id=provider_series_id,
                        provider_episode_id=ch_id,
                        episode_number=ch_num,
                        title=c.get('chapterName'),
                        free=is_free,
                        locked=not is_free,
                        playback_available=True
                    ))
                    
            process_chapters(d.get('chapterList', []))
            current_index = 6
            
            while current_index <= total_chapters:
                batch = await self._api_call("/drama-box/chapterv2/batch/load", {
                    "boundaryIndex": 0,
                    "index": current_index,
                    "preLoad": False,
                    "bookId": provider_series_id
                })
                items = batch.get('data', {}).get('chapterList', [])
                if items:
                    process_chapters(items)
                    current_index += 5
                else:
                    break
                    
            episodes.sort(key=lambda e: e.episode_number)
            return episodes
        except Exception as exc:
            logger.warning('dramabox list_episodes failed: %s', exc)
            return []

    async def resolve_playback(
        self,
        provider_episode_id: str,
        provider_series_id: str,
        quality: str = 'best',
    ) -> ProviderPlayback | None:
        try:
            # First, fetch episodes to get the target index. 
            # We can cache list_episodes, but for now we fetch.
            eps = await self.list_episodes(provider_series_id)
            target_ep = next((e for e in eps if e.provider_episode_id == provider_episode_id), None)
            if not target_ep:
                return None
                
            if target_ep.locked:
                return None

            batch = await self._api_call("/drama-box/chapterv2/batch/load", {
                "boundaryIndex": 0,
                "comingPlaySectionId": provider_episode_id,
                "index": target_ep.episode_number,
                "preLoad": False,
                "bookId": provider_series_id
            })
            
            items = batch.get('data', {}).get('chapterList', [])
            target = next((c for c in items if str(c.get('chapterId')) == provider_episode_id), None)
            
            if not target:
                return None
                
            cdn_list = target.get('cdnList', [])
            if not cdn_list:
                return None
                
            video_paths = cdn_list[0].get('videoPathList', [])
            if not video_paths:
                return None
                
            video_paths.sort(key=lambda v: v.get('quality', 0), reverse=True)
            chosen = video_paths[0]
            
            return ProviderPlayback(
                provider=self.name,
                provider_episode_id=provider_episode_id, type="mp4", url=chosen.get("videoPath"),
                headers={"User-Agent": "okhttp/4.10.0"},
                quality=f"{chosen.get('quality')}p" if chosen.get('quality') else "best"
            )
            
        except Exception as exc:
            logger.warning('dramabox resolve_playback failed: %s', exc)
            return None

    def health_check(self) -> _Health:
        return self.health
