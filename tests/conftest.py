"""pytest configuration."""

import pytest


@pytest.fixture(autouse=True)
def _clear_api_token():
    import app.config as config_mod
    original = getattr(config_mod.settings, 'api_token', '')
    config_mod.settings.api_token = ''
    try:
        yield
    finally:
        config_mod.settings.api_token = original
