---
phase: 03-google-chat-bot
plan: 05
subsystem: bot-core
tags: [langgraph, refusal, retry, escalation, sensitive-topics, gap-log, citation-gate, tdd]

requires:
  - phase: 03-google-chat-bot (03-01)
    provides: "gap_question decision (standalone reformulated question is logged), no new pinned dependency"
  - phase: 03-google-chat-bot (03-02)
    provides: "buddy_core.escalation EscalationTable and the eight topic ids"
  - phase: 03-google-chat-bot (03-03)
    provides: "RunContext, State, build_graph, run_workflow, gate.check, ports, conftest FakeLlm/RecordingConnector/gaplog"
provides:
  - "workflow.py decision logic: one RetryPlan retry after a failed gate, refusal, referral, smalltalk and error replies; gap written once by run_workflow after the graph returns"
  - "referral.resolve_referente: role from the shared table, contact only as a verbatim substring of a handbook page returned in the run"
  - "schemas.RetryPlan and schemas.ContactExtraction"
  - "prompts: RETRY_SYSTEM, CONTACT_SYSTEM, ANSWER_SENSITIVE_SYSTEM, format_topics, build_reformulate_system (REFORMULATE_SYSTEM is its default-table instance)"
  - "gate reasons blank_answer (check order: no_evidence, blank_answer, no_citation, unsupported_citation, not_grounded, low_confidence) and invalid_output (workflow-level)"
  - "WorkflowDeps.escalation and RunContext.escalation (default: the shipped table)"
affects: [03-06, 03-08, 03-09, 03-11, 03-12]

actuals:
  tokens: 11300
  tasks: 3
  commits: 5
plan_head_before: c650901191de43cd0e868af28bace2b43b7a7be8
commits: 5
plan_head_after: 8566d6b5eaba2329b3c27528fb5b810726598a3c

tech-stack:
  added: []
  patterns:
    - "Single bounded retry as a graph loop (retry_plan -> retrieve) driven by an attempt counter in State; routing through conditional edges only"
    - "Side effect (gap write) outside the graph, in run_workflow after ainvoke, so a graph re-execution cannot log twice"
    - "Contact accepted only as verbatim substring of tool-returned text; the model supplies a pointer, never the value"
    - "Prompt built from the shared escalation table so bot and Skill cannot drift on topic ids"

key-files:
  created:
    - services/chat_bot/buddy_bot/referral.py
    - tests/unit/chat_bot/test_refusal.py
    - tests/unit/chat_bot/test_gate.py
    - tests/unit/chat_bot/test_workflow.py
    - tests/unit/chat_bot/test_sensitive.py
  modified:
    - services/chat_bot/buddy_bot/workflow.py
    - services/chat_bot/buddy_bot/prompts.py
    - services/chat_bot/buddy_bot/schemas.py
    - services/chat_bot/buddy_bot/gate.py

key-decisions:
  - "Gap log stores the standalone reformulated question (03-01 gap_question option b) plus the full tried list of both attempts; the contact lookup query is not part of tried; no identity is passed"
  - "LlmUnavailableError propagates from retry_plan like from every later node (plan task 1 said LlmError skips the retry; task 2 says unavailable propagates; only LlmOutputError skips the retry, so an outage shows the error text instead of a misleading refusal)"
  - "LlmError from reformulate (output or unavailable) returns the error reply with no retrieval and no gap"
  - "A non-null sensitive_topic marks the run sensitive, including an empty string or an unknown id (safe branch, HR fallback role)"
  - "The contact lookup and RetryPlan use the reformulate (cheap) model; only the answer step uses the answer model"
  - "A retry that returns only already-known pages still counts as found and re-runs the answer; an attempt with zero results skips the answer call and takes the retry-or-refuse decision directly"

requirements-completed: [BOT-04, BOT-05, BOT-06, BOT-11]

coverage:
  - id: D1
    description: "A failed gate retries once with new keywords, answers again over the evidence of both attempts, and on a second failure refuses with `Non lo so, chiedi a HR (hr@example.invalid).` and exactly one gap record"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_refusal.py#test_unsupported_question_is_retried_once_then_refused_with_quoted_contact"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_workflow.py#test_low_confidence_then_good_second_draft_answers_over_both_attempts"
        status: pass
    human_judgment: false
  - id: D2
    description: "Referente contact comes only verbatim from a handbook page returned in the run; a non-verbatim contact, a pointer to an unreturned page or a lookup failure names the role alone"
    requirement: BOT-04
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_refusal.py#test_contact_not_in_the_handbook_page_is_dropped"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_refusal.py#test_contact_cited_from_a_page_the_run_did_not_return_is_dropped"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_workflow.py#test_contact_lookup_failure_never_breaks_the_refusal"
        status: pass
    human_judgment: false
  - id: D3
    description: "Gap record holds the standalone question and the four tried queries and no identity; written on the real in-memory buddy_mcp server once; tool calls limited to handbook_search, guides_search, buddy_report_gap"
    requirement: BOT-11
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_refusal.py#test_unsupported_question_is_retried_once_then_refused_with_quoted_contact"
        status: pass
    human_judgment: false
  - id: D4
    description: "Gate edges: prefix, case variant, `#L` anchor, missing anchor and percent-decoded citations fail; whitespace-wrapped passes; empty citations, blank answer, empty evidence and the threshold boundary behave as specified"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_gate.py (15 cases)"
        status: pass
    human_judgment: false
  - id: D5
    description: "No answer call for an attempt with no results; smalltalk for chitchat/off_topic with no tools and no gap; history only in the reformulate prompt; reformulation failure gives the error reply with no tools and no gap; model outage propagates"
    requirement: BOT-04
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_workflow.py (13 cases)"
        status: pass
    human_judgment: false
  - id: D6
    description: "KEYWORD_BRIDGE equals the SKILL.md Italiano -> inglese rows"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_workflow.py#test_keyword_bridge_equals_the_skill_table"
        status: pass
    human_judgment: false
  - id: D7
    description: "Sensitive questions are answered with the restricted general-rule prompt and a table-derived referente, end as a referral plus gap when no rule is supported, unknown ids fall back to HR, and the reformulate prompt lists the eight table topics with no extra word list"
    requirement: BOT-06
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_sensitive.py (8 cases)"
        status: pass
    human_judgment: false
  - id: D8
    description: "The restricted prompt actually keeps the model from assessing or advising on an individual's case, and the fixed referral sentence is rendered by the bot"
    requirement: BOT-06
    verification: []
    human_judgment: true
    rationale: "Code cannot prove the absence of an individual assessment in model prose (plan flagged assumption); Phase 5 sensitive golden items judge it, and the fixed sentence is asserted in 03-08."

duration: about 25 min (start time not recorded; estimated from first to last commit and checks)
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 05: Retry, Refusal, Referral and Sensitive-Topic Workflow Summary

**The bot now retries a failed grounded answer exactly once with new keywords, then refuses with a referente whose contact is quoted verbatim from the handbook, logs one gap per refused company question through the real `buddy_report_gap`, and answers sensitive topics with only the cited general rule plus a table-derived referral.**

## Performance

- **Duration:** about 25 min (estimated)
- **Completed:** 2026-11-07
- **Tasks:** 3 (1 tracer, 2 TDD)
- **Files modified:** 9 (5 created, 4 modified); `--all` gives 722 passed, 18 skipped (emulator and local-only), ruff, ruff format and mypy --strict clean, coverage 97%

## Accomplishments

- Tracer verified end to end (`test_refusal.py`, 3 tests): reformulate, two answer drafts citing ids the run never returned, one RetryPlan call, refusal rendering `Non lo so, chiedi a HR (hr@example.invalid).`, one gap record `Come richiedo le ferie?` with tried `handbook_search: ferie`, `guides_search: holidays`, `handbook_search: permessi`, `guides_search: leave`. Tools called: handbook_search, guides_search, buddy_report_gap only.
- Referente safety: contact kept only when the model's `source_url` is a handbook page returned by the lookup and the stripped contact is a substring of that page text; otherwise the role alone. Lookup failures never break the refusal.
- Gate: new `blank_answer` reason, placed right after `no_evidence`; adjacency, case, anchor and encoding edges pinned by 15 test cases; exact code-point equality after `strip()` unchanged.
- Workflow branches: smalltalk (no tools, no answer call, no gap), error reply when reformulation fails, answer skipped when an attempt returns no results, `invalid_output` when the answer model returns unusable JSON twice, history isolated to the reformulate prompt.
- Sensitive topics (D-05, D-06, D-07): reformulate prompt built from the shared table via `format_topics`; non-null `sensitive_topic` selects `ANSWER_SENSITIVE_SYSTEM`; answers carry `referente` (HR, or `responsabile diretto` for `ferie_personali`); final failure becomes kind `referral` with a gap; unknown ids fall to HR.

## Task Commits

1. **Task 1: Tracer, retry then refusal with quoted referente and gap** - `5aa4669` (feat)
2. **Task 2 RED: gate edge and workflow decision tests** - `d55d171` (test)
3. **Task 2 GREEN: blank-answer gate, smalltalk, reformulation error reply** - `4d243f8` (feat)
4. **Task 3 RED: sensitive-topic tests** - `d7eafc1` (test)
5. **Task 3 GREEN: sensitive topics, general rule plus referral** - `8566d6b` (feat)

**Plan metadata:** the docs commit that adds this SUMMARY with STATE.md and ROADMAP.md.

## TDD Gate Compliance

Task 1 (tracer): written together with its implementation as one `feat` commit per the tracer task type; the tracer verify (`test_refusal.py`) was re-run and passed before expansion: Tracer verified end-to-end, expanding.

Task 2 (tdd):

- **RED** (`d55d171`): 4 of 28 cases failed on the planned behavior (test_gate: 4 blank_answer cases returned `ok`/`no_citation`; test_workflow: chitchat and off_topic returned `refusal` instead of `smalltalk`, and the two reformulation-error tests raised the uncaught `LlmOutputError`/`LlmUnavailableError`). Machine check: replayed the RED commit in a scratch export (`git archive d55d171`), pytest `--junitxml`, target `tests.unit.chat_bot.test_workflow#test_chitchat_and_off_topic_get_smalltalk_with_no_retrieval_and_no_gap[chitchat]` through `gsd_run check tdd-red-evidence`: `RED_EVIDENCE_OK`, reason `target_test_failed`. Semantic assessment: the target ran, was not skipped, failed on `assert 'refusal' == 'smalltalk'` for the intended reason; no import, collection or fixture fault.
- Green-on-arrival (characterization pins, not RED targets): near-miss citation cases, whitespace strip, empty evidence, threshold boundary, retry success, no-results shortcut, retry-plan failure, `invalid_output`, history isolation, model outage propagation, contact lookup failure and the KEYWORD_BRIDGE drift test already held because Task 1 and 03-03 implemented that behavior; they pin it against regression.
- **GREEN** (`4d243f8`): all 15 gate and 13 workflow cases pass.

Task 3 (tdd):

- **RED** (`d7eafc1`): 7 of 8 cases failed. Behavior cases failed on assertions (`referente` was None for sensitive answers, `refusal` instead of `referral`, reformulate prompt lacked the topic lines). `test_format_topics_renders_one_line_per_topic` fails with `AttributeError` (module has no `format_topics`), a missing-symbol failure rather than an assertion, so it is not offered as RED evidence. Machine check on a scratch replay of `d7eafc1`: target `tests.unit.chat_bot.test_sensitive#test_unknown_topic_id_is_treated_as_sensitive_with_the_fallback_role`, `RED_EVIDENCE_OK`, reason `target_test_failed`. Semantic assessment: target executed and failed on `assert None is not None` for `reply.referente`, the planned behavior.
- **GREEN** (`8566d6b`): all 8 pass; `--all` green.
- **REFACTOR:** none. A first draft cached a default-table prompt comparison in `workflow.py`; it was simplified to building the prompt from `ctx.escalation` before the GREEN commit, so no refactor commit was needed.

## Files Created/Modified

- `services/chat_bot/buddy_bot/workflow.py` - retry loop, refusal/referral, smalltalk, error reply, sensitive routing, gap write after the graph
- `services/chat_bot/buddy_bot/referral.py` - `resolve_referente`, `CONTACT_QUERY_SUFFIX`
- `services/chat_bot/buddy_bot/prompts.py` - retry, contact and sensitive-answer prompts, topic-aware reformulate prompt
- `services/chat_bot/buddy_bot/schemas.py` - `RetryPlan`, `ContactExtraction`
- `services/chat_bot/buddy_bot/gate.py` - `blank_answer`
- `tests/unit/chat_bot/test_refusal.py`, `test_gate.py`, `test_workflow.py`, `test_sensitive.py` - 3 + 15 + 13 + 8 = 39 tests

## Decisions Made

See `key-decisions` in the frontmatter. Hand-off to later plans: 03-08 renders `Per il tuo caso specifico chiedi a <referente>.` for kind answer with a referente (sensitive answers) and already renders kind `referral`; 03-11 and 03-12 read the gap log question as the standalone reformulation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RetryPlan unavailable-model handling aligned with the plan's own task 2 rule**
- **Found during:** Task 1
- **Issue:** Task 1 text says an `LlmError` from the RetryPlan call skips the retry; Task 2 says `LlmUnavailableError` from any later node propagates. Following Task 1 literally would turn an outage into a "Non lo so" refusal and a false gap.
- **Fix:** only `LlmOutputError` skips the retry; `LlmUnavailableError` propagates so the service shows the error text. The reformulate step catches the whole `LlmError` family as the plan states.
- **Files modified:** services/chat_bot/buddy_bot/workflow.py
- **Verification:** `test_retry_plan_failure_skips_the_retry_and_refuses`, `test_model_unavailable_during_answer_propagates_without_a_gap`
- **Commit:** 5aa4669

**2. [Rule 3 - Blocking] `GuidesSearchOutput` requires `query`**
- **Found during:** Task 1
- **Issue:** the lookup reuses `evidence_from` with an empty Guides envelope; the model requires a `query` field.
- **Fix:** `GuidesSearchOutput(status="no_results", query="", results=[])`.
- **Files modified:** services/chat_bot/buddy_bot/referral.py
- **Commit:** 5aa4669

**3. [Rule 1 - Bug] Ruff SIM300 on the drift test comparison**
- **Found during:** Task 2
- **Fix:** operands swapped to `_skill_bridge_rows() == KEYWORD_BRIDGE`.
- **Commit:** 4d243f8

**Total deviations:** 3 auto-fixed (2 bug, 1 blocking). **Impact:** none on scope.

### Guard note (not a plan deviation)

The Step 0 pre-commit assertion treats `main` as a protected branch (`git.base-branch --is-protected main` returns `true`). The orchestrator dispatched this plan as a sequential executor on `main`, and the user's persistent memory states all work in this repo is committed directly on `main` (no branches; push only on ask). All five task commits were made on `main` on that basis; `.planning/config.json` was not changed to set `git.allow_default_branch_commits`. Nothing was pushed.

## Issues Encountered

None.

## Known Stubs

None. Every new path is exercised through `run_workflow` on the in-memory MCP server; no placeholder values reach a rendered reply.

## Threat Flags

None. The plan's threat register is covered: T-03-10 (evidence stays delimited, citations equal run evidence ids, contact and referral text are code-rendered), T-03-11 (fixed refusal and referral strings, unknown topic falls to the safe branch), T-03-12 (non-verbatim contact test), T-03-13 (gap record read from the server holds only the question and tried queries). No new endpoint, auth path or storage was added.

## User Setup Required

None.

## Next Phase Readiness

- 03-06 and later plans can rely on `WorkflowDeps(llm, mcp, config)` unchanged (escalation defaults to the shipped table).
- 03-08 must render the fixed referral sentence for sensitive answers (`reply.referente` set on kind `answer`) and may append a provenance line after the refusal prefix.
- The BOT-06 individual-case guarantee depends on model behavior under `ANSWER_SENSITIVE_SYSTEM`; Phase 5 sensitive golden items are the judge.

## Self-Check: PASSED

- FOUND: referral.py, test_refusal.py, test_gate.py, test_workflow.py, test_sensitive.py (all verified on disk)
- FOUND commits 5aa4669, d55d171, 4d243f8, d7eafc1, 8566d6b (`git merge-base --is-ancestor`), commit count measured `git rev-list --count c650901..HEAD` = 5
- Acceptance criteria re-run: resolve_referente 1, `report_gap(` in workflow.py 1, class RetryPlan 1, gaplog.records in test_refusal 3, test_gate defs 9 (>= 6), KEYWORD_BRIDGE in test_workflow 2, `"smalltalk"` in workflow.py 5, ANSWER_SENSITIVE_SYSTEM in workflow.py 2, format_topics 1, `referente_role(` 1, `git diff --quiet 7d772e2 -- services/mcp_server jobs/sync skills/digitiamo-buddy/SKILL.md` exit 0
- `./run-unit-tests.sh --all`: 722 passed, 18 skipped, coverage 97.09%
