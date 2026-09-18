"""Disposable in-memory TTL cache (speed only; system works without it)."""

from __future__ import annotations

import threading
import time


class TTLCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            expires, value = hit
            if expires < now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: object, ttl: int) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + max(1, ttl), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


cache = TTLCache()
