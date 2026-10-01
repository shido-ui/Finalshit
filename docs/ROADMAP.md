# FocusForge Engineering Roadmap

1. Foundation — **implemented**. Android shell, Compose, Room/DataStore/WorkManager foundations, FastAPI gateway, CI and documentation.
2. Focus OS — **in progress**. Persistent focus-session state machine, Room-backed lifecycle, WorkManager expiry/recovery, usage-access detection and a real session UI are implemented. App blocking/enforcement is intentionally not faked; the next Focus OS work adds supported launcher/enforcement capabilities.
3. Knowledge Engine — **implemented**. PDF ingestion, rendering, robust cross-page question reconstruction, embedded visual asset extraction with persisted geometry/provenance, geometry-aware content-block and question↔asset association, canonical + AI-discovered taxonomy, AI-first question classification with deterministic quarantine fallback, structured question intelligence, filtered retrieval, and end-to-end persistence validation.
4. Solution Engine — **implemented**. Structured Solution objects, server-side grounded Gemini generation, source-page provenance, confidence/evidence gates, deterministic structural validation, persistent solutions, and solution retrieval/generation APIs.
5. Library + Practice — local Library, Fast Mode, question bank, tests, scoring and results.
6. Intelligence — mistake intelligence, weakness model, adaptive practice, SRS and Knowledge Graph foundations.
7. AI + Hard Mode — grounded Study Copilot and strongest supported Device Owner/Lock Task implementation.
8. Hardening — performance, battery, rendering, accessibility, security, regression benchmark, crash reduction and release readiness.

## Phase rule

Each phase is implemented in a focused pass, then checked for bugs and build/test regressions before moving to the next phase. A phase is not declared green while its validation is still running.
