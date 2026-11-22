---
phase: 05-evaluation-and-milestone-gate
plan: 12
subsystem: evaluation-gate
tags: [eval, gate, preflight, readme, smoke, EVAL-06, EVAL-02]
requires:
  - phase: 05-08
    provides: headline(verdicts).invented, judge phase (no unjudged after it)
  - phase: 05-09
    provides: measure_recall, format_recall
  - phase: 05-10
    provides: run_empty_context, format_empty_context, mcp-server-empty and eval-fixture compose services
provides:
  - "python -m buddy_eval gate: recall (informational), scoring run, empty-context, one GATE line, exit 0 only on PASS"
  - "python -m buddy_eval preflight: one ping per model, one MCP session, MLflow connect"
  - "jobs/eval/README.md operator documentation"
  - "eval-smoke.sh asserts the gate exit code follows its GATE line"
affects: [05-13]
actuals:
  tokens: 18070
  tasks: 2
  commits: 2
plan_head_before: ae31269ce9c129f55cbf3287426779a5a233bd05
plan_head_after: f0c9c8fc868959f324325a33ebd36ccec05beae7
tech-stack:
  added: []
  patterns: [readiness short-circuit before any model call, report written before the verdict is printed, injected factories for every outside collaborator]
key-files:
  created:
    - jobs/eval/buddy_eval/preflight.py
    - jobs/eval/README.md
    - tests/unit/buddy_eval/test_gate_command.py
    - tests/unit/buddy_eval/test_preflight.py
  modified:
    - jobs/eval/buddy_eval/cli.py
    - jobs/eval/buddy_eval/gate.py
    - scripts/eval-smoke.sh
    - tests/unit/test_compose.py
    - tests/unit/buddy_eval/test_tracer.py
key-decisions:
  - "Partial invented count: reported as counted when it already holds a flagged item, otherwise `not measured` (a partial zero proves nothing); complete means every approved item has a judged verdict"
  - "The gate report file is written before the verdict is printed, so a failed write leaves no printed GATE line behind"
  - "Readiness failures print only the golden_set lines (not the unmeasured invented and empty_context lines) plus the SKIPPED line"
  - "Recall is not wrapped in a catch-all: recall item errors are informational, but a dead MCP session ends the command with an ERROR line and exit 1, never a PASS"
requirements-completed: [EVAL-06, EVAL-02]
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
---

# Phase 5 Plan 12: Full Gate, Preflight, README and Smoke Summary

One `gate` command now composes recall, scoring and the empty-context test from the caches and prints `GATE: PASS` or `GATE: FAIL` with one line per failing metric; it spends nothing when the golden set cannot pass, and the hermetic smoke proves the container exit code follows the verdict.

## What was built

- **Gate (Task 1, c2db1b3).** `cli._gate` loads the golden set; a load error, a missing private file, any draft or no approved item prints `GATE: FAIL`, the `FAIL golden_set: ...` lines and `SKIPPED recall, run, empty_context: golden set not ready (no model call made)` without building any LLM client, connector or sink. Otherwise it prints `recall (informational, not gating):` plus the recall lines, runs the scoring with `run_items` and `report.emit`, then either prints `SKIPPED empty_context: run stopped after consecutive errors` (aborted run) or runs the empty-context test, builds `GateInputs` and prints the verdict. `GateInputs.empty_context_detail` makes the failure read `failed`, `incomplete (<n> errored)` or `not run`. `gate-<UTC>.json` under `PRIVATE_DIR/eval/reports` holds the metrics, verdict, failing item ids (not correct, invented, not refused) and the index identity. The empty-context run was extracted into `_run_empty_context`, shared by `empty-context` and `gate`, with a private `_FixtureMissing` so a missing fixture index is reported precisely (`ERROR: fixture index not found ...`, then `FAIL empty_context: not run`).
- **Preflight (Task 2, f0c9c8f).** `preflight.py` (`PreflightPing`, `PreflightCheck`, `run_preflight`) pings reformulate, answer and judge with a fresh client each, opens and closes one MCP session and constructs the sink (which contacts MLflow). Output is `preflight <check> <target>: ok|failed (<ErrorType>)`; URLs print scheme, host, port and path only; exit 0 only when all five pass.
- **README.** `jobs/eval/README.md`: gate rule, every command with exit codes and the compose form, settings and `EVAL_*` variables, private paths and cache reset, golden schema and review flow, eval image rebuild after editing `guides.yaml`, MLflow UI at `http://127.0.0.1:5000`, Max budget behaviour, privacy, the D-20 amendment, Guides applied. No handbook text and no handbook URI scheme string.
- **Smoke.** `scripts/eval-smoke.sh` starts `mcp-server-empty` after the trace check, runs `eval gate` and asserts exactly one `GATE: ` line, a `recall@5 guides:` line, an `empty_context:` line, and exit code 0 exactly when the line is `GATE: PASS`; prints `gate exit code consistent (<code>)`.

## Verification

- `./run-unit-tests.sh --single-file test_gate_command.py tests/unit/buddy_eval`: 25 passed. `test_preflight.py`: 10 passed.
- `scripts/eval-smoke.sh` (hermetic stack, re-run for the 05-07/05-08/05-10 carry-forward): printed `gate exit code consistent (0)` and `eval smoke ok`; the stub-LLM gate reached `GATE: PASS` (3/3 correct, invented 0, empty_context 2/2 refused with gap). No `timeout after`.
- `./run-unit-tests.sh --all` (after the one-line compose-test fix): ruff check, ruff format and mypy clean, 2050 passed, 26 skipped, coverage 98.10% (gate 80%). The first full run had one failure, a wrong ordering assertion I had written in `test_compose.py` (the header comment also contains `eval gate`); see Deviations.
- Acceptance greps: `golden set not ready (no model call made)` 1 in cli.py; `run_empty_context(` 4; `measure_recall(` 2; README `python -m buddy_eval gate` 2, `127.0.0.1:5000` 1, handbook URI scheme 0; smoke `gate exit code consistent` 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing tracer tests encoded the pre-05-12 gate**
- **Found during:** Task 1 full buddy_eval run
- **Issue:** `test_tracer.py` expected the gate to print `invented_policies: not measured` / `empty_context: not run`, and to run public items when the private file is missing. Both contradict the plan (D-17 composition, readiness short-circuit).
- **Fix:** Rewrote the two tests: a scripted full gate whose only failing metric is the empty-context test, and a missing-private-file gate that runs nothing and logs the warning once.
- **Files modified:** `tests/unit/buddy_eval/test_tracer.py`
- **Commit:** c2db1b3

**2. [Rule 1 - Bug] Wrong ordering assertion in the compose test**
- **Found during:** `--all` run after Task 2
- **Issue:** `text.index("eval gate")` matched the header comment, so "gate after trace check" failed.
- **Fix:** Match `--no-deps eval gate` instead.
- **Files modified:** `tests/unit/test_compose.py`
- **Commit:** f0c9c8f (fix was applied before the commit)

### Decisions beyond the plan text

- **Partial invented count (carry-forward from 05-08).** Complete = every approved item has a verdict that is neither errored nor unjudged. Complete: the count is used. Partial and at least one item flagged: the count is printed as counted. Partial and zero flagged: `invented_policies: not measured` (so an aborted run now lists this line in addition to `errored` and `empty_context: not run`; the plan's behaviour list named only those two, the extra line is the honest reading of the prohibition on an unmeasured invented count).
- **Report before verdict.** The gate JSON is written first, then `report: <path>` and the verdict lines print. If the write fails, an ERROR line and exit 1 result with no GATE line.
- **Readiness path writes a report too** (verdict and failures only, `metrics: null`).
- **Smoke builds `mcp-server-empty`** in the image build step so its build counts against the bounded step.

## Carry-forward status

- `_gate_inputs` now passes the real invented count and the empty-context result (done).
- `scripts/eval-smoke.sh` re-run: passes.
- Report filenames are per UTC second, so two runs of the same command within one second collide (`write_json_report` is in `report.py`, outside this plan's files). Not fixed; documented in the README table of private paths. The gate report (`gate-*`) and the run report (`run-*`) use different names, so one gate invocation does not collide with itself.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint or trust boundary: preflight reuses the existing LLM, MCP and MLflow connections; its output names ids, hosts and exception types only (T-05-35).

## Self-Check: PASSED

- FOUND: jobs/eval/buddy_eval/preflight.py, jobs/eval/README.md, tests/unit/buddy_eval/test_gate_command.py, tests/unit/buddy_eval/test_preflight.py
- FOUND commits: c2db1b3, f0c9c8f (ancestors of HEAD)
