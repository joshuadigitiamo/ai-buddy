---
phase: 05-evaluation-and-milestone-gate
plan: 17
subsystem: evaluation-gate
tags: [eval, gate, live-run, preflight, meridian, mlflow, gap-closure, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06]
status: complete
requires:
  - phase: 05-14
    provides: question-text Guides search at k=8, CASE_SCOPE_RULE
  - phase: 05-15
    provides: golden edits (gd-02, gd-05), lint and recall fixes
  - phase: 05-16
    provides: reply-bound verdicts, single current MLflow feedback, transport failures as errored items
provides:
  - "Live milestone gate re-run once on the 05-13 index with the gap-closure build: verdict PASS, recorded as printed"
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

Task 2 (Meridian preflight), final lines after the reseed below:

- `preflight reformulate claude-haiku-5-5: ok`
- `preflight answer claude-sonnet-5-5: ok`
- `preflight judge claude-opus-5-5: ok`
- `preflight mcp http://mcp-server:8000/mcp: ok`
- `preflight mlflow http://mlflow:5000: ok`

Deviations during preflight (operator-run, not code changes):

- `REDACT_PAGE_FILES=07-wi-fi.md` supplied inline, as in 05-13.
- The first preflight failed on reformulate, answer and judge with `LlmUnavailableError`; Meridian logged `loggedIn: false; login required` (the login reseeded in 05-13 was revoked again). The `meridian-claude` volume was reseeded from the host Claude login as services/chat_bot/README.md describes (copied inside Docker, never printed), `aibuddy-meridian-1` restarted, and the preflight re-run passed.

## Live gate (05-17)

Commands run once each, in order, through `docker compose -p aibuddy --profile eval run --rm eval` with LLM_BACKEND=meridian on the real index: recall (exit 0), run (exit 0), empty-context (exit 0), gate (exit 0). No command stopped on consecutive errors; nothing was resumed.

- gate_verdict: PASS
- fail_lines: none (no `FAIL` line printed)
- correctness_with_citation: 95.0% (38/40 approved items); wrong: gd-05, sr-03
- invented_policies: 0 (`invented-policy flags: none`)
- empty_context: PASS (28/28 refused with gap)
- recall_handbook: `recall@5 handbook: 1.00 (15/15; fractional 1.00)`
- recall_guides: `recall@5 guides: 0.85 (11/13; fractional 0.85)`
- d5_trigger: not printed
- index_content_hash: 55ce792552d8480d
- guides_commit_sha: 3cabe681fe76
- build_id: 20261122T094743Z-55ce792552d8
- models: reformulate=claude-haiku-5-5 answer=claude-sonnet-5-5 judge=claude-opus-5-5
- fresh_run: `docs/internal/eval/cache/outcome` did not exist before the first `run`; after it, 40 outcome entries (40/40 items collected); no `(cached)` item line on the first pass; totals approved=40 correct=38 wrong=2 errored=0 invented=0; bot_version baed06a5b44c…
- changed_vs_05_13: gd-02 wrong -> correct; gd-13 wrong (invented flag) -> correct, no flag; sr-02 wrong -> correct; sr-03 correct -> wrong (new failure); gd-05 wrong -> wrong (unchanged)

Trace check (MLflow API against the compose MLflow server, run report run-20261122T214341Z): one Guides (gd-01), one handbook (hb-01), one no-answer (na-01) and one sensitive (sn-01) trace each hold the spans reformulate, retrieve, answer, gate and the LLM calls (no-answer and sensitive also retry_plan and refuse); retrieve `tried` holds two `guides_search:` entries; each trace carries exactly one correctness, one citation and one invented_policy feedback value (WR-02 fix observed).

Reports (local, gitignored): run-20261122T214341Z.json, gate-20261122T214722Z.json. Nothing was tuned after the gate output (EVAL-06).
