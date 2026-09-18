"""DramaWave domain logic (official H5 API mapping)."""

from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request

from app.config import settings
from app.dramawave.client import api_call
from app.dramawave.episodes import get_episode
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.domain')

QUALITY_HEIGHTS = {'1080p': 1080, '720p': 720, '480p': 480}

def _pick_hls_url(raw: dict) -> str | None:
    return raw.get('external_audio_h264_m3u8') or raw.get('m3u8_url') or raw.get('video_url')


def parse_master_variants(master_url: str, timeout: int | None = None) -> list[dict]:
    """Parse an HLS master playlist into variant dicts (no media download)."""
    req = urllib.request.Request(master_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout or settings.dramawave_timeout) as resp:
            text = resp.read().decode('utf-8', 'replace')
    except Exception as exc:
        raise DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', f'playlist fetch {type(exc).__name__}')
    variants = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith('#EXT-X-STREAM-INF') or i + 1 >= len(lines):
            continue
        uri = lines[i + 1].strip()
        if not uri or uri.startswith('#'):
            continue
        m = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
        w, h = (int(m.group(1)), int(m.group(2))) if m else (None, None)
        bw = re.search(r'BANDWIDTH=(\d+)', line)
        fr = re.search(r'FRAME-RATE=([\d.]+)', line)
        short = min(w, h) if w and h else (h or w)
        variants.append({
            'quality': f'{short}p' if short else 'source',
            'width': w, 'height': h,
            'fps': float(fr.group(1)) if fr else None,
            'bandwidth': int(bw.group(1)) if bw else None,
            'url': urllib.parse.urljoin(master_url, uri),
        })
    if not variants:
        raise DramaWaveError('DRAMAWAVE_PLAYBACK_NOT_FOUND', 'no variants')
    return variants


def select_quality(variants: list[dict], quality: str) -> dict:
    """best, else nearest quality at/below target (lowest available if none below)."""
    want = (quality or 'best').strip().lower()

    def short(v: dict) -> int:
        w, h = v.get('width') or 0, v.get('height') or 0
        return min(w, h) if (w and h) else (h or w or 0)

    if want == 'best' or not variants:
        return max(variants, key=lambda v: (v.get('height') or 0, v.get('bandwidth') or 0))
    target = QUALITY_HEIGHTS.get(want, 10 ** 9)
    below = [v for v in variants if short(v) <= target]
    if below:
        return max(below, key=short)
    return min(variants, key=short)


def get_playback(series_id: str, episode_id: str, quality: str = 'best') -> dict:
    ep = get_episode(series_id, episode_id)
    if ep['locked']:
        raise DramaWaveError('DRAMAWAVE_EPISODE_LOCKED', episode_id[:32])
    raw = ep['_raw']
    url = _pick_hls_url(raw)
    if not url:
        raise DramaWaveError('DRAMAWAVE_PLAYBACK_NOT_FOUND', episode_id[:32])
    path = url.split('?')[0]
    if path.lower().endswith('.mp4'):
        return {'episode_id': episode_id, 'duration': ep['duration'], 'type': 'mp4',
                'codec': 'h264', 'quality': 'source', 'url': url, 'available_qualities': []}
    if '.m3u8' not in path:
        raise DramaWaveError('DRAMAWAVE_PLAYBACK_NOT_FOUND', 'unsupported playback')
    variants = parse_master_variants(url)
    chosen = select_quality(variants, quality)
    public_variants = [{k: v[k] for k in ('quality', 'width', 'height', 'fps', 'url')} for v in variants]
    return {'episode_id': episode_id, 'duration': ep['duration'], 'type': 'hls',
            'codec': 'h264', 'quality': chosen['quality'], 'url': chosen['url'],
            'available_qualities': public_variants}
