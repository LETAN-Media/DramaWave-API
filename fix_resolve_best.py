import re

with open('app/services/canonical.py', 'r') as f:
    content = f.read()

new_resolve = """async def resolve_best_source(
    canonical_id: str,
    episode_number: int,
    quality: str = 'best',
) -> dict | None:
    import asyncio
    sources = _store.get_episode_sources(canonical_id, episode_number)
    if not sources:
        return None
        
    priority = ordered_names()
    def get_priority(s):
        try:
            return priority.index(s.provider)
        except ValueError:
            return len(priority)
            
    free_sources = [s for s in sources if not s.locked and s.free and s.playback_available]
    if not free_sources:
        return None
        
    # We will resolve all free sources concurrently
    async def try_resolve(s):
        provider = get(s.provider)
        if provider is None:
            return None
        try:
            pb = await provider.resolve_playback(s.provider_episode_id, s.provider_series_id, quality)
            if pb and pb.url:
                return (s, pb)
        except Exception as exc:
            logger.warning('resolve failed provider=%s err=%s', s.provider, exc)
        return None

    results = await asyncio.gather(*[try_resolve(s) for s in free_sources])
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        return None
        
    # Sort by quality, then priority
    def quality_score(q_str):
        q_str = str(q_str).lower()
        if '1080' in q_str: return 1080
        if '720' in q_str: return 720
        if '480' in q_str: return 480
        if '360' in q_str: return 360
        return 0

    valid_results.sort(key=lambda r: (
        -quality_score(r[1].quality),  # higher quality first
        get_priority(r[0])             # lower priority index first
    ))
    
    best_s, best_pb = valid_results[0]
    return {
        'selected_provider': best_s.provider,
        'provider_series_id': best_s.provider_series_id,
        'provider_episode_id': best_s.provider_episode_id,
        'episode_number': episode_number,
        'playback': best_pb,
    }"""

content = re.sub(r'async def resolve_best_source\([^)]+\).*?(?=\n\ndef _count_usable_episodes)', new_resolve, content, flags=re.DOTALL)

with open('app/services/canonical.py', 'w') as f:
    f.write(content)
