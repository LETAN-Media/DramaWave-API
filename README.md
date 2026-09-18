# DramaWave Resolver API

Stateless JSON API over the official DramaWave H5 endpoints. **API-only**:
no video download, no FFmpeg, no ASR, no translation, no TTS, no rendering,
no database. A separate processor fetches the returned `m3u8` and downloads.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | public | Liveness, no upstream call |
| GET | `/v1/search?q=...` | optional token | Series search |
| GET | `/v1/series/{series_id}` | optional token | Series metadata |
| GET | `/v1/series/{series_id}/episodes` | optional token | Episode list with `locked` flags |
| GET | `/v1/episodes/{episode_id}?series_id=...` | optional token | One episode |
| GET | `/v1/episodes/{episode_id}/playback?series_id=...&quality=best` | optional token | HLS/mp4 playback JSON |

Quality: `best` (default), `1080p`, `720p`, `480p`. If the target is missing,
the nearest quality at/below it is chosen.

Interactive docs: `/docs`, `/openapi.json`.

## Guest auth

Anonymous guest login happens automatically at runtime (in-memory only),
with transparent refresh on expiry. Nothing is hardcoded or committed.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set `API_TOKEN=` in `.env` to require `Authorization: Bearer <token>` on `/v1/*`.

## Deploy (Render)

Uses `render.yaml` (Docker web service, free plan). Set `API_TOKEN` manually
in the Render dashboard. Health check: `/health`.

## Tests

```bash
pytest -q
```

Unit tests mock upstream; the production test below hits the real API.
