# FocusForge

FocusForge is a single-user, local-first Android study environment with a FastAPI knowledge backend.

## Architecture

- Android/Jetpack Compose: focus sessions, library, practice UI and device enforcement.
- FastAPI: PDF ingestion, question extraction, taxonomy, solutions, practice and intelligence.
- SQLite: local backend knowledge store.
- Gemini: optional AI enrichment; deterministic fallbacks keep ingestion usable without AI.

## Backend setup

From the repository root:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-3-flash"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend defaults to an absolute repository-local `data/` directory, so changing the uvicorn working directory does not silently create a second database. Set `FOCUSFORGE_DATA_DIR` to override it.

### LAN access

The backend is localhost-only by default. If it must be reachable from another device, set `FOCUSFORGE_API_TOKEN` and send:

```
Authorization: Bearer <token>
```

Do not expose the backend on a LAN without authentication.

## PDF ingestion

PDF upload creates a processing job and returns immediately. Poll:

```
GET /api/v1/knowledge/jobs/{job_id}
```

Job states include queued, extracting, ready and failed. AI enrichment uses bounded concurrency and retries transient Gemini failures with exponential backoff.

## Ground truth

Answer-key pages are parsed when they contain conventional numbered answer mappings. A question can also be corrected manually:

```
PATCH /api/v1/knowledge/questions/{question_id}/answer
Content-Type: application/json

{"answer":"B"}
```

Manual answers are treated as grading ground truth.

## Practice

Practice excludes archived documents and respects per-document Fast Mode. Questions without known answers are excluded rather than recorded as incorrect outcomes.

## Security

- Keep the backend bound to `127.0.0.1` for same-device Android + Termux use.
- Never commit Gemini API keys.
- Configure `FOCUSFORGE_API_TOKEN` for LAN deployment.
- Backend API routes reject non-loopback requests when no token is configured.

## Development

Run the backend tests from `backend/`:

```bash
pytest
ruff check .
```

Android release builds should be tested on a physical device before distribution.
