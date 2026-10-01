# FocusForge AI Gateway

Server-side AI gateway for the FocusForge Android app.

## Local setup

Use Python 3.12:

    python -m venv .venv
    . .venv/bin/activate
    pip install -e ".[dev]"

Copy `.env.example` to `.env` and set GEMINI_API_KEY locally. Never place the key in Android source, Gradle files, Git history, or client-visible configuration.

Run:

    uvicorn app.main:app --reload

Health endpoint: GET /health

## Phase 12 — Study Copilot

The Study Copilot endpoint is:

    POST /api/v1/knowledge/documents/{document_id}/copilot

The backend reads the Gemini credential only from GEMINI_API_KEY, sends only the selected source-page text, requires structured JSON, and validates returned citations against the supplied page provenance.

The default model is gemini-3.8-flash; override it with GEMINI_COPILOT_MODEL when required.

Gemini credentials remain server-side by design.
