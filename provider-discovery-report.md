# PROVIDER DISCOVERY REPORT

## Research Summary
Total Providers Researched: 5
- **ReelShort**: `PLAYBACK` (Implemented)
- **GoodShort**: `PLAYBACK` (Implemented)
- **FlexTV**: `CATALOG_ONLY` / `UNSUPPORTED` (Requires WAF/signature bypass)
- **ShortMax**: `CATALOG_ONLY` / `UNSUPPORTED` (Requires WAF/signature bypass)
- **MoboReels**: `CATALOG_ONLY` / `UNSUPPORTED` (API missing documentation/parameters, easily blocked)

## Implementation Details

### ReelShort
- **Status**: `PLAYBACK` PASS
- **Authentication**: No DRM. Open Next.js API endpoints.
- **Playback**: Returns HLS `.m3u8` streams for all episodes.
- **Integration**: Added to `ReelShortProvider` utilizing the Next.js `_next/data/{build_id}` endpoints and resolving `m3u8` natively.

### GoodShort
- **Status**: `PLAYBACK` PASS
- **Authentication**: Requires correct payload and `WEB` headers, but exposes full chapter list in `/hwycreels/chapter/page`.
- **Playback**: Returns HLS `.m3u8` for free episodes directly in the chapter list. Locked episodes correctly hide the playback URL. 
- **Integration**: Added to `GoodShortProvider`.

### FlexTV, ShortMax, MoboReels
- **Status**: `UNSUPPORTED` (Degraded)
- **Reason**: FlexTV and ShortMax utilize strict API signatures (`Signature authentication failed.`, `非法请求!!`) requiring significant reverse engineering of their obfuscated Webpack/Wasm bundles. They have been omitted from the registry to prioritize stability and speed.

## System Improvements
- **HTTP Layer**: Built a generic `ProviderSession` in `app/providers/http.py` integrating `curl_cffi` to handle WAFs, impersonation, retries, and rate limits generically.
- **Concurrency**: Upgraded `canonical.py`'s `search_all` to use `asyncio.gather` with a semaphore (limit 4) for true parallel searches.
- **Quality Scoring**: `resolve_best_source` now resolves all free playback URLs concurrently and picks the highest quality stream (e.g. `1080p` > `720p`) or relies on priority if qualities match.

## Fallback Chain & Coverage
- **Highest Merged Coverage Test**: The fallback mechanism was successfully verified. Tests seamlessly fall back when a primary provider has locked episodes but a secondary provider yields free `1080p`/`720p` playback.
- **Best Fallback Chain**: `dramawave -> dramabox -> reelshort -> goodshort`.
