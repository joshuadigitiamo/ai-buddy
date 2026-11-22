---
phase: 05-evaluation-and-milestone-gate
plan: 04
subsystem: evaluation-adapters
tags: [mlflow, trace-sink, tracking-uri-guard, llm-seam, entrypoint]
requires:
  - phase: 05-03
    provides: TraceSink port, cli.main with injected factories, EvalSettings
  - phase: 05-02
    provides: mlflow-skinny 3.18.0 hashed locks, eval image stage
provides:
  - MlflowTraceSink (only buddy_eval module importing mlflow), TraceSink contract in trace mode
  - MLFLOW_TRACKING_URI locality validator (D-21)
  - LlmBackendSettings Protocol in buddy_bot.llm (bot_seam resolution)
  - cli.main production defaults and python -m buddy_eval entry point
affects: [05-05, 05-06]
tech-stack:
  added: []
  patterns: [one third-party adapter behind a port with the mlflow module attributes monkeypatched in tests, structural Protocol seam instead of a shared dependency]
key-files:
  created:
    - jobs/eval/buddy_eval/__main__.py
    - tests/unit/buddy_eval/test_tracing_adapter.py
    - tests/unit/buddy_eval/test_entrypoint.py
  modified:
    - jobs/eval/buddy_eval/tracing.py
    - jobs/eval/buddy_eval/config.py
    - jobs/eval/buddy_eval/cli.py
    - services/chat_bot/buddy_bot/llm.py
decisions:
  - "score() refuses (TracingError, before any mlflow call) a collected trace id with no verdict, so a scorer never meets a missing key inside evaluate"
  - "Scorers are closures over the verdict mapping, named by function (correctness, citation) and also pass name= to Feedback; the citation value is the raw check (True, False or None when not judged)"
  - "cli.main resolves defaults at call time from module globals (build_llm_client, MlflowTraceSink) so tests patch them on buddy_eval.cli; settings are built inside the try so a settings error keeps the one ERROR line path"
  - "pyproject.toml unchanged: mypy reports no missing stubs for mlflow (165 files clean), so no override block was added"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 7500
  tasks: 2
  commits: 2
plan_head_before: 066748b0a560929a8665d5dd41c22e1bbb3422d1
plan_head_after: f153b6f2180ab0307ed63d9df693a3aac95ef5b9
---

# Phase 5 Plan 04: MLflow adapter and production entry point Summary

`python -m buddy_eval` now binds the real LLM client (`build_llm_client(settings)`), `FastMcpConnector` and `MlflowTraceSink(settings)` by default, while injected factories still win, so the 05-03 tracer test passes unchanged. The adapter collects one `bot_run` root trace per item and scores over the collected traces in trace mode; tracking servers off the host are refused at settings load.

## Tasks

| Task | Name | Commit | Key files |
|------|------|--------|-----------|
| 1 | MLflow trace sink adapter and tracking-URI locality guard | 1183943 | jobs/eval/buddy_eval/{tracing,config}.py, tests/unit/buddy_eval/test_tracing_adapter.py |
| 2 | Bot LLM seam, CLI production defaults, `__main__` | f153b6f | services/chat_bot/buddy_bot/llm.py, jobs/eval/buddy_eval/{cli,__main__}.py, tests/unit/buddy_eval/test_entrypoint.py |

## What was built

- **MlflowTraceSink**: constructor requires `MLFLOW_TRACKING_URI` (TracingError naming it, raised before any mlflow call), then sets the tracking URI and experiment and enables LangChain and Anthropic autolog; the experiment id is kept for `trace_url`. `traced` runs `fn` under an `mlflow.trace(name=...)` root, tags the trace via `update_current_trace`, reads `get_last_active_trace_id` and raises TracingError when it is None. `log_expectations` calls `log_expectation` per key. `run` wraps `start_run(run_name, tags)` and yields the run id. `score` fetches each trace, disables Anthropic autolog (`autolog(disable=True)`), calls `mlflow.genai.evaluate(data=traces, scorers=[correctness, citation])`, and re-enables autolog in `finally`. No prediction function anywhere (`predict_fn` count 0).
- **config.py**: field validator on `mlflow_tracking_uri`, scheme http and host in {mlflow, localhost, 127.0.0.1}; message "MLFLOW_TRACKING_URI must point at the local MLflow server (mlflow, localhost or 127.0.0.1)". The CLI's validation-error describer prints only the variable name for it.
- **buddy_bot.llm**: `LlmBackendSettings` Protocol (read-only properties); `build_llm_client` parameter annotation changed, `BotSettings` import dropped. No behaviour change; test_llm_client.py passes unchanged. No mlflow dependency added to the bot.
- **cli.main**: final signature `main(argv=None, *, settings=None, llm_factory=None, connector_factory=None, sink_factory=None, out=None)`. The sink is still built after the zero-approved check. With `MLFLOW_TRACKING_URI` unset the default sink raises TracingError and the run ends with one `ERROR: TracingError: ... MLFLOW_TRACKING_URI ...` line, exit 1, zero LLM calls.
- **`__main__.py`**: `raise SystemExit(main())`, same shape as buddy_sync.

## Verification

- `./run-unit-tests.sh --single-file test_tracing_adapter.py tests/unit/buddy_eval`: 23 passed.
- `./run-unit-tests.sh --single-file test_entrypoint.py tests/unit/buddy_eval`: 6 passed.
- `./run-unit-tests.sh --single-file test_llm_client.py tests/unit/chat_bot`: 14 passed (unchanged).
- `./run-unit-tests.sh --all`: ruff, ruff format and mypy (165 files) clean; 1677 passed, 26 skipped; coverage gate met; tracing.py, config.py and `__main__.py` at 100 percent, cli.py 98 percent.
- Acceptance greps: only `tracing.py` imports mlflow; `predict_fn` 0; `mlflow.genai.evaluate(` 1; locality message 1; `class LlmBackendSettings` 1; `settings: BotSettings` 0; `raise SystemExit(main())` 1; `build_llm_client(` in cli 1; `MlflowTraceSink` in cli 2.

## Deviations from Plan

None - plan executed as written. Task 1 and Task 2 were verified together by one `--all` run before the two commits were made (separate commits, same verified tree).

## Notes for later plans

- **CI trigger (RESEARCH Pitfall 12):** the edit to `services/chat_bot/buddy_bot/llm.py` triggers the chat-bot workflow on push.
- A-04-1 and A-04-2 stand: the deep link route and MLflow 3.18.0 compatibility with the repo's newer langgraph and anthropic pins are covered by a call-contract test only; 05-06's compose smoke must check the real span tree, the trace tag lookup and that `@scorer` closures run inside a real `evaluate`.
- `Feedback` carries `value=None` for an unjudged citation check; accepted by the installed MLflow in a direct probe, not exercised through a real `evaluate`.
- The `sink.run` run id is yielded but still unused by the runner (as noted in 05-03).
- The eval image ENTRYPOINT `python -m buddy_eval` now resolves.

## Known Stubs

None.

## Threat Flags

None. T-05-09 (tracking URI allow-list, tested), T-05-39 (autolog suspended during score and restored in finally, tested incl. the raising path) and T-05-40 (annotation-only seam, test_llm_client.py unchanged) are mitigated as planned.

## Self-Check: PASSED

- FOUND: jobs/eval/buddy_eval/__main__.py, tests/unit/buddy_eval/test_tracing_adapter.py, tests/unit/buddy_eval/test_entrypoint.py
- FOUND commits: 1183943, f153b6f (ancestors of HEAD); `git rev-list --count 066748b..HEAD` = 2 at write time
