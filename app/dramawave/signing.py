"""Request signing (oauth_signature header). Kept in one place."""

from __future__ import annotations

import hashlib
import time

from app.dramawave.auth import GuestCredentials


def sign_request(creds: GuestCredentials) -> str:
    """Build the `authorization` header value for one request."""
    ts = int(time.time() * 1000)
    sig = hashlib.md5(
        f'8IAcbWyCsVhYv82S2eofRqK1DF3nNDAv&{creds.auth_secret}'.encode()
    ).hexdigest()
    return f'oauth_signature={sig},oauth_token={creds.auth_key},ts={ts}'
