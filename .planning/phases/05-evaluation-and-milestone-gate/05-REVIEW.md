---
phase: 05-evaluation-and-milestone-gate
reviewed: 2026-11-22T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - .env.example
  - docker-compose.yml
  - jobs/eval/buddy_eval/cli.py
  - jobs/eval/buddy_eval/empty_context.py
  - jobs/eval/buddy_eval/golden.py
  - jobs/eval/buddy_eval/recall.py
  - jobs/eval/buddy_eval/runner.py
  - jobs/eval/buddy_eval/tracing.py
  - jobs/eval/golden/guides.yaml
  - services/chat_bot/README.md
  - services/chat_bot/buddy_bot/mcp_client.py
  - services/chat_bot/buddy_bot/prompts.py
  - services/chat_bot/buddy_bot/workflow.py
  - tests/unit/buddy_eval/test_empty_context.py
  - tests/unit/buddy_eval/test_gate_command.py
  - tests/unit/buddy_eval/test_golden.py
  - tests/unit/buddy_eval/test_recall.py
  - tests/unit/buddy_eval/test_resume.py
  - tests/unit/buddy_eval/test_tracing_adapter.py
  - tests/unit/chat_bot/test_prompts.py
  - tests/unit/chat_bot/test_refusal.py
  - tests/unit/chat_bot/test_workflow.py
  - tests/unit/test_compose.py
findings:
  critical: 0
  warning: 1
  info: 8
  total: 9
  necessity: 0
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-11-22
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Incremental re-review of the files changed by plans 05-14 to 05-17 since commit 5173860. The delta covers the second Guides search with the question text (05-14), the recall and run transport-failure handling (05-15), the verdict-keyed scored marker and stale-feedback deletion (05-16), and Meridian's own long-lived token profile (05-17). CLAUDE.md does not exist in the repo; the global rules were applied. Nothing was run. The review read the full current files and the delta.

Prior findings CR-01 and WR-01 to WR-03 were verified fixed (next section). No new critical issue was found. One new warning concerns the stale-feedback deletion, which is not limited to feedback the harness wrote. Prior IN-01 to IN-05 still stand; their line references are updated. Three new info items were added.

Not treated as defects: the golden and prompt edits made after the live FAIL are recorded in the phase gap-decision file as approved by the project owner, and the final gate result was accepted as is.

No structural findings (fallow) were provided. Necessity was assessed; nothing qualified.

## Verification of prior fixes

No finding headings here; these items are closed.

- CR-01 (verdict cache key): fixed. `runner.py:194-201` builds the verdict key from the outcome key, a digest of the full reply, the judge model, the judge prompt version and the scoring version. A re-collected item with a different reply is judged again, and an identical reply reuses the verdict. Both cases are covered by `tests/unit/buddy_eval/test_resume.py` (the re-collected-item tests).
- WR-01 (transport failures crash the run): fixed. `runner.py:111-114` and `empty_context.py:240-243` turn any non-tracing exception into an errored item and log the type name only. `recall.py:217-221` errors every unmeasured item when the session fails to open, breaks mid-run or fails on close. The gate test asserts one FAIL verdict, a written report and no traceback. `TracingError` still ends the run, by design.
- WR-02 (scored marker blind to a changed verdict): fixed. `runner.py:68-80` appends a digest of status, checks, reasons, invented flag and judge verdict to the marker. `empty_context.py:429-431` keys the empty-context marker on the status. `tracing.py:181-198` deletes earlier same-name feedback before re-scoring (but see WR-04).
- WR-03 (lint prints private page ids): fixed. `golden.py:215-218` names a handbook entry by its position only. The test asserts that neither the scheme nor the id appears in the output. Other lint messages carry item ids and field names only.

## Warnings

### WR-04: Stale-feedback cleanup deletes every feedback row with a scorer name, including human or other-source ones

**File:** `jobs/eval/buddy_eval/tracing.py:181-198`
**Issue:** `_without_stale_feedback` selects `assessment.feedback is not None and assessment.name in names`, then deletes each match. Nothing checks the assessment source. A reviewer who labels a trace in the MLflow UI under the same name (`correctness`, `citation`, `invented_policy`, `refused`) loses that label the next time the trace is re-scored. The docstring calls the rows "derived data the cached verdicts re-create". That holds only for rows the harness wrote. Human labels are not derived, and nothing re-creates them. The deletion also runs before `mlflow.genai.evaluate` (`tracing.py:173-177`). If evaluate fails, the trace is left with no feedback until the next run. The marker is not written on failure, so the next run re-scores it, but the gap exists and the failure is a raw MLflow exception.
**Fix:** Delete only rows the harness wrote, for example by source type:
```python
stale = [
    a.assessment_id
    for a in trace.info.assessments
    if a.feedback is not None
    and a.name in names
    and a.source is not None
    and a.source.source_type == "CODE"
]
```
If MLflow lets the scorer set a stable source id, filter on that too. Optionally log feedback first and delete the old rows after evaluate succeeds, so a failed evaluate leaves the old values in place.

## Info

### IN-01: `EVAL_LLM_BACKEND=api` is advertised but cannot work through compose

**File:** `docker-compose.yml:40` (header comment), `docker-compose.yml:378` (eval environment), `docker-compose.yml:436` (meridian dependency)
**Issue:** Still present. The `eval` service passes `LLM_BACKEND` but not `ANTHROPIC_API_KEY`, and the header lists `EVAL_LLM_BACKEND` as an optional variable. `EvalSettings` rejects `api` without the key, so the option is accepted by compose and always fails at startup. The service also declares `depends_on: meridian: service_started` for every backend, so Meridian and its external `meridian-claude` volume are required even then.
**Fix:** Drop `EVAL_LLM_BACKEND` from the documented knobs, or pass `ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}` and make the Meridian dependency conditional.

### IN-02: `assert` used for control-flow narrowing in a runtime path

**File:** `jobs/eval/buddy_eval/empty_context.py:271`, `jobs/eval/buddy_eval/runner.py:131`
**Issue:** Still present (lines moved). `assert host is not None and before is not None` and `assert outcome.reply is not None` are stripped under `python -O`. Both are internal invariants, so the risk is low, but the checks do the work of type narrowing.
**Fix:** Pass `host: str` and `before: int` as typed parameters, or raise `RuntimeError`.

### IN-03: `_safe_url` can raise outside the try block in preflight

**File:** `jobs/eval/buddy_eval/preflight.py:54-61`, `preflight.py:86`, `preflight.py:116`
**Issue:** Still present (prior line numbers were wrong; these are the current ones). `parts.port` raises `ValueError` for a malformed port. `_safe_url(url)` is called before the `try` in `_open_session` and in `run_preflight`, so a bad `MCP_URL` crashes preflight instead of reporting a failed check. This contradicts the "any failure is a reported check result" intent. `MLFLOW_TRACKING_URI` is validated by `EvalSettings`; `MCP_URL` is not.
**Fix:** Compute the target inside the `try`, or catch `ValueError` in `_safe_url` and return `UNSET`.

### IN-04: Duplicated constants and type aliases across modules

**File:** `jobs/eval/buddy_eval/golden.py:24` and `jobs/eval/buddy_eval/sources.py:20` (`HANDBOOK_SCHEME`), `jobs/eval/buddy_eval/runner.py:31` and `jobs/eval/buddy_eval/empty_context.py:37` (`TRACE_NAME = "bot_run"`), and the `LlmFactory`, `ConnectorFactory` and `Sleep` aliases in `cli.py`, `runner.py`, `empty_context.py`, `recall.py` and `preflight.py`
**Issue:** Still present. `HANDBOOK_SCHEME` is defined twice, and `scoring.py` imports it from `golden` while `sources.py` keeps its own copy. The traced root name must match in both runners for the smoke check to find the span. The factory aliases are repeated in five modules. The new `_missing_source` in `golden.py:217` adds another use of the `golden` copy.
**Fix:** Keep one definition (`sources.py` for the scheme; a shared `TRACE_NAME` in `tracing.py`) and import it. Put the factory aliases in one module.

### IN-05: Fixture page date assumes a plain date

**File:** `jobs/eval/buddy_eval/fixture.py:70-82`
**Issue:** Still present. `str(entry.get("last_updated"))` is joined as `f"{updated}T00:00:00+00:00"`. An unquoted YAML timestamp with a time part becomes a `datetime`, and `str()` of it yields `2026-01-01 10:00:00`, producing a malformed ISO string. The only check is that the value is non-empty. The committed fixture is safe today; a later edit is not validated.
**Fix:** Parse with `date.fromisoformat(str(value)[:10])` and raise `FixtureError` on failure.

### IN-06: Dead single-character entries in the question stopword set

**File:** `services/chat_bot/buddy_bot/workflow.py:54-58`, `workflow.py:147`
**Issue:** `guides_question_query` drops a token when `len(word) >= 2` is false, before it looks the word up in `_QUESTION_STOPWORDS`. The entries `a`, `e`, `è`, `i` and `o` are one character long after the non-word strip, so they can never be reached. The list reads as if they were doing work, and a maintainer tuning it may rely on them.
**Fix:** Remove the five single-character entries and keep the `len(word) >= 2` rule, or drop the length rule and keep them explicit. One of the two is enough.

### IN-07: An empty `MERIDIAN_OAUTH_TOKEN` yields a silently useless Meridian profile

**File:** `docker-compose.yml:220`
**Issue:** `MERIDIAN_PROFILES` interpolates `${MERIDIAN_OAUTH_TOKEN:-}`, so a missing variable produces `"oauthToken":""`. The comment on `MERIDIAN_API_KEY` explains why `:?` cannot be used (compose interpolates every service, including inactive profiles). The remaining failure mode is the one 05-17 set out to remove: Meridian starts, `restart: unless-stopped` keeps it up, and every call fails later with a login error. `chat-bot-live` fails fast on a missing `MERIDIAN_API_KEY` but has no equivalent for the token, because it never receives it. The eval preflight would show the failure, but the live profile would not.
**Fix:** Add a Meridian healthcheck that reports an unauthenticated state, or an entrypoint wrapper that exits when the token is empty (pass the token as its own env var and test it there, so the guard does not depend on compose interpolation). Failing that, state the check in the README start step.

### IN-08: Duplicated and inconsistent exception branches around the traced call

**File:** `jobs/eval/buddy_eval/empty_context.py:235-243`, `jobs/eval/buddy_eval/runner.py:107-114`
**Issue:** In `empty_context._collect` the `except (LlmError, McpToolError)` branch and the later `except Exception` branch have identical bodies, so the first one is redundant. In `runner.collect_item` the same first branch returns without logging, while the generic branch logs the type name; an item errored by `LlmError` or `McpToolError` leaves no warning line naming the cause, only the later `errored` status line. The `# noqa: BLE001` comments in both files refer to a rule that is not enabled (`pyproject.toml` selects E, F, I, UP, B and SIM).
**Fix:** Collapse each pair into `except TracingError: raise` followed by one `except Exception` that logs the type name. Drop the unused `noqa` markers.

---

_Reviewed: 2026-11-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
