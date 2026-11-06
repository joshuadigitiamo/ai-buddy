---
phase: 02-mcp-server-and-skill
plan: 04
subsystem: api
tags: [mcp, fastmcp, gap-tool, contract-tests, read-only, log-hygiene, hexagonal]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "guides and handbook tools, output models, build_server (plans 02-01, 02-02)"
  - phase: 02-mcp-server-and-skill
    provides: "GapLog port, GapRecord, InMemoryGapLog, FirestoreGapLog (plan 02-03)"
provides:
  - "buddy_report_gap tool (gap_tool.register_gap_tool, GAP_ANNOTATIONS) writing through the GapLog port, no caller identity"
  - "McpSettings.gap_ttl_days (default 90, at least 1) and gap_collection ([A-Za-z0-9_-]+)"
  - "build_server(settings, *, snapshot, gaplog, now) - the five-tool surface plus the handbook resource template"
  - "Cross-tool contract tests: exact surface, annotations, read-only index, log hygiene, source fields, explicit no_results"
affects: [02-05 auth and rate limit, 02-06 skill, 02-07 composition root (must pass a FirestoreGapLog and GAP_COLLECTION), 03 bot (parses these outputs)]

actuals:
  tokens: 5900
  tasks: 3
  commits: 4
plan_head_before: ec94fdb2fd3dd5242d9e60ebcf712122859af9fe
plan_head_after: 96fd1714bb884599ae93ac67b02b0aa6537c9a33

tech-stack:
  added: []
  patterns:
    - "Tool depends on the GapLog port; tests inject InMemoryGapLog via a conftest fixture"
    - "Contract tests walk every tool output with one helper (assert_cited) that fails on a missing source field"
    - "Log capture for the fastmcp logger is attached explicitly because it does not propagate to the root logger"

key-files:
  created:
    - services/mcp_server/buddy_mcp/gap_tool.py
    - tests/unit/mcp_server/test_gap_tool.py
    - tests/unit/mcp_server/test_tool_surface.py
    - tests/unit/mcp_server/test_read_only.py
    - tests/unit/mcp_server/test_log_hygiene.py
    - tests/unit/mcp_server/test_source_fields.py
    - tests/unit/mcp_server/test_no_results.py
  modified:
    - services/mcp_server/buddy_mcp/server.py
    - services/mcp_server/buddy_mcp/config.py
    - services/mcp_server/buddy_mcp/handbook_tools.py
    - tests/unit/mcp_server/conftest.py

key-decisions:
  - "buddy_report_gap never reads the access token or request context; a backend failure logs only the exception type (logger buddy_mcp.gap_tool) and returns the fixed ToolError 'gap log unavailable'. A GapRecordError becomes a ToolError with the rule message, never the question."
  - "No logging middleware and no fastmcp logger level change were needed: fastmcp logged no tool arguments at INFO. The hygiene test attaches the capture handler to the non-propagating 'fastmcp' logger so it cannot pass vacuously, and a second test proves that wiring sees records."
  - "tools/list order is not asserted (flagged assumption from the plan): the test checks set equality and call-to-call stability; clients must look tools up by name."
  - "handbook_get() TOC text gained a 'Fonte: handbook://<page_id>' line per entry so every returned source_url appears in the text rendering; the existing entry line is unchanged."

patterns-established:
  - "Settings validators name the field in the message and never echo the value (gap_ttl_days, gap_collection)"
  - "build_server takes its clock as a callable so tests pin time without monkeypatching"

requirements-completed: [MCP-02, MCP-03, MCP-04]

duration: ~8min
completed: 2026-11-06
status: complete
---

# Phase 2 Plan 4: buddy_report_gap and Tool Surface Contract Summary

**Fifth tool `buddy_report_gap` writing question, queries tried, UTC timestamps and build id through the GapLog port with no caller identity, plus cross-tool tests that fix the surface at exactly five tools, one non-read-only, every output cited, every miss an identical explicit `no_results`.**

## Performance

- **Duration:** about 8 min (start 2026-11-06T21:08:42Z, last code commit about 21:14Z)
- **Completed:** 2026-11-06
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 TDD-flagged)
- **Files modified:** 11 (7 created, 4 modified)

## Accomplishments

- Tracer: `buddy_report_gap(question, tried?)` returns `status recorded`, a `gap_id` and the marker `nessuna fonte trovata`; the injected log gets one `GapRecord` with the stripped question, `created_at` equal to the server clock, `expire_at` 90 days later (7 with `gap_ttl_days=7`), the index `build_id` and the `tried` tuple. Empty, whitespace and 2001-character questions are `isError` with no echo and nothing recorded. A failing backend gives `gap log unavailable` and exactly one WARNING naming only `RuntimeError`.
- Settings: `gap_ttl_days` below 1 (kwarg or `GAP_TTL_DAYS=0`) and `gap_collection` values such as `gaps/../x`, `gaps/sub`, `a b`, empty raise a `ValidationError` naming the field.
- Surface locked: `tools/list` is the five `TOOL_NAMES`, each with an object output schema and a description over 40 characters; the four content tools mention `no_results`, the two search tools name `buddy_report_gap`. Four tools carry `read_only true, destructive false, idempotent true, open_world false`; the gap tool is the only `read_only false` (destructive false, idempotent false, open_world false). Two `tools/list` calls dump identically; the `handbook://{pagina}` template and server instructions are present.
- Read-only: sha256 of `index.db` and the artifact-directory listing are unchanged after calling all five tools (including miss calls) and reading `handbook://02-ferie`.
- Log hygiene: at INFO with the `fastmcp` logger captured too, sentinel queries and questions appear in no log record.
- Sources: handbook search (4 queries), TOC, every page, Guides search (3 queries) and every chunk are checked by `assert_cited` (non-empty `source_url`, parseable ISO `revision_date`, correct `revision_kind`, prefix `handbook://` or `WEB_BASE/blob/SHA/`); each returned `source_url` also appears in the text of the same call; the mapped chunk carries `video_url ...demo.mp4#t=12`, the other two `None`. A negative self-test proves `assert_cited` fails on a missing field. The gap tool is the only output schema without `results` and without `source_url`.
- No-results: `handbook_search`, `guides_search`, `handbook_get(section="nope")` and `guides_get_section(id="nope")` all return `isError false`, `status no_results`, `results []`, empty `toc`, and the text is exactly `Nessun risultato per: <query>`.

## Task Commits

1. **Task 1 (tracer): buddy_report_gap through the GapLog port** - `80cc049` (feat)
2. **Task 2: surface, read-only and log hygiene tests** - `c9bf801` (test; no implementation change needed)
3. **Task 3: source and no_results contract** - RED `f8f5669` (test), GREEN `96fd171` (feat)

## TDD Gate Compliance

- **Task 3:** `test(02-04)` `f8f5669` precedes `feat(02-04)` `96fd171`. RED run (`./run-unit-tests.sh --single-file test_source_fields.py tests/unit/mcp_server`): 1 failed, 16 passed. The failure was `test_handbook_toc_entries_are_cited` on the planned assertion `handbook://01-benvenuto in text` (the TOC text listed `page_id - title (revisione date)` with no source). Semantic assessment: the target test executed and failed for the intended reason; the other 16 and all 4 `test_no_results.py` tests passed because 02-01 and 02-02 already satisfied them. GREEN: TOC text now has a `Fonte:` line per entry; 17 and 4 passed.
- **Task 2:** a characterization suite over behavior delivered by 02-01, 02-02 and Task 1. No RED phase was possible (every test passed on first run apart from two test-authoring errors, below), and no `feat` commit exists; this is a deliberate departure from the RED-then-GREEN order, not a missed gate. Mutation spot check not performed.
- `workflow.tdd_mode` is not enabled in config and the `tdd-red-evidence` classifier has no pytest report adapter, so it was not run; RED evidence is the real pytest output above.
- Task 1 carries `type="tracer"` and is committed as one `feat`; its tests were written before the code and all 15 passed on the first run after implementation.

## Verification

- `./run-unit-tests.sh --all`: exit 0. ruff check, ruff format --check and mypy --strict clean. **468 passed, 17 skipped** (the same 17 local-only or emulator-only skips as 02-03), coverage 97.46% (gate 80%). `gap_tool.py` 100%.
- `./run-unit-tests.sh --emulator`: exit 0, 3 passed (Firestore adapter unchanged).
- Per-file runs: `test_gap_tool.py` 15 passed, `test_tool_surface.py` 6, `test_read_only.py` 1, `test_log_hygiene.py` 2, `test_source_fields.py` 17, `test_no_results.py` 4.
- Acceptance greps: `async def buddy_report_gap` 1; `read_only_hint=False` 1; `get_access_token|get_http_request` in gap_tool.py 0; `register_gap_tool(` in server.py 1; `TOOL_NAMES` in test_tool_surface.py 2; `sha256` in test_read_only.py 1; `sentinella-` in test_log_hygiene.py 5; `def assert_cited` 1; `Nessun risultato per: ` in test_no_results.py 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] handbook_get() TOC text omitted every source_url**
- **Found during:** Task 3 (RED test `test_handbook_toc_entries_are_cited`)
- **Issue:** The text rendering of the table of contents showed page id, title and date but no `handbook://` citation, so the plan's "text rendering contains every source_url" truth failed for one tool.
- **Fix:** each TOC entry now renders a second line `Fonte: handbook://<page_id>`; the first line is byte-identical so `test_handbook_get.py` still matches.
- **Files modified:** `services/mcp_server/buddy_mcp/handbook_tools.py`
- **Commit:** `96fd171`

**2. [Rule 3 - Blocking] Lint, format and type gates on the new tests and config**
- **Found during:** Task 1 (`--all`), Task 2
- **Issue:** a docstring over 100 characters in `config.py`; import order in `config.py` and `test_gap_tool.py`; two unused `type: ignore` comments (the pydantic mypy plugin already accepts `McpSettings()`); `client.initialize_result` is `None` outside the handshake and the in-memory client negotiates the modern era with no `InitializeResult`, so the instructions check uses `client.instructions`.
- **Fix:** shortened the docstring, ran `ruff check --fix` and `ruff format`, removed the ignores, used `client.instructions`.
- **Commits:** `80cc049`, `c9bf801`

**3. [Rule 2 - Missing critical] Hygiene test could pass vacuously**
- **Found during:** Task 2
- **Issue:** the `fastmcp` logger has `propagate = False`, so caplog on the root logger never sees its records and a leak there would go unnoticed.
- **Fix:** the test attaches `caplog.handler` to the `fastmcp` logger, and a second test logs a probe through that logger to prove the wiring captures it.
- **Commit:** `c9bf801`

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing critical). **Impact:** one user-visible text change (extra `Fonte:` lines in the TOC text); no scope change.

### Plan variance (not a deviation)

- Beyond the plan's behavior list: parametrized `gap_collection` rejections (`gaps/sub`, `a b`, empty) and a `GAP_TTL_DAYS=30` env happy path.

## Authentication Gates

None.

## Requirements

- Marked complete: MCP-02 (five tools, tested), MCP-03 (source and revision date on every output, enforced by a failing-if-missing test), MCP-04 (explicit `no_results` on all four content tools).
- MCP-05 left pending: the shared-ID gate (`requirements.ready-ids`) blocks it because a later plan in this phase also declares it. Caveat: the tool-to-port contract is unit-tested with `InMemoryGapLog`, and the Firestore document shape was verified on the emulator in 02-03; no test drives the tool into Firestore end to end, because the composition root that builds `FirestoreGapLog` is plan 02-07.
- Not marked: MCP-07 (OAuth, `@digitiamo.com` restriction, rate limiting and the auth-off switch are 02-05; only its read-only half is covered here). MCP-06 was already complete.

## Known Stubs

None.

## Threat Flags

None. The only new trust-boundary surface is `buddy_report_gap` persisting untrusted question text, already covered by T-02-12 and T-02-13 in the plan's threat model (2000-character cap and bounded `tried` from 02-03; per-identity rate limit is 02-05).

## Issues Encountered

None open. Remaining for the phase: auth and rate limiting (02-05), skill (02-06), composition root and deploy wiring (02-07).

## Self-Check: PASSED

All created files exist on disk and the four task commits (`80cc049`, `c9bf801`, `f8f5669`, `96fd171`) are ancestors of HEAD.
