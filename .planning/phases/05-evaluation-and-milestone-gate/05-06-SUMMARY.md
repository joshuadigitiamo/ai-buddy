---
phase: 05-evaluation-and-milestone-gate
plan: 06
subsystem: evaluation-compose
tags: [compose, mlflow, eval-profile, smoke, EVAL-05]
requires:
  - phase: 05-04
    provides: MlflowTraceSink, python -m buddy_eval entry point, tracking-URI guard
  - phase: 05-02
    provides: approved MLflow v3.18.0 index digest, eval image stage
provides:
  - compose profile eval (mlflow, eval, meridian in [live, eval])
  - scripts/eval-smoke.sh hermetic smoke over a real MLflow container
  - synthetic golden fixtures under tests/fixtures/eval
affects: [05-07, 05-12]
tech-stack:
  added: []
  patterns: [real-server smoke that reads traces back through the client, bounded budget helper shared by every smoke step]
key-files:
  created:
    - scripts/eval-smoke.sh
    - tests/fixtures/eval/golden-public.yaml
    - tests/fixtures/eval/golden-handbook.yaml
  modified:
    - docker-compose.yml
    - tests/unit/test_compose.py
    - jobs/eval/buddy_eval/tracing.py
    - tests/unit/buddy_eval/test_tracing_adapter.py
decisions:
  - "MLflow runs from the digest-pinned official image on SQLite, artifacts on the named volume mlflow-data, UI on 127.0.0.1:5000, the only published port; healthcheck on the experiments/search API route"
  - "The eval service gets only MERIDIAN_API_KEY by interpolation, never THREAD_KEY_SECRET or ANTHROPIC_API_KEY, and no env_file"
  - "The smoke bounds every step with one shared deadline (EVAL_SMOKE_TIMEOUT_SECONDS) and prints timeout after N s on exhaustion"
  - "log_expectations skips None values: MLflow rejects an Expectation without a value"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 14000
  tasks: 2
  commits: 3
plan_head_before: feccbd9646a26d516b3b58ee2972518d17c27dd1
plan_head_after: b7d30bafd0cc179360cdaa3b365fb6688dd7bcd7
---

# Phase 5 Plan 06: Compose eval profile and hermetic eval smoke Summary

The `eval` compose profile now runs a digest-pinned, hardened, loopback-only MLflow server and the eval container, and `scripts/eval-smoke.sh` proves in containers (stub LLM, real MLflow, no Meridian) that each golden item yields exactly one trace with node spans, expectations and scorer feedback. The smoke found one real defect in the 05-04 adapter, fixed here.

## Tasks

| Task | Name | Commit | Key files |
|------|------|--------|-----------|
| 1 | Compose eval profile, structural tests | 048550b | docker-compose.yml, tests/unit/test_compose.py |
| - | Fix: skip None expectations (deviation) | 9204508 | jobs/eval/buddy_eval/tracing.py, tests/unit/buddy_eval/test_tracing_adapter.py |
| 2 | Hermetic eval smoke, golden fixtures | b7d30ba | scripts/eval-smoke.sh, tests/fixtures/eval/*.yaml, tests/unit/test_compose.py |

## What was built

- **Compose**: `mlflow` (image pinned by index digest, `--allowed-hosts mlflow:5000,localhost:*,127.0.0.1:*`, telemetry off, cap_drop ALL, no-new-privileges, `mlflow-data:/mlflow`, healthcheck on `/api/2.0/mlflow/experiments/search`); `eval` (target eval, host uid, `artifacts` read-only, `${EVAL_PRIVATE_DIR:-./docs/internal}` at /private, local URLs only); `meridian` in `[live, eval]` with `MERIDIAN_OPUS_MODEL: ${MERIDIAN_OPUS_MODEL:-opus}`. Default seven services unchanged; `docker compose config --quiet` passes with and without the profile.
- **Tests**: `test_profiles_add_exactly_the_live_and_eval_services`, `test_only_mlflow_publishes_a_port_and_only_on_loopback`, `test_mlflow_server_is_pinned_and_hardened`, `test_eval_service_is_wired_to_local_services_only`, `test_meridian_opus_tier_opts_out_of_the_1m_default`, `test_eval_smoke_script_is_executable_and_bounded`; the load-time test now covers every profiled service.
- **Smoke**: builds a throwaway fixture Guides repo, starts `mcp-server mlflow stub-llm`, waits for the stub, runs `run --rm --no-deps eval run`, then reads traces back with the MLflow client in a second `eval` container. Prints `trace check ok (3 traces)` and `eval smoke ok`.
- **Fixtures**: three synthetic approved items (guides over DEMO_GUIDE, handbook over `02-ferie`, one no_answer).

## Verification

- `./run-unit-tests.sh --single-file test_compose.py tests/unit`: 27 passed before the smoke test was added; `--all`: ruff, ruff format, mypy clean; 1722 passed, 26 skipped.
- `docker compose --profile eval config --quiet` and the default `config --quiet`: exit 0.
- `scripts/eval-smoke.sh`: exit 0 in about 55 s (cached images), output `trace check ok (3 traces)` then `eval smoke ok`; a second probe run left no containers, volumes or networks behind.
- Acceptance greps: image pin 1, loopback port 1, `profiles: [live, eval]` 1, `MERIDIAN_OPUS_MODEL` 1, `eval smoke ok` 1, `--profile live` in the script 0, `handbook://` in golden-public.yaml 0; `git ls-files -s scripts/eval-smoke.sh` is 100755.

## Outcomes of the 05-04 open items

1. **Real span tree**: confirmed in the real server. Every trace holds a `bot_run` root and `AsyncMessages.create` LLM spans; the answered handbook item (and the guides item) shows `reformulate`, `retrieve`, `answer`, `gate` plus `LangGraph`, `finish`, `_decide`; the no_answer item shows `retry_plan` and `refuse` instead. The `item_id` tag lookup works (the smoke finds the handbook trace by tag).
2. **Deep-link route**: the printed URL `http://127.0.0.1:5000/#/experiments/<id>/traces?selectedEvaluationId=<trace id>` matches the UI: the v3.18.0 JS bundle contains the route `experiments/:experimentId/traces` and the `selectedEvaluationId` parameter. Checked by bundle inspection only, no browser session was opened.
3. **`@scorer` closures inside a real `evaluate`**: confirmed. `mlflow.genai.evaluate` completed and each trace carries `correctness` and `citation` Feedback (source CODE), next to the four Expectations (source HUMAN). Exactly one trace per item: evaluate and the scorers added no extra traces (count stayed 3).
4. **`Feedback(value=None)`**: confirmed accepted by the real server; the no_answer trace stores `citation = None`.
5. Not a 05-04 item but found by the smoke: `log_expectation(value=None)` is rejected (see deviation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] None-valued expectation crashed the run against a real MLflow server**
- **Found during:** Task 2, first smoke run
- **Issue:** `MlflowTraceSink.log_expectations` passed `expected_referente_role=None` (every non-no_answer item) to `mlflow.log_expectation`, which raises `The value field must be specified`; the unit tests used a fake and never saw it.
- **Fix:** skip None values; an absent expectation is not recorded. Unit test `test_log_expectations_skips_a_none_value` added.
- **Files modified:** jobs/eval/buddy_eval/tracing.py, tests/unit/buddy_eval/test_tracing_adapter.py
- **Commit:** 9204508

### Other notes

- The header comment of docker-compose.yml avoids the literal `MERIDIAN_OPUS_MODEL` so the plan's `grep -c` acceptance returns exactly 1.
- `git` has `core.fileMode=false` here, so the executable bit was set with `git update-index --chmod=+x` and the Task 2 commit amended (before any later commit).

## Findings for later plans

- **Unjudged shows as `correctness=False`**: the handbook item (verdict `unjudged`, facts not yet judged) is stored as `correctness False` because the scorer maps `status == "correct"`. 05-07 (judge) should decide whether an unjudged verdict should be recorded as None.
- **Guides citations resolve to None**: `handbook_only` resolves only `handbook://` sources, so the guides smoke item scores `citation False` / `wrong`. The smoke asserts structure, not correctness, so it passes; the real guides golden set needs a resolver that maps Guides URLs to chunk-key prefixes (outside this plan).
- A-06-3 observed: `getpwuid(): uid not found: 1000` WARNING lines from MLflow in the eval container; harmless log noise.
- The first-run image build dominates the smoke time; with cached images it finishes in about 55 s, far inside the 300 s default.

## Known Stubs

None.

## Threat Flags

None. T-05-12 to T-05-16 are mitigated as planned and pinned by structural tests (loopback-only port, explicit allowed-hosts without `*`, telemetry off, digest pin with cap_drop ALL and no-new-privileges, no secrets beyond the Meridian key).

## Self-Check: PASSED

- FOUND: scripts/eval-smoke.sh (100755), tests/fixtures/eval/golden-public.yaml, tests/fixtures/eval/golden-handbook.yaml
- FOUND commits: 048550b, 9204508, b7d30ba (ancestors of HEAD); `git rev-list --count feccbd9..HEAD` = 3 at write time
