---
status: complete
phase: 05-evaluation-and-milestone-gate
source: 05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, 05-06-SUMMARY.md, 05-07-SUMMARY.md, 05-08-SUMMARY.md, 05-09-SUMMARY.md, 05-10-SUMMARY.md, 05-11-SUMMARY.md, 05-12-SUMMARY.md, 05-13-SUMMARY.md, 05-14-SUMMARY.md, 05-15-SUMMARY.md, 05-16-SUMMARY.md, 05-17-SUMMARY.md
started: 2026-11-22T21:50:00Z
updated: 2026-11-22T22:18:43.417Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: With the eval stack down (`docker compose -p aibuddy --profile eval down`), running `scripts/eval-smoke.sh` builds and starts the hermetic stack from scratch (stub LLM, real MLflow, no Meridian) and ends printing `eval smoke ok` with exit 0.
result: pass

### 2. Golden set lint on the live index
expected: `docker compose -p aibuddy --profile eval run --rm eval lint` prints `lint: OK (40 items: handbook=15 guides=13 no_answer=7 sensitive=5; draft=0 approved=40 rejected=0)`. No handbook page id or `handbook://` string appears in the output.
result: pass

### 3. Recall@5 command
expected: `docker compose -p aibuddy --profile eval run --rm eval recall` prints `recall@5 handbook: 1.00 (15/15 ...)` and `recall@5 guides: 0.85 (11/13 ...)`, and no D5 hybrid-upgrade trigger line (guides is above 0.8).
result: pass

### 4. Gate verdict from cache
expected: `docker compose -p aibuddy --profile eval run --rm eval gate` reuses the 05-17 cache (items marked cached, no fresh LLM answers) and prints `GATE: PASS` with no `FAIL` line: correctness-with-citation 95.0% (38/40), invented-policy flags none, empty-context PASS (28/28). Container exit code is 0.
result: pass

### 5. MLflow trace spot-check
expected: At http://127.0.0.1:5000, experiment `ai-buddy-eval`, open one judged trace from run-20261122T214341Z (e.g. gd-01). It shows a `bot_run` root with reformulate, retrieve, answer and gate spans plus LLM call spans; retrieve's `tried` lists two `guides_search:` entries; the trace carries exactly one correctness, one citation and one invented_policy feedback value.
result: pass

### 6. Milestone 1 outcome accepted
expected: You accept the recorded live gate result as the Milestone 1 outcome: GATE: PASS on build 20261122T094743Z-55ce792552d8, 38/40 correct (wrong: gd-05 unchanged, sr-03 new failure), invented 0, empty-context 28/28, nothing tuned after the run. No further golden/threshold/bot change wanted before closing the phase.
result: pass
note: "First asked to fix gd-05/sr-03 (gap G-05-6). After diagnosis (not bot faults) the owner accepted the 38/40 GATE: PASS as the M1 outcome; decision recorded in 05-GAP-DECISION.md (UAT follow-up decision)."

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-05-6
  truth: "Live gate scores every approved golden item correct (gd-05 and sr-03 wrong in 05-17 run, 38/40)"
  status: accepted
  accepted_by: "The owner, waiver recorded in 05-GAP-DECISION.md (UAT follow-up decision), 2026-11-22"
  reason: "User reported: Is everything working? I noticed 38/40 correct.. Can you fix all?"
  severity: minor
  test: 6
  root_cause: "Not a bot or retrieval fault. Both items: compound golden key fact + all-or-nothing judge ('present only if stated'), same class as gd-02/sr-02 in 05-GAP-DECISION. gd-05: expected chunk now retrieved and cited (05-14 fix works); key fact 3 bundles effect (full history) with purpose (audit/point-in-time) the 'how' question does not ask; answer at 600-char/4-bullet caps omits purpose. sr-03: run-to-run variance; identical retrieval and citation both runs, judge/scoring/golden unchanged; key fact 1 bundles an inapplicable component and the request channel; same partial coverage judged present in 05-13, absent in 05-17. No temperature pinned for answer or judge (provider defaults); 4/30 re-worded items flipped, all compound-fact items."
  artifacts:
    - path: "jobs/eval/golden/guides.yaml"
      issue: "gd-05 key_facts[2] compound (history + purpose)"
    - path: "docs/internal/golden-handbook.yaml"
      issue: "sr-03 key fact 1 compound (private, gitignored)"
    - path: "jobs/eval/buddy_eval/judge.py"
      issue: "JUDGE_SYSTEM all-or-nothing per fact; no partial-credit rule; default temperature"
  missing:
    - "Recorded EVAL-06 decision from the owner before any post-gate golden/judge change"
  debug_session: ".planning/debug/eval-gd-05-wrong.md, .planning/debug/eval-sr-03-wrong.md (private detail: docs/internal/05-gap-diagnosis-uat.md)"
