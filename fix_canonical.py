import re

with open('app/services/canonical.py', 'r') as f:
    content = f.read()

new_search_all = """async def search_all(query: str) -> list[dict]:
    import asyncio
    
    seen_series: dict[str, ProviderSeries] = {}
    searchable_providers = [p for p in all_providers() if p.capabilities.get(ProviderCapability.SEARCH, False)]
    
    async def _search_provider(provider):
        try:
            return await provider.search(query)
        except Exception as exc:
            logger.warning('search failed provider=%s query=%s err=%s', provider.name, query, exc)
            return []
            
    # Run searches concurrently with a limit
    sem = asyncio.Semaphore(4)
    async def _limited_search(provider):
        async with sem:
            return await _search_provider(provider)
            
    results_list = await asyncio.gather(*[_limited_search(p) for p in searchable_providers])
    
    for items in results_list:
        for item in items:
            norm = normalize_title(item.title or '')
            if not norm:
                continue
            if norm in seen_series:
                existing = seen_series[norm]
                if item.provider != existing.provider:
                    _store.upsert_mapping(SeriesProviderMapping(
                        canonical_series_id=f"cw:{norm}",
                        provider=item.provider,
                        provider_series_id=item.provider_series_id,
                        provider_title=item.title,
                        episode_count=item.episode_count,
                        match_score=1.0,
                        verified=True
                    ))
            else:
                seen_series[norm] = item
                _store.upsert_mapping(SeriesProviderMapping(
                    canonical_series_id=f"cw:{norm}",
                    provider=item.provider,
                    provider_series_id=item.provider_series_id,
                    provider_title=item.title,
                    episode_count=item.episode_count,
                    match_score=1.0,
                    verified=True
                ))
                cs = CanonicalSeries(
                    id=f"cw:{norm}",
                    canonical_title=item.title or '',
                    cover_url=item.cover_url,
                    episode_count=item.episode_count,
                    language=item.language,
                    aliases=item.aliases
                )
                _store._series[f"cw:{norm}"] = cs

    out = []
    for norm in seen_series.keys():
        cid = f"cw:{norm}"
        if cid in _store._series:
            out.append(get_canonical_series_sync(cid))
            
    return [c.model_dump() if hasattr(c, 'model_dump') else c for c in out if c]"""

content = re.sub(r'async def search_all\(query: str\) -> list\[dict\]:.*?(?=\n\n\n|\Z)', new_search_all, content, flags=re.DOTALL)

with open('app/services/canonical.py', 'w') as f:
    f.write(content)
