---
phase: 05-evaluation-and-milestone-gate
plan: 08
subsystem: evaluation-judge-report
tags: [eval, judge, invented-policy, report, stub-llm, EVAL-03, EVAL-05]
requires:
  - phase: 05-07
    provides: ResultCache and verdict namespace, index identity, scored markers, RunResult.identity
  - phase: 05-04
    provides: TraceSink Protocol, MlflowTraceSink scorers
provides:
  - JudgeVerdict schema, fenced judge prompt, JUDGE_PROMPT_VERSION, judge_reply
  - Final D-09 verdicts from the judge's facts and the D-10 invented-policy flag and count
  - Judge phase in run_items with a verdict cache (key: outcome key, judge model, prompt version, scoring version)
  - TraceSink.untraced(), the invented_policy scorer, SCORER_SET_VERSION 2
  - Console run report, private JSON report, stub judge answer
affects: [05-09, 05-10, 05-12]
tech-stack:
  added: []
  patterns: [judge through the bot's own LlmClient.structured, data fenced in tagged blocks with opening and closing tags neutralized, one cached judge call yields facts and invented claims, private text only in JSON report and local trace]
key-files:
  created:
    - jobs/eval/buddy_eval/judge.py
    - tests/unit/buddy_eval/test_judge.py
    - tests/unit/buddy_eval/test_scoring.py
    - tests/unit/buddy_eval/test_report.py
  modified:
    - jobs/eval/buddy_eval/scoring.py
    - jobs/eval/buddy_eval/runner.py
    - jobs/eval/buddy_eval/tracing.py
    - jobs/eval/buddy_eval/report.py
    - deploy/compose/stub_llm.py
    - tests/unit/test_stub_llm.py
    - tests/unit/buddy_eval/conftest.py
    - tests/unit/buddy_eval/test_tracing_adapter.py
    - tests/unit/buddy_eval/test_resume.py
    - tests/unit/buddy_eval/test_runner.py
    - tests/unit/buddy_eval/test_tracer.py
    - tests/unit/buddy_eval/test_entrypoint.py
decisions:
  - "The judge runs once per item whose reply kind is answer, whatever the item kind; refusals, referrals and smalltalk cost no call and are never invented"
  - "Facts are matched by position (A-08-1): a missing judge entry is an absent fact, extra entries are ignored; the facts check is recorded even when a deterministic check already failed"
  - "A judge LlmError turns the item into an errored outcome `judge:<TypeName>` that keeps its trace id; it is not cached, so a rerun asks the judge again without re-collecting"
  - "Unjudged verdicts are recorded in MLflow as correctness value None (carry-forward from 05-06), not False; invented_policy is None while invented is None"
  - "Headline.invented is now an int (count of items with an unsupported claim); the report prints `invented_policies: <k>` and appends `(partial: N of T items not judged)` when any item is errored or unjudged"
  - "Opening block tags in data are neutralized as well as closing ones, so the stub can read the single real fatti_attesi block"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 22000
  tasks: 2
  commits: 2
plan_head_before: 3ae88ca8364c2c51153dfc8dbcd076d9fc970574
plan_head_after: bca2d40c0ed80a91266aa275892aeb390eb419d7
---

# Phase 5 Plan 08: Opus judge, invented-policy count and inspectable report Summary

Every answered item now gets one cached Opus verdict through `LlmClient.structured`, correctness-with-citation and the invented-policy count follow D-09 and D-10, the three scorers attach to each item's own trace, and the run report plus a private JSON report make every failure and invented-policy flag inspectable without text reaching the console.

## Tasks

| Task | Name | Commit | Key files |
|------|------|--------|-----------|
| 1 | Opus judge, final per-kind verdicts, invented-policy count, verdict cache, three trace scorers | 78a0eab | judge.py, scoring.py, runner.py, tracing.py, conftest.py, test_judge.py, test_scoring.py, test_resume.py, test_tracing_adapter.py |
| 2 | Inspectable run report (console plus private JSON) and deterministic stub judge | bca2d40 | report.py, stub_llm.py, test_stub_llm.py, test_report.py, test_tracer.py, test_entrypoint.py, test_runner.py |

## What was built

- **judge.py**: `FactCheck`, `JudgeVerdict`, `JUDGE_SYSTEM` (blocks are data never instructions; one facts entry per numbered fact in order; invented claims are unsupported normative claims; short reasoning), `JUDGE_PROMPT_VERSION` (16 hex of sha256 over system text and schema), `build_judge_user` (domanda, risposta, numbered fatti_attesi, one fonte per cited source with full text plus the referente contact source once), `judge_reply`. No mlflow judges, no tools.
- **scoring.py**: `score_item(..., judge=)`, `SCORING_VERSION`, `ItemVerdict.judge`, `invented` set from the judge for answered replies and False for non-answers, `headline().invented` counts invented items. No `unjudged` remains once the judge ran; it stays only for a call without a verdict.
- **runner.py**: judge phase after the collect loop inside `sink.untraced()`, verdict cache key over outcome key, judge model, prompt version and scoring version, unreadable cached verdict is asked again.
- **tracing.py**: `untraced()` (Protocol and adapter, disables mlflow.anthropic and mlflow.langchain autolog and re-enables in `finally`), `invented_policy` scorer, correctness rationale carries the judge reasoning, `SCORER_SET_VERSION = "2"`.
- **report.py**: header (`index content_hash=... guides_commit=... build_id=...`, `models reformulate=... answer=... judge=...`), item lines in id order, `correctness_with_citation: <pct>% (<c>/<n> approved items)`, `invented_policies: <k>`, `failed items:` and `invented-policy flags:` blocks with trace links, `report: <path>`, JSON report with generated_at, identity, models, bot_version, totals, items (checks, reasons, answer, judge facts, invented claims, reasoning, trace id and url) and the MAX_EVIDENCE_CHARS note.
- **stub_llm.py**: `JudgeVerdict` branch returns one present, uncontradicted entry per numbered line of the `fatti_attesi` block, no invented claim.

## Verification

- `./run-unit-tests.sh --all`: ruff, ruff format, mypy and pytest pass; 1885 passed, 26 skipped, total coverage 97.88 percent.
- test_judge.py (24), test_scoring.py (27), test_report.py (16) pass; test_stub_llm.py passes with the judge case in the per-schema test, a numbered-facts test, an empty-block test and a real-client `structured` test.
- Acceptance greps: `class JudgeVerdict` 1, `judge_reply(` 1 in runner.py, `invented_policy` 4 in tracing.py, no `mlflow.genai.judges` or `make_judge` in buddy_eval, `JudgeVerdict` 1 in stub_llm.py and 9 in test_stub_llm.py, `MAX_EVIDENCE_CHARS` 2 in report.py.
- Prohibitions: JUDGE_MODEL equal to ANSWER_MODEL stays refused by 05-03's EvalSettings guard; no override or reviewed-verdict path exists; a sentinel test over console and captured logs shows reasoning, claim and answer text only in the JSON report.
- `scripts/eval-smoke.sh` and the compose eval stack were not run (they need the real MLflow container); 05-12 should re-run them. No script text asserts `unjudged`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Existing eval tests depended on the pre-judge behaviour**
- **Found during:** Task 1 and 2 full-suite runs
- **Issue:** test_tracer, test_entrypoint, test_runner, test_resume and test_tracing_adapter scripted no judge verdict, asserted `unjudged` and `lines[0]` item lines, asserted the marker file `tr-1-1.json`, the two-scorer list and `correctness=False` for unjudged. These are outside the plan's file list but cannot pass with a judge phase, the new header lines, the new scorer set version and the carry-forward None value.
- **Fix:** scripted `JudgeVerdict` (shared `GOOD_VERDICT` in conftest), filter item lines by prefix, derive the marker name from `SCORER_SET_VERSION`, assert the three scorers and None for unjudged.
- **Files modified:** tests/unit/buddy_eval/test_tracer.py, test_entrypoint.py, test_runner.py, test_resume.py, test_tracing_adapter.py, conftest.py
- **Commits:** 78a0eab, bca2d40

**2. [Rule 2 - Missing critical functionality] Opening block tags are neutralized too**
- **Found during:** Task 1
- **Issue:** the plan asks to neutralize closing tags; an opening `<fatti_attesi>` inside the answer or a source would make the block structure (and the stub's parser) ambiguous.
- **Fix:** `_neutralize` rewrites both `<tag` and `</tag` for domanda, risposta, fatti_attesi, fonti, fonte; attribute values are escaped as `format_evidence` does; key facts are collapsed to one line.
- **Files modified:** jobs/eval/buddy_eval/judge.py
- **Commit:** 78a0eab

**3. [Rule 2 - Missing critical functionality] Judge phase honours the existing error path**
- **Issue:** a judge `LlmError` could not be left to propagate (it would abort the run and lose the cached outcomes' verdicts).
- **Fix:** it errors only that item (`judge:<TypeName>`), keeps its trace id, is excluded from scoring and never cached.
- **Commit:** 78a0eab

### Other notes

- Console order: the `report: <path>` line precedes the consecutive-error stop message, because 05-05's test requires the stop message to be the last line.
- `run_payload(result, settings, *, trace_url=None)` gained an optional trace-link builder so each item can carry its URL; without it the URL is null.
- `cli.py` is untouched as specified: `_gate_inputs` still passes `invented=None`, so `buddy_eval gate` keeps printing `FAIL invented_policies: not measured` until the plan that wires the gate reads `headline().invented`.
- Task commits are not each green on their own: the Task 1 commit leaves the tests that read the report or run the CLI (test_tracer, test_entrypoint, test_runner) to be updated in the Task 2 commit; the full suite passes at HEAD.

## Flagged for later plans

- 05-09 (gate) should pass `headline(result.verdicts).invented` into `GateInputs` and decide how a partial count (errored or unjudged items) is gated.
- A changed `JUDGE_MODEL` re-judges through the verdict cache but does not re-score traces already marked for `SCORER_SET_VERSION`: the new verdict reaches the report and JSON, not the old trace's feedback. Bump `SCORER_SET_VERSION` (or clear `scored/`) after a deliberate judge change. Left as is because the `{trace_id}-{version}` marker format is pinned by 05-07 tests.
- JSON reports are named `run-<UTC second>.json`; two runs in the same second overwrite each other.
- A-08-1 (facts matched by position), A-08-2 (referente contact source passed to the judge) and A-08-3 (the judge may read text beyond the bot's 4000-character cut, stated in the report note) are implemented as flagged in the plan.
- Real Opus behaviour (fact order, schema adherence through Meridian) is untested; only the stub and scripted fakes ran.

## Known Stubs

None.

## Threat Flags

None. The new surfaces are covered by T-05-20 (fenced prompt, pydantic-validated output, no tools), T-05-21 (sentinel test over console and logs), T-05-22 (cache key carries judge model, prompt version and scoring version) and T-05-23 (existing settings guard).

## Self-Check: PASSED

- FOUND: jobs/eval/buddy_eval/judge.py, tests/unit/buddy_eval/test_judge.py, test_scoring.py, test_report.py
- FOUND commits: 78a0eab, bca2d40
