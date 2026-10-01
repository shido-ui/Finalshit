# FocusForge Single-User Beta Release Checklist

This is the release gate for the current FocusForge v5 single-user product. It does not require accounts, social features, multi-user tenancy, or cloud scaling.

## Automated gates

- [ ] Backend tests pass.
- [ ] Backend lint/static checks pass.
- [ ] Android debug APK assembles.
- [ ] Android JVM unit tests pass.
- [ ] Android release APK assembles with shrinking/resource removal enabled.
- [ ] Release configuration contains no credentials.
- [ ] Beta benchmark fixture integrity tests pass.

## End-to-end single-user path

- [ ] App launches into the local-first Android shell.
- [ ] Local backend health check succeeds.
- [ ] A representative JEE PDF imports successfully.
- [ ] PDF page count and provenance persist.
- [ ] Cross-page questions reconstruct correctly.
- [ ] Embedded diagrams/tables/assets retain page and geometry provenance.
- [ ] Chapter/topic/taxonomy assignment persists.
- [ ] Low-confidence classification is quarantined.
- [ ] Taxonomy filtering retrieves the expected questions.
- [ ] Solutions are generated only through the server-side AI gateway.
- [ ] AI answers retain valid source-page citations.
- [ ] Invalid citations are rejected.
- [ ] Library pin/archive/Fast Mode state survives restart.
- [ ] Practice excludes quarantined questions.
- [ ] Practice scoring and submission lifecycle remain deterministic.
- [ ] Mistakes update weakness/adaptive state.
- [ ] Spaced-repetition state persists.
- [ ] Knowledge-graph edges pass validation.
- [ ] Focus sessions recover after restart/expiry.
- [ ] Usage-access absence does not crash the app.
- [ ] Supported device-owner Hard Mode enters/exits correctly.
- [ ] Unsupported Hard Mode setup does not pretend enforcement is active.
- [ ] Back navigation and accessibility labels behave correctly.

## AI and secrets

- [ ] `GEMINI_API_KEY` exists only in the backend runtime.
- [ ] No Gemini key exists in Android source, Gradle files, fixtures, docs, or newly created Git history.
- [ ] `.env.example` contains no real credential.
- [ ] AI tests use mocks/fixtures and do not require a live key.
- [ ] Provider failures are bounded and do not leak credentials/raw upstream payloads.

## Privacy/data handling

- [ ] Study data remains local unless an AI-backed operation is explicitly invoked.
- [ ] No account or social data collection is required.
- [ ] No third-party analytics SDK is required.
- [ ] Any future telemetry avoids document text, question text, answers, API keys, tokens, and personal identifiers.
- [ ] Imported documents and derived study data are excluded from source control.

## Manual device validation

1. Fresh install.
2. Grant required permissions.
3. Configure the local backend.
4. Import a representative JEE PDF.
5. Complete ingestion → library → practice → mistake → adaptive flow.
6. Start and finish a focus session.
7. Restart app and backend.
8. Re-open the same study state.
9. Exercise grounded Copilot with source pages.
10. Verify Hard Mode only after real device-owner provisioning.
11. Install and launch the release APK.

CI proves reproducible build/test gates; it does not replace physical-device validation.
