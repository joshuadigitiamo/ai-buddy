---
phase: 05-evaluation-and-milestone-gate
plan: 11
subsystem: evaluation-golden-set
tags: [eval, golden-set, review, privacy, EVAL-01]
requires:
  - phase: 05-01
    provides: fresh index (artifacts/index.db) that lint checks expected sources against
  - phase: 05-03
    provides: GoldenItem schema and load_golden public/private merge
  - phase: 05-09
    provides: `python -m buddy_eval lint`
provides:
  - "40 golden items, all `review: approved`, lint OK against the fresh index"
  - "jobs/eval/golden/guides.yaml committed (22 public items: Guides, no-answer, no-rule sensitive)"
  - "docs/internal/golden-handbook.yaml kept private and gitignored (18 items)"
  - "eval image rebuilt so the public golden file inside the image matches the commit"
affects: [05-12]
actuals:
  tokens: 7080
  tasks: 3
  commits: 1
plan_head_before: 7ac6aa7f3b0a879b42e5e20e4ba5e92a9c1b54c1
plan_head_after: da5047637b55fe3a5eca194a0c9b3a07746553d4
tech-stack:
  added: []
  patterns: [public/private golden split by source privacy, neutral private ids]
key-files:
  created:
    - jobs/eval/golden/guides.yaml
  modified: []
key-decisions:
  - "Review approval was given in chat for the whole set at once (\"They are ok for now\"); recorded per item as review_note; the owner may revisit and change any item later"
  - "Public file holds Guides, no-answer and no-rule sensitive items only; every handbook-sourced item stays in the ignored private file"
requirements-completed: [EVAL-01]
metrics:
  duration: single session across a review checkpoint
  completed: 2026-11-22
status: complete
---

# Phase 5 Plan 11: Golden Set Review and Commit Summary

40-item Italian golden set drafted from the fresh index, approved by the owner in chat, linted OK, with only the 22 public items committed and the 18 handbook-derived items kept in the gitignored private file.

## Golden set (05-11)

Lint output after review (verbatim): `lint: OK (40 items: handbook=15 guides=13 no_answer=7 sensitive=5; draft=0 approved=40 rejected=0)`.

| Kind | Count | File |
|------|-------|------|
| handbook | 15 | private (gitignored) |
| sensitive, rule branch | 3 | private (gitignored) |
| guides | 13 | public (committed) |
| no_answer | 7 | public (committed) |
| sensitive, no-rule branch | 2 | public (committed) |
| Total | 40 | 22 public + 18 private |

Review status: approved 40, rejected 0, draft 0. Non-rejected count 40 is inside the 30-50 band. No item was left as draft, so the gate will not FAIL on drafts.

Sensitive split is 3 rule-branch and 2 no-rule, satisfying A-11-2 (at least 2 each). The D-03 split of 15/13/7/5 is unchanged; no count warning.

Public item ids: gd-01, gd-02, gd-03, gd-04, gd-05, gd-06, gd-07, gd-08, gd-09, gd-10, gd-11, gd-12, gd-13, na-01, na-02, na-03, na-04, na-05, na-06, na-07, sn-01, sn-02.

Private items are reported as counts only (15 handbook, 3 sensitive with a rule); no ids, titles or text appear here.

### Review record

The owner approved the whole set in chat ("They are ok for now"), not item by item in the files. The orchestrator then set every item to `review: approved` with `review_note: "approved by the owner in chat 2026-11-22 (all items, ok for now)"`; no other field was edited. This means the approval is a blanket one: the owner may revisit individual items later and change their review value or content. Any such edit to the public file needs an eval image rebuild (A-11-3).

## Verification

- `python -m buddy_eval lint` in the test image (network none): `lint: OK`, draft=0.
- `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit`: 14 passed (includes the committed-golden privacy test and the private-path gitignore test).
- `grep -c 'handbook://' jobs/eval/golden/guides.yaml` returns 0; `grep -ci clickup` returns 0.
- `git check-ignore -q docs/internal/golden-handbook.yaml` exits 0; `git status --porcelain docs/internal` prints nothing; `git ls-files docs/internal` prints nothing.
- `git ls-files jobs/eval/golden/guides.yaml` prints the path after the commit.
- Commit contained exactly one file (jobs/eval/golden/guides.yaml); no deletions.
- A-11-3: `docker compose --profile eval build eval` succeeded (image aibuddy-eval), with throwaway build-time values for the required compose variables; none were written to disk.

## Deviations from Plan

None in content. Process notes:

- Task 2 (blocking checkpoint) was resolved by the owner's chat reply, and the orchestrator, not the executor, wrote the `approved` values. The executor changed no review value.
- The eval image build needed the compose-required host variables HANDBOOK_SRC_DIR, GUIDES_SRC_DIR, REDACT_PAGE_FILES and THREAD_KEY_SECRET set in the shell, because `.env` lacks REDACT_PAGE_FILES; they were passed inline for the one command only.

## Known Stubs

None.

## Threat Flags

None. No new network surface; T-05-30 and T-05-31 mitigations held (no handbook text, titles or ids in the committed file, this SUMMARY or the commit message).

## Self-Check: PASSED

- jobs/eval/golden/guides.yaml exists and is tracked.
- Commit da50476 is an ancestor of HEAD.
- docs/internal/golden-handbook.yaml exists, is ignored and untracked.
