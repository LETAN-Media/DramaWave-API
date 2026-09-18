"""Guest auth: anonymous login, runtime cache, auto refresh on expiry.

Credentials live only in process memory. Never logged, never committed,
never exposed via any API response.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import urllib.request
from dataclasses import dataclass

from app.config import settings
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.auth')

_lock = threading.Lock()
_cached: 'GuestCredentials | None' = None


@dataclass
class GuestCredentials:
    user_id: int | None
    auth_key: str
    auth_secret: str


def _device_id() -> str:
    import string

    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    return hashlib.md5((ua + rand).encode()).hexdigest()


def device_id_for_header() -> str:
    """Public alias used by the HTTP client."""
    return _device_id()


def get_guest_credentials(force_refresh: bool = False) -> GuestCredentials:
    """Return cached guest credentials, logging in anonymously when needed."""
    global _cached
    with _lock:
        if _cached is not None and not force_refresh:
            return _cached
        url = settings.dramawave_api_base.rstrip('/') + '/h5-api/anonymous/login'
        did = _device_id()
        body = json.dumps({'device_id': did}).encode()
        req = urllib.request.Request(url, data=body, method='POST', headers={
            'Content-Type': 'application/json', 'app-name': 'com.dramawave.h5',
            'app-version': '1.2.20', 'device-id': did, 'device-hash': did,
            'device': 'h5', 'language': 'en', 'Skip-Encrypt': '1'})
        try:
            with urllib.request.urlopen(req, timeout=settings.dramawave_timeout) as resp:
                payload = json.loads(resp.read().decode('utf-8', 'replace'))
        except Exception as exc:
            raise DramaWaveError('DRAMAWAVE_AUTH_FAILED', f'guest login {type(exc).__name__}')
        data = payload.get('data') or {}
        if str(payload.get('code')) not in ('200', '0') or not data.get('auth_key'):
            raise DramaWaveError('DRAMAWAVE_AUTH_FAILED', 'guest login rejected')
        _cached = GuestCredentials(user_id=data.get('user_id'), auth_key=data['auth_key'],
                                   auth_secret=data['auth_secret'])
        logger.info('guest login ok')
        return _cached
