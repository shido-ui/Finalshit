# FocusForge Engineering Roadmap — v5

This file follows the v5 master specification as the source of truth. The v5 plan contains P0–P13; older phase numbering is not authoritative.

## Current repository audit

The current main branch contains substantial backend Knowledge/Practice/Intelligence work and Android Focus Core/Hard Mode foundations, but the repository does not yet prove the v5 P0 hardware gate or complete every P0–P13 product requirement.

| Phase | v5 goal | Current repository status |
|---|---|---|
| P0 | Device Owner/Lock Task + real-PDF benchmark on physical hardware | **NOT PROVEN** — code exists, but no repository evidence proves physical-device validation or the required benchmark measurements |
| P1 | Android shell, AI gateway/backend, local DB, CI, retained Termux/tunnel path | **PARTIAL** — Android/Room/WorkManager, FastAPI/SQLite and CI exist; phone-hosted deployment remains documentation/infrastructure work |
| P2 | Launcher, schedules, Soft/Strong locking, recovery | **PARTIAL** — focus state machine, usage-access detection and Lock Task controller exist; scheduled sessions/custom launcher/recovery UX are incomplete |
| P3 | Usage collector, classification, dashboard, personal analytics | **PARTIAL** — UsageStats reader and permission flow exist; persistent collector, classification, dashboard and Focus Score are missing |
| P4 | Extraction, diagrams, taxonomy, provenance, resumable processing | **PARTIAL** — strong deterministic PDF/asset/provenance pipeline exists; the v5 Gemini structured extraction path and full local/offline Android integration are not complete |
| P5 | Generated solutions, validators, verification | **PARTIAL** — grounded structured solution generation and provenance gates exist; specialized Math/Physics/Chemistry validators from v5 are not fully implemented |
| P6 | Library, Fast Mode, basic Tests | **PARTIAL** — backend Library/Practice APIs and minimal Android Library controls exist; Android practice/test UI is missing on main |
| P7 | Weakness model, mistake intelligence, SRS | **IMPLEMENTED BACKEND / PARTIAL PRODUCT** — deterministic intelligence, adaptive ranking and review state exist server-side; Android presentation/integration is missing |
| P8 | Knowledge Graph | **IMPLEMENTED BACKEND / PARTIAL PRODUCT** — persistent validated edges and APIs exist; Android graph/retrieval UX is missing |
| P9 | Grounded AI Study Copilot | **IMPLEMENTED BACKEND / PARTIAL PRODUCT** — grounded provider and citation validation exist; Android integration is missing on main |
| P10 | Device Owner setup and strongest supported management | **PARTIAL** — Lock Task/device-owner controller exists; provisioning flow and physical-device acceptance gate are not proven |
| P11 | Performance, accessibility, rendering and premium UI | **NOT STARTED** |
| P12 | Controlled adult JEE-user beta | **NOT STARTED** |
| P13 | VPS/cloud scale migration if required | **NOT STARTED** |

## Engineering rule

Implement only one v5 phase at a time. Before changing a data model or architectural boundary, stop and document the required architecture change. Every phase must add tests for new behavior, run existing tests, and provide a phase exit checklist.

## Explicitly excluded

The v5 specification removes multi-account, friends, global leaderboards, cross-user synchronization, public score participation, social competition and account lifecycle requirements. Do not reintroduce them.

## Current integration note

A separate open pull request (phase-9-android-backend-integration) adds an Android/backend API boundary and PDF import flow. It is not part of main until reviewed and merged; its implementation must still be checked against the v5 offline-first, security and backend-configuration requirements.
