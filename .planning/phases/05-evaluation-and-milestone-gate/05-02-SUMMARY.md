---
phase: 05-evaluation-and-milestone-gate
plan: 02
subsystem: build-wiring
tags: [mlflow-skinny, pandas, supply-chain, docker, hashed-locks, eval]
requires:
  - phase: 04
    provides: sync stage, hashed lock script, structural stage tests
provides:
  - approved eval pins (mlflow-skinny==3.18.0, pandas==3.1.1) and the hashed jobs/eval lock
  - Dockerfile eval stage (tracing and telemetry off, serial MLflow, uid 10001)
  - buddy_eval package root and pyproject tool entries
affects: [05-03, 05-04, 05-06, 05-07, 05-10]
tech-stack:
  added: [mlflow-skinny 3.18.0, pandas 3.1.1, numpy 2.5.5 (transitive)]
  patterns: [per-stage hashed lock, structural Dockerfile tests, no CI build for the eval image]
key-files:
  created:
    - jobs/eval/requirements.txt
    - jobs/eval/requirements.lock
    - jobs/eval/buddy_eval/__init__.py
  modified:
    - Dockerfile
    - pyproject.toml
    - requirements-dev.txt
    - requirements-dev.lock
    - services/chat_bot/requirements.lock
    - services/mcp_server/requirements.lock
    - scripts/lock-requirements.sh
    - .github/dependabot.yml
    - .github/workflows/tests.yml
    - tests/unit/test_requirements_lock.py
    - tests/unit/test_dockerfile_stages.py
    - tests/unit/test_repo_layout.py
    - tests/unit/test_workflows.py
decisions:
  - "jobs/eval/requirements.txt holds only the two approved pins; requirements-dev.txt pulls it in so the test image can import mlflow"
  - "The eval stage has no CI workflow; test_workflows parametrizes the Dockerfile-drift test over STAGE_WORKFLOWS, not RUNTIME_STAGES"
metrics:
  duration: multi-session (gate checkpoint, then two executors)
  completed: 2026-11-22
status: complete
actuals:
  tokens: 49600
  tasks: 3
  commits: 2
plan_head_before: 34641ad60e50c0ed1f60f16d09e556f52f73be17
plan_head_after: cdc4040e4361539064a07685d98dc32e94012ce1
---

# Phase 5 Plan 02: Eval build wiring Summary

The two approved pins (`mlflow-skinny==3.18.0`, `pandas==3.1.1`) are locked with hashes, the test image carries them, and a new digest-pinned `eval` Dockerfile stage installs only `jobs/eval/requirements.lock` with `--require-hashes`, with tracing, telemetry and parallel evaluation switched off. The bot and server images and locks stay mlflow-free.

## Supply chain (05-02 Task 1)

Approved by the owner at the blocking legitimacy checkpoint ("approved"). Nothing containing these packages was installed, locked or built before the reply.

| Item | Approved value |
|------|----------------|
| `mlflow-skinny` | `==3.18.0` |
| `pandas` | `==3.1.1` |
| MLflow server image (used in 05-06) | `ghcr.io/mlflow/mlflow:v3.18.0@sha256:257204c77980b0f3450a26eb6089e487603fcdd4509529eadaf88f90669f5c13` |

Verification done by the orchestrator in Chrome on 2026-11-22:

- PyPI `mlflow-skinny` 3.18.0: repository link points to github.com/mlflow/mlflow.
- PyPI `pandas` 3.1.1 (released 2026-11-04 15:05 UTC): source points to github.com/pandas-dev/pandas.
- Look-alikes `mlflow-skiny` and `mlflowskinny` do not exist. `panda` and `pandas3` exist as unrelated packages and are not pinned.
- GHCR mlflow organization: tag v3.18.0 exists and its digest matches the pin above.

## Phase decisions (05-02)

| Key | Resolution | Implemented in |
|-----|------------|----------------|
| d20_collect_then_score (A8) | Amendment to D-20: a collect phase runs the bot under an `@mlflow.trace` root, logs expectations and caches `{outcome, trace_id}`; a score phase runs `mlflow.genai.evaluate(data=<traces>)` with custom scorers; the gate reads the local cache, not MLflow | 05-03, 05-04, 05-07, 05-08 |
| golden_privacy (Open Q4) | Any golden item whose `expected_sources` contains `handbook://` lives in the private `docs/internal/golden-handbook.yaml`, whatever its kind; a unit test asserts the committed golden YAML has no `handbook://` and no `clickup` | 05-03, 05-09, 05-11 |
| bot_seam (Open Q3) | `build_llm_client` takes a structural `LlmBackendSettings` Protocol because eval cannot reuse it cleanly (BotSettings requires ALLOWED_USERS, THREAD_KEY_SECRET, MCP_URL, INTAKE, VIDEO_THUMBNAIL_URL, MCP_AUDIENCE); no behaviour change, covered by the existing LLM client tests | 05-04 |
| mlflow_server_root (Open Q2, A6) | Official `ghcr.io/mlflow/mlflow:v3.18.0` by index digest, as root with `cap_drop: [ALL]`, `no-new-privileges`, port published on 127.0.0.1 only, no host mount | 05-06 |
| meridian_opus (Open Q1, A2) | `MERIDIAN_OPUS_MODEL=opus` on the compose meridian service; a `preflight` command; a human checkpoint before the first live run | 05-06, 05-12, 05-13 |
| rescore_policy (Open Q5) | `mlflow.genai.evaluate` runs only on traces not yet scored for the current scorer set; `scored` markers live in the cache | 05-07, 05-08 |
| empty_fixture_form | D-16's "small committed fixture index" is committed as fixture sources under `jobs/eval/fixtures/empty_context/` and built deterministically into the `eval-empty` volume by a one-shot, because `*.db` is gitignored and dockerignored (interprets D-16) | 05-10 |
| checkpoints | D-01 Guides commit (05-01 T2); SUS pins (05-02 T1); golden review (05-11 T2); Meridian preflight (05-13 T2); live run, empty-context and gate (05-13 T3) | as listed |

## Tasks

| Task | Name | Commit | Key files |
|------|------|--------|-----------|
| 1 | Legitimacy gate (checkpoint) | none (approval only) | this SUMMARY |
| 2 | Pin eval requirements, regenerate hashed locks, extend lock tests and Dependabot | cb17d30 | jobs/eval/requirements.txt, jobs/eval/requirements.lock, requirements-dev.lock, scripts/lock-requirements.sh, tests/unit/test_requirements_lock.py, .github/dependabot.yml |
| 3 | Dockerfile eval stage, pyproject entries, package root, structural tests | cdc4040 | Dockerfile, pyproject.toml, jobs/eval/buddy_eval/__init__.py, tests/unit/test_dockerfile_stages.py, .github/workflows/tests.yml |

Task 2 was done by an earlier executor and committed by this one after re-running `test_requirements_lock.py` (26 passed). The earlier executor halted at the default-branch commit guard; the orchestrator then set `git.allow_default_branch_commits: true` on the owner's authorization to commit on main.

## Verification

- `./run-unit-tests.sh --single-file test_requirements_lock.py tests/unit`: 26 passed, including `test_bot_and_server_locks_carry_no_mlflow` for both locks.
- `./run-unit-tests.sh --single-file test_dockerfile_stages.py tests/unit`: 28 passed, including `test_eval_stage_copies_exactly_its_sources` and `test_eval_stage_disables_tracing_and_telemetry_and_ends_non_root`.
- `docker build --target eval -t ai-buddy-eval:check .`: exit 0, no hash mismatch; `docker run --rm --entrypoint python ai-buddy-eval:check -c "import mlflow, pandas, buddy_bot, buddy_eval"` exits 0 (mlflow 3.18.0).
- `./run-unit-tests.sh --all`: ruff, ruff format, mypy (152 files) clean; 1599 passed, 26 skipped, coverage 97.61 percent (gate 80).

## Deviations from Plan

**1. [Rule 1 - Expectation mismatch] python-multipart did not move in the shared locks**
- **Found during:** Task 2 (lock regeneration, earlier executor)
- **Issue:** RESEARCH expected cachetools 8.0.0 to 7.3.3 and python-multipart 0.0.33 to 0.0.34. Only cachetools moved (`services/chat_bot/requirements.lock`, `services/mcp_server/requirements.lock`, `requirements-dev.lock`). python-multipart stayed at its current version.
- **Fix:** none needed; no direct pin of another requirements file changed, so the plan's stop condition did not trigger.
- **Commit:** cb17d30

**2. [Plan wording] `grep -c 'jobs/eval' pyproject.toml` returns 4, not "at least 5"**
- **Found during:** Task 3 acceptance greps
- **Issue:** `grep -c` counts lines. The plan lists exactly four lines that mention `jobs/eval` (pytest pythonpath, mypy_path, mypy files via `jobs/eval/buddy_eval`, ruff src); coverage source and isort first-party use `buddy_eval`, which is not a `jobs/eval` match. All six required entries are present.
- **Fix:** none; the count in the plan was off by one.
- **Commit:** cdc4040

**3. [Rule 1 - Bug, test import] Removed the now-unused `RUNTIME_STAGES` import from `tests/unit/test_workflows.py`**
- **Found during:** Task 3, after switching the parametrization to `tuple(STAGE_WORKFLOWS)` (would fail ruff F401).
- **Commit:** cdc4040

## Notes for later plans

- `docker run ai-buddy-eval:check` with no arguments fails with "No module named buddy_eval.__main__": the stage's ENTRYPOINT `python -m buddy_eval` has no `__main__` until 05-03 adds the CLI. The plan only asks for the package root, so this is expected.
- A-02-2 stands: MLflow 3.18.0 declares tested ranges below this repo's langgraph and anthropic pins; 05-06's smoke re-checks it.

## Known Stubs

None. `buddy_eval/__init__.py` is intentionally minimal (docstring and version); 05-03 builds the package.

## Threat Flags

None. The new surface (two PyPI packages, one GHCR image digest) is covered by T-05-04, T-05-05, T-05-06, T-05-07 and T-05-SC in the plan's register.

## Self-Check: PASSED

- FOUND: jobs/eval/requirements.txt, jobs/eval/requirements.lock, jobs/eval/buddy_eval/__init__.py
- FOUND commits: cb17d30, cdc4040 (ancestors of HEAD); `git rev-list --count 34641ad..HEAD` = 2 at write time
