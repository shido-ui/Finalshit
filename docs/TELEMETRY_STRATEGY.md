# FocusForge Crash and Performance Telemetry Strategy

## Current beta policy

No third-party analytics or crash-reporting service is required for the single-user beta. First-line diagnostics are Android/Termux logs, backend structured logs, request IDs, local regression tests, and manual device validation.

## Privacy constraints

Telemetry must never include document contents, question text, answers, generated solutions, API keys, model prompts/responses, access tokens, or personal identifiers.

Allowed bounded operational categories include `app_start`, `backend_unreachable`, `ingestion_failed`, `ingestion_completed`, `practice_started`, `practice_completed`, `copilot_failed`, `focus_recovery`, and `hard_mode_unavailable`.

## Performance measurements

The beta process should measure cold app startup, backend health latency, representative PDF ingestion duration, extraction throughput, practice-session generation latency, Copilot latency when a real key is intentionally configured, memory/CPU behavior during large-document ingestion, and release APK size.

Measurements are diagnostic thresholds, not user-facing guarantees; device hardware and document complexity affect them.

## Future telemetry

Remote telemetry, if ever needed, is a separate engineering phase requiring a data inventory, retention policy, offline/failure behavior, documented user control, provider security review, and redaction tests. Do not add remote telemetry merely because the app is entering beta.
