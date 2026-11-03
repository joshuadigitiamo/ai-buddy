---
phase: 01-content-sync
plan: 04
subsystem: sync
tags: [clickup, httpx, pydantic, incremental-sync, denylist, retries, tdd]

requires:
  - phase: 01-02
    provides: HandbookPage, IndexContent, build_index, LocalDirArtifactStore, open_index
  - phase: 01-03
    provides: SyncSettings, Redactor, log_hits, REDACTION_VERSION
provides:
  - "buddy_sync.clickup: ClickUpPage, FlatPage, ClickUpError, ClickUpClient, flatten_pages, page_url, MAX_RESPONSE_BYTES"
  - "buddy_sync.handbook: HandbookSyncResult, EmptyDenylistError, EmptyHandbookError, revision_date_iso, sync_handbook"
  - "tests/fixtures/clickup/pages.json: synthetic OpenAPI-shaped /pages response"
affects: [01-05, 01-06, 01-07, 01-08]

plan_head_before: a86dd055f4b9a504058150c24cfd66f8f148aeb5
plan_head_after: 6b90e9f220623229bc35202beb4da5ad253afd88

actuals:
  tokens: 9118
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Anti-corruption layer: pydantic ClickUpPage (extra=ignore) at the boundary; FlatPage is the only shape the job sees"
    - "Streamed, size-capped response body; bounded retries on 429/5xx via injected sleep"
    - "Error messages carry status and doc id only; pydantic errors reduced to field paths"
    - "Change detection on stored (redacted) text: content_hash = sha256(title NUL content) of redacted values"

key-files:
  created:
    - jobs/sync/buddy_sync/clickup.py
    - jobs/sync/buddy_sync/handbook.py
    - tests/fixtures/clickup/pages.json
    - tests/unit/buddy_sync/test_redaction_pipeline.py
    - tests/unit/buddy_sync/test_clickup_client.py
    - tests/unit/buddy_sync/test_handbook_sync.py
  modified: []

key-decisions:
  - "A page is processed when new, versions_match is False, date_edited differs, or the redacted-text hash differs; unchanged pages keep the previous row and take the current position, depth and parent"
  - "removed counts previous page ids missing from the current non-denied set, so a page that newly joins the denylist also counts as removed"
  - "seen counts every non-archived fetched page including denied ones; processed + unchanged equals the stored row count"
  - "Transport errors (httpx.HTTPError) are not retried and surface as ClickUpError carrying only the exception type name, because the exception text can echo request details"
  - "The /pages response is read as a stream and rejected once it passes MAX_RESPONSE_BYTES, rather than after the whole body is in memory"

requirements-completed: [SYNC-01, SYNC-02, SYNC-03, SYNC-05, GUIDE-01]

coverage:
  - id: D1
    description: "ClickUpClient issues one GET to /api/v3/workspaces/{ws}/docs/{doc}/pages with max_page_depth=-1, content_format=text/md and the raw token in Authorization (no Bearer); non-https base URL refused unless a transport is injected"
    requirement: SYNC-01
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_clickup_client.py#test_request_shape_and_token_header_without_scheme"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_clickup_client.py#test_plain_http_base_url_is_refused_without_injected_transport"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every stored page has ClickUp deep link, title and revision date (date_edited else date_created); tree order position 0..n-1; archived subtree dropped; two pages titled Benvenuto stay distinct"
    requirement: SYNC-05
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction_pipeline.py#test_pages_carry_source"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_sync.py#test_revision_date_falls_back_to_created_then_none"
        status: pass
    human_judgment: false
  - id: D3
    description: "A denylisted page's id, title and secret, and the secret of a redacted page, are absent from every byte of index.db and the manifest; mask is present"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction_pipeline.py#test_denylisted_page_absent"
        status: pass
    human_judgment: false
  - id: D4
    description: "Incremental sync: re-run processes 0 and returns equal rows; one edit processes 1; update-timestamp-only change processes 0; content change with same date_edited processes 1; removed page counted; version change reprocesses all; moved page unchanged"
    requirement: SYNC-02
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_sync.py (18 test cases)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Empty denylist refused before any page is touched unless allowed; zero remaining pages raises EmptyHandbookError; empty content stored as empty string"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_sync.py#test_empty_denylist_refused_before_any_page_is_touched"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_sync.py#test_zero_pages_raises"
        status: pass
    human_judgment: false
  - id: D6
    description: "Client robustness: 429/5xx retried up to max_retries with Retry-After honoured and clamped to 1..30 s; other 4xx fail at once; oversized, malformed and wrongly shaped bodies raise ClickUpError; token and page content absent from errors and logs"
    requirement: SYNC-01
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_clickup_client.py (18 test cases)"
        status: pass
    human_judgment: false
  - id: D7
    description: "content_hash covers redacted stored text only, so a masked short secret cannot be brute-forced from the artifact (T-01-20)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_sync.py#test_content_hash_covers_redacted_text_only"
        status: pass
    human_judgment: false
  - id: D8
    description: "GUIDE-01: plan carries a Guides applied table (Adapter, Anti-Corruption Layer, Retry/Timeout, Incremental load, Idempotency, Capture metadata at load time) realised in clickup.py and handbook.py"
    requirement: GUIDE-01
    verification: []
    human_judgment: true
    rationale: "Convention compliance is a review judgment; the Guides-applied block is in the plan itself"
  - id: D9
    description: "Live-doc assumptions: /pages body shape, deep-link format, date unit and archived handling hold on the real test doc"
    requirement: SYNC-01
    verification: []
    human_judgment: true
    rationale: "Research A2, A5, A6 and A1/A7 are confirmed only against the live ClickUp doc in plan 08; this plan proves them against a synthetic fixture"

duration: 4min
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 04: ClickUp Handbook Sync Summary

**ClickUp v3 `/pages` adapter (token header without scheme, bounded retries, size-capped stream, error messages free of token and content) plus an incremental `sync_handbook` that drops denylisted pages before redaction, hashes only redacted text, and processes only new or changed pages.**

## Performance

- **Duration:** ~4 min (2026-11-03T19:21:54Z to ~19:25Z)
- **Tasks:** 3 (Task 1 tracer, Task 2 TDD, Task 3 TDD)
- **Files:** 6 created, 0 modified; `./run-unit-tests.sh --all`: 194 passed, coverage 97.97%

## Accomplishments

- Tracer verified end to end: the synthetic doc goes through `ClickUpClient` (MockTransport), `flatten_pages`, `sync_handbook`, `build_index` and `LocalDirArtifactStore.publish`; the raw bytes of `index.db` and the manifest contain neither the denylisted page (id, title, secret) nor the redacted page's secret, and do contain `[REDATTO]`.
- Client survives 429 and 5xx (delays 1, 2, 4 s; `Retry-After` and `X-RateLimit-Reset` honoured, clamped to 1..30 s), fails at once on 401, rejects oversized bodies while streaming, and turns JSON, shape and pydantic validation failures into `ClickUpError` that names field paths only.
- Incremental decision implemented as the plan's refinement: every fetched page is redacted each run and compared with the previous row on `date_edited` plus the hash of redacted text; an update-timestamp-only change reprocesses nothing; a version mismatch reprocesses everything.
- Guard rails: `EmptyDenylistError` before any page is touched, `EmptyHandbookError` when nothing remains.

## Task Commits

1. **Task 1: Tracer** - `1cef5a2` (feat)
2. **Task 2: Client robustness (TDD)** - RED `1b9bc20` (test), GREEN `b03cec1` (feat)
3. **Task 3: Incremental sync (TDD)** - RED `e5d145f` (test), GREEN `6b90e9f` (feat)

**Plan metadata:** committed separately (docs: complete plan).

## Files Created

- `jobs/sync/buddy_sync/clickup.py` - ClickUp adapter
- `jobs/sync/buddy_sync/handbook.py` - redaction, denylist and incremental decision
- `tests/fixtures/clickup/pages.json` - synthetic OpenAPI-shaped response (nested pages, archived subtree, denylisted `demo-page-wifi`, duplicate titles, unknown keys, an update-timestamp key, one null `date_edited`)
- `tests/unit/buddy_sync/test_redaction_pipeline.py` (2 tests), `test_clickup_client.py` (18 cases), `test_handbook_sync.py` (18 cases)

## Decisions Made

See key-decisions. All interface names and signatures follow the plan's `<interfaces>` block verbatim.

## TDD Gate Compliance

Tasks 2 and 3 are task-level `tdd="true"` tasks, not a `type: tdd` plan.

- **Task 2 RED** `1b9bc20`: 10 of 18 cases failed on missing behaviour (retry on 429/5xx, backoff, clamping, reset header, `MAX_RESPONSE_BYTES`, validation message, JSON and shape errors, transport errors). The remaining 8 passed against the Task 1 client, which already covered request shape, flattening, array/object bodies, 401, https refusal and token hygiene. GREEN `b03cec1`: all 18 pass. No REFACTOR commit.
- **Task 3 RED** `e5d145f`: 7 of 18 cases failed on the planned assertions (`processed` equal to the page count on a re-run, a single edit, a bumped update timestamp, a content change, a removed page, a moved page, hit logging on unchanged pages). The other 11 (first run, version change, denylist guards, dates, hash) passed because the Task 1 first-run path already implemented them. GREEN `6b90e9f`: all pass. No REFACTOR commit.
- The `gsd_run check tdd-red-evidence` classifier was not run, for the same reason as plan 01-03: the plan is `type: execute` with per-task `tdd="true"` and the classifier has no pytest-native adapter. Semantic check: every RED failure was the planned assertion or a missing attribute, not an import, collection or fixture fault.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lint and typing drift in new test files**
- **Found during:** Tasks 2 and 3 `--all` runs
- **Issue:** ruff E501 and SIM117 in `test_clickup_client.py`; mypy `arg-type` on `dataclasses.replace(**dict[str, object])` in `test_handbook_sync.py`
- **Fix:** restructured two statements; typed the helper kwargs as `Any`; `ruff format` run in the test image (the runner only has `--check`)
- **Files modified:** `tests/unit/buddy_sync/test_clickup_client.py`, `tests/unit/buddy_sync/test_handbook_sync.py`
- **Commits:** `b03cec1`, `6b90e9f`

**2. [Rule 2 - Missing critical] Streaming size cap and transport-error hygiene**
- **Found during:** Task 2
- **Issue:** the plan asks for a length check "before JSON parsing"; a plain `client.get` would read an unbounded body into memory first (T-01-17), and an `httpx.HTTPError` message could echo request details (T-01-16).
- **Fix:** `fetch_pages` reads the 200 body through `client.stream` and stops at `MAX_RESPONSE_BYTES`; `httpx.HTTPError` is converted to `ClickUpError` carrying the exception type name only.
- **Files modified:** `jobs/sync/buddy_sync/clickup.py`
- **Commit:** `b03cec1`

**3. [Process] Commits on protected branch `main`**
- As in plans 01-01 to 01-03: the orchestrator set `branching_strategy=none` and told me to proceed; nothing pushed, no branch created.

**Total deviations:** 2 auto-fixed (1 bug, 1 missing-critical), 1 process note. **Impact:** none on scope or interfaces.

## Authentication Gates

None. The synthetic token `pk_SYNTHETIC_TOKEN_DO_NOT_USE_0000000000` only goes to `httpx.MockTransport`; no network call was made.

## Issues Encountered

None remaining.

- Transport errors are not retried (the plan limits retries to 429 and 5xx); a transient timeout therefore fails the nightly run, which is acceptable for one request per run.
- Flagged assumptions stay open until plan 08 runs against the live doc: `/pages` returns an array (an object with `pages` is also accepted), deep link `https://app.clickup.com/<workspace_id>/v/dc/<doc_id>/<page_id>`, epoch values at or above 1e12 are milliseconds, archived and deleted subtrees are skipped. A page moved in the tree without an edit counts as unchanged but changes the artifact's logical hash (position is stored).

## Known Stubs

None.

## Threat Flags

None. T-01-15 (denylist byte-absence test), T-01-16 (error and log hygiene tests), T-01-17 (timeout, streamed size cap, bounded retries, pydantic validation), T-01-18 (`EmptyDenylistError`), T-01-19 (https-only without a test transport) and T-01-20 (hash of redacted text only) are mitigated as planned. T-01-SC: no packages installed (httpx and pydantic were already pinned).

## Next Phase Readiness

Ready for 01-05 and 01-06 (both only need the shared test image). Plan 07 wires `ClickUpClient`, `sync_handbook` and `build_index` into the job: it must pass `SyncSettings.redact_page_ids` as `denylist`, derive `versions_match` from the previous index's `meta` (`pipeline_version`, `redaction_version`), and call `previous=open_index(...).load_handbook()`.

## Self-Check: PASSED

- Created files exist (all 6 verified with `[ -f ]`).
- Commits `1cef5a2`, `1b9bc20`, `b03cec1`, `e5d145f`, `6b90e9f` are ancestors of HEAD; `git rev-list --count a86dd05..HEAD` = 5 (all five are this plan's task commits).
- Acceptance greps: `/api/v3/workspaces/` 2, `max_page_depth` 1, `Bearer` 0, `xkwgt-` 0 across clickup.py, handbook.py, fixture, `MAX_RESPONSE_BYTES` 2, `date_updated` in clickup.py and handbook.py 0, test defs 16 / 17 (thresholds 9 / 11).
- `./run-unit-tests.sh --all` exit 0: ruff, ruff format, mypy strict clean, 194 passed, coverage 97.97%; the three plan-level verify commands pass.
