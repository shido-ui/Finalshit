# FocusForge Privacy and Data Readiness

## Product model

FocusForge is a single-user, local-first study application. It does not require an account, social graph, user-to-user messaging, or multi-tenant storage.

## Local-first boundary

Personal study state is intended to remain on the user's Android device and local backend, including focus state, usage-derived analytics, library state, practice history, mistakes, adaptive state, and knowledge-graph state.

Imported documents and derived question/solution assets are runtime data and must not be committed to Git.

## AI boundary

Gemini credentials remain server-side. Android must never embed a Gemini API key. When an AI-backed feature is invoked, the backend may send the minimum source material required by the configured provider, then validates structured output and source citations before persistence/return.

## Telemetry boundary

The current single-user beta does not require a third-party analytics SDK. If telemetry is introduced later, it must not transmit API keys, document contents, question text, answers, solutions, notes, access tokens, or personal identifiers.

## Retention and deletion

Runtime data should remain locally deletable through the app/backend storage lifecycle. The single-user architecture must not introduce remote retention requirements.

## Release-readiness note

This is an engineering data-boundary document, not jurisdiction-specific legal advice. Before public distribution, review the final privacy notice, permissions, applicable Google Play requirements, and applicable local law.
