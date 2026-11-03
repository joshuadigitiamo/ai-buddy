---
phase: 01-content-sync
plan: 07
subsystem: sync
tags: [pipeline, cli, argparse, idempotency, end-to-end, atomic-publish, tracer]

requires:
  - phase: 01-02
    provides: IndexContent, compute_content_hash, build_index, open_index, LocalDirArtifactStore, video_link
  - phase: 01-03
    provides: SyncSettings, ConfigError, Redactor, REDACTION_VERSION
  - phase: 01-04
    provides: ClickUpClient, flatten_pages, sync_handbook, EmptyDenylistError, EmptyHandbookError
  - phase: 01-05
    provides: GitGuidesSource, sync_guides, check_guides_index, write_guides_index, heading_outline, PIPELINE_VERSION
  - phase: 01-06
    provides: resolve_video_links, VideoMapError
provides:
  - "buddy_sync.pipeline: SyncReport (to_json), run_sync"
  - "buddy_sync.cli: main(argv, *, transport, now) with run, list-pages, guides-index, search"
  - "python -m buddy_sync entry point"
  - "jobs/sync/README.md: operator documentation (env vars, Docker commands, local Guides dev setup, exit codes)"
affects: [01-08, phase-02, phase-03]

plan_head_before: ee75d56ce2ae33191af3bdd0ddf3e684c6155ee5
plan_head_after: bf378c37dd07ef5e418050078baa00a88156b843

actuals:
  tokens: 8350
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Hexagonal wiring: run_sync takes GuidesSource, ArtifactStore and an injectable-transport ClickUpClient; the CLI is the only place real adapters are built"
    - "Idempotent publish: content hash compared with the previous meta before any build; staged file discarded on any exception"
    - "CLI hygiene: stdout carries counts, ids, redacted titles or source locations only; errors are one ERROR line naming variables, never values"

key-files:
  created:
    - jobs/sync/buddy_sync/pipeline.py
    - jobs/sync/buddy_sync/cli.py
    - jobs/sync/buddy_sync/__main__.py
    - tests/unit/buddy_sync/test_sync_e2e.py
    - tests/unit/buddy_sync/test_cli.py
    - jobs/sync/README.md
  modified: []

key-decisions:
  - "The previous artifact is closed in a finally before the build starts; only IndexVersionError makes it count as absent (WARNING, full rebuild), other format errors surface"
  - "CLI maps OSError and sqlite3.Error (build and publish failures) to the one-ERROR-line, exit 1 path in addition to the plan's list, so a disk failure never produces a traceback"
  - "pydantic ValidationError is rendered as 'invalid or missing environment variables: NAMES', never with input values"
  - "The buddy_sync logger gets a per-call stderr handler that is removed in a finally, with propagation kept on, so repeated main() calls do not stack handlers and pytest caplog still sees records"
  - "list-pages marks denylisted pages with [denied] and still prints their (redacted) title, so the operator can identify the Wi-Fi page id"
  - "guides_index_drift is 0 when Guides were not rebuilt (the drift check runs only on a rebuild, as the plan orders)"

requirements-completed: [SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-06, SYNC-07, GUIDE-01]

coverage:
  - id: D1
    description: "`main(['run'])` on fixtures fetches the mock ClickUp doc, syncs a fixture Guides repo, resolves video links and publishes index.db; the JSON report has artifact_written true; every loaded page has a deep link under https://app.clickup.com/123/v/dc/demo-doc/, a title and a revision date; the denylisted page id and the synthetic secrets are absent from every artifact byte"
    requirement: SYNC-01
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
    human_judgment: false
  - id: D2
    description: "`search chunking` returns the DEMO_GUIDE chunk as file:line range with its video link ending #t=30 (ROADMAP criteria 2 and 4); search output lines carry location, 'h2 > h3' and link"
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_search_lines_carry_location_headings_and_video_link"
        status: pass
    human_judgment: false
  - id: D3
    description: "Idempotency (D-09, D-10, D-24): a second run with unchanged inputs reports pages_processed 0, guides_rebuilt false, artifact_written false and leaves index.db byte-identical; changing only ClickUp's date_updated reprocesses nothing; editing one page reprocesses exactly that page and writes a new artifact"
    requirement: SYNC-02
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
    human_judgment: false
  - id: D4
    description: "A failing build (partial staged file, then OSError) makes run return 1, leaves the previous index.db byte-identical and no .index.*.tmp file; the next run with the failure gone publishes (SYNC-04 concurrency edge, end to end)"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
    human_judgment: false
  - id: D5
    description: "Exit codes and guards: no or unknown subcommand returns 2; empty REDACT_PAGE_IDS returns 1 naming it (and 0 with --allow-empty-denylist); missing CLICKUP_TOKEN returns 1 naming it; an invalid CLICKUP_DOC_ID is named without echoing its value"
    requirement: SYNC-07
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_no_subcommand_and_unknown_subcommand_return_2"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_run_with_empty_denylist_fails_and_names_the_variable"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_run_with_empty_denylist_succeeds_when_allowed"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_run_without_token_fails_and_names_the_variable"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_run_with_invalid_settings_names_the_variable_not_its_value"
        status: pass
    human_judgment: false
  - id: D6
    description: "--strict exits 1 on GUIDES_INDEX.md drift and publishes nothing; without it the run exits 0, logs a `guides_index drift` WARNING and the report shows guides_index_drift >= 1 (D-23)"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_strict_fails_on_guides_index_drift_and_lenient_run_logs_it"
        status: pass
    human_judgment: false
  - id: D7
    description: "list-pages prints `<id>\\t<indented redacted title>` per page with [denied] on denylisted ids and none of the synthetic body secrets; guides-index writes a GUIDES_INDEX.md that parse_guides_index reads back with every heading and needs no CLICKUP_* variables; search accepts punctuation, reads ARTIFACT_DIR, and a missing artifact returns 1 with an ERROR line"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_list_pages_prints_ids_and_redacted_titles_only"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_guides_index_writes_a_file_the_parser_reads_back"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_search_accepts_punctuation_and_reports_a_missing_artifact"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_search_uses_artifact_dir_from_environment"
        status: pass
    human_judgment: false
  - id: D8
    description: "Prohibition SYNC-03: the synthetic ClickUp token never appears in stdout, stderr or captured logs of any CLI call (asserted inside the test helper on every invocation and again at the end of the e2e test)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py (every test via the Cli helper)"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
    human_judgment: false
  - id: D9
    description: "jobs/sync/README.md documents every env var by name, the Docker commands for run, list-pages, guides-index and search, the /guides-src local-Guides dev setup, exit codes and the never-commit warning; whether it reads clearly to an operator is a review judgment"
    requirement: GUIDE-01
    verification:
      - kind: command
        ref: "grep -qF for 'python -m buddy_sync run', list-pages, guides-index, search, REDACT_PAGE_IDS, /guides-src in jobs/sync/README.md"
        status: pass
    human_judgment: true
    rationale: "The required terms are mechanically checked; clarity and completeness for an operator is a judgment. The Guides-applied table (idempotent pipelines, ports and adapters, source-carrying retrieval output) is in the plan itself"

duration: ~25min
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 07: Sync Pipeline and CLI Summary

**`run_sync` wires the handbook, Guides and video-map pieces into one idempotent run that publishes a redacted, searchable `index.db` atomically (unchanged content writes nothing, a failed build leaves the last artifact untouched), exposed through `python -m buddy_sync run | list-pages | guides-index | search` and documented for Docker operation in `jobs/sync/README.md`.**

## Performance

- **Duration:** ~25 min (2026-11-03, ended 19:45Z)
- **Tasks:** 2 (Task 1 tracer, Task 2 tdd)
- **Files:** 6 created (pipeline, cli, `__main__`, two test files, README); `./run-unit-tests.sh --all`: ruff, ruff format, mypy strict clean, 308 passed, coverage 97.5% (`cli.py` 100%, `pipeline.py` 97%)

## Accomplishments

- Tracer verified end to end through the real CLI on fixtures: the first run publishes; `search chunking` prints `AI-Engineering/DEMO_GUIDE.md:<start>-<end>  1. Basics > Chunking  https://videos.example.invalid/demo.mp4#t=30`; the artifact contains none of the denylisted page id or synthetic secrets; the second run, a timestamp-only change, one edited page and a failed build all behave as ROADMAP criteria 2 to 4 require (`test_end_to_end`).
- `run_sync` order as planned: denylist guard before any network call, previous artifact opened (a different schema major counts as absent), `versions_match` from pipeline and redaction versions, handbook, Guides, video links (resolved on rebuild, reused otherwise), drift check on rebuild, content hash compared with the previous meta before any file is touched, stage then publish, discard on any exception.
- `cli.py` builds all real adapters in one place; `run`, `list-pages`, `guides-index`, `search` with exit codes 0, 1 and 2; every failure is one `ERROR` line naming variables, never values; `httpx` and `httpcore` loggers pinned to WARNING.
- `jobs/sync/README.md`: 12 env vars by name, Docker commands for each subcommand (network only for `run` and `list-pages`), local Guides at `/guides-src`, how to find the Wi-Fi page id, exit codes, never-commit warning.

## Task Commits

1. **Task 1: Tracer, `run` and `search` end to end on fixtures** - `a5986f5` (feat)
2. **Task 2: CLI tests** - `99b5973` (test)
3. **Task 2: Operator README** - `bf378c3` (docs)

**Plan metadata:** committed separately (docs: complete plan).

`commits: 3` is the measured `git rev-list --count ee75d56..HEAD` and equals the three task commits.

## TDD Gate Compliance

Task 2 is a task-level `tdd="true"` task inside a `type: execute` plan; `workflow.tdd_mode` is not enabled and the `check tdd-red-evidence` classifier has no pytest adapter, so it was not run (same as plans 01-02 to 01-06).

- **RED:** not observed. All 11 new `test_cli.py` tests passed on their first run, because the tracer commit `a5986f5` already contained `list-pages`, `guides-index`, `--strict` and `--allow-empty-denylist` (see Deviation 1). To compensate for the missing RED, one mutation check was run: removing the `[denied]` marker from `list-pages` made `test_list_pages_prints_ids_and_redacted_titles_only` fail (1 failed); the change was then reverted with `git checkout -- jobs/sync/buddy_sync/cli.py` and nothing was committed from it.
- **GREEN:** there is no separate `feat` commit for Task 2; the single `test(01-07)` commit pins the behaviour that already existed.
- No REFACTOR commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Process] Task 2 subcommands implemented during Task 1**
- **Found during:** Task 1
- **Issue:** the plan scopes Task 1's `cli.py` to `run` and `search`, and Task 2 to `list-pages`, `guides-index` and the two `run` flags. I wrote the whole CLI in one pass, so the Task 1 commit already carries the Task 2 code and Task 2 had no failing-test step.
- **Fix:** documented above; Task 2's tests were written to the Task 2 behaviour list and verified by mutation. No interface or behaviour differs from the plan.
- **Files modified:** `jobs/sync/buddy_sync/cli.py`
- **Commit:** `a5986f5`

**2. [Rule 2 - Missing critical] CLI catches OSError and sqlite3.Error**
- **Found during:** Task 1 (the e2e failure case requires `run` to return 1 when the build raises)
- **Issue:** the plan's list of exceptions mapped to exit 1 had no entry for a build or publish failure such as a full disk, which would have ended in a traceback and no clean ERROR line.
- **Fix:** `OSError` and `sqlite3.Error` added to the mapped exceptions (the second also covers a corrupt previous artifact), plus `IndexFormatError` for an unreadable artifact on `search`/`run`.
- **Files modified:** `jobs/sync/buddy_sync/cli.py`
- **Commit:** `a5986f5`

**3. [Process] Formatting and typing**
- ruff F401 (unused import) and mypy findings in the new e2e test (shadowed loop variable, `pipeline.build_index` not re-exported) were fixed before the first commit; formatting run inside the test image (`ruff format`; the runner only has `--check`).

**4. [Process] Commits on protected branch `main`**
- As instructed (sequential executor, `branching_strategy=none`); nothing pushed, no branch created.

**Total deviations:** 1 auto-fixed (missing-critical), 3 process notes. **Impact:** none on interfaces or scope; TDD RED not observable for Task 2 (see above).

## Authentication Gates

None. No live ClickUp call and no live sync were made; fixtures and an `httpx.MockTransport` only. The real Guides repo was not touched.

## Issues Encountered

None remaining.

## Known Stubs

None.

## Threat Flags

None. T-01-30 (no content on stdout: ids, redacted titles, counts, locations only; token-absence asserted on every CLI call), T-01-31 (`httpx` and `httpcore` at WARNING), T-01-32 (README warns, `artifacts/` and `*.db` already gitignored by plan 01) and T-01-33 (discard on exception; e2e keeps the previous artifact byte-identical) are mitigated with tests; T-01-SC: no packages installed.

## Next Phase Readiness

Ready for 01-08 (live run against the real sources). Notes for plan 08:

- The one-shot inputs are `.env` (real `CLICKUP_TOKEN`, `CLICKUP_WORKSPACE_ID`, `REDACT_PAGE_IDS`) and either the real Guides URL or the local checkout mounted at `/guides-src`; `list-pages` finds the Wi-Fi page id before the first `run`.
- `run` refuses an empty `REDACT_PAGE_IDS`; do not use `--allow-empty-denylist` for the real doc.
- `GUIDES_INDEX.md` in the real Guides repo must be generated with `guides-index --checkout` and committed there before `run --strict` can pass; a first non-strict run reports drift as a WARNING and `guides_index_drift` in the JSON.
- Guides drift is only checked when the Guides are rebuilt (new commit or version change); a repeat run on an unchanged commit reports `guides_index_drift` 0.

## Self-Check: PASSED

- All 6 created files exist; commits `a5986f5`, `99b5973`, `bf378c3` are ancestors of HEAD; `git rev-list --count ee75d56..HEAD` = 3.
- Acceptance greps: `compute_content_hash` in pipeline.py 2, `store.discard` 1, `raise SystemExit(main())` 1; `python -m buddy_sync --help` in the `ai-buddy-test` container exits 0 and lists `run` and `search`; `def test_` in test_cli.py 11 (>= 9); README contains all six required terms; README lines matching `^(CLICKUP_TOKEN|GUIDES_REPO_TOKEN)=.+` 0.
- `./run-unit-tests.sh --all` exit 0 (308 passed, coverage 97.5%); `--single test_sync_e2e.py test_end_to_end tests/unit/buddy_sync` 1 passed; `--single-file test_cli.py tests/unit/buddy_sync` 11 passed.
