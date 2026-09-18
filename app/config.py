"""DramaWave resolver API configuration (env only, no secrets in code)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'dramawave-api'
    version: str = '0.1.0'
    environment: str = 'production'
    log_level: str = 'INFO'

    api_token: str | None = None

    dramawave_api_base: str = 'https://api.mydramawave.com'
    dramawave_timeout: int = 20
    dramawave_max_retries: int = 2

    provider_priority: str = 'dramawave,netshort,dramabox,shortflix'
    series_match_threshold: float = 0.82

    cache_search_ttl: int = 300
    cache_series_ttl: int = 1800
    cache_episodes_ttl: int = 1800
    cache_playback_ttl: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
