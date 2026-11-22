---
phase: 05-evaluation-and-milestone-gate
reviewed: 2026-11-22T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - jobs/eval/buddy_eval/__init__.py
  - jobs/eval/buddy_eval/__main__.py
  - jobs/eval/buddy_eval/cache.py
  - jobs/eval/buddy_eval/cli.py
  - jobs/eval/buddy_eval/config.py
  - jobs/eval/buddy_eval/empty_context.py
  - jobs/eval/buddy_eval/fixture.py
  - jobs/eval/buddy_eval/gate.py
  - jobs/eval/buddy_eval/golden.py
  - jobs/eval/buddy_eval/judge.py
  - jobs/eval/buddy_eval/preflight.py
  - jobs/eval/buddy_eval/recall.py
  - jobs/eval/buddy_eval/report.py
  - jobs/eval/buddy_eval/runner.py
  - jobs/eval/buddy_eval/scoring.py
  - jobs/eval/buddy_eval/sources.py
  - jobs/eval/buddy_eval/tracing.py
  - deploy/compose/stub_llm.py
  - services/chat_bot/buddy_bot/llm.py
  - scripts/eval-smoke.sh
  - scripts/lock-requirements.sh
  - Dockerfile
  - docker-compose.yml
  - pyproject.toml
findings:
  critical: 1
  warning: 3
  info: 5
  total: 9
  necessity: 0
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-11-22
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Reviewed the phase-5 evaluation job (`buddy_eval`), the `LlmBackendSettings` protocol refactor in `buddy_bot/llm.py`, the stub judge branch, the `eval` Docker stage and compose profile, the smoke script and the lock script. CLAUDE.md does not exist in the repo; the global rules were applied. The review covered the code and did not run anything.

The gate arithmetic, the privacy posture of the console output, the judge prompt-injection fencing, the cache path-safety check and the compose/Dockerfile hardening are sound. The live-gate FAIL on `invented_policies` (gd-13) was not treated as a code defect.

Verified problems:
- One data-integrity defect in the verdict cache that can attach a stale judge verdict to a freshly collected answer.
- A scoring-feedback marker that cannot notice a changed verdict.
- Infrastructure failures that bypass the consecutive-error protection and crash the run.
- The `lint` command prints private handbook page ids.

No structural findings (fallow) were provided. Necessity was assessed; nothing qualified.

## Critical Issues

### CR-01: Judge verdict cache key does not identify the reply it judged (stale verdict applied to a re-collected answer)

**File:** `jobs/eval/buddy_eval/runner.py:172-189` (key), `runner.py:130-140` and `runner.py:242-257` (re-collection)
**Issue:** The verdict key is `key_for(outcome_key, judge_model, judge_prompt_version, scoring_version)`, and `outcome_key` is derived only from the item, the index identity, the bot version and the model settings. It contains nothing about the reply. `_cached_outcome` returns `None` whenever `sink.trace_exists(trace_id)` is false, for example after the MLflow volume is wiped or recreated while `PRIVATE_DIR/eval/cache` survives. The item is then collected again and `cache.put("outcome", key, ...)` overwrites the outcome under the same key. The model is not deterministic, so the new reply usually differs from the old one. `_judge_item` then computes the same verdict key, hits the old cached verdict and scores the new reply with the old answer's facts and invented-claim flags. No log line shows it, and the result feeds `correctness_with_citation` and `invented_policies`, which are the gate inputs. Cached verdicts also survive being judged against a different `trace_id`.
**Fix:** Make the reply part of the verdict identity:
```python
reply_digest = hashlib.sha256(
    json.dumps(reply.model_dump(mode="json"), sort_keys=True).encode("utf-8")
).hexdigest()
key = key_for(
    outcome_key=outcome_key,
    reply_digest=reply_digest,
    judge_model=settings.judge_model,
    judge_prompt_version=JUDGE_PROMPT_VERSION,
    scoring_version=SCORING_VERSION,
)
```
Alternatively, delete the cached verdict whenever the outcome is re-collected.

## Warnings

### WR-01: MCP session or transport failures are not turned into errored items, so they crash the run instead of tripping the consecutive-error stop

**File:** `jobs/eval/buddy_eval/runner.py:92-93`, `jobs/eval/buddy_eval/empty_context.py:235-237`, `jobs/eval/buddy_eval/recall.py:401`, `jobs/eval/buddy_eval/cli.py:67`
**Issue:** `run_workflow` opens `deps.mcp.session()` itself (`workflow.py:294`). `FastMcpConnector.session()` enters `fastmcp.Client` with no wrapping, so an unreachable or restarting MCP server raises a raw transport exception (httpx/fastmcp error or an `ExceptionGroup`). `McpToolError` is raised only by `FastMcpTools._call`. `collect_item` and `empty_context._collect` catch only `(LlmError, McpToolError)`, and `measure_recall` does not catch at all around `connector_factory(...).session()`. `_EXPECTED_ERRORS` in `cli.py` covers `OSError`, but httpx connect errors are not `OSError` subclasses. The result is an uncaught traceback that ends `gate` or `run` before the judge, score and report phases. This is the failure that `max_consecutive_errors` and the "re-run to resume" message exist for; mid-run outages never reach that path. Completed outcomes stay cached, but no report or verdict is written.
**Fix:** Catch `Exception` around the traced call in `collect_item` and `_collect`, log `type(exc).__name__` only, and return the errored outcome. For recall, wrap the `async with` in a handler that marks every remaining item errored. Add `McpToolError` and `LlmError` to `_EXPECTED_ERRORS` as a last resort.

### WR-02: "Scored" marker is keyed only by trace id and scorer-set version, so a changed verdict is never re-attached

**File:** `jobs/eval/buddy_eval/runner.py:288-297`, `jobs/eval/buddy_eval/cache.py:94-99`, `jobs/eval/buddy_eval/cli.py:255-258`
**Issue:** `cache.is_scored(trace_id, SCORER_SET_VERSION)` suppresses feedback for any trace that has been scored once, whatever the verdict was. When the judge prompt, the judge model or `SCORING_VERSION` changes, the cached outcome and trace are reused, the verdict is recomputed, but the MLflow feedback stays at the old value because `SCORER_SET_VERSION` (tracing.py:31) is a manual constant that is not bumped by those changes. The JSON report and the console then disagree with what the MLflow UI shows for the same trace. The same applies to the empty-context marker when a rerun changes an item's status. `SCORER_SET_VERSION` is only bumped when someone remembers.
**Fix:** Include a verdict digest in the marker: `mark_scored(trace_id, f"{SCORER_SET_VERSION}-{status_digest}")`, where the digest hashes `(status, checks, invented, judge_prompt_version, judge_model)`. Alternatively derive the marker version from `JUDGE_PROMPT_VERSION`, `SCORING_VERSION` and `judge_model` automatically.

### WR-03: `lint` prints private handbook page ids to the console

**File:** `jobs/eval/buddy_eval/golden.py:289`, rendered by `jobs/eval/buddy_eval/cli.py:167-168`
**Issue:** The issue text is `f"{entry} not in the current index"`, where `entry` is a `handbook://<page_id>` expected source from the private file. The rest of the job explicitly keeps page ids off the console (`cli.py:210` comment, `recall.py` docstring, `format_empty_context`, the `LintIssue` docstring says "never question or answer text" but not ids). In a public repo, where lint output is likely pasted into issues or CI logs, a stale-index lint run leaks internal page identifiers, which is inconsistent with the stated posture.
**Fix:** Print the position instead of the entry, for example `f"expected_sources[{position}] not in the current index"`, using the index from `enumerate(item.expected_sources)`. Print the entry only for non-handbook (Guides) keys.

## Info

### IN-01: `EVAL_LLM_BACKEND=api` is advertised but cannot work through compose

**File:** `docker-compose.yml:369` (eval environment), `docker-compose.yml:40` (header comment), `docker-compose.yml:403` (meridian dependency)
**Issue:** The `eval` service passes `LLM_BACKEND` but not `ANTHROPIC_API_KEY`, and the header lists `EVAL_LLM_BACKEND` as an optional variable. `EvalSettings` rejects `api` without the key, so the option is accepted by compose and always fails at startup. The service also declares `depends_on: meridian: service_started` for every backend, so Meridian (and its external `meridian-claude` volume) is required even then.
**Fix:** Drop `EVAL_LLM_BACKEND` from the documented knobs, or pass `ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}` and make the Meridian dependency conditional.

### IN-02: `assert` used for control-flow narrowing in a runtime path

**File:** `jobs/eval/buddy_eval/empty_context.py:265`, `jobs/eval/buddy_eval/runner.py:110`
**Issue:** `assert host is not None and before is not None` and `assert outcome.reply is not None` are stripped under `python -O`. Both are internal invariants, so the risk is low, but the checks are doing the work of type narrowing.
**Fix:** Pass `host: str` and `before: int` as typed parameters, or raise `RuntimeError`.

### IN-03: `_safe_url` can raise outside the try block in preflight

**File:** `jobs/eval/buddy_eval/preflight.py:485-492`, `preflight.py:517`, `preflight.py:547`
**Issue:** `parts.port` raises `ValueError` for a malformed port. `_safe_url(url)` is called before the `try` in `_open_session` and in `run_preflight`, so a bad `MCP_URL` or `MLFLOW_TRACKING_URI` crashes preflight instead of reporting a failed check, which contradicts the "any failure is a reported check result" intent. `MLFLOW_TRACKING_URI` is already validated by `EvalSettings`, but `MCP_URL` is not.
**Fix:** Compute the target inside the `try`, or catch `ValueError` in `_safe_url` and return `UNSET`.

### IN-04: Duplicated constants and type aliases across modules

**File:** `jobs/eval/buddy_eval/golden.py:24` and `jobs/eval/buddy_eval/sources.py:20` (`HANDBOOK_SCHEME`), `runner.py:31` and `empty_context.py:37` (`TRACE_NAME = "bot_run"`), `LlmFactory`, `ConnectorFactory` and `Sleep` aliases in `cli.py`, `runner.py`, `empty_context.py`, `recall.py` and `preflight.py`
**Issue:** `HANDBOOK_SCHEME` is defined twice, and `scoring.py` imports it from `golden` while `sources.py` uses its own copy. The traced root name must match in both runners for the smoke check to find the span. The factory aliases are repeated in five modules.
**Fix:** Keep one definition (`sources.py` for the scheme; a shared `TRACE_NAME` in `tracing.py`) and import it. Put the factory aliases in one module.

### IN-05: Fixture page date assumes a plain date

**File:** `jobs/eval/buddy_eval/fixture.py:253-266`
**Issue:** `str(entry.get("last_updated"))` is joined as `f"{updated}T00:00:00+00:00"`. An unquoted YAML timestamp with a time part becomes a `datetime`, and `str()` of it yields `2026-01-01 10:00:00`, producing a malformed ISO string. The committed fixture is safe today; a later edit is not validated.
**Fix:** Parse with `date.fromisoformat(str(value)[:10])` and raise `FixtureError` on failure.

---

_Reviewed: 2026-11-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
