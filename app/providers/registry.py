"""Provider registry with priority ordering and reliability tracking."""

from __future__ import annotations

import logging
import time

from app.config import settings
from app.providers.base import DramaProvider, ProviderCapability, ProviderHealth

logger = logging.getLogger('dramawave-api.registry')

_REGISTRY: dict[str, DramaProvider] = {}
_ORDER: list[str] = []


def register(provider: DramaProvider) -> None:
    _REGISTRY[provider.name] = provider
    _ORDER.append(provider.name)
    logger.info('provider registered name=%s', provider.name)


def get(name: str) -> DramaProvider | None:
    return _REGISTRY.get(name)


def all_providers() -> list[DramaProvider]:
    return [_REGISTRY[n] for n in _ORDER if n in _REGISTRY]


def ordered_names() -> list[str]:
    priority = [p.strip() for p in (settings.provider_priority or '').split(',') if p.strip()]
    ordered = [n for n in priority if n in _REGISTRY]
    for n in _ORDER:
        if n not in ordered:
            ordered.append(n)
    return ordered


def get_status() -> list[dict]:
    out = []
    for p in all_providers():
        h = p.health_check()
        out.append({
            'provider': p.name,
            'enabled': True,
            'available': h.available,
            'capabilities': {c.value: v for c, v in p.capabilities.items()},
            'latency': round(h.average_latency, 3),
            'last_success': h.last_success,
            'last_failure': h.last_failure,
            'failure_rate': round(h.failure_rate, 3),
            'consecutive_failures': h.consecutive_failures,
            'last_error': h.last_error,
        })
    return out
