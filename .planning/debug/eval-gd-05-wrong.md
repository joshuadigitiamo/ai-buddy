---
status: diagnosed
trigger: "Golden item gd-05 (public Guides item) judged wrong in the live Milestone 1 gate run of 05-17 (run-20261122T214341Z); also wrong in 05-13. Find why: retrieval miss, reformulation, answer generation, judge, or golden item itself."
created: 2026-11-22T22:15:00Z
updated: 2026-11-22T22:30:00Z
goal: find_root_cause_only
---

## Current Focus

hypothesis: CONFIRMED. The 05-13 retrieval fault is fixed. gd-05 now fails only on key fact 3 (a purpose clause), which the answer omits; golden key fact bundles rationale the "how" question does not ask for, and the judge scores a compound fact all-or-nothing.
test: done (trace span inspection, report/verdict comparison, live BM25 replay against mcp-server, source text check)
expecting: n/a
next_action: return diagnosis to caller (no fix applied; read-only investigation)

## Symptoms

expected: Live gate scores every approved golden item correct with citation.
actual: 38/40 correct. gd-05 and sr-03 wrong. gd-05 was also wrong in 05-13.
errors: none (judge verdict wrong, not a crash).
reproduction: Test 6 in 05-UAT.md; run report run-20261122T214341Z, trace tr-4f02a68865d7bfe62501fdb72681e720.
started: wrong in 05-13 run (build 20261122T094743Z) and again in the 05-17 run (bot_version baed06a5b44c...); the reason differs between the two.

## Eliminated

- hypothesis: retrieval miss is still the cause (05-13 diagnosis carried forward)
  evidence: 05-17 trace `retrieve` span has `found: true` and the expected ETL SCD Type 2 chunk (slug `type-2-versioned-rows-the-audit-standard`, lines L658-L684) is in the evidence and is the only citation. Live replay: it ranks 7th for the keywords_en query and 6th for the question-text query, both inside k=8. Report checks: citation true.
  timestamp: 2026-11-22T22:25:00Z

- hypothesis: reformulator dropped the key term again
  evidence: `reformulate` span keywords_it contains "SCD Type 2"; keywords_en does not contain it (same drop as 05-13). It no longer matters because the second `guides_search` (question text, added in 05-14) and k=8 recover the chunk. `tried` shows one handbook_search and two guides_search entries as designed.
  timestamp: 2026-11-22T22:25:00Z

- hypothesis: answer step was starved of the source (truncation or missing text)
  evidence: expected chunk is 1295 chars, well under the 4000-char per-source truncation; the answer-span prompt contains the full chunk including the purpose sentence. Evidence order puts it 7th of 12 sources; the answer cites it correctly.
  timestamp: 2026-11-22T22:26:00Z

- hypothesis: answer is wrong, ungrounded, or contains invented claims
  evidence: facts 1 and 2 present, none contradicted, invented_claims empty, citation resolves under expected_sources, grounded true, confidence 0.95. Every statement in the answer traces to the cited chunk.
  timestamp: 2026-11-22T22:26:00Z

- hypothesis: judge hallucinated or misread the source
  evidence: the judge saw the full cited source (the purpose sentence is in it) and its finding is literal: the purpose clause of fact 3 is not stated. The judge prompt says a fact is present "only if the answer states it". Behaviour is consistent with its prompt, not a judge error.
  timestamp: 2026-11-22T22:27:00Z

## Evidence

- timestamp: 2026-11-22T22:18:00Z
  checked: run report run-20261122T214341Z, item gd-05
  found: status wrong; checks citation=true, facts=false, kind_answer=true; reasons ["facts: failed"]; judge_facts present = [true, true, false]; invented_claims []
  implication: only key fact 3 failed. In 05-13 (run-20261122T113929Z) the item failed citation AND facts with present = [false, true, true]. Different failure signature: the fault moved, the item did not stay "unchanged" in cause.

- timestamp: 2026-11-22T22:20:00Z
  checked: MLflow trace tr-4f02a68865d7bfe62501fdb72681e720 span tree (bot_run, LangGraph, reformulate, _after_reformulate, retrieve, _after_retrieve, answer, gate, _decide, finish plus 2 LLM spans)
  found: retrieve.tried = [handbook_search, guides_search (keywords_en), guides_search (question text)]; evidence = 3 handbook + 9 guides chunks (12 sources); gate_reason ok; finish reply kind answer, one citation (the expected ETL chunk).
  implication: pipeline ran as designed after 05-14/05-16; no span error or fallback.

- timestamp: 2026-11-22T22:22:00Z
  checked: live BM25 replay via mcp-server (no LLM), guides_limit 20, both actual queries
  found: ETL Type 2 chunk rank 7 (keywords_en) and rank 6 (question text). BigQuery Type 2 section (`scd-type-2-versioned-rows-full-history`, L1006-L1078) is rank 9 on the question query and absent from the top 10 of the keywords query: not retrieved with k=8.
  implication: expected-source retrieval works but sits at the edge of k=8 (ranks 6 and 7 of 8). Recall@5 still counts gd-05 as a miss (rank > 5), which matches UAT test 3 (guides 11/13). The second expected source added in 05-15 was not needed this run.

- timestamp: 2026-11-22T22:24:00Z
  checked: answer span input (system prompt rules) and output shape
  found: system prompt caps `answer` at 600 chars and at 4 bullets and says not to add unrequested details. The answer is 587 chars with exactly 4 bullets. Its 4 bullets are used on source-supported procedure details; the purpose clause of fact 3 is not stated as such (detail in the gitignored docs/internal/05-gap-diagnosis-uat.md, section gd-05).
  implication: the answer is at both caps; stating the audit/point-in-time purpose would have displaced another detail. Omission is a compliant trade-off for a "how do you handle it" question.

- timestamp: 2026-11-22T22:25:00Z
  checked: golden item gd-05 (jobs/eval/golden/guides.yaml) vs cited source text
  found: key fact 3 is "preserves complete history for audit and point-in-time queries": a compound fact (effect plus purpose). The source states it in one sentence of the section intro. The question asked is procedural ("how is a Type 2 dimension handled when a value changes"). Facts 1 and 2 are the procedure and both are present. 05-15 narrowed the analogous compound facts for gd-02 and sr-02 but left gd-05 fact 3 as is (only a second expected source was added).
  implication: same fault class the 05-13 diagnosis called (d) golden compound fact with (c) strict all-or-nothing judge, now applying to gd-05 as well.

- timestamp: 2026-11-22T22:26:00Z
  checked: sample count
  found: runs 20261122T214341Z, 214720Z and 220954Z all carry the same gd-05 trace id and answer digest (cache reuse). The post-fix bot has exactly one live answer sample for gd-05.
  implication: whether another sample would include the purpose clause is [Unknown]; the failure is one draw, not a measured rate.

## Resolution

root_cause: |
  Fault class: golden item (over-specified compound key fact) interacting with a strict all-or-nothing judge. Not retrieval, not reformulation, not a defect in answer generation.
  The 05-13 cause (retrieval miss, k=4) was fixed by 05-14 (question-text Guides search, k=8): the expected chunk is now retrieved (rank 6-7) and cited, and facts 1 and 2 are present. gd-05 still fails because key fact 3 bundles "full history" with its purpose "audit and point-in-time queries". The answer does not state the purpose clause, and it is at the 600-char / 4-bullet caps and the question asks "how", not "why". The judge, per its prompt, scores a partially stated fact as absent, so one fact fails the whole item.
  Secondary, minor: the answer model preferred other source-supported details over the one-sentence purpose line; this is a style choice within the prompt rules, not an error, and rests on a single sample.
fix: (none applied: diagnose-only)
verification: n/a
files_changed: []
