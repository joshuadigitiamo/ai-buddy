---
phase: 05-evaluation-and-milestone-gate
plan: 03
subsystem: evaluation-core
tags: [tracer, golden-set, collect-then-score, trace-sink-port, gate, cli]
requires:
  - phase: 05-02
    provides: buddy_eval package root, eval Dockerfile stage, hashed locks
  - phase: 03
    provides: run_workflow, FastMcpConnector, BotReply schemas
provides:
  - EvalSettings with the D-08 and tracing guards
  - GoldenItem schema and the public/private split loader (D-02, D-04)
  - TraceSink port and TracingError (no mlflow import in buddy_eval)
  - collect-then-score runner over the real run_workflow and MCP connector
  - pure deterministic scoring (D-09) and gate verdict (D-17)
  - report (item lines, summary lines, atomic JSON writer) and run/gate CLI with injected collaborators
affects: [05-04, 05-05, 05-06, 05-07, 05-08, 05-09, 05-10]
tech-stack:
  added: []
  patterns: [ports and adapters with a recording fake, pure scoring and gate, TYPE_CHECKING cycle break between runner and scoring, injected factories on main]
key-files:
  created:
    - jobs/eval/buddy_eval/cli.py
    - jobs/eval/buddy_eval/config.py
    - jobs/eval/buddy_eval/golden.py
    - jobs/eval/buddy_eval/runner.py
    - jobs/eval/buddy_eval/tracing.py
    - jobs/eval/buddy_eval/scoring.py
    - jobs/eval/buddy_eval/gate.py
    - jobs/eval/buddy_eval/report.py
    - tests/unit/buddy_eval/conftest.py
    - tests/unit/buddy_eval/test_tracer.py
  modified: []
decisions:
  - "ERROR lines (load errors, unknown --item, invalid settings) go to the injected out stream (stdout), not the logger; the only log records are the WARNING for a missing private file and per-item `item <id> <status>` INFO lines"
  - "Score hand-off: sink.score(trace_ids, verdicts) receives only completed outcomes, verdicts keyed by trace id; an errored item with kind=error reply still has a trace but is excluded from score"
  - "Gate with zero approved items prints the verdict (golden_set failures) and exits 1 without building a sink; run with zero approved items prints `no approved items`"
  - "handbook_only resolver means a guides item cannot match a citation until 05-07 supplies the index-backed resolver through score_item(resolve=...)"
  - "No pct line for correctness when any answered item is unjudged: the unjudged line replaces it; errored items count as not correct in the 0.90 rational (correct * 10 >= approved_total * 9)"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 15400
  tasks: 1
  commits: 1
plan_head_before: 8806cedb794ce83cba83a8b0fbe8652473722382
plan_head_after: b845ff3a8c5f1eb3a359e45ae1facb7e71033238
---

# Phase 5 Plan 03: Tracer slice Summary

One golden item now travels golden file, real `run_workflow` over a real `FastMcpConnector`, one `bot_run` trace per item through the `TraceSink` port (expectations logged on it), deterministic verdict, report line, honest gate FAIL and exit code, all in-process. `grep` confirms no `buddy_eval` module imports mlflow; 05-04 adds the adapter behind the port.

## Tasks

| Task | Name | Commit | Key files |
|------|------|--------|-----------|
| 1 | Tracer: golden files to gate line and exit code | b845ff3 | jobs/eval/buddy_eval/{cli,config,golden,runner,tracing,scoring,gate,report}.py, tests/unit/buddy_eval/{conftest,test_tracer}.py |

## What was built

- **config.py**: `EvalSettings` with every key from the interfaces block. The model validator refuses `LLM_BACKEND=vertex`, `api` without `ANTHROPIC_API_KEY`, `JUDGE_MODEL == ANSWER_MODEL` (D-08) and LANGSMITH_TRACING / LANGCHAIN_TRACING_V2 true. Messages name variables only.
- **golden.py**: `GoldenItem` (extra forbid, frozen, id pattern, per-kind rules), `sensitive_branch`, `GoldenSet`, `load_golden`. The privacy check runs on the raw YAML before schema validation, so a public item with `handbook://` in any source always fails with `<file>: item <id> references handbook:// and belongs in the private file`. A missing private file logs one WARNING naming only the path. Duplicate ids across files are a load error naming the id. Errors name file, item id and field, never question text; invalid YAML is reported without echoing content.
- **tracing.py**: `TraceSink` Protocol and `TracingError`, no third-party import.
- **runner.py**: `collect_item` builds the LLM client and connector inside the coroutine, runs `run_workflow(question, [], deps)` under `sink.traced("bot_run", {item_id, kind}, fn)`, logs expectations, and turns `LlmError`, `McpToolError` or a `kind=error` reply into an `errored` outcome carrying the exception type name only. `run_items` processes in id order inside one `sink.run("eval-run", ...)`, pauses `item_pause_seconds` between items, then calls `sink.score` once.
- **scoring.py**: D-09 table per kind; answerable items that pass every deterministic check are `unjudged` (`facts` is None until 05-08); smalltalk is `wrong` with reason `classified as smalltalk` (A-03-1); role comparison strips and casefolds (A-03-2).
- **gate.py**: full D-17 rule set with `correct * 10 >= approved_total * 9`, failure order golden_set, errored, correctness_with_citation, invented_policies, empty_context.
- **report.py**: `format_run`, `write_json_report` (temp file then `os.replace`), `emit`.
- **cli.py**: `run [--item ID]` and `gate`; `main(argv=None, *, llm_factory, sink_factory, settings=None, connector_factory=None, out=None)`; exit 0 success or PASS, 1 reported failure or FAIL, 2 bad arguments.

## Verification

- `./run-unit-tests.sh --single-file test_tracer.py tests/unit/buddy_eval`: 49 passed.
- `./run-unit-tests.sh --all`: ruff, ruff format and mypy (162 files) clean; 1648 passed, 26 skipped; coverage 97.59 percent (gate 80). buddy_eval modules between 94 and 100 percent.
- Acceptance greps: no `import mlflow` in `jobs/eval/buddy_eval`; `run_workflow(` count 1; `sink.(traced|score)(` count 2; `correct * 10 >= ` count 1.

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] Extra unit tests inside test_tracer.py beyond the tracer behaviours**
- **Found during:** Task 1, coverage and threat register (T-05-08, T-05-10, T-05-11)
- **Issue:** The plan's behaviour list does not cover the golden schema violations, the gate boundary, `--item` selection, bad arguments, wrong-kind and smalltalk verdicts, or the JSON writer, all of which the threat mitigations and the 80 percent coverage gate depend on.
- **Fix:** added `TestEvalSettings`, `TestGolden` and `TestGateAndReport` classes plus the selection and verdict tests to `test_tracer.py` (no new test files). 05-05 still owns the full gate truth table.
- **Files modified:** tests/unit/buddy_eval/test_tracer.py
- **Commit:** b845ff3

No other deviations; the plan was executed as written.

## Notes for later plans

- `python -m buddy_eval` still has no `__main__` (05-04 adds it with the production factories), so the eval image ENTRYPOINT keeps failing until then, as noted in 05-02.
- A-03-3 stands: the report prints the raw trace id next to the link because the MLflow deep link route is unverified.
- `RunResult.aborted` is always False here; 05-05 adds the consecutive-error stop using `settings.max_consecutive_errors`.
- The `sink.run` context value (run id) is ignored by the runner; the MLflow adapter in 05-04 can use it for run-level metrics.
- `scoring.score_item` reaches `ItemOutcome` and `tracing.TraceSink` reaches `ItemVerdict` through `TYPE_CHECKING` imports to avoid a runtime cycle (runner imports scoring, tracing).

## Known Stubs

None. `invented_policies` and `empty_context` are reported as `not measured` / `not run` by design until 05-08 and 05-10; the gate FAILs on both, which is the intended honest behaviour for the slice.

## Threat Flags

None. New surface is local file parsing (covered by T-05-08, T-05-10, T-05-11 with tests) and no network endpoint.

## Self-Check: PASSED

- FOUND: all ten created files (cli, config, golden, runner, tracing, scoring, gate, report, tests conftest and test_tracer)
- FOUND commit: b845ff3 (ancestor of HEAD); `git rev-list --count 8806ced..HEAD` = 1 at write time
