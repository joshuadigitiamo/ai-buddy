---
phase: 02-mcp-server-and-skill
plan: 02
subsystem: api
tags: [fastmcp, mcp, sqlite-fts5, snowball, italian, handbook, resource-template]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "buddy_mcp package, D-06 models, READ_ONLY annotations, synthetic fixture conftest (plan 02-01)"
  - phase: 01-content-sync
    provides: "buddy_core.index_reader.to_match_query and handbook_pages in index.db (read-only reuse, untouched)"
provides:
  - "handbook_search: Italian keyword search over whole pages, in-memory FTS5 with Snowball stems"
  - "handbook_get: table of contents (no section) or one page by exact page_id"
  - "Resource template handbook://{pagina} (text/markdown) with a citation header"
  - "stemming.py (normalize, stem_text, stem_query, ITALIAN_STOPWORDS) and HandbookIndex built inside load_snapshot"
affects: [02-03, 02-04 contract tests, 02-05 auth, 02-06 skill, 03 chat bot]

actuals:
  tokens: 5350
  tasks: 2
  commits: 3
plan_head_before: 1c1a2babeb10a5d538a96ea0fea33ca414e73da2
plan_head_after: 78c0685d377940fed71754fe121bee7f24aaaf54

tech-stack:
  added: []
  patterns:
    - "Handbook FTS: separate in-memory sqlite3 db (fts5 title, body; unicode61 remove_diacritics 2) holding stems of page text; index.db stays schema 1.0.0"
    - "Query path: stem_query -> to_match_query (every token a quoted phrase) -> bound ? parameter; ORDER BY bm25(pages, 5.0, 1.0), rowid"
    - "Resource lookup is a dict get on page_id; the argument never becomes a path"

key-files:
  created:
    - services/mcp_server/buddy_mcp/stemming.py
    - services/mcp_server/buddy_mcp/handbook_tools.py
    - tests/unit/mcp_server/test_handbook_search.py
    - tests/unit/mcp_server/test_handbook_get.py
    - tests/unit/mcp_server/test_handbook_resource.py
  modified:
    - services/mcp_server/buddy_mcp/snapshot.py
    - services/mcp_server/buddy_mcp/server.py
    - tests/unit/mcp_server/conftest.py
    - pyproject.toml

key-decisions:
  - "Only the resource template is advertised (resources/list stays empty, Claude's discretion). A client that reads only resources/list will not discover pages and must use the template or handbook_get()."
  - "Exact page_id match only in handbook_get and the resource (no fuzzy match, case-sensitive): 02-FERIE and 02-ferie/ are no_results."
  - "Stopword-only queries are no_results by construction: stem_query drops them, to_match_query returns None, search returns []."
  - "No prefix matching on top of stemming; Phase 5 Recall@5 decides."

patterns-established:
  - "Shared page rendering (render_page) between handbook_search and handbook_get: '# title', markdown, 'Fonte: handbook://id', 'Revisione: YYYY-MM-DD'"
  - "Resource body: 'Fonte: handbook://id - Revisione: YYYY-MM-DD', blank line, '# title', markdown"

requirements-completed: [MCP-06]

duration: ~10min
completed: 2026-11-06
status: complete
---

# Phase 2 Plan 2: Handbook Search, Lookup and Resource Summary

**Italian handbook slice on the 02-01 server: `handbook_search` over an in-memory Snowball-stemmed FTS5 table returns whole pages cited with `handbook://<id>` and their last-updated date, `handbook_get` serves the table of contents or one page, and `handbook://{pagina}` attaches a page as a resource.**

## Performance

- **Duration:** about 10 min (start time was not recorded; estimated from the session)
- **Completed:** 2026-11-06
- **Tasks:** 2 (Task 1 tracer, Task 2 TDD)
- **Files modified:** 9 (5 created, 4 modified)

## Accomplishments

- Tracer: `"quando posso chiedere una feria?"` and `"richiedo ferie"` both return `02-ferie` first, as the full page markdown, `source_url` `handbook://02-ferie`, `revision_date` `2026-10-03T00:00:00+00:00`, `revision_kind` `last_updated`. Verified end to end through the in-memory fastmcp client against the `server` fixture.
- Case and accent folding is identical on page text and query (`normalize`: lowercase, NFKD, combining marks dropped, before stemming): `citta`, `CITTÀ` and `città` all find `04-sede`.
- Explicit `no_results` (status, `results: []`, query echoed, `isError` false, text `Nessun risultato per: <query>`) for empty, whitespace-only, punctuation-only, stopword-only (`come e quando`) and unmatched queries.
- FTS5 operators, quotes, `title:*`, `NEAR(` and NUL in a query are inert (stems go through `to_match_query` and are bound as a parameter). Limit clamps 1..10 (limit 0 returns 1 result, default 5). Equal bm25 scores keep page position order; identical calls return identical lists.
- `handbook_get()` returns status ok, `results: []` and a 4-entry table of contents in position order; `handbook_get("02-ferie")` returns the same page object as the search hit; unknown, case-different, path-like and empty ids are `no_results`.
- `handbook://{pagina}` is listed in `resources/templates/list` (and `resources/list` is empty); reading `handbook://02-ferie` returns `Fonte: handbook://02-ferie - Revisione: 2026-10-03`, a blank line, `# Ferie e permessi`, then the markdown, mime type `text/markdown`. An unknown id and `handbook://..%2F..%2Fetc%2Fpasswd` raise an MCP error.
- `git diff --quiet f2364c5 -- jobs/sync packages/buddy_core` exits 0: index.db schema and sync are untouched.
- Verification: `./run-unit-tests.sh --all` exits 0 (ruff check, ruff format, mypy --strict, 402 passed, 14 skipped, coverage 97.53% against the 80% floor). `handbook_tools.py`, `snapshot.py` and `stemming.py` are at 100%. Per-file runs: `test_handbook_search.py` 18 passed, `test_handbook_get.py` 7 passed, `test_handbook_resource.py` 4 passed.

## Task Commits

1. **Task 1: Tracer, handbook_search** - `c63e86f` (feat)
2. **Task 2: handbook_get and resource (TDD)**
   - RED `a96876d` (test)
   - GREEN `78c0685` (feat)
   - REFACTOR: none needed, no commit

**Plan metadata:** recorded in the final docs commit (SUMMARY, STATE, ROADMAP, REQUIREMENTS, state.json).

## TDD

- **RED:** `test_handbook_get.py` and `test_handbook_resource.py` written first, run on `c63e86f`. `test_handbook_get.py`: 7 failed, all on `assert None is not None` because `handbook_get` was not registered (`Unknown tool: 'handbook_get'`). `test_handbook_resource.py`: 2 failed (`[] == ['handbook://{pagina}']` and `Resource not found: 'handbook://02-ferie'`), 2 passed.
- **Semantic assessment:** the 9 failures are the target behaviors absent for the planned reason (tool and resource template not registered); no collection, import or fixture errors. The 2 passing resource tests (unknown id and traversal id raise an MCP error) pass at RED because nothing is registered, so any URI is "not found"; they are regression locks that become meaningful once the template exists, and they still pass at GREEN with the template present (the error then comes from `ResourceError` or template matching, not from a missing resource).
- **GREEN:** `handbook_get` and the resource template added to `handbook_tools.py`; 7 + 4 tests pass.
- **Classifier:** `gsd_run check tdd-red-evidence` was not run: Task 2 is a task-level `tdd="true"` in an `execute` plan, no `TDD_MODE=true` was passed, and pytest's console report is not one of the classifier's formats. The evidence above is the raw pytest output.
- **Gate commits:** `test(02-02)` `a96876d` precedes `feat(02-02)` `78c0685`.
- Task 1 is `type="tracer"` (test and implementation in one `feat` commit, as the plan specifies); the tracer feedback gate ran in the plan's `<verify>`: both automated commands pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy --strict rejects untyped snowballstemmer**
- **Found during:** Task 1 (`./run-unit-tests.sh --all`)
- **Issue:** `snowballstemmer` ships no stubs and no `py.typed`; `error: module is installed, but missing library stubs` (import-untyped).
- **Fix:** `[[tool.mypy.overrides]] module = "snowballstemmer", ignore_missing_imports = true` in `pyproject.toml`, scoped to that one module (strict stays on everywhere else).
- **Files modified:** `pyproject.toml`
- **Commit:** `c63e86f`

**2. [Rule 2 - Missing critical] Test fixtures close the HandbookIndex connection**
- **Found during:** Task 1
- **Issue:** `HandbookIndex` owns an in-memory sqlite connection; the 02-01 fixtures closed only `reader`.
- **Fix:** added `HandbookIndex.close()` and call it in the `snapshot` and `server_for` fixtures.
- **Files modified:** `services/mcp_server/buddy_mcp/snapshot.py`, `tests/unit/mcp_server/conftest.py`
- **Commit:** `c63e86f`

**3. [Rule 1 - Bug] Test used deprecated camelCase SDK fields**
- **Found during:** Task 2 GREEN (warnings summary)
- **Issue:** `ResourceTemplate.uriTemplate` and `TextResourceContents.mimeType` raise `FastMCPDeprecationWarning` (MCP SDK v2 renamed them to snake_case). The plan's behavior text names `uriTemplate`.
- **Fix:** tests read `uri_template` and `mime_type`. The wire contract (`uriTemplate` in the JSON) is unchanged.
- **Files modified:** `tests/unit/mcp_server/test_handbook_resource.py`
- **Commit:** `78c0685`

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 missing critical, 1 bug)
**Impact on plan:** no scope change; no new package (T-02-SC holds: `snowballstemmer` was approved in 02-01).

## Issues Encountered

- The plan says the FTS rowid is the page position; the implementation uses the 0-based index into the position-ordered page tuple. Ordering is identical, and the test for ties confirms it.
- `.planning/state.json` carried a small pre-existing modification from a gsd tool side effect; it is included in the docs commit as instructed.

## Known Stubs

None.

## Requirements Coverage

- **MCP-06:** fully met by this plan (resource template `handbook://{pagina}` lists, reads, errors on unknown ids). Marked complete.
- **MCP-02, MCP-03, MCP-04:** this plan adds the handbook side only (`handbook_search`, `handbook_get`, handbook citations, handbook `no_results`). `buddy_report_gap` (the fifth tool of MCP-02) does not exist yet, and the 02-01 SUMMARY already flagged that these three IDs were marked complete in REQUIREMENTS.md on Guides coverage alone. This plan did not change their state; verification should check MCP-02..04 against the finished phase.

## Threat Flags

None new. T-02-05 (MATCH injection) and T-02-06 (id to path) are mitigated and covered by tests: operators, quotes, `title:*`, `NEAR(` and NUL queries; `../`, encoded-traversal, case-different and trailing-slash ids. The 02-01 flag (`/mcp` unauthenticated until 02-05) still stands.

## Next Phase Readiness

- Plan 02-03 (`buddy_report_gap`) can add its tool in `build_server` next to `register_guides_tools` and `register_handbook_tools`; all handbook and Guides tools return the D-06 contract.
- `IndexSnapshot` now has a required `handbook_index` field; anything constructing an `IndexSnapshot` directly (only `load_snapshot` today) must pass it.
- No blockers.

## Self-Check: PASSED

- Files: all 5 created files found on disk (`stemming.py`, `handbook_tools.py`, three test files).
- Commits: `c63e86f`, `a96876d`, `78c0685` are ancestors of HEAD.
- Acceptance criteria: stemmer("italian") 1, "remove_diacritics 2" 1, `to_match_query(` 1, `register_handbook_tools(` 1, `handbook://{pagina}` 1, `async def handbook_get` 1, `Fonte: handbook://` 1; `git diff --quiet f2364c5 -- jobs/sync packages/buddy_core` exit 0.

---
*Phase: 02-mcp-server-and-skill*
*Completed: 2026-11-06*
