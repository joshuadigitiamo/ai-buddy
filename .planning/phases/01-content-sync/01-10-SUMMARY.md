---
phase: 01-content-sync
plan: 10
subsystem: sync
tags: [cleanup, docs, gap-closure, local-source, tracer, requirements]

requires:
  - phase: 01-09
    provides: local handbook folder source, handbook:// citation, token-free configuration
provides:
  - "Job, tests, pins and image with no task-tracker adapter, fixture or HTTP client dependency"
  - "jobs/sync/README.md for local-source runs (HANDBOOK_DIR, REDACT_PAGE_FILES, read-only mounts, no network)"
  - "docs/index-format.md handbook_pages contract for the local folder, with the 1.0.0 amendment in the changelog"
  - "COVERAGE.md with every former API capability recorded as OPT-OUT by D-25"
  - "REQUIREMENTS SYNC-01/02/05 and ROADMAP Phase 1 goal and criteria 2-3 reworded for local sources"
affects: [01-11, phase-02, phase-05]

plan_head_before: 91b3a9f7c0b5ae04d6cd2288031351d096cf8116
plan_head_after: 36fc03f90608669e9abba5802f0ce547c0119909

actuals:
  tokens: 3100
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Delete rather than flag: the retired adapter and its dependency are removed, history stays in git"
    - "Documents state the source of every stored column (RAG guide s.6: capture metadata at load time)"

key-files:
  created: []
  modified:
    - requirements.txt
    - tests/unit/buddy_sync/test_corpus_local.py
    - jobs/sync/README.md
    - docs/index-format.md
    - .planning/phases/01-content-sync/COVERAGE.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
  deleted:
    - jobs/sync/buddy_sync/clickup.py
    - tests/unit/buddy_sync/test_clickup_client.py
    - tests/fixtures/clickup/pages.json

key-decisions:
  - "revision_date_iso is documented as the full ISO-8601 UTC datetime that handbook.revision_date_iso produces (for example 2026-11-03T00:00:00+00:00), not a bare date: the old YYYY-MM-DD wording did not match the code"
  - "Format change recorded as an amendment of 1.0.0 (DDL unchanged, schema_version stays 1.0.0), valid because no consumer or artifact had been published"

requirements-completed: [SYNC-07]

coverage:
  - id: D1
    description: "Retired adapter, its unit test, fixture and HTTP client pin are gone; rebuilt image passes the whole suite and the end-to-end run"
    requirement: SYNC-01
    verification:
      - kind: e2e
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_end_to_end"
        status: pass
      - kind: command
        ref: "./run-unit-tests.sh --all (317 passed, 7 skipped, coverage 97.25%)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Operator README documents the seven SyncSettings variables, the handbook folder format, handbook:// citation and no-network run; names no tracker variable"
    requirement: SYNC-05
    verification:
      - kind: command
        ref: "plan Task 2 greps: tracker name 0, HANDBOOK_DIR 2+, handbook:// 1+, list-pages/_TOKEN 0, every README table variable is a SyncSettings field"
        status: pass
    human_judgment: true
    rationale: "Whether an operator can run the sync from the README alone is a readability judgment; a live run needs the local handbook and Guides mounts and was not part of this plan"
  - id: D3
    description: "index-format.md states the amended handbook_pages and source_doc_id meaning and records the 1.0.0 amendment"
    requirement: SYNC-05
    verification:
      - kind: command
        ref: "plan Task 2 greps: handbook:// 2+, local-handbook 1+, amended 2026-11-03 1+, source tool 0"
        status: pass
    human_judgment: false
  - id: D4
    description: "SYNC-01, SYNC-02, SYNC-05 and ROADMAP Phase 1 text describe local sources, with every checkbox and status unchanged"
    requirement: SYNC-02
    verification:
      - kind: command
        ref: "plan Task 3 greps incl. checkbox/ID-list equality against HEAD"
        status: pass
    human_judgment: false

duration: 2 min of measured command time (clock started after plan load)
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 10: Retire the Tracker Adapter and Align Contract Documents Summary

**Deleted the retired tracker adapter, its test, fixture and HTTP client pin (suite green in the rebuilt image, 317 passed), then rewrote the operator README, index format contract, coverage note and SYNC-01/02/05 plus ROADMAP Phase 1 wording for the local handbook folder and the handbook:// citation.**

## Performance

- **Duration:** about 2 min of measured command time (the clock started after reading the plan)
- **Completed:** 2026-11-03
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files changed:** 10 outside the SUMMARY (7 modified, 3 deleted; 62 insertions, 626 deletions outside `.planning/`)

## Accomplishments

- Tracer: `git rm` of the adapter module, its unit test and its fixture; `httpx` pin removed; image rebuilt from the remaining pins; full suite and `test_end_to_end` pass; no tracker name in code, pins, `pyproject.toml` or `.env.example`; no HTTP client anywhere.
- README rewritten for local runs: seven variables (all `SyncSettings` fields), "Handbook folder" section (front matter keys, page id = file stem, `handbook://<page id>`), `--network none` shorthand with read-only handbook and Guides mounts, exit-code examples for folder errors, stale-`.env` note (T-01-44).
- `docs/index-format.md`: every `handbook_pages` column states its source; `source_doc_id` = `local-handbook`; "Not indexed" updated; changelog line "1.0.0 amended 2026-11-03".
- `COVERAGE.md`: no external API in Phase 1; all eight capability rows OPT-OUT with the D-25 reason; Guides note says the clone source is a local path.
- REQUIREMENTS SYNC-01/02/05, scope line and footer, and ROADMAP overview, list line, Phase 1 goal, criteria 2 and 3 reworded; all statuses untouched.

## Task Commits

1. Task 1 (tracer): `69314ef` chore - remove retired tracker adapter, its test, fixture and HTTP client pin
2. Task 2: `5f07885` docs - operator README, index format and coverage note for local sources
3. Task 3: `36fc03f` docs - reword SYNC-01/02/05 and Phase 1 roadmap for local sources

Tracer gate: `<verify>` is automated-only and `HUMAN_VERIFY_MODE` is end-of-phase, so the full suite and the end-to-end test were re-run before expansion (317 passed, 7 skipped; `test_end_to_end` 1 passed); no checkpoint.

## Verification

- `./run-unit-tests.sh --all` (final run after Task 2): ruff check, ruff format --check and mypy clean; **317 passed, 7 skipped, 0 failed**; coverage 97.25% (gate 80%). The drop from 335 is the 18 tests of the deleted adapter test module. The 7 skips are the local-only Guides checkout tests (`GUIDES_LOCAL_DIR` unset).
- `--single test_sync_e2e.py test_end_to_end tests/unit/buddy_sync`: 1 passed.
- Task 1 gates: tracker-name grep over code, pins, `pyproject.toml`, `.env.example` = 0; HTTP client grep = 0; tests naming the tracker outside `test_redaction.py` = 0; deleted paths absent; `^httpx` in `requirements.txt` = 0.
- Task 2 gates: all four plan greps pass; `REDACT_PAGE_FILES` appears on 3 README lines; every README table variable is a field in `config.py`.
- Task 3 gates: all three plan checks pass (including requirement ID and checkbox list equal to HEAD); `D-25..D-27 scope change` 1 hit; `local handbook snapshot` 3 hits in ROADMAP.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replacement comment exceeded the line-length limit**
- **Found during:** Task 1 (ruff E501 in the first `--all` run)
- **Issue:** the comment text prescribed for `WIFI_FILE` ("file-based too (REDACT_PAGE_FILES, D-25)") made the line 113 characters (limit 100).
- **Fix:** shortened to `# local test only; production denylist is file-based (D-25)`; the meaning (file-based instead of id-based) is unchanged. Two intermediate attempts were still too long and were rerun.
- **Files modified:** tests/unit/buddy_sync/test_corpus_local.py
- **Commit:** 69314ef

**2. [Rule 1 - Bug] index-format wording for `revision_date_iso` did not match the code**
- **Found during:** Task 2 (plan told to read the helper)
- **Issue:** document said `YYYY-MM-DD`; `handbook.revision_date_iso` returns a full ISO-8601 UTC datetime.
- **Fix:** documented the actual format with an example.
- **Files modified:** docs/index-format.md
- **Commit:** 5f07885

**3. [Rule 3 - Blocking] Plan gate needed a second `handbook://` line in the format document**
- **Found during:** Task 2 verification (`grep -c` counts lines; only the `url` row had it)
- **Fix:** added one sentence with the citation form and an example to the handbook_pages introduction.
- **Files modified:** docs/index-format.md
- **Commit:** 5f07885

### Already done by plan 01-09

Step 3 of Task 1 (package docstring) was already in place from plan 01-09, so no edit was needed.

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking). **Impact:** none on scope or behaviour.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None. T-01-44 (stale `.env`) is mitigated by the README note; T-01-45 by documenting keys and shapes only (no page title, value or tracker id copied); T-01-SC: no package added, one pin removed.

## Issues Encountered

None open. The 01-08 plan still has no SUMMARY (incomplete, not part of this gap closure).

## Requirements Tracking

The plan declares SYNC-01, SYNC-02, SYNC-03, SYNC-05, SYNC-07 and GUIDE-01. `requirements.ready-ids` returned only SYNC-07 as ready; the other five are also declared by plan 01-11 (which has no SUMMARY yet), so under the shared-ID gate they are not marked by this plan. SYNC-07 already read Complete, so marking it changes nothing. No checkbox or status was altered by this plan's wording edits.

## Next Phase Readiness

Ready for 01-11 (live local run and verification). No tracker code, token, variable or dependency remains in the job; documents match the code.

## Self-Check: PASSED

Deleted files absent (clickup.py, test_clickup_client.py, tests/fixtures/clickup); modified files present; commits 69314ef, 5f07885, 36fc03f are ancestors of HEAD; measured commit count 3 from the recorded ledger.
