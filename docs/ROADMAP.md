# FocusForge Engineering Roadmap

1. Foundation — **implemented**. Android shell, Compose, Room/DataStore/WorkManager foundations, FastAPI gateway, CI and documentation.
2. Focus OS — **implemented**. Persistent focus-session state machine, Room-backed lifecycle, WorkManager expiry/recovery, usage-access detection, session UI, and supported device-owner lock-task enforcement.
3. Knowledge Engine — **implemented**. PDF ingestion, rendering, robust cross-page question reconstruction, embedded visual asset extraction with persisted geometry/provenance, geometry-aware content-block and question↔asset association, canonical + AI-discovered taxonomy, AI-first question classification with deterministic quarantine fallback, structured question intelligence, filtered retrieval, and end-to-end persistence validation.
4. Solution Engine — **implemented**. Structured Solution objects, server-side grounded Gemini generation, source-page provenance, confidence/evidence gates, deterministic structural validation, persistent solutions, and solution retrieval/generation APIs.
5. Library + Practice — **implemented**. Room-backed local Library with pin/archive/Fast Mode controls, backend library persistence, bounded Fast Mode/Test question-bank sessions, quarantine exclusion, deterministic selection, server-side scoring, submission lifecycle protection, and regression coverage.
6. Intelligence — **implemented**. Deterministic mistake capture, taxonomy-scoped weakness profiles, adaptive practice ranking, question-level spaced-repetition state, and persistent validated Knowledge Graph edges with API access and regression coverage.
7. AI Study Copilot — **implemented**. Grounded Study Copilot with source citations, provenance validation, server-side Gemini credentials, structured output validation, and Android/backend integration foundations.
8. Hard Mode — **implemented**. Device-owner setup and strongest supported lock-task enforcement.
9. Hardening — **implemented**. API security headers and request IDs, SQLite concurrency hardening, targeted query indexes, regression coverage, and successful backend/Android CI validation.
10. Performance & Polish (P11) — **implemented**. Hardened release shrinking/minification, configurable backend endpoint, HTTPS-by-default network policy with local-only cleartext allowance, Android 13+ back-navigation configuration, and accessibility resource labels. CI validates debug assembly and unit tests.
11. Beta (P12) — **next**. Controlled single-user JEE validation, benchmark fixtures, release validation checklist, crash/performance telemetry strategy, and privacy/legal readiness review without accounts or social features.
12. Scale Infrastructure (P13) — **conditional**. Only needed if actual usage requires moving the backend from phone/Termux to VPS/cloud; preserve the storage/API abstraction and add deployment/backup/monitoring infrastructure then.

## Master phase mapping

P0 Risk validation → P1 Foundation → P2 Focus Core → P3 Usage Analytics → P4 Knowledge Engine → P5 Solution Engine → P6 Library/Fast Mode/Tests → P7 Adaptive Intelligence → P8 Knowledge Graph → P9 AI Study Copilot → P10 Hard Mode → P11 Performance & Polish → P12 Beta → P13 Scale Infrastructure.

## Phase rule

Each phase is implemented in a focused pass, then checked for bugs and build/test regressions before moving to the next phase. A phase is not declared green while its validation is still running.
