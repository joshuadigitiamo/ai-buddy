---
phase: 05-evaluation-and-milestone-gate
verified: 2026-11-22T22:45:00Z
status: passed
score: 5/5 must-haves verified
covered_files:
  - ".planning/phases/05-evaluation-and-milestone-gate/05-01-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-01-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-02-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-02-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-03-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-03-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-04-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-04-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-05-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-05-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-06-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-06-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-07-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-07-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-08-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-08-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-09-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-09-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-10-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-10-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-11-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-11-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-12-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-12-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-13-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-13-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-14-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-14-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-15-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-15-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-16-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-16-SUMMARY.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-17-PLAN.md"
  - ".planning/phases/05-evaluation-and-milestone-gate/05-17-SUMMARY.md"
  - "docker-compose.yml"
  - "jobs/eval/buddy_eval/cli.py"
  - "jobs/eval/buddy_eval/empty_context.py"
  - "jobs/eval/buddy_eval/gate.py"
  - "jobs/eval/buddy_eval/judge.py"
  - "jobs/eval/buddy_eval/recall.py"
  - "jobs/eval/buddy_eval/runner.py"
  - "jobs/eval/buddy_eval/scoring.py"
  - "jobs/eval/buddy_eval/tracing.py"
  - "jobs/eval/golden/guides.yaml"
  - "scripts/eval-smoke.sh"
  - "services/chat_bot/buddy_bot/mcp_client.py"
  - "services/chat_bot/buddy_bot/prompts.py"
covered_digest: "v4:sha256:9702b33efd0f88d9bcfa933f0d8c03569bd6249f853a3c7004d5c8795832c60a"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Live gate scores every approved golden item correct (gd-05 and sr-03 wrong in the 05-17 run, 38/40)"
    reason: "Not a bot or retrieval fault: compound golden key facts judged all-or-nothing, plus run-to-run variance at provider-default temperature. No roadmap criterion requires 100%; the gate bar is >= 90%. Diagnosis in .planning/debug/eval-gd-05-wrong.md and eval-sr-03-wrong.md."
    accepted_by: "The owner (05-GAP-DECISION.md, UAT follow-up decision; 05-UAT.md test 6 and gap G-05-6)"
    accepted_at: "2026-11-22"
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "Decision on the earlier GATE: FAIL verdict (invented_policies 1 > 0 on gd-13): resolved by gap-closure plans 05-14..05-17 and the recorded decision in 05-GAP-DECISION.md; live re-run now GATE: PASS"
    - "Spot-check of MLflow traces: covered by 05-UAT.md test 5 (pass) and re-corroborated in 05-17-SUMMARY"
  gaps_remaining: []
  regressions: []
---

# Phase 5: Evaluation and Milestone Gate Verification Report

**Phase Goal:** The developer can run one command and know whether Milestone 1 passes its gate, with every judged answer inspectable.
**Verified:** 2026-11-22T22:45:00Z
**Status:** passed
**Re-verification:** Yes. The previous report (12:30Z) predates plans 05-14..05-17 and recorded GATE: FAIL; it is replaced.

## Headline

The gate machinery is built, wired, tested and has been run live twice. After the gap-closure plans (05-14..05-16) the one live re-run (05-17) printed **GATE: PASS**: correctness-with-citation 38/40 = 95.0%, invented policies 0, empty-context 28/28 refused with a logged gap, Recall@5 handbook 15/15 and Guides 11/13 (0.85, no D5 trigger). The private gate report written during UAT (from cache, no model call) confirms the same numbers and index identity (build `20261122T094743Z-55ce792552d8`). Two approved items are still wrong (gd-05, sr-03); the owner accepted this explicitly (UAT test 6, 05-GAP-DECISION.md). Nothing was tuned after the live gate output (EVAL-06). I made no live LLM calls and did not run `run`, `gate` or `empty-context`.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Golden set of 30-50 items, expected answer and source per item, answerable, no-answer and sensitive cases, review status, none pointing at the official handbook | VERIFIED | 40 items. Public `jobs/eval/golden/guides.yaml` (git-tracked): 22 items, 13 guides, 7 no_answer, 2 sensitive, all 22 `review: approved`. Private `docs/internal/golden-handbook.yaml`: 18 items (gitignored; `git check-ignore` matches; 0 tracked files under `docs/internal`). Live lint (UAT test 2): `lint: OK (40 items: handbook=15 guides=13 no_answer=7 sensitive=5; draft=0 approved=40 rejected=0)`. `grep -ci "clickup\|handbook://"` on the public file returns 0. "In the repo" is met by the documented public/private split (public-repo rule); the gate fails closed (`golden_set: private handbook file missing`) if the private half is absent. |
| 2 | One command prints Recall@5 for handbook and Guides and flags Guides < 0.8 as the hybrid-upgrade trigger | VERIFIED | `recall.py` defines `D5_TRIGGER_LINE`; the trigger uses integer arithmetic (`hits * den < total * num`) so exactly 0.8 does not trigger. Live: handbook 15/15 = 1.00, Guides 11/13 = 0.85, trigger line not printed (UAT test 3, gate JSON recall `[15,15]` / `[11,13]`). Unit tests in test_recall.py pass in the full suite. |
| 3 | One command runs the golden set through the bot workflow with the configured `LLM_BACKEND` and prints correctness-with-citation % and invented-policy count; each judged answer has an MLflow trace (retrieval, generation, gate) in a containerized MLflow UI | VERIFIED | `runner.py` calls the real `run_workflow` (line 100) over a real MCP connector; `tracing.py` uses `mlflow.langchain.autolog`, `mlflow.anthropic.autolog` and an `@mlflow.trace` `bot_run` root; judge via `judge.py`, invented flag via `scoring.py`. Bot-side changes from 05-14 are present in code: `DEFAULT_GUIDES_LIMIT = 8` (`mcp_client.py`), `CASE_SCOPE_RULE` embedded in both answer prompts (`prompts.py`). Live 05-17 totals: approved 40, correct 38, errored 0, invented 0. Compose `eval` profile runs a pinned, loopback-only MLflow. `scripts/eval-smoke.sh` passed again in UAT test 1 (`eval smoke ok`) on the post-05-17 tree. Trace inspection: UAT test 5 (gd-01: `bot_run` root, 12 spans, 2 `guides_search` entries, one correctness, citation and invented_policy feedback each); 05-17-SUMMARY records the same structure for one item of each kind. |
| 4 | Empty-context test passes: no matching content gives a refusal and a logged gap for every question; fails if any answer is produced | VERIFIED | `empty_context.py`: `classify` returns `refused` only for a refusal or referral with `gap_reported`; `answered`, `no_gap`, `smalltalk` and `errored` all fail `_verdict`; independent Firestore gap-document cross-check; second MCP server over a committed fixture index. Behavior-dependent invariant, covered by named passing tests: `test_negative_variant_an_answer_fails_and_names_the_item`, `test_a_smalltalk_reply_is_not_a_refusal`, `test_a_refusal_whose_gap_report_failed_is_not_a_pass`, `test_stub_variant_every_item_is_refused_with_a_logged_gap` (all in the full suite, which passed). Live: 28/28 refused with gap, PASS (05-17, gate JSON). |
| 5 | Gate prints PASS only when correctness >= 90%, invented = 0 and empty-context passes; otherwise FAIL with the failing metric | VERIFIED | `gate.py` `evaluate()` is pure: exact-rational bar `correct*10 >= approved*9`; `invented is None` or `> 0` fails; `empty_context_passed` None or False fails; guards for private file missing, drafts, no approved items, errored and unjudged. `format_verdict` prints `GATE: PASS` or `GATE: FAIL` plus one `FAIL <metric>: <detail>` per failure. `cli.py` returns 0 only when `verdict.passed`. Truth-table test `test_no_unmeasured_draft_errored_or_missing_input_ever_prints_pass` passes in the full suite. Both live outcomes are consistent with the rules: 05-13 printed FAIL with `invented_policies: 1 > 0` (correctness exactly 90.0% not a failure); 05-17 and the UAT cache re-run printed PASS with exit 0. |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified).

### Overrides

One accepted deviation (gap G-05-6): the strict reading "every approved golden item is correct" is not met (38/40; wrong items gd-05, sr-03). It is carried as PASSED (override), not as a roadmap truth, because no roadmap criterion or EVAL requirement asks for 100%; the contract is >= 90%. The owner accepted it with the diagnosis recorded (05-GAP-DECISION.md "UAT follow-up decision", `.planning/debug/eval-gd-05-wrong.md`, `eval-sr-03-wrong.md`; UAT test 6 pass).

### Coincidental-reliance advisory

None flagged. The PASS depends on a gitignored private golden file and the local per-item cache, but both are declared preconditions and the gate fails closed when either input is missing or unjudged.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `jobs/eval/buddy_eval/gate.py` | D-17 verdict | VERIFIED | 88 lines, pure, imported and used by `cli.py` |
| `jobs/eval/buddy_eval/cli.py` | gate, run, recall, empty-context, preflight, lint, build-fixture | VERIFIED | `_gate_inputs`, `_finish_gate` write the private report then print the verdict |
| `jobs/eval/buddy_eval/recall.py` | Recall@5 + D5 | VERIFIED | |
| `jobs/eval/buddy_eval/empty_context.py` | EVAL-04 test | VERIFIED | |
| `jobs/eval/buddy_eval/tracing.py` | MLflow trace sink | VERIFIED | autolog + `bot_run` root, stale-feedback replacement (05-16) |
| `jobs/eval/buddy_eval/runner.py`, `judge.py`, `scoring.py`, `cache.py`, `report.py`, `golden.py`, `sources.py`, `preflight.py`, `config.py`, `fixture.py` | supporting modules | VERIFIED | all present, 3405 lines total in the package; 17 test modules under `tests/unit/buddy_eval` |
| `jobs/eval/golden/guides.yaml` | public golden | VERIFIED | 22 items, tracked |
| `docs/internal/golden-handbook.yaml` | private golden | VERIFIED | 18 items, gitignored |
| `docker-compose.yml` profile `eval`, `scripts/eval-smoke.sh`, `jobs/eval/README.md` | containerized MLflow, smoke, docs | VERIFIED | `docker compose config` resolves the file (fails only on unset required host variables, as designed) |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| gate command | recall, run, empty-context | `cli.py` builds `GateInputs`, verdict from `gate.evaluate` | WIRED |
| runner | real bot `run_workflow` over MCP | in-process, TraceSink port | WIRED (`runner.py:100`, `empty_context.py` likewise) |
| tracing | MLflow server | `mlflow.*.autolog`, tracking URI from settings | WIRED (smoke, UAT test 5) |
| scoring | gate | invented flag counted into `GateInputs.invented` via `_invented_count` | WIRED (05-13: flag became the FAIL line; 05-17: none) |
| bot Guides search (05-14) | eval runs | `DEFAULT_GUIDES_LIMIT = 8`, question-text query, `CASE_SCOPE_RULE` | WIRED (in source; effect visible in the changed live outcomes) |

### Data-Flow Trace (Level 4)

Gate numbers come from real judged per-item cache entries, not static values. The private gate report written during UAT (`gate-20261122T220955Z.json`, cache re-run, ids and numbers only) shows verdict PASS, no failures, approved 40, correct 38, 95.0%, invented 0, empty-context passed, recall handbook `[15,15]`, Guides `[11,13]`, not-correct ids `[gd-05, sr-03]`, and the same identity as 05-17. FLOWING.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Whole suite incl. ruff, mypy strict, all `buddy_eval` unit tests | `./run-unit-tests.sh --all` (Docker, run by me at HEAD 586b707) | 2093 passed, 26 skipped, exit 0 (skips are local-only live-artifact tests) | PASS |
| Golden counts and privacy | grep on `guides.yaml`, `git check-ignore`, `git ls-files docs/internal` | 22 public items, 0 forbidden strings, private file ignored, 0 tracked | PASS |
| Debt markers | grep TBD/FIXME/XXX over `jobs/eval/buddy_eval` and `scripts/eval-smoke.sh` | none | PASS |
| Live gate / lint / recall / smoke | not run by me (no live LLM rule); verified from the UAT record and the private gate JSON | consistent | See UAT |

### Probe Execution

No `probe-*.sh` declared by the phase plans. `scripts/eval-smoke.sh` is the hermetic smoke; its pass is recorded in UAT test 1 and 05-17-SUMMARY (not re-run here: it starts the compose stack).

### Requirements Coverage

All six IDs appear in PLAN `requirements:` frontmatter and in REQUIREMENTS.md (lines 62-67); the traceability table maps only EVAL-01..06 to Phase 5. No orphans.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| EVAL-01 | 05-01, 05-03, 05-09, 05-11, 05-15 | SATISFIED | SC1: 40 items, review status per item, no official handbook references |
| EVAL-02 | 05-09, 05-12, 05-13, 05-15, 05-17 | SATISFIED | SC2: 1.00 / 0.85, D5 logic |
| EVAL-03 | 05-03, 05-04, 05-05, 05-07, 05-08, 05-13, 05-14, 05-16, 05-17 | SATISFIED | SC3: 95.0%, invented 0 |
| EVAL-04 | 05-10, 05-13, 05-16, 05-17 | SATISFIED | SC4: 28/28 refused with gap |
| EVAL-05 | 05-02, 05-03, 05-04, 05-06, 05-08, 05-13, 05-16, 05-17 | SATISFIED | SC3: containerized MLflow, traces inspected in UAT |
| EVAL-06 | 05-03, 05-05, 05-12, 05-13, 05-14, 05-16, 05-17 | SATISFIED | SC5: PASS/FAIL rules; live verdict PASS |

Bookkeeping for the orchestrator: REQUIREMENTS.md still shows EVAL-01..06 unchecked and "Pending" (lines 62-67, 148-153), and the ROADMAP Phase 5 list entry (line 21) is still `[ ]`. These are status updates owed after this verification, not gaps.

### Other Phase Artifacts Cross-Checked

| Artifact | Claim | Check |
|----------|-------|-------|
| 05-UAT.md | complete, 6/6 pass | read; test 6 carries the human decision, gap G-05-6 `status: accepted` |
| 05-GAP-DECISION.md | EVAL-06 record, UAT follow-up decision | read; the accepted 38/40 PASS and the no-further-change decision are recorded |
| 05-SECURITY.md | threats_open 0 | frontmatter read: `status: verified`, `threats_open: 0`, ASVS L1 |
| 05-VALIDATION.md | validated, nyquist_compliant | frontmatter read: `status: validated`, `nyquist_compliant: true` |
| 05-REVIEW-DISPOSITION.md | CR-01, WR-01..03 fixed | read: those four `fixed`; WR-04 and IN-01..IN-08 `open` (9 open of 13) |

### Post-Phase Commits (6a4bfd7..586b707 and 8ee67fb)

No regression of phase 5 found. Since the 05-17 record (`9b32f8c`), non-planning changes touch only: `docker-compose.yml` (live-profile Meridian service gets an `oauthToken` profile and `restart: unless-stopped`; the eval profile is otherwise unchanged), `.env.example`, `scripts/kind-up.sh`, `deploy/k8s/base/chat-bot.yaml`, READMEs, `skills/digitiamo-buddy/SKILL.md`, and three infra tests. `git diff` shows no change to `jobs/eval/`, `services/chat_bot/buddy_bot/` or `packages/` Python code. The full suite is green at HEAD, and UAT tests 1-5 (smoke, lint, recall, gate, trace) ran after `8ee67fb`.

### Anti-Patterns Found

None blocking. No TBD/FIXME/XXX in the eval package or smoke script; no stubs in gate, recall, empty-context or tracing paths. Public-repo scan: no `handbook://` strings with ids outside `docs/internal`, none in the tracked golden file, and this report holds ids and counts only.

### Advisory (open, non-blocking)

| # | Finding | Category | Why advisory |
|---|---------|----------|--------------|
| 1 | WR-04: stale-feedback cleanup in `tracing.py` removes every feedback row with a scorer name, including ones from other sources | other | Open in 05-REVIEW-DISPOSITION; only matters if humans annotate eval traces with these scorer names |
| 2 | IN-01..IN-08 (e.g. `EVAL_LLM_BACKEND=api` advertised but unusable through compose, empty `MERIDIAN_OAUTH_TOKEN` yields a useless profile) | other | Info-level review notes, recorded as open |
| 3 | Answer and judge sample at provider-default temperature; the sr-03 flip between 05-13 and 05-17 is run-to-run variance. The gate verdict can therefore move by an item or two on a re-run. The margin is now 2 failures used of 4 allowed (36/40 is the pass floor), against 0 spare before | other | Diagnosed and accepted by the owner; any change (pin temperature, narrow compound facts) needs a new EVAL-06 decision |
| 4 | `_empty_context_detail` returns the string `failed` even when the test passed (visible as `detail: failed` beside `passed: true` in the gate JSON) | other | Cosmetic; the detail is only printed on a failing verdict |

### Human Verification Required

None. The two items from the previous report are covered: the FAIL-verdict decision by the gap-closure decision plus UAT test 6, and the MLflow trace spot-check by UAT test 5. I found no evidence that either is uncovered.

### Gaps Summary

No gaps. The one command (`docker compose -p aibuddy --profile eval run --rm eval gate`) answers the Milestone 1 question with a named verdict, and each judged answer has an inspectable MLflow trace. The recorded Milestone 1 outcome is GATE: PASS at 95.0%, with two accepted known-wrong compound-fact items.

---

_Verified: 2026-11-22T22:45:00Z_
_Verifier: Claude (gsd-verifier)_
