# FocusForge Engineering Roadmap

1. Foundation — **implemented**. Android shell, Compose, Room/DataStore/WorkManager foundations, FastAPI gateway, CI and documentation.
2. Focus OS — **in progress**. Persistent focus-session state machine, Room-backed lifecycle, WorkManager expiry/recovery, usage-access detection and a real session UI are implemented. App blocking/enforcement is intentionally not faked; the next Focus OS work adds supported launcher/enforcement capabilities.
3. Knowledge Engine — **implemented**. PDF ingestion, rendering, robust cross-page question reconstruction, embedded visual asset extraction with persisted geometry/provenance, geometry-aware content-block and question↔asset association, canonical + AI-discovered taxonomy, AI-first question classification with deterministic quarantine fallback, structured question intelligence, filtered retrieval, and end-to-end persistence validation.
4. Solution Engine — **implemented**. Structured Solution objects, server-side grounded Gemini generation, source-page provenance, confidence/evidence gates, deterministic structural validation, persistent solutions, and solution retrieval/generation APIs.
5. Library + Practice — **implemented**. Room-backed local Library with pin/archive/Fast Mode controls, backend library persistence, bounded Fast Mode/Test question-bank sessions, quarantine exclusion, deterministic selection, server-side scoring, submission lifecycle protection, and regression coverage.
6. Intelligence — **implemented**. Deterministic mistake capture, taxonomy-scoped weakness profiles, adaptive practice ranking, question-level spaced-repetition state, and persistent validated Knowledge Graph edges with API access and regression coverage.
7. AI + Hard Mode — **implemented**. Grounded Study Copilot with source citations and provenance validation, plus hardened device-owner focus enforcement.
8. Hardening — **implemented**. API security headers and request IDs, SQLite concurrency hardening, targeted query indexes, regression coverage, and successful backend/Android CI validation.

## Phase rule

Each phase is implemented in a focused pass, then checked for bugs and build/test regressions before moving to the next phase. A phase is not declared green while its validation is still running.
