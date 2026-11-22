---
phase: 05-evaluation-and-milestone-gate
plan: 07
subsystem: evaluation-cache-sources
tags: [eval, cache, resume, citation, permalink, index-identity, EVAL-03]
requires:
  - phase: 05-04
    provides: TraceSink Protocol, MlflowTraceSink, EvalSettings
  - phase: 05-05
    provides: consecutive-error stop, RunResult.aborted
provides:
  - SourceIndex (index identity, Guides permalink to stable chunk key, expected-source check)
  - matches() section-prefix matching at a segment boundary
  - ResultCache (atomic per-item JSON cache), key_for, bot_version
  - run_items resume from cache, trace-existence check, scored markers, index identity on every run
  - TraceSink.trace_exists, SCORER_SET_VERSION, RunResult.identity
affects: [05-08, 05-09, 05-10, 05-12]
tech-stack:
  added: []
  patterns: [content-hash cache keyed over item, index, bot code and models, cached hit valid only while its trace exists]
key-files:
  created:
    - jobs/eval/buddy_eval/sources.py
    - jobs/eval/buddy_eval/cache.py
    - tests/unit/buddy_eval/test_sources.py
    - tests/unit/buddy_eval/test_cache.py
    - tests/unit/buddy_eval/test_resume.py
  modified:
    - jobs/eval/buddy_eval/scoring.py
    - jobs/eval/buddy_eval/config.py
    - jobs/eval/buddy_eval/runner.py
    - jobs/eval/buddy_eval/tracing.py
    - tests/unit/buddy_eval/conftest.py
    - tests/unit/buddy_eval/test_tracing_adapter.py
decisions:
  - "A Guides permalink resolves only when its commit equals the index guides_commit_sha and its file and line span exist in the index; a section prefix (file#h2/h3) matches any part of that section, a handbook id matches by exact equality"
  - "The outcome cache key is sha256 over the golden item JSON, index content_hash, guides_commit_sha, bot version, reformulate and answer model, confidence threshold and OUTCOME_SCHEMA_VERSION; errored outcomes are never cached"
  - "bot_version hashes every buddy_bot *.py (recursive, intake included) plus escalation_topics.yaml, so any bot edit invalidates every cached outcome (A-07-2)"
  - "MlflowTraceSink.score returns early for zero traces so a fully cached rerun makes no evaluate run; trace_exists treats only MlflowException as a missing trace, other errors propagate"
  - "The pacing sleep runs before an item only when an earlier item of the same run was actually collected"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 36000
  tasks: 2
  commits: 2
plan_head_before: 700d68fae726c4b51b2b3930947d5f95508bfc1b
plan_head_after: 84b10d220738912bdaf2e9d4819caa9281b09c8f
---

# Phase 5 Plan 07: Index-backed sources, result cache and resume Summary

Guides citations now resolve through the run's own index to stable chunk keys and match section-prefix expectations, and every item outcome is cached under `PRIVATE_DIR/eval/cache` so an interrupted or rate-limited run resumes and a full rerun makes zero LLM calls and opens zero traces.

## Tasks

| Task | Name | Commit | Key files |
|------|------|--------|-----------|
| 1 | Index identity and source resolution, wired into the citation check | 2829e68 | sources.py, scoring.py, config.py, test_sources.py |
| 2 | Per-item cache, resume, trace-existence check and scored markers | 84b10d2 | cache.py, runner.py, tracing.py, conftest.py, test_cache.py, test_resume.py, test_tracing_adapter.py |

## What was built

- **sources.py**: `IndexIdentity`, `SourceIndex.open(artifact_dir)` (reads meta, guide chunks and handbook page ids through `open_index`, then closes it; no SQL in the module), `resolve` (one anchored permalink pattern, unquoted path, SHA must equal the index commit), `has_expected`, and `matches`.
- **scoring.py**: the citation check collects the set of expected entries matched by any resolved cited key; several parts of one section fill one entry once. Statuses and other checks unchanged.
- **cache.py**: `ResultCache` (get, put with temp file then `os.replace`, `is_scored`, `mark_scored`), `key_for`, `bot_version`, the five namespaces. A file that is not a JSON object is a miss with one WARNING naming namespace and key; keys that could leave the namespace folder are refused.
- **runner.py**: opens the index once (a missing index raises FileNotFoundError naming ARTIFACT_DIR before any run opens), tags the run with `index_content_hash`, `guides_commit_sha`, `build_id`, `bot_version`, `reformulate_model`, `answer_model`, reuses a cached outcome only while `sink.trace_exists`, caches only completed outcomes, passes `resolve=index.resolve` to `score_item`, scores only traces without a marker for `SCORER_SET_VERSION`, and returns `RunResult.identity`.
- **tracing.py**: `TraceSink.trace_exists`, `SCORER_SET_VERSION = "1"`, adapter `trace_exists` (None or MlflowException means missing), early return in `score` for zero traces.

## Verification

- `./run-unit-tests.sh --all`: ruff, ruff format, mypy and pytest pass; 1811 passed, 26 skipped (emulator and local-only), total coverage 97.70 percent.
- test_sources.py (36), test_cache.py (30) and test_resume.py (18) pass individually.
- EVAL-03 prohibition (no stale reuse) is covered by `test_a_changed_setting_or_index_never_reuses_a_cached_outcome` (answer model, reformulate model, threshold, Guides commit, index content), the golden-item-text test and the bot-version test.
- Acceptance greps: `def matches` 1, `open_index(` 2, `sqlite3` 0 in sources.py; `os.replace` 2, five namespace literals 3 matching lines, `def trace_exists` 2 in tracing.py (Protocol and adapter).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Eval test fixtures needed the index directory**
- **Found during:** Task 2
- **Issue:** `run_items` now opens the index from `settings.artifact_dir` (default `/artifacts`), which does not exist for the existing runner, entrypoint and tracer tests. The plan limited the conftest edit to `RecordingTraceSink`.
- **Fix:** `eval_settings` sets `artifact_dir` to `tmp_path / "artifacts"` (where the `mcp_server` fixture already writes its index), and `ARTIFACT_DIR` joins the cleaned environment variables. No existing test changed.
- **Files modified:** tests/unit/buddy_eval/conftest.py
- **Commit:** 84b10d2

**2. [Rule 2 - Missing critical functionality] Zero-trace scoring on a fully cached rerun**
- **Found during:** Task 2
- **Issue:** a rerun whose traces are all marked scored reaches `MlflowTraceSink.score` with no trace ids, which would start an empty `mlflow.genai.evaluate` run.
- **Fix:** `score` returns early for zero traces after the missing-verdict check; the runner still calls `sink.score` (with no ids) so the earlier all-errored contract is kept. Test added in test_tracing_adapter.py.
- **Files modified:** jobs/eval/buddy_eval/tracing.py, tests/unit/buddy_eval/test_tracing_adapter.py
- **Commit:** 84b10d2

**3. [Rule 2 - Missing critical functionality] Cache payload and key hardening**
- **Found during:** Task 2
- **Issue:** a cache file that parses but does not fit the item (wrong item id, invalid reply) or a key containing path separators would otherwise crash or escape the namespace folder.
- **Fix:** a payload that does not rebuild into an outcome is a miss; `ResultCache` refuses keys outside `[A-Za-z0-9][A-Za-z0-9._-]*`.
- **Files modified:** jobs/eval/buddy_eval/runner.py, jobs/eval/buddy_eval/cache.py
- **Commit:** 84b10d2

### Other notes

- `RunResult.identity` is `IndexIdentity | None = None`: the empty-selection path in `cli.py` builds `RunResult((), (), aborted=False)` without opening an index, so a default was needed instead of editing cli.py.
- Task 1 tests were written alongside the implementation and passed on the first run, so there is no separate failing-test commit.

## Flagged for later plans

- `scripts/eval-smoke.sh` was not re-run here (it needs the compose stack with a real MLflow container). It should still work: the eval container mounts the `artifacts` volume the `sync` service fills, and the smoke golden fixture already uses a section-prefix expected source (`AI-Engineering/DEMO_GUIDE.md#1-basics/chunking`). 05-12 should re-run it.
- 05-06 finding resolved at the source: the `handbook_only` resolver made every guides item `citation=False`; the runner now passes the index resolver, so Guides citations can pass.
- Parts of a split section that share one line span cannot be told apart by a permalink; the first chunk wins and a section-prefix expectation matches any part (A-07-1).
- 05-08 must bump `SCORER_SET_VERSION` when it adds the `invented_policy` scorer.

## Known Stubs

None.

## Threat Flags

None. The cache root is `PRIVATE_DIR/eval/cache` (gitignored `docs/internal` by default), covered by T-05-17 to T-05-19.

## Self-Check: PASSED

- FOUND: jobs/eval/buddy_eval/sources.py, jobs/eval/buddy_eval/cache.py
- FOUND: tests/unit/buddy_eval/test_sources.py, test_cache.py, test_resume.py
- FOUND commits: 2829e68, 84b10d2
