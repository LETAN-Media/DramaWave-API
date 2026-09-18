"""H5 API client: GET/POST, timeout, retry, 429/5xx backoff, auth refresh."""

from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from app.config import settings
from app.dramawave.auth import device_id_for_header, get_guest_credentials
from app.dramawave.signing import sign_request
from app.errors import DramaWaveError

logger = logging.getLogger('dramawave-api.client')


def redact_url(url: str) -> str:
    """Strip query (signed tokens) for safe logging."""
    try:
        parts = urlparse(url)
        return f'{parts.scheme}://{parts.hostname or ""}{parts.path}'
    except (ValueError, AttributeError):
        return '<url>'


def _base_headers() -> dict:
    did = device_id_for_header()
    return {
        'Content-Type': 'application/json',
        'app-name': 'com.dramawave.h5',
        'app-version': '1.2.20',
        'device-id': did,
        'device-hash': did,
        'device': 'h5',
        'language': 'en',
        'Skip-Encrypt': '1',
    }


def api_call(method: str, path: str, params: dict | None = None, body: dict | None = None,
             need_auth: bool = True, timeout: int | None = None) -> dict:
    """Call the official H5 API. Refreshes guest auth once on 401/403."""
    timeout = timeout or settings.dramawave_timeout
    max_retries = max(0, settings.dramawave_max_retries)
    attempted_refresh = False
    last_err: DramaWaveError | None = None
    for attempt in range(max_retries + 1):
        headers = _base_headers()
        if need_auth:
            headers['authorization'] = sign_request(get_guest_credentials())
        url = settings.dramawave_api_base.rstrip('/') + path
        data = None
        if method == 'GET' and params:
            url += '?' + urllib.parse.urlencode(params)
        if method == 'POST':
            data = json.dumps(body or {}).encode()
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode('utf-8', 'replace'))
            if str(payload.get('code')) not in ('200', '0'):
                raise DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR',
                                     f'{path} code={payload.get("code")} msg={str(payload.get("message"))[:150]}')
            return payload.get('data') or {}
        except DramaWaveError:
            raise
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and need_auth and not attempted_refresh:
                attempted_refresh = True
                get_guest_credentials(force_refresh=True)
                logger.info('guest auth refreshed after %s, retrying %s', exc.code, path)
                continue
            if exc.code == 429:
                retry_after = exc.headers.get('Retry-After') if exc.headers else None
                wait = float(retry_after) if retry_after and str(retry_after).isdigit() else (2 * (attempt + 1))
                logger.warning('rate limited path=%s retry_after=%s', path, retry_after)
                time.sleep(min(wait, 30) + random.uniform(0, 1))
                last_err = DramaWaveError('DRAMAWAVE_RATE_LIMITED', f'{path} 429')
                continue
            if exc.code == 404:
                raise DramaWaveError('DRAMAWAVE_SERIES_NOT_FOUND', path)
            if 500 <= exc.code < 600 and attempt < max_retries:
                time.sleep(2 * (attempt + 1) + random.uniform(0, 1))
                last_err = DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', f'{path} {exc.code}')
                continue
            raise DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', f'{path} HTTP {exc.code}')
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
            last_err = DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', f'{path} {type(exc).__name__}')
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1) + random.uniform(0, 1))
                continue
            break
    raise last_err or DramaWaveError('DRAMAWAVE_UPSTREAM_ERROR', path)
