"""Unit tests (upstream mocked). Production test hits the real API separately."""

import json
import urllib.error

import pytest
from fastapi.testclient import TestClient


def _app():
    from app.main import app
    return app


def test_health():
    client = TestClient(_app())
    r = client.get('/health')
    assert r.status_code == 200
    body = r.json()
    assert body['ok'] is True
    assert body['service'] == 'dramawave-api'
    assert body['guest_auth'] == {'configured': True}
    assert 'auth_key' not in json.dumps(body)
    assert 'auth_secret' not in json.dumps(body)


def test_request_signing():
    from app.dramawave.auth import GuestCredentials
    from app.dramawave.signing import sign_request

    header = sign_request(GuestCredentials(user_id=1, auth_key='K', auth_secret='S'))
    assert header.startswith('oauth_signature=')
    assert 'oauth_token=K' in header
    assert ',ts=' in header
    assert 'S' not in header.split('oauth_signature=')[1].split(',')[0]


def test_auth_refresh(monkeypatch):
    import app.dramawave.auth as auth_mod

    calls = {'n': 0}

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({'code': 200, 'data': {'user_id': 9, 'auth_key': 'AK', 'auth_secret': 'AS'}}).encode()

    def fake_urlopen(req, timeout=None):
        calls['n'] += 1
        return FakeResp()

    monkeypatch.setattr('app.dramawave.auth.urllib.request.urlopen', fake_urlopen)
    monkeypatch.setattr(auth_mod, '_cached', None)
    first = auth_mod.get_guest_credentials()
    second = auth_mod.get_guest_credentials()
    assert first.auth_key == 'AK' and second is first and calls['n'] == 1
    third = auth_mod.get_guest_credentials(force_refresh=True)
    assert third is not first and calls['n'] == 2


def _mock_api(monkeypatch, routes):
    import app.dramawave.client as client_mod

    LOGIN_OK = {'code': 200, 'data': {'user_id': 1, 'auth_key': 'AK', 'auth_secret': 'AS'}}

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if '/h5-api/anonymous/login' in url:
            return _FakeResp(LOGIN_OK)
        for prefix, payload in routes.items():
            if prefix in url:
                return _FakeResp(payload)
        raise urllib.error.HTTPError(url, 404, 'nf', {}, None)

    class _FakeResp:
        def __init__(self, payload): self._payload = payload
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(self._payload).encode()

    monkeypatch.setattr(client_mod.urllib.request, 'urlopen', fake_urlopen)


SEARCH_OK = {'code': 200, 'data': {'items': [
    {'id': 'S1', 'name': 'Dragon Tale', 'cover': 'c', 'episodeCount': 62}]}}
INFO_OK = {'code': 200, 'data': {'info': {
    'id': 'S1', 'name': 'Dragon Tale', 'desc': 'd', 'cover': 'c',
    'episodeCount': 62, 'original_audio_language': 'zh',
    'episode_list': [
        {'id': 'E1', 'name': 'Ep 1', 'duration': 67, 'episode_price': 0,
         'unlock': True, 'external_audio_h264_m3u8': 'https://cdn.example.com/e1.m3u8',
         'subtitle_list': []},
        {'id': 'E9', 'name': 'Ep 9', 'duration': 70, 'episode_price': 50,
         'unlock': False, 'subtitle_list': []},
    ]}}}


def test_search_schema(monkeypatch):
    _mock_api(monkeypatch, {'/h5-api/search/drama': SEARCH_OK})
    client = TestClient(_app())
    r = client.get('/v1/search', params={'q': 'dragon'})
    assert r.status_code == 200
    body = r.json()
    assert body['items'][0]['series_id'] == 'S1'
    assert body['items'][0]['episode_count'] == 62
    assert 'auth_key' not in json.dumps(body)


def test_series_schema(monkeypatch):
    _mock_api(monkeypatch, {'/h5-api/drama/info': INFO_OK})
    client = TestClient(_app())
    r = client.get('/v1/series/S1')
    assert r.status_code == 200
    body = r.json()
    assert body['series_id'] == 'S1' and body['episode_count'] == 62
    assert body['metadata']['original_audio_language'] == 'zh'


def test_episode_list_schema(monkeypatch):
    _mock_api(monkeypatch, {'/h5-api/drama/info': INFO_OK})
    client = TestClient(_app())
    r = client.get('/v1/series/S1/episodes')
    assert r.status_code == 200
    body = r.json()
    assert body['total'] == 2
    assert body['episodes'][0]['locked'] is False
    assert body['episodes'][1]['locked'] is True


def test_locked_episode(monkeypatch):
    _mock_api(monkeypatch, {'/h5-api/drama/info': INFO_OK})
    client = TestClient(_app())
    r = client.get('/v1/episodes/E9/playback', params={'series_id': 'S1'})
    assert r.status_code == 403
    assert r.json()['error']['code'] == 'DRAMAWAVE_EPISODE_LOCKED'


MASTER = ('#EXTM3U\n'
          '#EXT-X-STREAM-INF:BANDWIDTH=1956634,RESOLUTION=1080x1920,FRAME-RATE=25.000\nv1080.m3u8\n'
          '#EXT-X-STREAM-INF:BANDWIDTH=1356113,RESOLUTION=720x1280,FRAME-RATE=25.000\nv720.m3u8\n'
          '#EXT-X-STREAM-INF:BANDWIDTH=554814,RESOLUTION=480x854,FRAME-RATE=25.000\nv480.m3u8\n')


def test_playback_schema(monkeypatch):
    import app.dramawave.client as client_mod

    class FakeResp:
        def __init__(self, body: bytes): self._body = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self._body

    def dispatch(req, timeout=None):
        url = req.full_url
        if url.endswith('.m3u8') or '.m3u8' in url.split('?')[0]:
            return FakeResp(MASTER.encode())
        return FakeResp(json.dumps(INFO_OK).encode())

    monkeypatch.setattr(client_mod.urllib.request, 'urlopen', dispatch)
    client = TestClient(_app())
    r = client.get('/v1/episodes/E1/playback', params={'series_id': 'S1'})
    assert r.status_code == 200
    body = r.json()
    assert body['type'] == 'hls' and body['codec'] == 'h264'
    assert body['quality'] == '1080p'
    assert len(body['available_qualities']) == 3
    assert body['available_qualities'][0]['fps'] == 25.0
    assert body['url'].endswith('v1080.m3u8')


def test_quality_selection():
    from app.dramawave.playback import select_quality

    variants = [
        {'quality': '1080p', 'width': 1080, 'height': 1920, 'fps': 25.0, 'bandwidth': 3, 'url': 'a'},
        {'quality': '720p', 'width': 720, 'height': 1280, 'fps': 25.0, 'bandwidth': 2, 'url': 'b'},
        {'quality': '480p', 'width': 480, 'height': 854, 'fps': 25.0, 'bandwidth': 1, 'url': 'c'},
    ]
    assert select_quality(variants, 'best')['quality'] == '1080p'
    assert select_quality(variants, '720p')['quality'] == '720p'
    assert select_quality(variants, '480p')['quality'] == '480p'


def test_api_token_auth(monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod.settings, 'api_token', 'secret123')
    client = TestClient(_app())
    assert client.get('/health').status_code == 200
    assert client.get('/v1/search', params={'q': 'x'}).status_code == 401
    r = client.get('/v1/search', params={'q': 'x'}, headers={'Authorization': 'Bearer wrong'})
    assert r.status_code == 401
    monkeypatch.setattr(config_mod.settings, 'api_token', '')


def test_redacted_logging():
    from app.dramawave.client import redact_url

    assert redact_url('https://cdn.example.com/v/x.m3u8?sig=SECRET&exp=1') == 'https://cdn.example.com/v/x.m3u8'
    assert 'SECRET' not in redact_url('https://cdn.example.com/v/x.m3u8?sig=SECRET')


def test_audio_track_parsing():
    from app.dramawave.playback import parse_audio_tracks, select_audio_track

    master = ('#EXTM3U\n'
              '#EXT-X-MEDIA:TYPE=AUDIO,URI="en.m3u8",GROUP-ID="g",NAME="en-US",LANGUAGE="en-US",DEFAULT=NO,AUTOSELECT=YES,CHANNELS="2"\n'
              '#EXT-X-MEDIA:TYPE=AUDIO,URI="zh.m3u8",GROUP-ID="g",NAME="zh-CN",LANGUAGE="zh-CN",DEFAULT=NO,AUTOSELECT=NO,CHANNELS="2"\n')
    import app.dramawave.playback as pb_mod

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return master.encode()

    orig = pb_mod.urllib.request.urlopen
    pb_mod.urllib.request.urlopen = lambda req, timeout=None: FakeResp()
    try:
        tracks = parse_audio_tracks('https://cdn.example.com/master.m3u8')
    finally:
        pb_mod.urllib.request.urlopen = orig
    assert len(tracks) == 2
    assert select_audio_track(tracks)['language'] == 'zh-CN'
    assert select_audio_track([tracks[0]])['language'] == 'en-US'
