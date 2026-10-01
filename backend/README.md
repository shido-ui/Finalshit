# FocusForge AI Gateway

Phase 1 provides the backend boundary only. AI credentials and document-processing implementation are intentionally deferred to later phases.

Run locally with a Python 3.12 environment:

    pip install -e ".[dev]"
    uvicorn app.main:app --reload

Health endpoint: GET /health
