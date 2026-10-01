# FocusForge v5 — Engineering Source of Truth

FocusForge is a single-user, local-first, AI-connected Android study environment.

## Architectural boundary
- Android app ↔ FocusForge backend/AI services.
- No user-to-user communication.
- Room is the primary local source of truth for personal study state.
- Gemini credentials remain server-side.
- Backend remains replaceable between phone-hosted Termux and future VPS/cloud hosting.

## v1 scope
Focus lockdown and scheduling, custom launcher, usage analytics, AI PDF/document ingestion, automatic chapter/topic organization, question/answer/solution/diagram/table extraction, solution generation and verification, local Library, Fast Mode, basic JEE-style tests, and local Focus Score/personal analytics.

## Phase rule
Implement one engineering phase at a time. Do not redesign unrelated systems. Add tests for new behavior and run relevant existing tests before declaring a phase complete.

The supplied Master Product & Engineering Specification v5 remains the detailed product authority.
