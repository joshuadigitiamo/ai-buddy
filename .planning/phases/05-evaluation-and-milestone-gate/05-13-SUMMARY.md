---
phase: 05-evaluation-and-milestone-gate
plan: 13
subsystem: evaluation-gate
tags: [eval, gate, live-run, preflight, meridian, mlflow, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06]
status: complete
requires:
  - phase: 05-11
    provides: reviewed golden set (40 approved items), lint
  - phase: 05-12
    provides: gate, preflight and README commands
provides:
  - "Live milestone gate run once on the real index through Meridian: verdict FAIL (invented_policies 1 > 0), recorded as is"
  - "Preflight evidence: reformulate, answer, judge, mcp and mlflow all ok"
affects: [phase-05-follow-up]
actuals:
  tokens: 0
  tasks: 3
  commits: 0
plan_head_before: 392f7e452f4eea197850b46e891fadbe895da9bf
plan_head_after: 392f7e452f4eea197850b46e891fadbe895da9bf
tech-stack:
  added: []
  patterns: [operator checkpoint, verdict recorded without tuning]
key-files:
  created: []
  modified: []
key-decisions:
  - "A gate FAIL is a valid phase outcome (A-13-2): recorded as is, no golden item, threshold, judge prompt or bot edit after seeing live results (EVAL-06)"
duration: n/a
completed: 2026-11-22
---

# Phase 5 Plan 13: Live Milestone Gate Summary

The live gate ran once on the real index through Meridian and returned `GATE: FAIL`; the single failing rule is `invented_policies: 1 > 0` (flag on gd-13), and nothing was tuned.

`commits: 0` is legitimate: this plan has an empty `files_modified` by design and committed no code; `plan_head_before` and `plan_head_after` are both the HEAD at execution start.

## Preflight (05-13)

Task 1 (hermetic proof, image rebuild, live lint), counts only:

- Unit suite: 2050 passed, 26 skipped, exit 0.
- Hermetic eval smoke: `eval smoke ok` (stub gate printed `GATE: PASS`, empty_context 2/2).
- Eval image `aibuddy-eval` rebuilt with the reviewed golden files.
- Live lint against the compose artifacts volume: `lint: OK`, 40 items, draft=0, approved=40.

Task 2 (Meridian preflight), final lines after the reseed below:

- `preflight reformulate claude-haiku-5-5: ok`
- `preflight answer claude-sonnet-5-5: ok`
- `preflight judge claude-opus-5-5: ok`
- `preflight mcp http://mcp-server:8000/mcp: ok`
- `preflight mlflow http://mlflow:5000: ok`

Meridian logs "Claude subscription: team (Max recommended)"; non-blocking, the judge ping on Opus succeeded.

Deviations during preflight (operator-run, not code changes):

- `REDACT_PAGE_FILES=07-wi-fi.md` was supplied inline for the Task 1 compose commands because the repository `.env` does not define it.
- The first preflight attempt failed on reformulate, answer and judge with `LlmUnavailableError`. Meridian logged `loggedIn: false; login required`: the `meridian-claude` volume held a revoked login seeded 2026-11-07. The orchestrator reseeded the volume from the host Claude login as `services/chat_bot/README.md` describes (copied inside Docker, never printed) and restarted meridian. The rerun passed all five checks. No live recall, run, empty-context or gate command ran before the passing preflight.

## Live gate (05-13)

Commands run in order through `docker compose --profile eval run --rm eval`: recall (exit 0), run (exit 0), empty-context (exit 0), gate (exit 1, as the gate exits non-zero on FAIL).

- gate_verdict: FAIL
- fail_lines: `FAIL invented_policies: 1 > 0` (the only FAIL line)
- correctness_with_citation: 90.0% (36/40 approved items); exactly 90.0% meets the >= 0.90 rule, so it is not a failing rule
- invented_policies: 1 (flag on gd-13, claims=1)
- empty_context: PASS (28/28 refused with gap)
- recall_handbook: 1.00 (15/15; fractional 1.00)
- recall_guides: 0.85 (11/13; fractional 0.85)
- d5_trigger: no (no D5 TRIGGER line printed)
- index_content_hash: 55ce792552d8480d
- guides_commit_sha: 3cabe681fe76
- build_id: 20261122T094743Z-55ce792552d8
- models: reformulate claude-haiku-5-5, answer claude-sonnet-5-5, judge claude-opus-5-5 (all via Meridian)

Index identity note: the identity above is the compose volume build (`20261122T094743Z-55ce792552d8`, content hash `55ce7925...`), consistent with the `compose_build_id` recorded in 05-01.

Failed items (ids only):

| Item | Group | Failure |
|------|-------|---------|
| gd-02 | guides | facts |
| gd-05 | guides | citation and facts |
| gd-13 | guides | citation; also carries the invented-policy flag (claims=1) |
| sr-02 | sensitive | facts |

Trace inspection (EVAL-05, orchestrator via Chrome, MLflow UI 3.18.0 at 127.0.0.1:5000, experiment `ai-buddy-eval`):

- 68 traces total: 40 scoring-run traces plus 28 empty-context traces.
- gd-13 trace shows the full span tree `bot_run` -> LangGraph -> reformulate, retrieve, answer, gate (`_decide`), finish, plus two `AsyncMessages.create` LLM spans, with 6 assessments attached.
- All empty-context traces are refusal or referral with `gap_reported` true and referente HR.

## Status and Follow-up

- Phase 5 deliverable (a working gate run once on the live stack, traces inspectable) is met. The Milestone 1 gate verdict is FAIL.
- Requirements: the plan lists EVAL-02..EVAL-06. Because the gate FAILed, requirements that depend on a PASS are NOT marked complete here; requirement status is left to the orchestrator and Joshua's follow-up decision.
- No golden item, threshold, judge prompt or bot change was made after seeing results (EVAL-06 prohibition honored).
- Follow-up input for `/gsd-plan-phase 5 --gaps` or a new phase (Joshua decides):
  1. Investigate the gd-13 invented-policy claim (the only failing rule): inspect the trace and judge feedback for gd-13 locally and decide whether the answer, the retrieval or the judge is at fault.
  2. Investigate the Guides failures gd-02 (facts), gd-05 (citation and facts) and gd-13 (citation); Guides Recall@5 is 0.85 (11/13), below handbook 1.00, so check whether the two non-recalled Guides items overlap these ids.
  3. Investigate sr-02 (sensitive, facts).
  4. Any change to golden items, thresholds, judge or bot needs a recorded decision by Joshua, then a re-run of `gate` (cache reuse per D-13/D-14).

## Deviations from Plan

- Operator deviations only: inline `REDACT_PAGE_FILES` for Task 1, and the Meridian login reseed before the passing preflight (both described under Preflight). No code, golden, threshold or judge changes. No auth gate remains open.

## Known Stubs

None. No files were created or modified by this plan.

## Threat Flags

None. No new network endpoint, auth path or file surface was introduced; the SUMMARY holds only verdict lines, counts, ids and hashes (T-05-36).

## Self-Check: PASSED

- Both required sections present; the twelve live-gate keys are recorded once each.
- No question, answer, judge-reasoning or handbook text is included.
- `commits: 0` matches `git rev-list --count 392f7e4..HEAD` at execution start; no code files changed.
