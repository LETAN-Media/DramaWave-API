"""Backward-compatible facade over the split domain modules."""

from app.dramawave.episodes import get_episode, list_episodes
from app.dramawave.playback import get_playback, parse_master_variants, select_quality
from app.dramawave.search import search_series
from app.dramawave.series import get_series

__all__ = [
    'get_episode',
    'get_playback',
    'get_series',
    'list_episodes',
    'parse_master_variants',
    'search_series',
    'select_quality',
]
