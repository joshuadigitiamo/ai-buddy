---
phase: 05-evaluation-and-milestone-gate
plan: 05
subsystem: evaluation-error-states
tags: [eval, runner, circuit-breaker, gate, truth-table, EVAL-03, EVAL-06]
requires:
  - phase: 05-03
    provides: run_items, RunResult, report.emit, gate.evaluate and format_verdict, cli exit-1-on-aborted
provides:
  - runner.STOP_MESSAGE and the consecutive-error stop in run_items (RunResult.aborted set)
  - report.emit prints the stop line after the item and summary lines when aborted
  - parametrized D-17 truth table over gate.evaluate and format_verdict
affects: [05-06, 05-07, 05-08]
tech-stack:
  added: []
  patterns: [consecutive-failure threshold as a loop circuit breaker with rerun as the half-open probe, no retry inside a run]
key-files:
  created:
    - tests/unit/buddy_eval/test_runner.py
    - tests/unit/buddy_eval/test_gate.py
  modified:
    - jobs/eval/buddy_eval/runner.py
    - jobs/eval/buddy_eval/report.py
decisions:
  - "A-05-1: the stop counts consecutive errored items only; a completed item, whatever its verdict, resets the counter"
  - "After an abort, uncollected items get no outcome and no verdict (verdicts zip with strict=False over the collected prefix), so they are not reported as errored"
  - "STOP_MESSAGE is printed by report.emit after the summary lines (the last line of the output); cli.py is unchanged"
  - "gate.py needed no change: the truth table confirmed every D-17 rule and the exact rational comparison already in place"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 9000
  tasks: 2
  commits: 2
plan_head_before: 1daa9260f1d11713147e2463be1f0e4d7000f0c1
plan_head_after: 731b05a2ecc2b5923104665a8dd39f7814d5a3cd
---

# Phase 5 Plan 05: Error states of the eval slice Summary

Collect loop stops after MAX_CONSECUTIVE_ERRORS errored items with a resume hint and never retries, errored items stay out of the wrong count, and the gate's D-17 rules are pinned by a 17-row truth table plus ordering and no-false-PASS tests.

## What was built

- `runner.py`: `STOP_MESSAGE`; `run_items` counts consecutive errored outcomes, resets on a completed item, stops when the count reaches `settings.max_consecutive_errors`, returns `aborted=True`. The stop is logged with the count only. No retry path exists.
- `report.py`: `emit` prints `STOP_MESSAGE.format(n=settings.max_consecutive_errors)` when `result.aborted`.
- `test_runner.py` (12 tests): stop after 3 of 5 with no LLM call for items 4 and 5 (counted on FakeLlm.calls); stop line is the last output line; no stop line on a complete run; error-good-error pattern resets the counter; errored verdict is never `wrong`; reformulate `LlmError` gives an `ErrorReply` errored item; exactly one collect attempt per item; limit read from settings; `cli.main(["run"])` exits 1 with the stop line; `gate` over an aborted run prints `FAIL errored: 3 items errored (incomplete run)`; counts below the limit never stop.
- `test_gate.py` (28 cases): 9/10 PASS, 899/1000 FAIL with `89.9% < 90% (899/1000)`, 900/1000 PASS, invented 0/1/None, empty-context False/None, draft, private file missing, no approved items, errored, unjudged, fixed multi-failure order, PASS has zero failure lines, no unmeasured/draft/errored/unjudged/missing input ever prints PASS.

## Verification

- `./run-unit-tests.sh --single-file test_runner.py tests/unit/buddy_eval`: 12 passed.
- `./run-unit-tests.sh --single-file test_gate.py tests/unit/buddy_eval`: 28 passed.
- `./run-unit-tests.sh --all`: exit 0, ruff clean, ruff format clean, mypy clean (167 files), 1717 passed, 26 skipped, coverage 97.67%.
- Acceptance greps: stop-message literal in runner.py = 1; `STOP_MESSAGE` in report.py = 2; `correct * 10 >= ` in gate.py = 1.

## Deviations from Plan

None - plan executed exactly as written. The gate.py step ("adjust only where the table shows a deviation") required no edit. Both new test files and the edited sources were formatted with the project's ruff inside the test image (host has no ruff).

## Known Stubs

None.

## Threat Flags

None. T-05-41 (quota exhaustion stop, no in-run retries) and T-05-42 (no false PASS, errored never wrong) are covered by the tests above.

## Self-Check: PASSED

- FOUND: tests/unit/buddy_eval/test_runner.py, tests/unit/buddy_eval/test_gate.py
- FOUND commits: eb2e076 (feat 05-05 stop), 731b05a (test 05-05 gate table)
