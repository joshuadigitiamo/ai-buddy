---
gsd_state_version: "1.0"
current_phase: 02
current_phase_name: MCP Server and Skill
status: executing
stopped_at: Phase 2 context gathered
last_updated: "2026-11-06T20:42:35.067Z"
last_activity: 2026-11-03
last_activity_desc: Phase 01 complete, transitioned to Phase 2
state_head: f2364c51ef26fc9e8ac5e0becc853f05123bc106
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 18
  completed_plans: 11
  percent: 20
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-03)

**Core value:** An employee gets an answer only from official sources with the source cited, or an honest "non lo so, chiedi a ..." with the gap logged. Never an invented policy.
**Current focus:** Phase 1 — Content Sync

## Current Position

Phase: 02 (MCP Server and Skill) — READY TO EXECUTE
Plan: Not started
Status: Ready to execute
Last activity: 2026-11-03 — Phase 01 complete, transitioned to Phase 2

Progress: [██░░░░░░░░] 20%

## Performance Metrics

**Velocity:**
- Total plans completed: 11
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 11 | - | - |

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
| Phase 01 P07 | 25 min | 2 tasks | 6 files |
| Phase 1 P09 | 45 min | 3 tasks | 18 files |
| Phase 1 P10 | 2 min | 3 tasks | 10 files |

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
- [Phase 01]: 01-07: run_sync closes the previous artifact before building; only IndexVersionError counts it as absent (WARNING, full rebuild)
- [Phase 01]: 01-07: CLI maps OSError/sqlite3.Error/IndexFormatError to one ERROR line and exit 1; ValidationError names variables only, never values
- [Phase 01]: 01-07: guides_index_drift is checked only when Guides are rebuilt; list-pages prints denylisted pages with [denied] and redacted title
- [Phase 1]: Handbook citation is handbook://<page_id>, page_id = file stem (costly; no consumer yet)
- [Phase 1]: REDACT_PAGE_FILES holds bare file names and every entry must name an existing page file (fail closed)
- [Phase 1]: Handbook pages flat (parent_id null, depth 0) in file-name order; index.db schema stays 1.0.0
- [Phase 1]: Executor commits went to branch gsd/phase-01-content-sync because main is guard-protected; needs merge to main
- [Phase 1]: 01-10: revision_date_iso documented as full ISO-8601 UTC datetime (matches code); handbook format change recorded as 1.0.0 amendment (DDL unchanged, no artifact published)

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

Last session: 2026-11-06T19:47:40.627Z
Stopped at: Phase 2 context gathered
Resume file: .planning/phases/02-mcp-server-and-skill/02-CONTEXT.md
