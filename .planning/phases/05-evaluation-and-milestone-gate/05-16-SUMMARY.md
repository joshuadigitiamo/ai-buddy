---
phase: 05-evaluation-and-milestone-gate
plan: 16
subsystem: evaluation
tags: [mlflow, eval-cache, judge, scored-marker, mcp, error-handling]
requires:
  - phase: 05-evaluation-and-milestone-gate
    provides: "05-14 bot retrieval change (re-collected answers) and the 05-07/05-08 cache and scoring pipeline"
provides:
  - "Verdict cache key bound to the judged reply (reply_digest)"
  - "Verdict-specific scored marker for run traces and status-specific marker for empty-context traces"
  - "Stale same-name MLflow Feedback deleted before scoring; citation rationale narrowed"
  - "MCP/transport failures become errored items; McpToolError and LlmError reach main as one ERROR line"
affects: [05-17 live re-run, milestone gate]
actuals:
  tokens: 22000
  tasks: 3
  commits: 7
plan_head_before: 52fc6e3b4a6fd068a27dbfdee8653d378336f5e5
plan_head_after: 3f5ef6a3f15a87f873297f21998ee61418b985cd
tech-stack:
  added: []
  patterns:
    - "Scored marker = scorer-set version plus a digest of the verdict (or the item status)"
    - "Collect paths: TracingError propagates, every other exception errors the item with its type name only"
key-files:
  created: []
  modified:
    - jobs/eval/buddy_eval/runner.py
    - jobs/eval/buddy_eval/tracing.py
    - jobs/eval/buddy_eval/empty_context.py
    - jobs/eval/buddy_eval/cli.py
    - tests/unit/buddy_eval/test_resume.py
    - tests/unit/buddy_eval/test_tracing_adapter.py
    - tests/unit/buddy_eval/test_empty_context.py
    - tests/unit/buddy_eval/test_gate_command.py
key-decisions:
  - "Reply digest covers the whole BotReply JSON (A-16-1)"
  - "Stale feedback is deleted, not overridden (A-16-2)"
  - "TracingError keeps propagating from the collect paths (A-16-3)"
  - "SCORER_SET_VERSION bumped to 3 because the citation rationale changed"
requirements-completed: [EVAL-03, EVAL-04, EVAL-05, EVAL-06]
status: complete
---

# Phase 5 Plan 16: Eval run integrity fixes Summary

Verdicts are now bound to the reply they judged, MLflow shows one current value per feedback name, and an MCP outage mid-run ends in a reported `GATE: FAIL` instead of a traceback.

## Tasks

| Task | What | Commits |
| ---- | ---- | ------- |
| 1 (tracer) | CR-01: `reply_digest` added to the verdict key in `_judge_item`; `scored_version(verdict)` replaces the bare scorer-set constant in the `run_items` filter and marking loop (WR-02, run side) | e802554 (RED), d8dda4f (GREEN) |
| 2 | WR-02, MLflow side: `_evaluate` deletes earlier Feedback named correctness/citation/invented_policy (or refused) via `mlflow.delete_assessment` before `mlflow.genai.evaluate`; expectations stay. Citation rationale is `citation: ok / failed / not checked`. `SCORER_SET_VERSION = "3"` | eaa1c93 (RED), ccdb7a3 (GREEN) |
| 3 | WR-01: `collect_item` and `_collect` catch non-tracing exceptions and return errored items (type name logged, never the message); `empty_scored_version(item)` binds the empty-context marker to status; `_EXPECTED_ERRORS` gains `McpToolError` and `LlmError` | 9516964 (RED), b0038e9 (test fix), 3f5ef6a (GREEN) |

## Verification

- `./run-unit-tests.sh --single-file` for test_resume.py (23 passed), test_tracing_adapter.py (green in Task 2), test_empty_context.py (51 passed), test_gate_command.py (28 passed).
- RED check for Task 3: test_empty_context.py failed at collection (missing `empty_scored_version`); test_gate_command.py failed 3 (MCP outage, McpToolError and LlmError reaching main); the tracing-error tests in test_resume.py already passed because they guard existing behavior.
- `./run-unit-tests.sh --all`: ruff check, ruff format and mypy clean; pytest 2035 passed, 31 skipped, 4 failed; coverage 98.12% (gate 80%). See Issues for the 4 failures.
- Acceptance greps: `reply_digest` 2, `scored_version(` 3 in runner.py, old `is_scored(v.trace_id, SCORER_SET_VERSION)` 0, `delete_assessment` 1, `SCORER_SET_VERSION: Final = "3"` 1, `except Exception` 1 each in runner.py and empty_context.py, `McpToolError` 2 and `empty_scored_version(` 1 in cli.py.
- Gate rules, thresholds, judge prompt, JUDGE_PROMPT_VERSION and SCORING_VERSION untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong assertion in the RED gate test**
- **Found during:** Task 3
- **Issue:** `test_an_mcp_outage_errors_items_stops_the_run_and_still_reports_a_fail` asserted `GATE: FAIL` is the last output line, but `format_verdict` prints one `FAIL <metric>` line after it.
- **Fix:** assert `lines.count("GATE: FAIL") == 1`, as the other gate tests do.
- **Commit:** b0038e9

**2. [Rule 1 - Bug] Unused `type: ignore` comments in the RED tests**
- **Found during:** Task 3 (`mypy` in `--all`)
- **Fix:** removed the two comments in test_gate_command.py and test_empty_context.py.
- **Commit:** b0038e9

**3. [Rule 3 - Blocking] ruff E501 on the new `empty_scored_version` docstring**
- **Fix:** shortened the docstring. **Commit:** 3f5ef6a

## Issues Encountered

- `./run-unit-tests.sh --all` reports 4 failures, all environmental, none in code this plan touched: `tests/unit/test_repo_layout.py::test_committed_golden_files_hold_no_handbook_reference`, `::test_private_golden_path_is_gitignored`, `tests/unit/test_workflows.py::test_run_unit_tests_is_executable_in_the_git_index`, `::test_every_tracked_script_has_index_mode_100755`. They shell out to `git` inside the test container, and in a linked worktree `.git` is a file pointing outside the bind mount, so git exits 128 (`CalledProcessError ... git ls-files ... status 128`). The orchestrator should re-run `--all` in the primary checkout to confirm exit 0.
- The worktree had no `.env`; the secret-read guard blocked copying it from the main checkout, so tests ran with `.env.example` placeholders (the script's fallback). The unit tests run with `--network none` and do not need real values.

## Known Stubs

None.

## Threat Flags

None. New error log lines carry exception type names only (T-05-53), covered by a caplog test with a sentinel message.

## Self-Check: PASSED

All 8 modified files exist; commits e802554, d8dda4f, eaa1c93, ccdb7a3, 9516964, b0038e9, 3f5ef6a are ancestors of HEAD.
