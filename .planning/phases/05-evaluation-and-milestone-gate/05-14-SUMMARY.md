---
phase: 05-evaluation-and-milestone-gate
plan: 14
subsystem: chat-bot-retrieval
tags: [retrieval, guides, prompt, gap-closure, EVAL-03, EVAL-06]
status: complete
requires:
  - phase: 05-13
    provides: live gate FAIL (invented_policies 1 > 0) and the 05-GAP-DECISION record
provides:
  - "First-attempt retrieve runs a second guides_search over the standalone question minus Italian function words; results merged keyword-first, deduped by source_url"
  - "FastMcpConnector Guides default limit 8 (DEFAULT_GUIDES_LIMIT); handbook stays 3"
  - "CASE_SCOPE_RULE in ANSWER_SYSTEM and ANSWER_SENSITIVE_SYSTEM"
affects: [05-17]
actuals:
  tokens: 4900
  tasks: 2
  commits: 2
plan_head_before: 7fb1d3007d8393c806847ee7df3cba82763854bd
plan_head_after: c6f861b4ebaf8144dd883183122ca84c3b75f6f7
tech-stack:
  added: []
  patterns: [keyword-first union of two BM25 lists, stopword-filtered question query]
key-files:
  created: []
  modified:
    - services/chat_bot/buddy_bot/workflow.py
    - services/chat_bot/buddy_bot/mcp_client.py
    - services/chat_bot/buddy_bot/prompts.py
    - tests/unit/chat_bot/test_workflow.py
    - tests/unit/chat_bot/test_prompts.py
    - tests/unit/chat_bot/test_refusal.py
    - tests/unit/buddy_eval/test_empty_context.py
key-decisions:
  - "05-14: Guides evidence is the uncapped union of the keyword top-8 and the question top-8 (A-14-1); the question search runs on the first attempt only (A-14-3)"
  - "05-14: Italian function words are stripped from the question before guides_search; an empty result skips the question search (A-14-2)"
duration: 7min
completed: 2026-11-22
---

# Phase 5 Plan 14: Question-text Guides search (k=8) and case-scope rule Summary

The bot now also searches Guides with the stopword-filtered standalone question, with Guides k raised from 4 to 8. Both answer prompts now forbid turning a statement about one named case into a general rule.

## What changed

- `workflow.py`: `guides_question_query(question)` keeps tokens as written. It drops a token when its casefolded word characters are in `_QUESTION_STOPWORDS` or shorter than 2 characters. On the first attempt (`retry` is None), `retrieve` calls `guides_search(question_query)` after the keyword Guides search and appends `guides_search: <query>` to `tried`. An empty query means no third call. The retry is unchanged: one handbook search and one keyword Guides search.
- `mcp_client.py`: adds `DEFAULT_HANDBOOK_LIMIT = 3` and `DEFAULT_GUIDES_LIMIT = 8` as the `FastMcpConnector` defaults. `evidence_from(handbook, *guides)` reads the Guides outputs in argument order, and a source_url already present keeps its first position. The `referral.py` call is unchanged.
- `prompts.py`: `CASE_SCOPE_RULE` (exact Italian text from the plan) sits right after the "Cita ogni affermazione" rule in both answer prompts. No other rule text changed.
- No change under `services/mcp_server` or `packages/buddy_core` (`git diff --quiet 6ad3dce` ok). The handbook query and its limit of 3 are unchanged.

## Tests

- New tests in `test_workflow.py`:
  - tracer over the real in-memory MCP server: calls are exactly handbook, guides, guides, and the gateway chunk's `<fonte id=` appears in the AnswerDraft prompt
  - evidence found only by the question search, with an ungrounded draft, still ends in a refusal with one gap record
  - dedupe
  - the retry makes 3 guides calls in total and keeps the question-search evidence
  - `tried` order
  - stopword filter (4 cases)
  - a question made only of function words makes no third call
  - default limits 8/3, checked by recording `fastmcp.Client.call_tool` arguments
- `test_prompts.py`: checks the rule's bullet form and wording, and that both prompts hold it right after the citation rule.
- Full suite `./run-unit-tests.sh --all`: ruff ok, 200 files formatted, mypy ok (186 files). Pytest: 2064 passed, 26 skipped, coverage 98.11%, exit 0.
- Tracer feedback gate: the `<verify>` re-run passed (25/25 in test_workflow.py), so execution moved on to Task 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test expectation] Question-only gate test asserts `no_citation`, not `not_grounded`**
- **Found during:** Task 1
- **Issue:** `gate.check` tests citations before grounding, so a draft with `grounded=false` and empty citations fails with `no_citation`.
- **Fix:** the test asserts the reason the gate actually returns. The behaviour under test still holds: the gate decides, and the reply is a refusal with one gap record and no answer text.
- **Commit:** 0c3cb50

**2. Coupled test modules updated (both on the plan's allowed list)**
- `tests/unit/chat_bot/test_refusal.py`: the expected `tried` tuple gains `"guides_search: richiedo ferie?"` after the keyword entries. This is a search-count update and no other assertion changed.
- `tests/unit/buddy_eval/test_empty_context.py`: the negative variant's `evidence=1` is now `evidence=2`. The question "Domanda sul gizmo?" hits the same chunk, and the console counts raw search results.
- `tests/unit/chat_bot/test_sensitive.py`: no change was needed.
- **Commit:** c6f861b

Also added `DEFAULT_HANDBOOK_LIMIT` as a named constant for the existing default of 3. The value is unchanged.

## Known Stubs

None.

## Threat Flags

None. The question text already reached the MCP server through `buddy_report_gap`. The bot adds no log line, and `format_evidence` escaping is unchanged.

## Self-Check: PASSED

- FOUND: services/chat_bot/buddy_bot/workflow.py, mcp_client.py, prompts.py
- FOUND: 0c3cb50, c6f861b (ancestors of HEAD)
