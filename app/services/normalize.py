"""Title normalization for cross-provider series matching."""

from __future__ import annotations

import re
import unicodedata


_VIET_SUFFIXES = [
    'dubbed',
    'eng dubbed',
    'english dub',
    'vietsub',
    'full movie',
    'short drama',
    'episode',
    'season',
]

_VIET_PUNCT = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')


def normalize_title(title: str) -> str:
    if not title:
        return ''
    title = unicodedata.normalize('NFKD', title)
    # remove combining marks (Vietnamese diacritics)
    title = ''.join(c for c in title if not unicodedata.combining(c))
    title = title.lower()
    for suffix in _VIET_SUFFIXES:
        if title.endswith(suffix):
            title = title[:-len(suffix)]
    title = re.sub(r'\b(season\s*\d+|episode\s*\d+)\b', '', title)
    title = ''.join(' ' if c in _VIET_PUNCT else c for c in title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def alias_variants(title: str) -> list[str]:
    raw = title.strip()
    variants = {raw, normalize_title(raw)}
    parts = re.split(r'[:\-]', raw)
    for part in parts:
        variants.add(part.strip())
        variants.add(normalize_title(part))
    return [v for v in variants if v]
