---
phase: 03-google-chat-bot
plan: 09
subsystem: bot-service
tags: [google-chat, allowlist, thread-memory, dedupe, idempotency, timeout, tdd]

requires:
  - phase: 03-google-chat-bot (03-01)
    provides: "memory_key decision (b): DM space name, room thread name"
  - phase: 03-google-chat-bot (03-03)
    provides: "run_workflow, ThreadMemory/Turn ports, BotService tracer, FakeLlm/FakeChatApi/RecordingConnector fixtures"
  - phase: 03-google-chat-bot (03-04)
    provides: "normalize_event for both Chat shapes, event fixtures"
  - phase: 03-google-chat-bot (03-06)
    provides: "FirestoreThreadMemory / InMemoryThreadMemory (consumed through the ThreadMemory port)"
provides:
  - "BotService.handle complete: bot-sender and allowlist drop, message-name TTL dedupe, canned replies, memory wiring, run deadline, never-raise"
  - "service.memory_key_source, INTRO_TEXT, USAGE_TEXT, DEDUPE_TTL_SECONDS=600, DEDUPE_MAX_ENTRIES=1024"
  - "BotService(*, allowed_users, chat, deps, memory, memory_turns, video_thumbnail_url, help_command_id=None, run_deadline_seconds=120.0, clock=time.monotonic)"
  - "tests/unit/chat_bot/conftest.py: DictThreadMemory, make_service factory fixture, with_message, shared REFORMULATION and GOOD_DRAFT"
affects: [03-10, 03-11, 03-12]

actuals:
  tokens: 7155
  tasks: 2
  commits: 3
plan_head_before: e8968cb1c46b1deb1d06306e64acc2a6943168e3
commits: 3
plan_head_after: e7a5ef1c299766ffa7ea05d0579e28849c4bcc94

tech-stack:
  added: []
  patterns:
    - "Message name as idempotency key in an insertion-ordered dict with TTL purge and size cap (clock injected)"
    - "History read and workflow run inside one asyncio.timeout; every failure collapses to the error reply"
    - "Canned replies bypass the workflow: one create_message, no placeholder, no model or MCP call"

key-files:
  created:
    - tests/unit/chat_bot/test_conversation.py
    - tests/unit/chat_bot/test_service.py
    - tests/unit/chat_bot/test_allowlist.py
  modified:
    - services/chat_bot/buddy_bot/service.py
    - tests/unit/chat_bot/conftest.py
    - tests/unit/chat_bot/test_tracer.py

key-decisions:
  - "memory_key_source follows 03-01 option (b): space name for DM events, thread name for rooms, None when a room event has no thread (then no read and no write)"
  - "Only reply kinds answer, refusal, referral, smalltalk are remembered; the stored answer is reply.answer or, when empty (refusal, referral, smalltalk), the rendered text. Error replies are never stored"
  - "Allowlist entries are trimmed and lowercased at construction and empty entries are discarded; identities are trimmed and lowercased at match time; sender passes when user name or e-mail is a member"
  - "The placeholder is created before the deadline starts, so create_message failure ends handle with no other call; memory read, workflow and rendering share the deadline; memory append runs after the patch"
  - "Dedupe marks a message name as seen when first handled (also if that attempt later fails), so a redelivery after a failure is not retried; added and removed events are not deduped"
  - "make_service is a factory fixture (llm, *, chat, memory, **overrides) rather than a zero-argument fixture, so tests keep a handle on the fakes they assert against"

patterns-established:
  - "Drop path logs one fixed INFO line and nothing from the event"
  - "Log lines in service.py carry fixed text plus exception type name only"

requirements-completed: [BOT-03, BOT-10, BOT-11]

coverage:
  - id: D1
    description: "A follow-up in the same DM or room thread sends the previous question and answer to the reformulation step only; memory_turns bounds the read; key source is the DM space name or the room thread name"
    requirement: BOT-11
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_conversation.py#test_dm_follow_up_reformulation_sees_history_and_answer_step_does_not"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_conversation.py#test_room_follow_up_uses_the_thread_name_as_memory_key"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_conversation.py#test_memory_turns_limits_how_many_turns_are_read"
        status: pass
    human_judgment: false
  - id: D2
    description: "Allowlist matching is exact after trim and lowercase on name or e-mail; missing sender or identity-less sender is dropped; every drop for every event kind makes no Chat, MCP, LLM or memory call and logs no identity"
    requirement: BOT-03
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_allowlist.py (14 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "ADDED_TO_SPACE gets the Italian intro, /aiuto, typed /aiuto and mention-only messages get the usage text, all without LLM or MCP calls; REMOVED_FROM_SPACE and bot senders produce no call"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py (added, aiuto, mention-only, removed, bot-sender tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Redelivered message name within 10 minutes produces no second placeholder, run or memory turn; handled again after the TTL; table capped at 1024 entries"
    requirement: BOT-11
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py#test_redelivered_event_is_handled_once"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py#test_same_message_name_is_handled_again_after_the_ttl"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py#test_dedupe_table_is_capped"
        status: pass
    human_judgment: false
  - id: D5
    description: "handle never raises: workflow exception or deadline overrun patches the placeholder with the error text; failing memory read or write is logged by exception type and the reply is still delivered"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py#test_workflow_exception_patches_the_placeholder_with_the_error_text"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py#test_run_past_the_deadline_patches_the_error_text"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_service.py#test_memory_failure_does_not_stop_the_reply"
        status: pass
    human_judgment: false
  - id: D6
    description: "Wording of INTRO_TEXT and USAGE_TEXT (Italian, tone, adequacy for Joshua) is a discretion item"
    verification: []
    human_judgment: true
    rationale: "Tests assert presence of key elements only; whether the copy reads right is a human review item"

duration: 8min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 09: BotService rules and thread memory Summary

**BotService.handle now enforces the allowlist and bot-sender drop first, suppresses redeliveries by message name for 10 minutes, answers join and /aiuto with fixed Italian texts, feeds thread history only to the reformulation step, and ends every failure or 120 s overrun in a visible error text.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-11-07T12:02:02Z
- **Completed:** 2026-11-07T12:10:00Z
- **Tasks:** 2 (tracer, then TDD with RED, GREEN)
- **Files modified:** 6

## Accomplishments

- Follow-ups work in a DM (key: space name) and in a room thread (key: thread name), per 03-01 memory_key (b); history reaches only the reformulation prompt, asserted in both directions in test_conversation.py.
- Guard order in `_handle`: normalize, bot sender, allowlist (single fixed INFO line), removed, dedupe, then added, help/command/empty text, or the answer flow. A drop touches no Chat, MCP, LLM or memory port.
- `asyncio.timeout(run_deadline_seconds)` wraps history read, workflow and rendering; any exception or the timeout patches the placeholder with the 03-08 error text, and no turn is stored for it.
- Full gate green: `./run-unit-tests.sh --all` gives ruff, format, mypy --strict and 841 passed, 21 skipped, coverage 97.93%, service.py 100%.

## Task Commits

1. **Task 1: Tracer, follow-up through reformulation-only history** - `9101b2d` (feat)
2. **Task 2 RED: failing tests for allowlist, canned replies, dedupe, deadline** - `d3b27bc` (test)
3. **Task 2 GREEN: service rules** - `e7a5ef1` (feat)

**Plan metadata:** recorded in the docs commit that follows this file (docs: complete plan)

## TDD Gate Compliance

- RED: `test(03-09)` commit `d3b27bc` precedes GREEN `feat(03-09)` `e7a5ef1`. At RED, 14 of 20 test_service tests and 1 of 14 test_allowlist tests failed on their planned assertions (for example the deadline test received the real answer instead of the error text; the bot-sender test created a placeholder; the trimmed-allowlist test dropped a sender it should admit). The 6 passing test_service tests and 13 test_allowlist tests characterise behaviour already present from 03-03 (never-raise, create failure, memory failures, no-memory room, removed events, prefix/case/missing-sender drops).
- Semantic assessment of RED: targets executed and failed on assertions, not on import or setup errors. To let the tests collect, the RED commit also carried a service.py skeleton (new constructor parameters and empty INTRO_TEXT/USAGE_TEXT constants) with no behaviour.
- `gsd_run check tdd-red-evidence` was not run: pytest console output is not one of the supported report formats (TAP, JUnit, unittest, go, swift-testing). Evidence is the pytest failure output inspected manually.
- No REFACTOR commit.

## Files Created/Modified

- `services/chat_bot/buddy_bot/service.py` - full handle flow, `memory_key_source`, canned texts, dedupe, deadline
- `tests/unit/chat_bot/conftest.py` - DictThreadMemory, make_service factory, with_message, shared REFORMULATION/GOOD_DRAFT
- `tests/unit/chat_bot/test_tracer.py` - builds the service through make_service; assertions unchanged
- `tests/unit/chat_bot/test_conversation.py` - 3 follow-up tests
- `tests/unit/chat_bot/test_allowlist.py` - 14 tests (parametrised)
- `tests/unit/chat_bot/test_service.py` - 21 tests (parametrised)

## Decisions Made

See key-decisions. Honoured from 03-01: memory_key (b) as the D-11 amendment; gap_question (b) and http_ack (b) are not touched by this plan (workflow logs the standalone question; the 25 s ack belongs to 03-10).

## Deviations from Plan

None - plan executed exactly as written, with two points that sit inside the plan's discretion:

- `help_command_id` is accepted and used (`_is_help`), but every command and every `/aiuto` message maps to USAGE_TEXT as the plan specifies, so the id match is behaviourally redundant today. It is kept because 03-10/03-11 pass it.
- Task 1 was a tracer, so its tests and code share one commit (`9101b2d`) rather than a RED/GREEN pair.

**Total deviations:** 0 auto-fixed.

## Issues Encountered

- mypy `comparison-overlap` on `INTRO_TEXT != USAGE_TEXT` (both `Final` literals) and `func-returns-value` on assigning the result of `handle`; both test assertions were rewritten to check content instead.

## Deferred Items (out of scope, events.py from 03-04)

- A mention-only message whose `argumentText` is blank but whose `text` is `@AI Buddy` (two-word display name) normalises to `Buddy` (the leading-mention regex strips only `@AI`), so it would reach the workflow instead of USAGE_TEXT. The test uses a one-word mention (`@AIBuddy`). Real Chat sends `argumentText` for mentions, so this is probably theoretical, but 03-12's live check should include a bare @mention in a room.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path, file access or schema; T-03-06, T-03-07 and T-03-08 are mitigated and covered by test_allowlist.py and test_service.py. The BOT-03 prohibition holds: the drop path logs one fixed line, asserted free of `users/` and `@`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 03-10 (adapters/intake) and 03-11 (wiring) can construct `BotService` with the interface above; `ThreadMemory` is passed in, `memory_turns` and `run_deadline_seconds` come from settings. The BotService dedupe is per process: with more than one instance, redelivery suppression is per instance.
- http_ack (25 s then `{}`) is not implemented here by design; it belongs to the 03-10 HTTP intake.

---
*Phase: 03-google-chat-bot*
*Completed: 2026-11-07*

## Self-Check: PASSED

- Files present: service.py, conftest.py, test_tracer.py, test_conversation.py, test_service.py, test_allowlist.py
- Commits reachable: 9101b2d, d3b27bc, e7a5ef1
- Acceptance greps: memory_key_source 1, memory.(recent|append) 2, DictThreadMemory 1, DEDUPE_TTL_SECONDS 2, asyncio.timeout 1, INTRO/USAGE 2, mcp_server and jobs/sync diff against 7d772e2 clean
