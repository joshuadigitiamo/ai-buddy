# Phase 05 gap-closure decision (EVAL-06 record)

Date: 2026-11-22. Decided by Joshua in chat after the live gate FAIL (05-13) and the root-cause diagnosis (private detail: docs/internal/05-gap-diagnosis.md, gitignored).

## Diagnosis (public-safe)

| Item | Fault | Evidence (summary) |
|---|---|---|
| gd-13 | retrieval miss, then answer over-generalised | Guides retrieval searches only reformulated English keywords (BM25, k=4); expected chunk ranks 8th. Answer generalised a system-specific remark from an unrelated chunk into a general rule; judge invented-claim flag is correct. |
| gd-05 | retrieval miss | Expected chunk ranks 7th; key term dropped by reformulator; answer honestly reported missing info. |
| gd-02 | golden key facts over-specified; all-or-nothing judge on partial facts | Expected chunk retrieved and cited; answer correct but omits a mechanism detail the golden fact bundles in. |
| sr-02 | golden compound fact | Citation and referente pass; key fact 1 bundles a topic the question never raises. |

Guides Recall@5 misses: gd-05, gd-13. Code-review CR-01 did not affect this run (verified: cached trace ids and answers match MLflow and the report).

## Approved changes (all four options, "accept all recommendations")

1. Retrieval fix: Guides search uses the standalone question text in addition to the reformulated keywords; Guides k raised from 4 to about 8.
2. Answer-prompt rule: do not generalise statements about one specific system into general rules.
3. Code-review fixes: CR-01, WR-01, WR-02, WR-03 (05-REVIEW.md).
4. Golden edits: narrow key facts for gd-02 and sr-02; add a second expected source for gd-05.

Then re-run the live gate once on the same index; record verdict as is.

## Orchestrator note

05-16 also fixes a harness display issue found in the diagnosis: the MLflow citation assessment rationale copied unrelated failure reasons. This changes only the feedback rationale text, not any gate rule, threshold, verdict or judge prompt. Added by the orchestrator under the code-review-fixes umbrella and flagged to Joshua in chat.

## UAT follow-up decision (2026-11-22, after 05-17 GATE: PASS)

During /gsd-verify-work 5 (test 6), Joshua asked whether the two wrong items (gd-05, sr-03; 38/40) could be fixed. Diagnosis (public: .planning/debug/eval-gd-05-wrong.md, .planning/debug/eval-sr-03-wrong.md; private detail: docs/internal/05-gap-diagnosis-uat.md):

| Item | Fault | Evidence (summary) |
|---|---|---|
| gd-05 | golden compound fact + all-or-nothing judge | 05-13 retrieval miss fixed by 05-14 (expected chunk retrieved at rank 6-7 of 8 and the sole citation; no invented claim). Key fact 3 bundles an effect with its purpose; the "how" question does not ask the purpose; answer at length caps omits it. |
| sr-03 | run-to-run variance on a compound fact | Identical retrieval, citation, golden, judge and scoring code in 05-13 and 05-17; same partial coverage of key fact 1 judged present once and absent once. Answer and judge sample at provider default temperature. |

Neither is a bot or retrieval fault.

**Decision (Joshua, in chat): accept the 05-17 result GATE: PASS, 38/40 (95.0%), invented 0, empty-context 28/28, as the Milestone 1 outcome.** No golden, judge, threshold or bot change; no re-run. gd-05 and sr-03 are recorded as known compound-fact items. Options not taken: narrow both facts and re-run; additionally pin judge temperature and add a partial-fact rule; measure variance first.
