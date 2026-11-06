---
phase: 02-mcp-server-and-skill
plan: 01
subsystem: api
tags: [fastmcp, mcp, streamable-http, sqlite-fts5, pydantic, guides-search]

requires:
  - phase: 01-content-sync
    provides: "buddy_core index reader/writer/store and the index.db artifact (read-only reuse, untouched)"
provides:
  - "services/mcp_server/buddy_mcp package on pinned fastmcp 4.1.6 (config, snapshot, models, guides_tools, server)"
  - "Stateless JSON streamable-HTTP ASGI app (POST /mcp 200 JSON, no mcp-session-id, GET /mcp 405)"
  - "guides_search and guides_get_section with GitHub permalink source_url pinned to the indexed commit, indexed_on revision_date and video_url"
  - "Complete D-06 output contract (models.py) for all five tools, consumed by 02-02, 02-04, 02-06 and the Phase 3 bot"
  - "Synthetic fixture index conftest (server, server_for, make_server, snapshot, settings) reused by later plans"
affects: [02-02 handbook tools, 02-03, 02-04 contract tests, 02-05 auth, 02-06 skill, 02-07 packaging, 03 chat bot]

actuals:
  tokens: 9535
  tasks: 3
  commits: 3
plan_head_before: b26066d2f86231e72c8b529198677bdc31e23d9f
plan_head_after: cb35969b0f79f129c03092371db777c2e90e5d85

tech-stack:
  added: [fastmcp==4.1.6, snowballstemmer==3.1.1, google-cloud-firestore==2.34.1]
  patterns:
    - "async tool functions returning ToolResult(content=<Italian text>, structured_content=<model_dump>) with output_schema from the pydantic output model"
    - "cold-start read-only IndexSnapshot held in RAM; no per-connection state"
    - "FastMCP.http_app(stateless_http=True, json_response=True)"
    - "in-memory fastmcp.Client for tool tests, httpx2 ASGITransport for transport tests, anyio marker (no pytest-asyncio)"

key-files:
  created:
    - services/mcp_server/requirements.txt
    - services/mcp_server/buddy_mcp/__init__.py
    - services/mcp_server/buddy_mcp/config.py
    - services/mcp_server/buddy_mcp/snapshot.py
    - services/mcp_server/buddy_mcp/models.py
    - services/mcp_server/buddy_mcp/guides_tools.py
    - services/mcp_server/buddy_mcp/server.py
    - tests/unit/mcp_server/conftest.py
    - tests/unit/mcp_server/test_http_transport.py
    - tests/unit/mcp_server/test_guides_tools.py
    - tests/unit/mcp_server/test_snapshot.py
    - tests/unit/mcp_server/test_models.py
  modified:
    - requirements-dev.txt
    - Dockerfile
    - pyproject.toml
    - tests/unit/test_repo_layout.py
  deleted:
    - services/mcp_server/.gitkeep

key-decisions:
  - "Package legitimacy gate: Joshua approved the three pins as written (fastmcp==4.1.6, snowballstemmer==3.1.1, google-cloud-firestore==2.34.1); the orchestrator confirmed all three on the PyPI JSON API with the expected project links. No pin was changed."
  - "revision_kind keeps its default on HandbookPageResult and GuidesSectionResult (02-02 constructs HandbookPageResult relying on it) but is forced into the advertised JSON schema `required` list through json_schema_extra, so clients see it as always present."
  - "Guides revision_date is the index build date labelled indexed_on (user decision 2); source_url is a GitHub permalink pinned to guides_commit_sha with #L<n> for one-line sections and #L<start>-L<end> otherwise."
  - "Tool functions are async: sync tools run in a threadpool while the SQLite connection belongs to the loop thread."

patterns-established:
  - "Contract-first models: every result item rejects empty source_url / revision_date (Field(min_length=1))"
  - "no_results is a normal result (status no_results, isError false, text starting 'Nessun risultato per: <query>'), never an MCP error"
  - "Fixtures are synthetic only (*.invalid URLs, no handbook text); server_for builds one-off tmp indexes per test"

requirements-completed: [MCP-01, MCP-02, MCP-03, MCP-04]

coverage:
  - id: D1
    description: "Stateless JSON streamable-HTTP transport: initialize 200 JSON without mcp-session-id, GET /mcp 405"
    requirement: MCP-01
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_initialize_is_stateless_json"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_get_mcp_is_not_a_stream"
        status: pass
    human_judgment: false
  - id: D2
    description: "guides_search over HTTP returns cited, video-linked sections pinned to the indexed commit"
    requirement: MCP-03
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_guides_search_over_http_is_cited"
        status: pass
    human_judgment: false
  - id: D3
    description: "guides_get_section by section_id; unknown id is no_results; single-line anchor and percent-encoded permalink"
    requirement: MCP-02
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_guides_tools.py#test_get_section_returns_the_same_citation_as_search"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_guides_tools.py#test_permalink_percent_encodes_spaces_in_the_path"
        status: pass
    human_judgment: false
  - id: D4
    description: "Explicit no_results for empty, punctuation-only and unmatched queries; FTS5 operators inert; limit clamp 1..10 default 5; stable tie order"
    requirement: MCP-04
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_guides_tools.py#test_unanswerable_query_is_no_results_not_an_error"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_guides_tools.py#test_limit_is_clamped"
        status: pass
    human_judgment: false
  - id: D5
    description: "Cold-start failures (missing directory, no index, other schema major, undated page) and read-only artifact directory"
    requirement: MCP-03
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_snapshot.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "Full D-06 output contract for the five tools, required citation fields, GAP_MARKER"
    requirement: MCP-02
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_models.py"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-06
status: complete
---

# Phase 2 Plan 1: MCP Server Tracer and Guides Slice Summary

**Stateless JSON FastMCP server (`buddy_mcp`, fastmcp 4.1.6) serving cited, video-linked Guides sections from the cold-start index snapshot, with the complete five-tool D-06 output contract fixed in one module.**

## Performance

- **Duration:** 8 min of executor time (continuation after the Task 1 gate; the wait for Joshua's approval is not counted)
- **Started:** 2026-11-06T20:47:55Z
- **Completed:** 2026-11-06T20:55Z
- **Tasks:** 3 (Task 1 gate, Task 2 tracer, Task 3 TDD)
- **Files modified:** 17 (12 created, 4 modified, 1 deleted)

## Accomplishments

- Tracer: an MCP client posting `tools/call guides_search` to `/mcp` of the ASGI app gets `structuredContent` whose results carry `source_url` (GitHub permalink at the indexed commit), `revision_date` = index build time, `revision_kind` = `indexed_on` and `video_url` (`...#t=12` for the mapped section, null otherwise). Transport is stateless JSON: initialize returns 200 `application/json` with no `mcp-session-id`, GET /mcp returns 405.
- Contract: `buddy_mcp/models.py` holds `TOOL_NAMES`, `GAP_MARKER`, `clamp_limit` and all item and output models for the five tools; every cited item rejects an empty `source_url` or `revision_date`.
- Guides slice finished: `guides_get_section(id)`, explicit `no_results` (never an MCP error), limit default 5 clamped to 1..10, FTS5 operators typed by the user are inert, ties break by chunk id, one-line sections cite `#L<n>`, spaces in file paths are percent-encoded.
- Cold start fails fast on a missing directory, a directory without `index.db`, another schema major, or a handbook page with no revision date; the server never creates or writes in the artifact directory (listing compared before and after load and search).
- Verification: `./run-unit-tests.sh --all` exits 0 (ruff, ruff format, mypy --strict, 373 passed, 14 skipped, coverage 97.41% against the 80% floor). `buddy_mcp` modules are at 89% (config.py line 35, the https validator branch, is not exercised) to 100%.

## Task Commits

1. **Task 1: Package legitimacy gate** - no commit (gate only). Joshua replied "approved" to the three pins as written; the orchestrator confirmed all three on the PyPI JSON API.
2. **Task 2: Tracer** - `1ac65e8` (feat)
3. **Task 3: D-06 contract, guides_get_section, edges, cold-start failures (TDD)**
   - RED `0490bff` (test)
   - GREEN `cb35969` (feat)
   - REFACTOR: none needed, no commit

**Plan metadata:** recorded in the final docs commit (SUMMARY, STATE, ROADMAP, REQUIREMENTS).

## TDD

- **RED:** `test_models.py`, `test_guides_tools.py`, `test_snapshot.py` written first. Run on `1ac65e8`: test_models 15 failed / 12 passed, test_guides_tools 5 failed / 14 passed, test_snapshot 7 passed. The failures are on the planned behavior: the models are missing (`buddy_mcp.models.<Name> is missing` or `TOOL_NAMES`/`GAP_MARKER` not equal to the contract), `revision_kind` absent from the schema `required` list, `guides_get_section` unknown (`structured_content` is None for an "Unknown tool" result), and the single-line anchor is `#L40-L40` instead of `#L40`. Tests were written so a missing symbol fails an assertion instead of breaking collection; no collection, import or fixture errors occurred.
- **Semantic assessment:** the targeted new-behavior tests executed and failed for the intended reason. The tests that passed at RED (clamp, `no_results` edges, limit, ordering, operator inertness, and all of test_snapshot) pass because the tracer already shipped that code (Task 2 steps 4-6 specified `snapshot.py` and `clamp_limit` and `no_results`); they are regression locks, not unexpected greens of a target test.
- **GREEN:** `models.py` completed and `guides_tools.py` gained `guides_get_section` and the single-line anchor. 27 + 19 + 7 tests pass.
- **Classifier:** `gsd_run check tdd-red-evidence` was not run. Task 3 is a task-level `tdd="true"` inside an `execute` plan, the orchestrator did not pass `TDD_MODE=true`, and pytest's console report is not one of the classifier's listed formats. The evidence above is the raw pytest output of the actual runs.
- **Gate commits:** `test(02-01)` `0490bff` precedes `feat(02-01)` `cb35969`.

## Files Created/Modified

- `services/mcp_server/requirements.txt` - three approved pins
- `services/mcp_server/buddy_mcp/config.py` - `McpSettings` (ARTIFACT_DIR, GUIDES_WEB_BASE https-only, MCP_HOST, PORT); error text names variables only
- `services/mcp_server/buddy_mcp/snapshot.py` - `IndexSnapshot`, `resolve_index_path`, `load_snapshot`, `SnapshotError`
- `services/mcp_server/buddy_mcp/models.py` - D-06 contract
- `services/mcp_server/buddy_mcp/guides_tools.py` - `guides_search`, `guides_get_section`, `guides_permalink`, `READ_ONLY`
- `services/mcp_server/buddy_mcp/server.py` - `build_server`, `build_app`, `SERVER_NAME = "digitiamo-buddy"`
- `tests/unit/mcp_server/` - conftest (synthetic index, `server`, `server_for`, `make_server`) and four test files
- `requirements-dev.txt`, `Dockerfile`, `pyproject.toml`, `tests/unit/test_repo_layout.py` - build and tooling wiring for the new package
- `services/mcp_server/.gitkeep` - deleted (intentional; the directory now holds the package and `test_d11_layout_exists` still passes)

## Decisions Made

- Three pins approved unchanged at the legitimacy gate (see key-decisions); the image built and resolved them against the existing pydantic pins without touching other pins (mcp 2.3.0, httpx2 2.16.0, starlette 1.10.0, anyio 4.16.0 installed).
- `revision_kind` default retained, schema `required` forced via `json_schema_extra` (reconciles the plan's "default" wording with its "listed as required" test and 02-02's constructor usage).
- Test modules import shared constants from `tests.unit.mcp_server.conftest`. This works under `--import-mode=importlib` with `python -m pytest` from the repo root and passes mypy.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lint failures on first full run of the tracer**
- **Found during:** Task 2 (`./run-unit-tests.sh --all`)
- **Issue:** two E501 lines and two unsorted import blocks in new files
- **Fix:** wrapped the long lines; ran `ruff check --fix` and `ruff format` inside the test image
- **Files modified:** guides_tools.py, conftest.py, test_http_transport.py
- **Verification:** `--all` exit 0
- **Committed in:** `1ac65e8`

**2. [Rule 2 - Missing critical] `snapshot` fixture closes its SQLite reader**
- **Found during:** Task 2 (conftest)
- **Issue:** the plan's fixture list did not close the reader, leaking one connection per test
- **Fix:** `snapshot` yields and closes `reader`; added a `server_for` factory fixture (closes its readers) for the extra tmp indexes Task 3 needs
- **Files modified:** tests/unit/mcp_server/conftest.py
- **Committed in:** `1ac65e8`, `0490bff`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** no scope change. `snapshot.py` was written complete in Task 2 as the plan's step 4 specified, so Task 3 step 3 needed no source change (its behavior is locked by tests).

## Issues Encountered

- `ruff check` and `mypy` do not need a host Python: ran them through `docker run ... ai-buddy-test` for auto-fixing. Repository path contains a space, so shell helpers quote `$PWD`.
- `fastmcp` and `mcp` versions differ (server info reports 4.1.6; protocol package is `mcp 2.3.0`), as the research predicted.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: unauthenticated-endpoint | services/mcp_server/buddy_mcp/server.py | `/mcp` accepts any caller and has no auth or rate limiting yet; plan 02-05 adds auth, rate limiting is planned in the same phase. Do not deploy this build as is. |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-02 can import `HandbookPageResult`, `HandbookTocEntry`, `HandbookSearchOutput`, `HandbookGetOutput`, `READ_ONLY`, `clamp_limit`, `DEFAULT_LIMIT`, and use the `server`/`server_for`/`make_server` fixtures and the four-page handbook fixture.
- `requirements-completed` lists MCP-01..MCP-04 as the plan frontmatter assigns them, but only the Guides side of MCP-02, MCP-03 and MCP-04 exists (two of five tools; no handbook or `buddy_report_gap` yet). Full coverage lands with 02-02 and the later plans; verification should check those requirements against the finished phase, not this plan alone.
- No blockers.

## Self-Check: PASSED

- Files: all 12 created files found; `services/mcp_server/.gitkeep` absent as intended.
- Commits: `1ac65e8`, `0490bff`, `cb35969` are ancestors of HEAD.

---
*Phase: 02-mcp-server-and-skill*
*Completed: 2026-11-06*
