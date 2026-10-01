# FocusForge Single-User Release Setup

## 1. API key location

For the local phone/Termux deployment, put the Gemini key in:

    backend/.env

Example:

    GEMINI_API_KEY=YOUR_NEW_GEMINI_KEY
    GEMINI_COPILOT_MODEL=gemini-3.8-flash

The repository ignores .env, so this file must remain local.

## 2. Create the file in Termux

From the FocusForge repository root:

    cd backend
    nano .env

Paste the two environment lines, save, and exit.

Never paste the key into Android/Kotlin source, Gradle files, BuildConfig, AndroidManifest.xml, .env.example, GitHub source files, GitHub Issues/PRs, the APK, screenshots, or logs.

## 3. Start the backend

From backend/:

    python -m venv .venv
    . .venv/bin/activate
    pip install -e ".[dev]"
    uvicorn app.main:app --host 0.0.0.0 --port 8080

FocusForge loads backend/.env automatically before the AI providers initialize.

## 4. Android backend address

The Android release build defaults to:

    http://localhost:8080

If the backend is moved to another machine on the local network, configure the APK with:

    -Pfocusforge.backendUrl=http://DEVICE_OR_HOST:8080

or:

    FOCUSFORGE_BACKEND_URL=http://DEVICE_OR_HOST:8080

Do not put the Gemini key in this URL or in Android configuration.

## 5. Verify the backend without exposing the key

Check:

    curl http://127.0.0.1:8080/health

Expected:

    {"status":"ok","service":"focusforge-backend"}

Then test an AI-backed operation from the app. A missing key should produce a bounded configuration error; the key itself should never be returned.

## 6. API-key safety

The key previously shared in chat should not be reused. Revoke/rotate it in the Google AI/Gemini credential management interface and use the newly generated key only in backend/.env.

If a key is ever accidentally committed or exposed, rotate it immediately. Removing the file in a later commit does not make an exposed credential safe.

## 7. Final release order

1. Rotate/create a fresh Gemini key.
2. Put it only in backend/.env.
3. Start the backend.
4. Confirm /health.
5. Install the signed release APK.
6. Configure/verify the backend endpoint.
7. Import a real JEE PDF.
8. Exercise ingestion, Library, Practice, Intelligence, and Copilot.
9. Confirm AI citations are grounded in the selected pages.
10. Restart the app/backend and verify persisted state.
11. Keep backend/.env out of Git.
12. Keep the key out of logs and screenshots.

## Important

CI does not need the personal Gemini key for the current test suite. AI tests use mocks/fixtures. Do not add the personal key as source code or as a test fixture.

This is a single-user local-first deployment. P13 cloud scaling is not required unless the backend is intentionally moved to VPS/cloud infrastructure.