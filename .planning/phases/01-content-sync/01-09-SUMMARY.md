---
phase: 01-content-sync
plan: 09
subsystem: sync
tags: [handbook, local-source, markdown, front-matter, denylist, citation-uri, tdd, tracer, gap-closure]

requires:
  - phase: 01-04
    provides: sync_handbook incremental transform, EmptyDenylistError, EmptyHandbookError, revision_date_iso
  - phase: 01-07
    provides: run_sync, SyncReport, CLI, end-to-end test scenario
provides:
  - "buddy_sync.handbook_files: read_handbook_dir, SourcePage, HandbookFiles, HandbookFilesError, citation_uri, SOURCE_ID, CITATION_PREFIX, PAGE_FILE_RE"
  - "sync_handbook(pages, *, previous, versions_match, redactor, logger) over local pages; HandbookSyncResult without seen/denied/skipped_archived"
  - "run_sync and CLI without a tracker client; subcommands run, guides-index, search"
  - "SyncSettings with handbook_dir and redact_page_files (bare .md names); no token, no tracker variable"
  - "Handbook citation scheme handbook://<page_id>, page_id = file stem"
  - "Synthetic handbook fixtures tests/fixtures/handbook/ (4 pages, one denylisted)"
affects: [01-10, 01-11, phase-02, phase-03, phase-05]

plan_head_before: 6979f60132274e2ea777ba8bffe48e087affd32e
plan_head_after: 94cded8fa0e194ed094e5438e9e093a16852fddb

actuals:
  tokens: 19400
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Adapter / anti-corruption layer: read_handbook_dir turns a Markdown folder into SourcePage rows; only title, last_updated, date_created cross the boundary"
    - "Fail-closed denylist: entries must name an existing page file; a denylisted file is counted but never opened"
    - "Error hygiene: messages carry file names, key names and exception class names, never file content (YAML errors reduced to their class, raised from None)"

key-files:
  created:
    - jobs/sync/buddy_sync/handbook_files.py
    - tests/fixtures/handbook/01-benvenuto.md
    - tests/fixtures/handbook/02-ferie.md
    - tests/fixtures/handbook/03-accesso-ufficio.md
    - tests/fixtures/handbook/04-rete-ospiti.md
    - tests/unit/buddy_sync/test_handbook_files.py
  modified:
    - jobs/sync/buddy_sync/handbook.py
    - jobs/sync/buddy_sync/pipeline.py
    - jobs/sync/buddy_sync/config.py
    - jobs/sync/buddy_sync/cli.py
    - jobs/sync/buddy_sync/__init__.py
    - tests/unit/buddy_sync/test_sync_e2e.py
    - tests/unit/buddy_sync/test_handbook_sync.py
    - tests/unit/buddy_sync/test_redaction_pipeline.py
    - tests/unit/buddy_sync/test_cli.py
    - tests/unit/buddy_sync/test_config.py
    - tests/unit/test_repo_layout.py
    - .env.example

key-decisions:
  - "Citation is handbook://<page_id> with page_id = file name without .md (rated costly in the plan; no consumer or published artifact exists yet)"
  - "Denylist variable is REDACT_PAGE_FILES holding bare file names; every entry must name a *.md file in HANDBOOK_DIR, so a typo or stale tracker-era id fails the run instead of letting a page through"
  - "Handbook pages are flat (parent_id None, depth 0) in file-name order"
  - "index.db schema stays 1.0.0 (DDL unchanged; no artifact was ever published)"
  - "Symlinks are only checked for non-denylisted files, so a denylisted file is touched by nothing but the directory listing"
  - "Commits were made on branch gsd/phase-01-content-sync, not main: the commit guard treats main as protected and git.allow_default_branch_commits is unset"

patterns-established:
  - "TDD per task: test commit (RED, failures recorded) then feat commit (GREEN)"
  - "Secret-shaped assertions compare booleans ((literal in blob) is False) so a failure never prints a secret"

requirements-completed: [SYNC-01, SYNC-02, SYNC-03, SYNC-05, GUIDE-01]

coverage:
  - id: D1
    description: "python -m buddy_sync run reads a local handbook folder and publishes index.db with handbook://<page_id> citations, titles and revision dates in file-name order"
    requirement: SYNC-01
    verification:
      - kind: e2e
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
    human_judgment: false
  - id: D2
    description: "A REDACT_PAGE_FILES file is never opened and leaves no byte in index.db or the manifest; empty list refused; unknown entry fails the run"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_files.py#test_denylisted_file_is_never_opened"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_files.py#test_denylist_entry_naming_no_file_fails_closed"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction_pipeline.py#test_denylisted_file_absent"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_run_with_empty_denylist_fails_and_names_the_variable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Re-run and mtime-only change process 0 pages; one edit processes 1; date_edited wins over update date"
    requirement: SYNC-02
    verification:
      - kind: e2e
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_handbook_files.py#test_export_string_form_gives_the_date_edited_value"
        status: pass
    human_judgment: false
  - id: D4
    description: "Sync configuration holds no task-tracker variable and no token; .env.example holds exactly seven keys"
    requirement: SYNC-05
    verification:
      - kind: unit
        ref: "tests/unit/test_repo_layout.py#test_env_example_holds_exactly_the_contract_keys"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_config.py#test_settings_hold_exactly_the_documented_fields"
        status: pass
    human_judgment: false
  - id: D5
    description: "Legacy front-matter keys (ids, source URLs) never reach the artifact"
    requirement: SYNC-03
    verification:
      - kind: e2e
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 09: Local Handbook Source Summary

**Sync job now builds the handbook snapshot from a read-only local Markdown folder (front-matter adapter, per-file denylist that is never opened, handbook://<page_id> citations) with no token and no network client; full suite 335 passed, 7 skipped.**

## Performance

- **Duration:** about 45 min (start time not recorded at launch; estimate)
- **Completed:** 2026-11-03
- **Tasks:** 3 (1 tracer, 2 TDD)
- **Files changed:** 18 (765 insertions, 537 deletions, outside `.planning/`)

## Accomplishments

- Tracer: fixture folder to `index.db` through `python -m buddy_sync run`, searchable, byte-stable on re-run, mtime ignored, one edit reprocesses exactly one page, failed build keeps the previous artifact.
- `handbook_files.read_handbook_dir`: sorted `*.md` regular files, `yaml.safe_load` front matter, revision date = `date_edited` (the `YYYY-MM-DD (date_edited YYYY-MM-DD)` form resolves to the inner date), unknown keys dropped at read time.
- Fail-closed loader: denylist entries must exist, file names must match `PAGE_FILE_RE`, symlinks may not leave the folder, root must be a directory, YAML errors reduced to their class name.
- Config, `.env.example` and CLI are token-free: `SyncSettings` has seven fields, `list-pages` is gone (exit 2), `GitGuidesSource` is built with `token=None`.

## Task Commits

1. Task 1 (tracer): `0021634` feat - local handbook folder to index.db with handbook:// citations
2. Task 2 (TDD): `88d4d07` test (RED, 6 loader cases failing) then `1953d56` feat (GREEN, 25/25)
3. Task 3 (TDD): `8080539` test (RED, 11 failing parametrised cases) then `94cded8` feat (GREEN, suite green)

Tracer gate: `<verify>` carried only an automated command and HUMAN_VERIFY_MODE is end-of-phase, so it was re-run end to end (1 passed) before expansion; no checkpoint.

## TDD Gate Compliance

Task 2 and Task 3 each have a `test(01-09)` commit that failed on the behaviours listed above before the `feat(01-09)` commit that made it pass. Task 1 is a tracer and follows the tracer rules. Note: the Task 1 loader was deliberately minimal (no PAGE_FILE_RE, existence check, symlink check, root check, YAML hygiene) so that Task 2's RED was real; the YAML error text leaked the offending line between commits 0021634 and 1953d56 only (never released).

## Verification

- `./run-unit-tests.sh --all`: ruff check, ruff format --check, mypy strict clean; **335 passed, 7 skipped, 0 failed**; coverage 97.31% (gate 80%). The 7 skips are the pre-existing local-only Guides checkout tests (`GUIDES_LOCAL_DIR` unset).
- `--single test_sync_e2e.py test_end_to_end`: 1 passed. `test_handbook_files.py`: 25 passed. `test_handbook_sync.py`: 14 passed. `test_redaction_pipeline.py`: 2 passed.
- Plan greps: no tracker name or retired variable/HTTP client in the run path and `.env.example` (0 matches); ported tests name the tracker nowhere outside the allowed exceptions (0 files); acceptance counts all met (`read_handbook_dir` 1, `source_doc_id=SOURCE_ID` 1, `citation_uri(page.page_id)` 1, fixtures 4, `PAGE_FILE_RE` 3, tests in loader file 21, `HANDBOOK_DIR=/handbook` 1, `_TOKEN=` 0, `redact_page_files` 4).
- As planned, between the Task 1 and Task 3 commits the five tracker-shaped test modules failed by design (mypy and pytest); each was ported by Task 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test used a parameter that is a substring of the error text**
- **Found during:** Task 3 GREEN run
- **Issue:** `test_page_file_entries_must_be_bare_md_names[a]` asserted the entry `a` is absent from the message; `a` occurs in any English sentence.
- **Fix:** entry renamed `plainname`.
- **Files modified:** tests/unit/buddy_sync/test_config.py
- **Commit:** 94cded8

**2. [Rule 3 - Blocking] Test text named the retired tracker**
- **Found during:** Task 3 verification greps
- **Issue:** a field-name check in test_config.py contained the tracker name, tripping the plan's "no ported test names the tracker" gate.
- **Fix:** replaced with an exact-field-set assertion (`test_settings_hold_exactly_the_documented_fields`), which is stricter.
- **Files modified:** tests/unit/buddy_sync/test_config.py
- **Commit:** 94cded8

**3. [Rule 2 - Missing critical] Package docstring named the retired tracker**
- **Found during:** Task 1
- **Issue:** `buddy_sync/__init__.py` docstring still described a tracker handbook.
- **Fix:** docstring now says local handbook folder.
- **Files modified:** jobs/sync/buddy_sync/__init__.py
- **Commit:** 0021634

### Environment adjustment (not a plan deviation)

The working tree was on `main`, which the executor commit guard treats as protected (`git.base-branch --is-protected main` returned true, no override configured). Configuration was not changed. A branch `gsd/phase-01-content-sync` was created from `main` HEAD `6979f60` and all commits live there; merging back to `main` is a fast-forward. The orchestrator must merge or fast-forward that branch.

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing-critical). **Impact:** none on scope or behaviour.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None. All new surface (a local folder read) is covered by T-01-39 to T-01-42; T-01-43 accepted as planned.

## Issues Encountered

None open. `.planning/STATE.md` and `.planning/state.json` carried uncommitted orchestrator edits at start; they are committed with the tracking update, not with task commits.

## Next Phase Readiness

Ready for 01-10 (delete the retired tracker module, test and fixture; record the amended column meanings in the format changelog; docs) and 01-11. Interfaces named in the plan are in place with the binding signatures.

## Self-Check: PASSED

Created files exist (handbook_files.py, four fixtures, test_handbook_files.py); commits 0021634, 88d4d07, 1953d56, 8080539, 94cded8 are ancestors of HEAD; measured commit count 5 from the recorded ledger.
