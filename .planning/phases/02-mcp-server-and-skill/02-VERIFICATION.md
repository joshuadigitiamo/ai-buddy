---
phase: 02-mcp-server-and-skill
verified: 2026-11-06T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .planning/phases/02-mcp-server-and-skill/02-01-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-01-SUMMARY.md
  - .planning/phases/02-mcp-server-and-skill/02-02-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-02-SUMMARY.md
  - .planning/phases/02-mcp-server-and-skill/02-03-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-03-SUMMARY.md
  - .planning/phases/02-mcp-server-and-skill/02-04-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-04-SUMMARY.md
  - .planning/phases/02-mcp-server-and-skill/02-05-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-05-SUMMARY.md
  - .planning/phases/02-mcp-server-and-skill/02-06-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-06-SUMMARY.md
  - .planning/phases/02-mcp-server-and-skill/02-07-PLAN.md
  - .planning/phases/02-mcp-server-and-skill/02-07-SUMMARY.md
  - docs/install-guide.md
  - services/mcp_server/buddy_mcp/auth.py
  - services/mcp_server/buddy_mcp/cli.py
  - services/mcp_server/buddy_mcp/config.py
  - services/mcp_server/buddy_mcp/gap_tool.py
  - services/mcp_server/buddy_mcp/gaplog.py
  - services/mcp_server/buddy_mcp/guides_tools.py
  - services/mcp_server/buddy_mcp/handbook_tools.py
  - services/mcp_server/buddy_mcp/models.py
  - services/mcp_server/buddy_mcp/oauth_storage.py
  - services/mcp_server/buddy_mcp/server.py
  - services/mcp_server/buddy_mcp/snapshot.py
  - services/mcp_server/buddy_mcp/stemming.py
  - skills/digitiamo-buddy/SKILL.md
covered_digest: "v4:sha256:574b73a058bed7841a29939940e82eb1160131048e312e47662ba620a5898be9"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "claude.ai custom connector can connect to the server (live)"
    addressed_in: "Phase 4"
    evidence: "Recorded in STATE.md blockers/todos; needs a claude.ai org owner and a hosted server URL (Phase 4 infrastructure)"
  - truth: "A non-digitiamo Google account is rejected on the live OAuth flow"
    addressed_in: "Phase 4"
    evidence: "Recorded in STATE.md; unit-tested at verifier level, live rejection not yet exercised"
  - truth: "Skill digitiamo-buddy makes a live model follow the answer format, refusal and escalation rules"
    addressed_in: "Phase 5"
    evidence: "Phase 5 EVAL-03 (user-confirmed scheduling)"
human_verification:
  - test: "Add the server as a custom connector in claude.ai (org owner) and ask a handbook question"
    expected: "Connector authorizes with Google, the 5 tools are listed, answer carries Fonte and Data di revisione"
    why_human: "Needs a claude.ai org owner and a hosted URL; not reachable from the test environment. Deferred to Phase 4 by user decision (MCP-07 marked complete 2026-11-06)."
  - test: "Log in through the live OAuth flow with a non-@digitiamo.com Google account"
    expected: "Login/token is rejected; no tool call succeeds"
    why_human: "Needs a real external Google account against the live consent screen. Domain check is unit-tested (DomainRestrictedGoogleVerifier); the live path is untested. Deferred to Phase 4."
  - test: "Install the Skill and ask handbook, Guides, no-answer and sensitive (illness, pay) questions with a live model"
    expected: "Italian answer template with source and date; 'Non lo so, chiedi a ...' plus one buddy_report_gap on no answer; at most the general rule plus HR referral on sensitive topics"
    why_human: "Model behaviour cannot be checked by grep. Only mechanical file checks exist (test_skill_package.py). Scheduled for Phase 5 EVAL-03."
---

# Phase 2: MCP Server and Skill Verification Report

**Phase Goal:** Any MCP client can ask the synced handbook and Guides for answers through five cited tools over stateless HTTP, and Claude knows how to use them via the Skill.
**Verified:** 2026-11-06
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Client over streamable-http (stateless, JSON, no held-open stream) lists exactly five tools and the `handbook://{pagina}` resource | VERIFIED | `server.py:build_app` calls `mcp.http_app(stateless_http=True, json_response=True, ...)` with Host/Origin guard. `models.TOOL_NAMES` holds the five names; tools are registered in `guides_tools.py`, `handbook_tools.py`, `gap_tool.py`; resource `@mcp.resource("handbook://{pagina}")` at `handbook_tools.py:126`. Tests: `test_http_transport.py`, `test_tool_surface.py`, `test_handbook_resource.py` pass in the full run. |
| 2 | Every tool result carries source URL and revision date, plus `video_url` for mapped Guides sections; a test fails if output lacks a source | VERIFIED | Pydantic models require `source_url` and `revision_date` (`min_length=1`) and force `revision_kind` into the advertised schema (`models.py`). `guides_tools.py` builds a pinned GitHub permalink and `video_link`; `handbook_tools.py` sets `source_url=page_uri(...)` and `revision_date`. Contract test `test_source_fields.py` passes. Handbook source is a `handbook://` URI, a Phase 1 citation design. |
| 3 | No match returns explicit "no results"; `buddy_report_gap` writes a Firestore doc with question, timestamp, marker and no user id (emulator) | VERIFIED | `status="ok" if results else "no_results"` in all four read tools; `test_no_results.py` passes. `gaplog.gap_document` writes exactly six keys (question, marker, created_at, expire_at, build_id, tried); `gap_tool.py` never reads the token or request context. `./run-unit-tests.sh --emulator` re-run by me: 4 passed. `tests/integration/test_firestore_gaplog.py` asserts the key set, marker, and that no key matches an identity pattern. |
| 4 | With auth on, requests without a valid `@digitiamo.com` Google identity are rejected; tools are read-only; rate limit refuses excess | VERIFIED | `auth.py`: `DomainRestrictedGoogleVerifier` requires verified email, exact domain match, and `hd` consistency (the `hd` authorize param is only a hint, and the check is the real boundary). Bot service-account ID tokens via allowlisted `ServiceAccountIdTokenVerifier` joined through `MultiAuth`. `config.py` refuses `AUTH_MODE=off` when `K_SERVICE` is set and requires OAuth settings when on. Read tools use `READ_ONLY` annotations; only `buddy_report_gap` is non-read-only, and it only appends. `RateLimitingMiddleware` is keyed by `caller_identity`. Tests `test_auth.py`, `test_auth_mode.py`, `test_read_only.py`, `test_rate_limit.py` pass. Live OAuth verified by the user end to end (DCR, consent, Google Internal login, token, 5 tools). Live rejection of an external account is deferred (see Human Verification). |
| 5 | `digitiamo-buddy` Skill states when to use each tool, answer format, escalation topics with referral contacts, and ships with a one-page install guide | VERIFIED (content) | `skills/digitiamo-buddy/SKILL.md` (96 lines) has "When to use", "Tools" (all five plus the resource), the Italian-English keyword bridge, an answer template (Risposta / Fonte / Referente / Data di revisione / Video), a no-answer rule, and the "Temi da escalare" table with roles and a "Finding the referente" rule (no contacts from memory). `docs/install-guide.md` (38 lines) covers claude.ai, Claude Desktop and Claude Code. `test_skill_package.py` checks front matter, description length, tool coverage and the escalation table. Live behaviour is not verified here (see Human Verification). |

**Score:** 5/5 truths verified. `behavior_unverified` is 0 because none of the five roadmap truths asserts a model-runtime behaviour. Skill live behaviour sits in the human items.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | claude.ai connector live check | Phase 4 | STATE.md blockers; needs an org owner and a hosted URL |
| 2 | Non-digitiamo account rejection, live | Phase 4 | STATE.md blockers |
| 3 | Skill behaviour with a live model | Phase 5 | EVAL-03 (user-confirmed) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `services/mcp_server/buddy_mcp/server.py` | Stateless JSON app, five-tool composition, rate limit | VERIFIED | 91 lines, wired through `build_server` and `build_app` |
| `.../guides_tools.py`, `handbook_tools.py`, `gap_tool.py` | Tool groups and resource | VERIFIED | Substantive, registered in `build_server` |
| `.../gaplog.py` | Port, Firestore adapter, in-memory double | VERIFIED | Lazy client, identity-free document |
| `.../auth.py`, `oauth_storage.py`, `config.py` | Domain-restricted OAuth, bot verifier, guard, Fernet store | VERIFIED | Wired in `cli.py` and `build_auth`; tests pass, emulator test for the OAuth store passes |
| `.../models.py`, `snapshot.py`, `stemming.py` | D-06 contract, index snapshot, Italian stemming | VERIFIED | Used by the tools |
| `skills/digitiamo-buddy/SKILL.md` | Skill | VERIFIED | See truth 5 |
| `docs/install-guide.md` | One-page install guide | VERIFIED | 38 lines |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `server.build_server` | tool groups | `register_*` calls | WIRED | All three groups registered, gap tool gets `build_id` from the snapshot |
| `server.build_server` | rate limiter | `RateLimitingMiddleware(get_client_id=caller_identity)` | WIRED | Per-identity key from the access token |
| `build_auth` | `FastMCP(auth=...)` | `build_server(auth=...)` | WIRED | `AUTH_MODE=off` returns `None`, with a warning |
| `gap_tool` | `GapLog` port | `gaplog.record` | WIRED | Real Firestore proven on the emulator |
| Skill | tool names | text in SKILL.md | WIRED | Names match `models.TOOL_NAMES`, mechanically tested |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `guides_search` / `guides_get_section` | results | `IndexSnapshot` over `index.db` from Phase 1 | Yes (fixture index in tests; live user run on real data) | FLOWING |
| `handbook_search` / `handbook_get` | results | In-memory FTS over the snapshot pages | Yes | FLOWING |
| `buddy_report_gap` | gap id | Firestore `document().set()` | Yes (emulator) | FLOWING |

### Behavioral Spot-Checks and Test Evidence

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite, lint, types, coverage gate | `./run-unit-tests.sh --all` (Docker, run by me) | 604 passed, 18 skipped (all `local-only` env-gated), exit 0 | PASS |
| Firestore emulator integration (gap log, OAuth store, server process) | `./run-unit-tests.sh --emulator` (run by me) | 4 passed | PASS |

### Probe Execution

Step 7c: SKIPPED (the phase declares no `probe-*.sh` scripts).

### Requirements Coverage

All eight IDs are claimed by at least one PLAN `requirements:` field, and all are `[x]` / "Complete" in REQUIREMENTS.md. No orphaned requirement for Phase 2.

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| MCP-01 | 02-01, 02-03, 02-05, 02-07 | Stateless streamable-http, JSON, no state on container FS | SATISFIED | `build_app`; Firestore OAuth store (`oauth_storage.py`), `storage` always handed to the proxy |
| MCP-02 | 02-01, 02-02, 02-04 | Exactly five namespaced tools | SATISFIED | `test_tool_surface.py` |
| MCP-03 | 02-01, 02-02, 02-04 | Source URL, revision date, `video_url` | SATISFIED | models plus `test_source_fields.py` |
| MCP-04 | 02-01, 02-02, 02-04 | Explicit no-results | SATISFIED | `test_no_results.py` |
| MCP-05 | 02-03, 02-07 | Gap written to Firestore, no user id, emulator | SATISFIED | emulator test re-run: 4 passed |
| MCP-06 | 02-02 | `handbook://{pagina}` resource | SATISFIED | `handbook_tools.py:126`, `test_handbook_resource.py` |
| MCP-07 | 02-03, 02-05, 02-07 | Google OAuth restricted to `@digitiamo.com`, read-only, rate limit, auth off only for local | SATISFIED, with live items deferred | Code and tests verified; Google OAuth verified live by the user; claude.ai connector and non-digitiamo live rejection deferred to Phase 4. User marked complete 2026-11-06. |
| MCP-08 | 02-06 | Skill with tool guidance, format, escalation list, install guide | SATISFIED (content) | Files and mechanical test; live behaviour scheduled for Phase 5 EVAL-03 |

Note: 02-03-SUMMARY lists `requirements-completed: []`, although its PLAN declares MCP-05 and MCP-07. Both are covered by 02-07, so this is a bookkeeping inconsistency only.

### Anti-Patterns Found

No `TBD`, `FIXME`, `XXX`, `TODO` or `HACK` markers in the phase's source, Skill or install guide. No stub returns found in the tool modules. The 02-REVIEW.md warnings are open and advisory (0 critical). I did not re-triage them, and they are flagged here so they are not silently absorbed:

| Ref | Pattern | Severity | Impact |
|-----|---------|----------|--------|
| WR-01 | `AUTH_MODE=off` guard keys only on `K_SERVICE` (Cloud Run); fails open on other hosts | Warning | Phase 4 must add its own host marker (config.py comment A6) |
| WR-02 | Loopback prefix check on `MCP_PUBLIC_BASE_URL` accepts lookalike hostnames such as `http://localhost.evil.com` | Warning | Deployment misconfiguration risk |
| WR-03 | Gap log stores raw question text, including sensitive topics the Skill escalates | Warning | Privacy; no user id is stored |
| WR-04 | Tool descriptions and server instructions contradict the Skill, possibly causing spurious gap records | Warning | Answer quality, to be judged in Phase 5 |
| WR-05 | `OAUTH_JWT_SIGNING_KEY` minimum length documented but not enforced | Warning | Weak-key risk |

02-SECURITY.md reports 0 open threats. 02-VALIDATION.md is Nyquist compliant. I read both only via the brief, not line by line.

### Human Verification Required

1. **claude.ai connector (deferred to Phase 4).** Test: an org owner adds the custom connector and asks a handbook question. Expected: Google authorization, five tools listed, cited answer. Why human: needs an org owner and a hosted URL.
2. **Non-digitiamo account rejection, live (deferred to Phase 4).** Test: log in with an external Google account. Expected: rejected, no tool access. Why human: needs a real external account. The domain check is unit-tested.
3. **Skill behaviour with a live model (Phase 5 EVAL-03).** Test: install the Skill and ask answerable, unanswerable and sensitive questions. Expected: template, refusal plus one gap report, escalation with no personal assessment. Why human: model behaviour is not checkable by grep.

These items do not invalidate the user's decision to mark MCP-07 complete on 2026-11-06. They are reported so the deferral stays visible.

### Gaps Summary

No gaps. All five roadmap success criteria are verified against the code and by re-running the Docker suite (604 passed) and the Firestore emulator tests (4 passed). The status is `human_needed` only because three live or model-behaviour checks cannot be run programmatically. They are already scheduled for Phases 4 and 5. Five advisory review warnings remain open.

---

_Verified: 2026-11-06_
_Verifier: Claude (gsd-verifier)_
