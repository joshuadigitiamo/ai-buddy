---
phase: 05-evaluation-and-milestone-gate
verified: 2026-11-22T12:30:00Z
status: human_needed
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
  - "jobs/eval/buddy_eval/cli.py"
  - "jobs/eval/buddy_eval/empty_context.py"
  - "jobs/eval/buddy_eval/gate.py"
  - "jobs/eval/buddy_eval/recall.py"
  - "jobs/eval/buddy_eval/tracing.py"
  - "jobs/eval/golden/guides.yaml"
  - "scripts/eval-smoke.sh"
covered_digest: "v4:sha256:65fd8656ea430144efff1008525e406c9ee8377eda464fdcfb4577d5bfea53ed"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Decide what to do with the recorded live Milestone 1 gate verdict GATE: FAIL (sole failing rule invented_policies: 1 > 0, item gd-13)"
    expected: "Joshua records a decision: accept the FAIL as the M1 outcome and open gap closure (/gsd-plan-phase 5 --gaps or a new phase), or accept it with a documented waiver. Any change to golden items, thresholds, judge or bot needs a recorded decision, then a gate re-run."
    why_human: "The phase delivers the gate; the gate's verdict on the real index is FAIL. Whether that FAIL is the answer to the milestone question or triggers rework is a product decision, not something code inspection can settle."
  - test: "Open the MLflow UI (127.0.0.1:5000, experiment ai-buddy-eval) and spot-check one trace"
    expected: "bot_run root with reformulate, retrieve, answer, gate spans plus LLM spans and attached assessments; 68 traces total (40 scoring + 28 empty-context)"
    why_human: "The live-volume trace inspection is recorded in 05-13-SUMMARY by the orchestrator via Chrome; this verifier did not start the stack. The hermetic smoke script asserts the same span structure in code (verified below)."
---

# Phase 5: Evaluation and Milestone Gate Verification Report

**Phase Goal:** The developer can run one command and know whether Milestone 1 passes its gate, with every judged answer inspectable.
**Verified:** 2026-11-22T12:30:00Z
**Status:** human_needed
**Re-verification:** No, initial verification

## Headline

The gate machinery is built, wired, tested and was run live: one command (`python -m buddy_eval gate` via `docker compose --profile eval run --rm eval gate`) produced a verdict with named failing metric and inspectable traces. The goal as worded ("know whether Milestone 1 passes") is achieved. The answer it gave is **GATE: FAIL** (sole failing rule `invented_policies: 1 > 0`, item gd-13). No roadmap success criterion requires the gate to PASS (SC5 requires correct PASS/FAIL logic), so this is not recorded as a gap, but it is the single most important outcome of the phase and needs a human decision (see Human Verification Required). Nothing was tuned; I did not tune anything either.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Golden set of 30-50 items in the repo, drafted from test doc and Guides, expected answer and source per item, covering answerable, no-answer and sensitive-escalation, review status per item, none pointing at the official handbook | VERIFIED | 40 items: public `jobs/eval/golden/guides.yaml` (git-tracked, 22 items: 13 guides, 7 no_answer, 2 sensitive) plus private `docs/internal/golden-handbook.yaml` (18 items: 15 handbook, 3 sensitive; gitignored, 0 tracked files under `docs/internal`). All 40 `review: approved` with note. `grep -ci "clickup\|handbook://"` on the public file returns 0. `lint_golden` flags ClickUp references and sources not in the index; live lint `OK` (05-13). Note: the handbook-derived 18 items are intentionally not in the public repo (public-repo rule); "in the repo" is satisfied by the public/private split documented in 05-11. |
| 2 | One command prints Recall@5 for handbook and Guides search and flags Guides Recall@5 < 0.8 as the D5 trigger | VERIFIED | `recall.py` defines `D5_TRIGGER_LINE`, integer-arithmetic threshold at 0.8 (exactly 0.8 does not trigger). `recall` command and `gate` print it. Live: handbook 15/15 = 1.00, guides 11/13 = 0.85, no D5 trigger (matches `gate-20261122T113930Z.json` metrics). test_recall.py: 29 passed (run by me in Docker). |
| 3 | One command runs the golden set through the bot workflow with configured `LLM_BACKEND`, prints correctness-with-citation % and invented-policy count; each judged answer has an MLflow trace (retrieval, generation, gate) in a containerized MLflow UI | VERIFIED | `run` command, real `run_workflow` over MCP, `tracing.py` (`mlflow.langchain.autolog`, `mlflow.anthropic.autolog`, `@mlflow.trace` bot_run root), judge via LlmClient, `scoring.py` invented flag. Live report: 36/40 = 90.0%, invented 1, errored 0, unjudged 0. Compose profile `eval` with pinned `ghcr.io/mlflow/mlflow:v3.18.0@sha256:...` on loopback. `scripts/eval-smoke.sh` asserts per item exactly one trace with bot_run root, LLM spans, node spans, expectations and correctness feedback. Live trace inspection (68 traces, gd-13 span tree) recorded in 05-13-SUMMARY by the orchestrator; not re-run by me (see human item 2). |
| 4 | Empty-context test passes: no matching content gives a refusal and a logged gap for every question; fails if any answer is produced | VERIFIED | `empty_context.py`: status `refused` only for refusal/referral with `gap_reported`; `answered`, `no_gap`, `smalltalk`, `errored` all fail the verdict; independent Firestore gap-count cross-check; second mcp-server over committed fixture index. test_empty_context.py: 48 passed (run by me). Live: 28/28 refused with gap, PASS (matches gate JSON: no empty_context failure). |
| 5 | Gate prints PASS only when correctness >= 90%, invented = 0 and empty-context passes; otherwise FAIL with failing metric | VERIFIED | `gate.py` `evaluate()` is a pure rule set: exact-rational 90% bar (`correct*10 >= total*9`), `invented is None` or `> 0` fails, `empty_context_passed` None/False fails, plus golden-set, errored and unjudged guards; `format_verdict` prints `GATE: PASS` or `GATE: FAIL` plus one `FAIL <metric>: <detail>` per failure. test_gate.py 28 passed including a no-unmeasured-ever-passes property test; test_gate_command.py 25 passed (exit code 0 only on PASS). Live behavior confirmed: it printed FAIL with `invented_policies: 1 > 0` while correctness exactly 90.0% was correctly not a failure. Smoke script asserts container exit code matches the `GATE:` line. |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified). Behavior-dependent truths (SC4 refusal invariant, SC5 truth table) have named passing tests.

### Live Milestone 1 Gate Result (recorded, corroborated)

Corroborated against the private gate report `gate-20261122T113930Z.json` (ids and numbers only): verdict FAIL; failures `["invented_policies: 1 > 0"]`; approved 40, correct 36, pct 90.0, errored 0, unjudged 0; invented items [gd-13]; not-correct items [gd-02, gd-05, gd-13, sr-02]; recall handbook 15/15, guides 11/13; index identity build `20261122T094743Z-55ce792552d8`, content hash prefix `55ce7925`. This matches 05-13-SUMMARY exactly. Code changes since `392f7e4` are planning-doc commits only (`git diff --stat 392f7e4..HEAD` outside `.planning` is empty), so the recorded full suite (2050 passed, 26 skipped) still applies.

Margin note: correctness is exactly at the bar (36/40). One further failure would also fail the correctness rule.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `jobs/eval/buddy_eval/gate.py` | D-17 verdict | VERIFIED | 88 lines, pure, wired from `cli.py` |
| `jobs/eval/buddy_eval/cli.py` | gate/run/recall/empty-context/preflight/lint/build-fixture | VERIFIED | 633 lines, `__main__` entrypoint |
| `jobs/eval/buddy_eval/recall.py` | Recall@5 + D5 | VERIFIED | 279 lines |
| `jobs/eval/buddy_eval/empty_context.py` | EVAL-04 test | VERIFIED | 431 lines |
| `jobs/eval/buddy_eval/tracing.py` | MLflow trace sink | VERIFIED | autolog + bot_run root |
| `jobs/eval/buddy_eval/judge.py`, `scoring.py`, `sources.py`, `cache.py`, `report.py`, `runner.py`, `golden.py`, `preflight.py`, `config.py`, `fixture.py` | supporting modules | VERIFIED | all present, substantive; 17 test modules under `tests/unit/buddy_eval` |
| `jobs/eval/golden/guides.yaml` | public golden | VERIFIED | 22 items, tracked |
| `docs/internal/golden-handbook.yaml` | private golden | VERIFIED | 18 items, gitignored, untracked |
| `docker-compose.yml` profile eval, `scripts/eval-smoke.sh`, `jobs/eval/README.md` | containerized MLflow + smoke + docs | VERIFIED | pinned digest image, loopback |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| gate command | recall, run, empty-context | `cli.py` orchestrates, verdict from `gate.evaluate` | WIRED (test_gate_command 25 passed; live run) |
| runner | real bot `run_workflow` over MCP | in-process with TraceSink port | WIRED (live run, 40 traces) |
| tracing | MLflow server | `mlflow.*.autolog`, tracking URI locality guard | WIRED (smoke asserts; live traces) |
| scoring | gate | invented flag counted into `GateInputs.invented` | WIRED (live: gd-13 flag became the FAIL line) |

### Data-Flow Trace (Level 4)

Gate numbers come from the local per-item cache of real judged runs, not from MLflow or static values; the live report holds real counts (40 approved, 36 correct, 1 invented) and the gate JSON agrees with the console verdict. FLOWING.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Gate truth table | `./run-unit-tests.sh --single-file test_gate.py tests/unit/buddy_eval` | 28 passed | PASS |
| Gate command exit codes | `... test_gate_command.py ...` | 25 passed | PASS |
| Empty-context verdicts | `... test_empty_context.py ...` | 48 passed | PASS |
| Recall and D5 | `... test_recall.py ...` | 29 passed | PASS |
| Tracing adapter | `... test_tracing_adapter.py ...` | 34 passed | PASS |

I did not re-run the live gate (needs Meridian, MLflow stack; running it again would also risk changing cached state). The live evidence is the private gate JSON plus 05-13-SUMMARY.

### Probe Execution

No probe-*.sh declared by the phase plans. Step 7c: not applicable. `scripts/eval-smoke.sh` is the hermetic smoke; its pass (`eval smoke ok`) is recorded in 05-13 Task 1 and was not re-run here (needs Docker compose profile with real MLflow container).

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EVAL-01 | 05-01, 05-03, 05-09, 05-11 | Golden set 30-50, expected answer/source, review status, no official handbook | SATISFIED | SC1 evidence above |
| EVAL-02 | 05-09, 05-12, 05-13 | Recall@5 for handbook and Guides, D5 flag | SATISFIED | SC2 |
| EVAL-03 | 05-03, 05-04, 05-05, 05-07, 05-08, 05-13 | End-to-end correctness + citation, invented-policy count | SATISFIED | SC3; ran live |
| EVAL-04 | 05-10, 05-13 | Empty-context test | SATISFIED | SC4; live 28/28 |
| EVAL-05 | 05-02, 05-03, 05-04, 05-06, 05-08, 05-13 | MLflow tracing, containerized | SATISFIED | SC3; smoke + live traces |
| EVAL-06 | 05-03, 05-05, 05-12, 05-13 | Gate PASS/FAIL against the three rules | SATISFIED (mechanism) | SC5. The mechanism works; the live verdict itself is FAIL. |

All six IDs appear in at least one PLAN `requirements:` frontmatter and in REQUIREMENTS.md (lines 62-67). No orphaned requirements: REQUIREMENTS.md traceability maps only EVAL-01..06 to Phase 5, all claimed by plans.

Bookkeeping to fix (orchestrator): REQUIREMENTS.md still shows EVAL-01..06 unchecked and "Pending", and ROADMAP progress row shows Phase 5 "In Progress" (13/13 plans executed). 05-13-SUMMARY deliberately left requirement status to the orchestrator and Joshua. Requirement text for EVAL-06 asks for the command to "report PASS/FAIL", which is met; do not read the FAIL verdict as unmet requirements.

### Anti-Patterns Found

None. `grep TBD|FIXME|XXX` over `jobs/eval/buddy_eval` returns nothing. No stubs in the gate, recall, empty-context or tracing paths. Public-repo privacy checks pass (no ClickUp or `handbook://` strings in the tracked golden file; no handbook or golden text copied into this report).

### Deferred Items

None. Phase 5 is the last phase in the roadmap; follow-up for the FAIL belongs to gap closure or a new phase, not a deferral.

### Human Verification Required

#### 1. Decision on the GATE: FAIL verdict

**Test:** Review the recorded verdict (invented_policies 1 > 0 on gd-13; failed items gd-02, gd-05, gd-13, sr-02; correctness exactly at the 90% bar).
**Expected:** A recorded decision: open gap closure to investigate whether gd-13's flag is a bot, retrieval or judge fault (05-13-SUMMARY follow-up list), or accept and document. Any golden/threshold/judge/bot change needs a recorded decision, then a gate re-run (cache reuse per D-13/D-14).
**Why human:** Milestone 1 pass/fail consequence is a product decision.

#### 2. Spot-check traces in the MLflow UI

**Test:** Start the eval profile MLflow and open one judged trace.
**Expected:** bot_run root, reformulate/retrieve/answer/gate spans, LLM spans, assessments.
**Why human:** Live-stack UI inspection was done by the orchestrator, not independently here.

### Gaps Summary

No code gaps against the roadmap success criteria. The milestone outcome is FAIL, which is a legitimate recorded result of a correctly working gate. Status is `human_needed` solely because that outcome requires Joshua's decision; if Joshua decides the FAIL must be fixed, the follow-up is `/gsd-plan-phase 5 --gaps` seeded from 05-13-SUMMARY.

---

_Verified: 2026-11-22T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
