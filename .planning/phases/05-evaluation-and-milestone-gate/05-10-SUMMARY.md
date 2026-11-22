---
phase: 05-evaluation-and-milestone-gate
plan: 10
subsystem: evaluation-empty-context
tags: [eval, empty-context, fixture, compose, gap-log, EVAL-04, D-16]
requires:
  - phase: 05-06
    provides: compose eval profile (mlflow, eval, eval-empty mount point in the eval image)
  - phase: 05-07
    provides: ResultCache, key_for, bot_version, SourceIndex identity
  - phase: 05-08
    provides: report.write_json_report, TraceSink score pattern
  - phase: 05-09
    provides: cli subcommand pattern, _recall_items selection of approved handbook and guides items
provides:
  - "`python -m buddy_eval build-fixture --dest DIR`: reproducible fixture index from committed sources"
  - "`python -m buddy_eval empty-context [--item ID]...`: every approved handbook and guides item through the real bot over the fixture server; PASS only when all are refused or referred with a logged gap"
  - EmptyContextItem, EmptyContextResult, run_empty_context, count_gap_documents, format_empty_context in empty_context.py
  - build_fixture_content, build_fixture, FIXTURE_NOW, FixtureError in fixture.py
  - compose services eval-fixture and mcp-server-empty, volume eval-empty
affects: [05-11, 05-12]
tech-stack:
  added: []
  patterns: [committed sources built into an index at start-up instead of a committed .db, a counting connector wrapper to expose evidence counts without text, per-scorer-set feedback on one TraceSink, fresh-items-only emulator cross-check]
key-files:
  created:
    - jobs/eval/buddy_eval/fixture.py
    - jobs/eval/buddy_eval/empty_context.py
    - jobs/eval/fixtures/empty_context/fixture.yaml
    - tests/unit/buddy_eval/test_fixture.py
    - tests/unit/buddy_eval/test_empty_context.py
  modified:
    - jobs/eval/buddy_eval/cli.py
    - jobs/eval/buddy_eval/config.py
    - jobs/eval/buddy_eval/tracing.py
    - docker-compose.yml
    - tests/unit/test_compose.py
    - tests/unit/buddy_eval/conftest.py
    - tests/unit/buddy_eval/test_tracing_adapter.py
decisions:
  - "Verdict precedence: a definite failure (answered, smalltalk, no_gap, gap count mismatch) prints FAIL and appends any errored ids to the same line; INCOMPLETE is printed only when the sole problem is errored items"
  - "evidence=<n> is the number of search results the run's handbook_search and guides_search calls returned, counted by a connector wrapper, so a fixture overlap is visible even when the bot refused (A-10-3)"
  - "Cross-check outcome strings: `gap cross-check ok (<d> documents for <n> gap_reported replies)`, `gap count mismatch (...)`, `gap cross-check skipped (FIRESTORE_EMULATOR_HOST unset | no fresh items | emulator unreadable: <ExceptionType>)`. Only fewer documents than fresh gap_reported replies fails; more is accepted; with zero fresh gaps nothing is compared"
  - "A gap_reported reply still stands when the emulator cannot be read: the cross-check is skipped with its reason, never silently counted as ok"
  - "Cached items keep their status (answered, no_gap and smalltalk are cached too, so a second run gives the same verdict); only errored items are never cached"
  - "`build-fixture` runs before EvalSettings is built, so the env-less eval-fixture container needs no settings; FixtureError is an expected error with one ERROR line"
  - "TraceSink.score gained `scorers: Literal['run','empty_context']`; the empty-context set (feedback `refused`) has its own scored-cache version `empty-1`, independent of SCORER_SET_VERSION"
  - "Zero selected items prints only `empty_context: FAIL (no approved answerable items)` and opens neither the fixture index nor an MLflow run"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 23000
  tasks: 3
  commits: 3
plan_head_before: 6c690096aae56fd9ec378d15112823d5ec3541da
plan_head_after: c83fc65a6c5d0c984085875dd5092ab7572a6299
---

# Phase 5 Plan 10: Empty-context test (EVAL-04) Summary

`empty-context` runs every approved handbook and Guides item through the real bot against a second MCP server over an unrelated fixture index (mycology in Italian, celestial mechanics in English), and prints PASS only when each reply is a refusal or referral with a logged gap.

## What was built

**Task 1 (c74a36b): fixture sources and builder**
- `fixture.yaml`: 2 handbook pages and 3 Guides chunks written as term lists without function words; no office, HR, software or Guides vocabulary.
- `fixture.py`: `build_fixture_content` parses and validates the YAML (`FixtureError` names the field), `build_fixture` stages, builds and publishes through `LocalDirArtifactStore` at the fixed `FIXTURE_NOW`, so the same sources give the same `content_hash` and `build_id`.
- `cli.py`: `build-fixture --dest DIR` prints `fixture built: build_id=<id> content_hash=<hash>` or one ERROR line.

**Task 2 (95b8693): empty-context command**
- `empty_context.py`: `run_empty_context` selects approved handbook and guides items in id order, opens the fixture identity from `FIXTURE_DIR`, checks the `empty_context` cache (item, fixture content hash, bot version, models, threshold, schema version) plus `trace_exists`, else runs `run_workflow` over `connector_factory(settings.mcp_empty_url)` inside one `bot_run` trace tagged `run=empty-context` and logs `expected_outcome: refusal_with_gap`. Statuses: refused (refusal or referral with `gap_reported`), no_gap, answered, smalltalk, errored (never cached).
- `count_gap_documents` reads the emulator REST list with a 5 s timeout and follows `nextPageToken`; the cross-check compares the document delta with the fresh `gap_reported` replies.
- `tracing.py`: `score(..., scorers="empty_context")` attaches the `refused` feedback; the shared evaluate/autolog guard moved into `_evaluate`.
- `config.py`: `mcp_empty_url`, `fixture_dir`, `empty_gap_collection`, `firestore_emulator_host`, `google_cloud_project`.
- `cli.py`: `empty-context` (repeatable `--item`) inside `sink.run("empty-context", tags)`, scores unscored fresh traces, prints item lines, cross-check line and verdict, writes `PRIVATE_DIR/eval/reports/empty-context-<UTC>.json`, exit 0 only on PASS.

**Task 3 (c83fc65): compose**
- `eval-fixture` (profile eval, restart "no", sole writer of `eval-empty`), `mcp-server-empty` (mcp_server image, `eval-empty:/artifacts:ro`, `MCP_ALLOWED_HOSTS mcp-server-empty`, `GAP_COLLECTION gaps_empty_context`, no port, depends on eval-fixture completed and firestore healthy). `eval` gets the three variables, `eval-empty:/eval-empty:ro` and a healthy dependency on `mcp-server-empty`.
- `test_compose.py`: `EVAL_SERVICES` extended, two new structural tests, one-shot restart test extended, eval wiring test updated.

## Verification

- `./run-unit-tests.sh --single-file test_fixture.py tests/unit/buddy_eval`: 22 passed.
- `./run-unit-tests.sh --single-file test_empty_context.py tests/unit/buddy_eval`: 48 passed (stub PASS, negative FAIL naming the item, smalltalk, referral with and without gap, LlmUnavailableError INCOMPLETE and uncached, zero items, id order, cross-check 0->2 pass / 0->1 mismatch / unreadable / unset / cached-only, second run with zero LLM calls, pacing, REST paging).
- `./run-unit-tests.sh --single-file test_compose.py tests/unit`: 30 passed, including `test_empty_context_server_reads_only_the_fixture_volume` and `test_eval_fixture_is_the_only_writer_of_its_volume`.
- Hermetic compose check (project `ai-buddy-fixture-check`, torn down with `down -v --remove-orphans`, volumes confirmed gone): `up -d --wait mcp-server-empty` exit 0; eval-fixture Exited (0), mcp-server-empty healthy on the built fixture.
- Live check against that stack from a container on its network: `micelio` finds a page, `ferie` and `chunking` return `no_results`, one `buddy_report_gap` raised `gaps_empty_context` from 0 to 1 documents through `count_gap_documents`, the `gaps` collection stayed 0.
- `./run-unit-tests.sh --all`: ruff, ruff format and mypy clean; 2015 passed, 26 skipped; total coverage 98.07% against the 80% floor.
- Acceptance greps: `^pages:` 1, `publish(` in fixture.py 1, `empty_context: PASS` 1, `mcp_empty_url` 1, `timeout=5` 1, `mcp-server-empty:` 3, `eval-empty` 7, `gaps_empty_context` 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test double and conftest followed the widened `TraceSink.score` signature**
- **Found during:** Task 2
- **Issue:** `RecordingTraceSink.score` in `tests/unit/buddy_eval/conftest.py` no longer satisfied the Protocol once `score` gained `scorers` and accepted `EmptyContextItem` values; mypy would fail. The conftest env-clean list also had to name the five new settings variables so the host environment cannot leak into settings under test.
- **Fix:** `RecordingTraceSink.score` takes `scorers`, `ScoreCall` records it (default `"run"`), `_SETTINGS_VARIABLES` extended.
- **Files modified:** tests/unit/buddy_eval/conftest.py, tests/unit/buddy_eval/test_tracing_adapter.py (two tests for the new scorer set)
- **Commit:** 95b8693

**2. [Rule 3 - Blocking] Negative variant uses a Guides chunk but derives the citation URL at run time**
- The plan asks for "one chunk matching the scripted keywords". The permalink the FakeLlm must cite depends on the server's URL scheme, so the test reads it from a real `guides_search` first instead of hard-coding it. No behaviour change.

Otherwise the plan was executed as written; the points it left open are under `decisions`. The step 0p guard was run in a condensed form (same git-vs-git comparison of the pinned and actual toplevel, without the Windows drive-letter arm) before each commit.

## Carry-forward

- 05-11/05-12: `_gate_inputs` still passes `empty_context_passed=None`. The gate wiring should read the empty-context verdict (the JSON report `passed` field or a direct run) in 05-12.
- 05-11: run `lint`, then `empty-context` on the live stack with the real golden set; `evidence=<n>` on a refused item above 0 means the fixture overlaps a real question (A-10-3), which cannot be checked offline.
- Exercising `empty-context` against the real Meridian and MLflow is not part of this plan's automated verification; it runs in 05-11/05-12.

## Known Stubs

None.

## Threat Flags

None. T-05-27 is mitigated (only `eval-empty:/artifacts:ro` on the server, `eval-fixture` the single writer, both asserted by tests); T-05-28 by `gap_reported` plus the emulator document-count cross-check on a separate collection; T-05-29 by console output limited to ids, statuses, evidence counts and trace links, with the JSON under `PRIVATE_DIR`.

## Self-Check: PASSED

- FOUND: jobs/eval/buddy_eval/fixture.py, jobs/eval/buddy_eval/empty_context.py, jobs/eval/fixtures/empty_context/fixture.yaml, tests/unit/buddy_eval/test_fixture.py, tests/unit/buddy_eval/test_empty_context.py
- FOUND commits: c74a36b, 95b8693, c83fc65
