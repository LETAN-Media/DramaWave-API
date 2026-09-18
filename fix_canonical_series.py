with open('app/services/canonical.py', 'r') as f:
    content = f.read()

replacement = """
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
                cid = f"cw:{norm}"
                if cid not in _store._series:
                    from app.models.provider import CanonicalSeries
                    _store._series[cid] = CanonicalSeries(
                        id=cid,
                        canonical_title=item.title,
                        cover_url=item.cover_url,
                        episode_count=item.episode_count,
                        aliases=item.aliases
                    )
                _store.upsert_mapping(SeriesProviderMapping(
                    canonical_series_id=cid,
                    provider=item.provider,
                    provider_series_id=item.provider_series_id,
                    provider_title=item.title,
                    episode_count=item.episode_count,
                    match_score=1.0,
"""

content = content.replace("""
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
                    match_score=1.0,""", replacement)

with open('app/services/canonical.py', 'w') as f:
    f.write(content)
