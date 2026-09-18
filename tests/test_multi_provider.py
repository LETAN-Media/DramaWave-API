"""Tests for multi-provider architecture."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.providers.dramawave.provider import DramaWaveProvider
from app.services.canonical import (
    CanonicalStore,
    SeriesProviderMapping,
    _store,
    alias_variants,
    get_store,
    normalize_title,
    score_match,
    search_all,
)
from app.providers.base import ProviderEpisode, ProviderSeries


def test_normalize_title():
    assert normalize_title('Dragon Tale') == 'dragon tale'
    assert normalize_title('Dragon Tale: Season 1') == 'dragon tale'
    assert normalize_title('Alpha Mated To Enemy') == 'alpha mated to enemy'
    assert normalize_title('ENG DUBBED') == 'eng'
    assert normalize_title('') == ''


def test_alias_variants():
    variants = alias_variants('Dragon Tale')
    assert 'Dragon Tale' in variants
    assert 'dragon tale' in variants


def test_score_match():
    a = ProviderSeries(provider='a', provider_series_id='1', title='Dragon Tale', aliases=['dragon tale'], episode_count=60)
    b = ProviderSeries(provider='b', provider_series_id='2', title='Dragon Tale', aliases=['dragon tale'], episode_count=60)
    score = score_match(a, b)
    assert score > 0.8


def test_score_match_low():
    a = ProviderSeries(provider='a', provider_series_id='1', title='Dragon Tale', episode_count=60)
    b = ProviderSeries(provider='b', provider_series_id='2', title='Completely Different', episode_count=10)
    score = score_match(a, b)
    assert score < 0.5


def test_canonical_store_upsert():
    store = CanonicalStore()
    m = SeriesProviderMapping(canonical_series_id='cw:test', provider='dw', provider_series_id='S1', provider_title='Test', episode_count=10)
    store.upsert_mapping(m)
    assert len(store.get_mappings('cw:test')) == 1
    m2 = SeriesProviderMapping(canonical_series_id='cw:test', provider='ns', provider_series_id='S2', provider_title='Test', episode_count=10)
    store.upsert_mapping(m2)
    assert len(store.get_mappings('cw:test')) == 2


def test_canonical_store_episode_sources():
    store = CanonicalStore()
    from app.models.provider import EpisodeSource
    s1 = EpisodeSource(canonical_series_id='cw:test', episode_number=1, provider='dw', provider_series_id='S1', provider_episode_id='E1', locked=True, free=False, playback_available=False)
    s2 = EpisodeSource(canonical_series_id='cw:test', episode_number=1, provider='ns', provider_series_id='S2', provider_episode_id='E1', locked=False, free=True, playback_available=True)
    store.update_episode_sources('cw:test', [s1, s2])
    sources = store.get_episode_sources('cw:test', 1)
    assert len(sources) == 2
    assert any(s.free and s.playback_available for s in sources)


def test_provider_registry():
    from app.providers.registry import all_providers, get, ordered_names, register
    register(DramaWaveProvider())
    names = ordered_names()
    assert 'dramawave' in names


def test_dramawave_provider_capabilities():
    p = DramaWaveProvider()
    assert p.capabilities['search'] is True
    assert p.capabilities['playback'] is True


def test_stub_providers_not_implemented():
    from app.providers.netshort.provider import NetShortProvider
    from app.providers.shortflix.provider import ShortFlixProvider
    for cls in [ShortFlixProvider]:
        p = cls()
        assert p.capabilities['search'] is False
        assert p.capabilities['playback'] is False
    p = NetShortProvider()
    assert p.capabilities['search'] is True
    assert p.capabilities['series'] is True
    assert p.capabilities['episodes'] is False
    assert p.capabilities['playback'] is False


def test_health_tracking():
    from app.providers.base import ProviderHealth
    h = ProviderHealth()
    assert h.average_latency == 0.0
    h.record_success(0.5)
    assert h.success_count == 1
    h.record_failure('err')
    assert h.failure_count == 1
    assert h.consecutive_failures == 1


def _app():
    from app.main import app
    import app.config as config_mod
    config_mod.settings.api_token = ''
    return app


def test_providers_status_endpoint():
    client = TestClient(_app())
    r = client.get('/v1/providers')
    print(r.json())
    assert r.status_code == 200
    body = r.json()
    assert 'providers' in body
    names = [p['provider'] for p in body['providers']]
    assert 'dramawave' in names


def test_provider_capabilities_in_status():
    client = TestClient(_app())
    r = client.get('/v1/providers/status')
    print(r.json())
    assert r.status_code == 200
    dw = next(p for p in r.json()['providers'] if p['provider'] == 'dramawave')
    assert dw['capabilities']['search'] is True
    assert dw['capabilities']['playback'] is True


def test_search_all_endpoint(monkeypatch):
    client = TestClient(_app())
    import app.dramawave.client as client_mod

    SEARCH_OK = {'code': 200, 'data': {'items': [
        {'id': 'S1', 'name': 'Dragon Tale', 'cover': 'c', 'episodeCount': 62}]}}

    class FakeResp:
        def __init__(self, payload): self._payload = payload
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(self._payload).encode()

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if '/h5-api/anonymous/login' in url:
            return FakeResp({'code': 200, 'data': {'user_id': 1, 'auth_key': 'AK', 'auth_secret': 'AS'}})
        if '/h5-api/search/drama' in url:
            return FakeResp(SEARCH_OK)
        raise Exception(f'unexpected {url}')

    monkeypatch.setattr(client_mod.urllib.request, 'urlopen', fake_urlopen)
    r = client.get('/v1/search-all', params={'q': 'dragon'})
    print(r.json())
    assert r.status_code == 200
    body = r.json()
    assert 'items' in body
    assert body['query'] == 'dragon'


def test_legacy_search_still_works(monkeypatch):
    client = TestClient(_app())
    import app.dramawave.client as client_mod

    SEARCH_OK = {'code': 200, 'data': {'items': [
        {'id': 'S1', 'name': 'Dragon Tale', 'cover': 'c', 'episodeCount': 62}]}}

    class FakeResp:
        def __init__(self, payload): self._payload = payload
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(self._payload).encode()

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if '/h5-api/anonymous/login' in url:
            return FakeResp({'code': 200, 'data': {'user_id': 1, 'auth_key': 'AK', 'auth_secret': 'AS'}})
        if '/h5-api/search/drama' in url:
            return FakeResp(SEARCH_OK)
        raise Exception(f'unexpected {url}')

    monkeypatch.setattr(client_mod.urllib.request, 'urlopen', fake_urlopen)
    r = client.get('/v1/search', params={'q': 'dragon'})
    print(r.json())
    assert r.status_code == 200
    body = r.json()
    assert body['items'][0]['series_id'] == 'S1'


def test_providers_status_has_capabilities():
    client = TestClient(_app())
    r = client.get('/v1/providers/status')
    print(r.json())
    assert r.status_code == 200
    body = r.json()
    for p in body['providers']:
        assert 'capabilities' in p
        assert 'provider' in p
        assert 'latency' in p
