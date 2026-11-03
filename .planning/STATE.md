---
gsd_state_version: "1.0"
current_phase: 01
current_phase_name: Content Sync
status: executing
stopped_at: Completed 01-06-PLAN.md
last_updated: "2026-11-03T19:40:03.995Z"
last_activity: 2026-11-03
last_activity_desc: Phase 01 execution started
state_head: 09d6772587d99b79a1358a9c5fdee08c0b46c1be
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 8
  completed_plans: 6
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-03)

**Core value:** An employee gets an answer only from official sources with the source cited, or an honest "non lo so, chiedi a ..." with the gap logged. Never an invented policy.
**Current focus:** Phase 01 — Content Sync

## Current Position

Phase: 01 (Content Sync) — EXECUTING
Plan: 7 of 8
Status: Ready to execute
Last activity: 2026-11-03 — Phase 01 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 25 min | 3 tasks | 17 files |
| Phase 01 P02 | 5 min | 3 tasks | 13 files |
| Phase 01 P03 | 5 min | 3 tasks | 5 files |
| Phase 01 P04 | 4 min | 3 tasks | 6 files |
| Phase 01 P05 | 6 min | 3 tasks | 11 files |
| Phase 01 P06 | 4 min | 3 tasks | 9 files |

## Accumulated Context

### Decisions

Full log in PROJECT.md Key Decisions (`<decisions>` block, D1-D16 locked).
Recent decisions affecting current work:

- [Init]: D1a — Meridian + Joshua's Max only for personal dev; guards: Chat app visible to Joshua, `ALLOWED_USERS`, `LLM_BACKEND` meridian|api
- [Init]: D14 — Test handbook `xkwgt-39975` (id via env); official `xkwgt-22915` not used in Milestone 1
- [Init]: D16 — every phase plan cites applied Guides sections and justifies exceptions
- [Init]: Foundation (repo skeleton, `run-unit-tests.sh`, tooling) moved from Phase 4 to Phase 1 so Phases 1-3 can be verified in Docker
- [Init]: Golden set drafted by Claude from test doc + Guides (incl. no-answer and sensitive cases), reviewed by Joshua
- [Phase 01]: Dependency pins: user chose latest versions; verified latest on PyPI 2026-11-03 (ten direct packages, pinned with ==)
- [Phase 01]: ruff extend-exclude .planning and docs: ruff 0.17 formats Python code blocks in Markdown
- [Phase 01]: 01-02: search queries built only via to_match_query (quoted tokens, NUL as separator, bound MATCH parameter); chunk_key is heading-based (changing it needs a schema major bump plus re-sync)
- [Phase 01]: 01-02: only the latest artifact is kept in ARTIFACT_DIR; versioned = schema_version + build_id + manifest. ArtifactStore port with LocalDirArtifactStore; bucket vs baked image deferred to Phase 4 (D-12, ADR 0001)
- [Phase 01]: 01-03: IBAN rule retries shorter heads when an uppercase word is swallowed; signed_url_query keeps fragment; entropy rule skips URLs via one alternation
- [Phase 01]: 01-03: non-company e-mails masked by default; allow-listing calendar/reply-to domains deferred to plan 08
- [Phase 01]: Plan 01-04: a page is processed when new, versions_match is False, date_edited differs, or the redacted-text hash differs; unchanged pages keep the previous row with current position, depth and parent
- [Phase 01]: Plan 01-04: ClickUp response is streamed and capped at MAX_RESPONSE_BYTES; transport errors are not retried and report the exception type only
- [Phase 01]: 01-05: chunk keys always derive from redacted headings via public assign_chunk_keys; GUIDES_INDEX.md table format is the costly cross-repo contract (File | Level | Section | Line)
- [Phase 01]: 01-05: GitGuidesSource attaches the token only as an http.extraHeader in GIT_CONFIG env for https urls; destructive git requires the .buddy-sync-checkout marker
- [Phase 01]: resolve_video_links fails on a duplicate README row or a guide mapped by two sections.yaml files, and needs the chunks of every mapped guide — Silent override is the drift D-02 forbids; guide must be an indexed file (T-01-26)
- [Phase 01]: Only a dash in the README video cell means no video; an empty or malformed cell raises VideoMapError — Format drift guard for the cross-repo README table contract

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] How synced data reaches the MCP container (image rebuild vs bucket read): decide in Phase 1 plan (SYNC-07)
- [Phase 1] Per-scene video clips: source is the Guides README (full-video URLs); scene-clip URLs may not exist yet, fall back to full video
- [Phase 1] ClickUp read-only API token needed (Admin ClickUp)
- [Phase 2] Bot-to-MCP authentication mechanism is not defined in the source; decide in Phase 2 plan
- [Phase 4] GCP project + active billing account needed for live Cloud Run deploy and Workload Identity Federation (Admin Google); region europe-west8 still "da confermare" (D7)
- [Phase 4] Cost of chat_bot service, Pub/Sub, CI and kind is not covered by research 07; ~0 EUR/month holds for the MCP server only
- [Later] Videos must move to Google Drive before any non-dev user (D15); `LLM_BACKEND` must move to API key before any second user (D1a)
- [Later] Open: real team chat channel, Team license budget, CCNL, official handbook owner, which Guides go company-wide, formal data-sovereignty constraint

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-11-03T19:40:03.959Z
Stopped at: Completed 01-06-PLAN.md
Resume file: None
