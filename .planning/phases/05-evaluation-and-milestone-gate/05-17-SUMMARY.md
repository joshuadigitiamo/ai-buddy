---
phase: 05-evaluation-and-milestone-gate
plan: 17
subsystem: evaluation-gate
tags: [eval, gate, live-run, preflight, meridian, mlflow, gap-closure, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06]
status: in-progress
requires:
  - phase: 05-14
    provides: question-text Guides search at k=8, CASE_SCOPE_RULE
  - phase: 05-15
    provides: golden edits (gd-02, gd-05), lint and recall fixes
  - phase: 05-16
    provides: reply-bound verdicts, single current MLflow feedback, transport failures as errored items
provides: []
affects: [phase-05-verification]
completed: 2026-11-22
---

# Phase 5 Plan 17: Live Gate Re-run Summary

## Preflight (05-17)

Task 1 (disposition, hermetic proof, image rebuild, cache, lint, index identity), counts and ids only:

- 05-REVIEW-DISPOSITION.md: CR-01, WR-01, WR-02, WR-03 set to `fixed` (05-15 7f92173; 05-16 d8dda4f, ccdb7a3, 3f5ef6a); IN-01 to IN-05 stay `open`.
- `git diff --quiet 6ad3dce -- services/mcp_server packages/buddy_core`: exit 0 (compose mcp-server and sync images unchanged).
- Unit suite at dcbf0fd: 2086 passed, 26 skipped, coverage 98.12%, exit 0.
- Hermetic eval smoke: `eval smoke ok`.
- Eval image `aibuddy-eval` rebuilt from the merged tree; in-image check printed `eval image ok` (DEFAULT_GUIDES_LIMIT 8, CASE_SCOPE_RULE in ANSWER_SYSTEM, gd-05 two expected sources).
- 05-13 cache moved to `docs/internal/eval/cache-05-13`; no `docs/internal/eval/cache` before the first live command.
- Live lint: `lint: OK (40 items: handbook=15 guides=13 no_answer=7 sensitive=5; draft=0 approved=40 rejected=0)`.
- Index build after the compose sync: `20261122T094743Z-55ce792552d8` (unchanged from 05-13).
