---
status: diagnosed
trigger: "eval-sr-03-wrong: golden item sr-03 judged wrong in the live Milestone 1 gate run of 05-17 (run-20261122T214341Z); it was correct in the 05-13 run (run-20261122T113929Z)."
created: 2026-11-22T22:30:00Z
updated: 2026-11-22T22:55:00Z
goal: find_root_cause_only
---

## Current Focus

hypothesis: sr-03 flipped because of sampling variance (answer wording, then a judge threshold on a compound key fact), not a deterministic regression. Fault class: golden (compound key fact) + variance.
test: compare 05-13 and 05-17 sr-03 end to end (reformulate, retrieve, answer prompt, answer, judge facts) from the cache and MLflow spans; diff judge, scoring and bot code between the two builds.
expecting: if regression, retrieval or judge inputs differ in a way that explains the omission; if variance, the relevant evidence and judge are byte-identical and only wording differs.
next_action: none (diagnosis returned to caller). Private detail is in docs/internal/05-gap-diagnosis-uat.md under "## sr-03" (gitignored).

reasoning_checkpoint:
  hypothesis: "The scored answer differs in wording between runs (default sampling, no temperature set). The 05-17 sample omitted the one token that named the request channel; the judge then marked key fact 1 not present. Key fact 1 bundles three components, one of which does not apply to the question, so the all-or-nothing `present` flag turns on incidental wording."
  confirming_evidence:
    - "Cited source is the same single handbook page in both runs, byte-identical text (same hash)."
    - "Judge module, scoring module, judge model and judge prompt version are unchanged between the builds (git diff of judge.py and scoring.py from 6ad3dce to HEAD is empty)."
    - "Both answers omit the same ordinary-period component; the 05-13 judge still marked fact 1 present, the 05-17 judge did not; the only wording difference touching fact 1 is the channel mention."
    - "30 of 40 answers differ in wording between the runs and only 4 changed status; judge fact vectors agree in 26 of 30 differently-worded items; the 4 that differ are items with compound key facts (gd-02, gd-05, sr-02, sr-03)."
  falsification_test: "Re-sample sr-03 N times under both bot variants (05-13 prompt and k, 05-17 prompt and k). A regression predicts the 05-17 variant fails clearly more often than the 05-13 variant; variance predicts overlapping pass rates for both."
  fix_rationale: "No code fault found. The recurring cause across gd-02, sr-02 and sr-03 is a compound golden key fact judged all-or-nothing."
  blind_spots: "One sample per condition. Cannot separate a small effect of CASE_SCOPE_RULE or of the extra Guides noise from chance without LLM calls (forbidden in this session)."
  candidate_causes:
    - "data (golden): compound key fact 1 with a component that does not apply to the question"
    - "code (bot): CASE_SCOPE_RULE nudged the answer to drop a named system"
    - "environment (retrieval): Guides noise grew from 4 to 9 irrelevant chunks, longer answer prompt"
    - "judge: sampled at default temperature, lenient in 05-13 and strict in 05-17 on the same partial coverage"
  and_gate: "yes: the failure needs the answer to omit the channel mention AND the key fact to bundle an inapplicable component AND the judge to apply the strict reading. Removing any one of the three would have kept the item correct in 05-17."

## Symptoms

expected: Live gate scores every approved golden item correct with citation.
actual: 38/40 correct. gd-05 and sr-03 wrong. sr-03 was correct in 05-13 and flipped to wrong in 05-17.
errors: None (judge verdict wrong, not a crash). Failed check for sr-03 is `facts` only; citation, kind_answer and referente_role checks pass; invented claims empty.
reproduction: Test 6 in .planning/phases/05-evaluation-and-milestone-gate/05-UAT.md
started: Between 05-13 and 05-17 (05-14 bot changes, 05-15 golden edits to gd-02, gd-05, sr-02 only, 05-16 eval harness changes).

## Eliminated

- hypothesis: Retrieval regression (relevant evidence missing or reordered after the 05-14 Guides changes).
  evidence: In both runs the retrieve span returns the same 3 handbook pages at positions 0 to 2 with identical text hashes and order; the handbook query (keywords_it) is identical. The cited source is the same single handbook page. Only Guides results differ, and those are irrelevant technical chunks in both runs.
  timestamp: 2026-11-22T22:40:00Z
- hypothesis: Judge prompt, judge model, scoring or caching change (05-16 verdict key with reply_digest, scorer version 3) changed the outcome.
  evidence: judge.py and scoring.py have an empty diff from 6ad3dce (pre-05-14) to HEAD; judge model is claude-opus-5-5 in both reports. The 05-17 cache directory did not exist before the run (40 fresh outcomes, 31 fresh verdicts), so the verdict key change could not have served or hidden a verdict. The later reports run-20261122T214720Z and run-20261122T220954Z replay the same trace and verdict from cache.
  timestamp: 2026-11-22T22:42:00Z
- hypothesis: Golden item edited between runs.
  evidence: The sr-03 entry is unchanged since the pre-gap golden copy; the 05-15 golden edits touched other items only.
  timestamp: 2026-11-22T22:43:00Z
- hypothesis: CASE_SCOPE_RULE systematically suppresses named systems in answers.
  evidence: Not supported at corpus level, but only 3 items cite a source naming the system: one still names it in 05-17 (hb-03), one never named it (hb-04), sr-03 dropped it. Mean answer length of generated answers is unchanged (31 answers per run). Neither confirmed nor eliminated; see Evidence.
  timestamp: 2026-11-22T22:46:00Z

## Evidence

- timestamp: 2026-11-22T22:35:00Z
  checked: Run reports run-20261122T113929Z (05-13; run-20261122T113552Z holds the same trace id) and run-20261122T214341Z (05-17), sr-03 entries.
  found: Same kind (sensitive), same cited source, same referente role. Checks: 05-13 all true; 05-17 `facts` false only. Judge facts: facts 2 and 3 present in both; fact 1 present in 05-13, not present in 05-17; no contradicted facts; invented claims empty in both.
  implication: The whole flip is the single judge verdict on key fact 1 (the first of three).

- timestamp: 2026-11-22T22:37:00Z
  checked: MLflow spans of both sr-03 traces (reformulate, retrieve, answer, gate, LLM calls).
  found: Reformulation wording differs slightly between runs (standalone question and English keywords) while keywords_it is identical. Handbook evidence positions 0 to 2 identical. Guides evidence: 4 chunks in 05-13, 9 in 05-17 (merge of the keyword search and the new question-text search; `tried` holds one guides_search entry in 05-13 and two in 05-17). Answer prompt size grew (user text 12.5k to 16.7k characters; system prompt differs only by the CASE_SCOPE_RULE line, 2923 to 3111 characters). LLM calls carry no temperature parameter; no `temperature` appears in services, packages or jobs code.
  implication: Reformulation, answer and judge are all sampled at provider defaults, so identical inputs are not expected to give identical text. The 05-14 changes enlarged the prompt with irrelevant Guides chunks for a handbook question.

- timestamp: 2026-11-22T22:44:00Z
  checked: All 40 items, 05-13 versus 05-17 (answer text equality, judge fact vectors, status).
  found: Answer text differs for 30 of 40 items; the 10 identical are fixed-text refusals plus hb-15. Status changed for 4 items (gd-02, sr-02, gd-13 wrong to correct; sr-03 correct to wrong); gd-05 wrong in both. Judge fact vectors equal for 26 of the 30 differently-worded items; the 4 that differ are gd-02, gd-05, sr-02, sr-03, all compound-key-fact items already named in 05-GAP-DECISION (gd-02 and sr-02 diagnosed as over-specified or compound golden facts judged all-or-nothing).
  implication: Baseline run-to-run churn is about 10 percent of items; judge verdicts are stable on non-compound facts and unstable on compound ones. sr-03 is the same fault class as gd-02 and sr-02, not a new one.

- timestamp: 2026-11-22T22:48:00Z
  checked: Answer wording difference for sr-03 against key fact 1 (three components, one inapplicable to the question).
  found: Both answers state the high-demand-period lead time and omit the ordinary-period lead time. The 05-13 answer also names the request channel; the 05-17 answer does not. The 05-13 judge marked fact 1 present; the 05-17 judge marked it not present (judge rationales are in the private file). Judge instruction is "present only if the answer states it".
  implication: Same partial coverage was judged present once and absent once; the swing follows the incidental channel mention. This is judge and golden fault with answer-wording variance as the trigger.

## Resolution

root_cause: Variance, not a deterministic regression. Fault class: golden (compound key fact 1 for sr-03, one component not applicable to the question) interacting with judge threshold variance, triggered by answer-wording variance. The relevant evidence, cited source, judge code, judge model and scoring are identical between 05-13 and 05-17. The 05-17 answer sample dropped the request-channel mention that the 05-13 sample had, and the judge applied the all-or-nothing reading to a partially covered compound fact. Same class as gd-02 and sr-02. Unresolved: whether CASE_SCOPE_RULE or the larger Guides noise (4 to 9 irrelevant chunks) shifts answer wording; one sample per condition cannot tell.
fix: none applied (diagnose only)
verification: not applicable
files_changed: []
