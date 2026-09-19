import re
with open('app/api/episodes.py', 'r') as f:
    content = f.read()

replacement = """
        all_eps: dict[int, dict] = {}
        # Make sure we use the correct providers!
        asyncio.get_event_loop().run_until_complete(refresh_series_sources(series_id))
        sources_map = store.get_episode_sources(series_id, None) or {}
        # Wait, get_episode_sources takes episode_number!
        # It's better to access _episode_sources map directly:
        sources_map = store._episode_sources.get(series_id, {})
        for ep_num, sources in sources_map.items():
            all_eps[ep_num] = {'episode_number': ep_num, 'sources': []}
            for s in sources:
                all_eps[ep_num]['sources'].append({
                    'provider': s.provider,
                    'status': 'free' if s.free else 'locked',
                    'locked': s.locked or not s.playback_available,
                })
"""

content = re.sub(r'all_eps: dict\[int, dict\] = \{\}.*?for ep in eps:.*?\}\)', replacement, content, flags=re.DOTALL)

with open('app/api/episodes.py', 'w') as f:
    f.write(content)
