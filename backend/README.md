# FocusForge AI Gateway

The backend is the only component that talks to Gemini. Never put a Gemini API key in the Android application.

Run locally with Python 3.12:

    pip install -e ".[dev]"
    uvicorn app.main:app --reload

Health endpoint: GET /health

## Gemini configuration

Copy `backend/.env.example` to a private environment configuration or export the variables in the shell running Uvicorn.

Required for live AI features:

    GEMINI_API_KEY=<your server-side key>

Optional model overrides:

    GEMINI_COPILOT_MODEL=gemini-3-flash
    GEMINI_SOLUTION_MODEL=gemini-3-flash
    GEMINI_QUESTION_CLASSIFICATION_MODEL=gemini-3-flash
    GEMINI_QUESTION_INTELLIGENCE_MODEL=gemini-3-flash
    GEMINI_TAXONOMY_MODEL=gemini-3-flash

Do not commit the real key, place it in the Android project, or send it from Android requests. Without the key, AI endpoints fail safely with a configuration response while deterministic features remain available.
