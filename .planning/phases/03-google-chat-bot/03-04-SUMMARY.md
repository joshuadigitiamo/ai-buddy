---
phase: 03-google-chat-bot
plan: 04
subsystem: bot-core
tags: [google-chat, event-normalization, anti-corruption-layer, add-on-events, fixtures, tdd]

requires:
  - phase: 03-google-chat-bot (03-03)
    provides: "ChatEvent and the legacy MESSAGE branch of normalize_event, BotService.handle, conftest FakeLlm/FakeChatApi/RecordingConnector/load_event/ALLOWED, test_tracer.py"
provides:
  - "buddy_bot.events.normalize_event: one ChatEvent (kinds message, added, removed, command) from the legacy flat shape and the add-on shape (top-level `chat` key); None for anything else, never raises on any JSON-decoded value"
  - "ten synthetic recorded event fixtures in tests/fixtures/chat_events (legacy_dm_message from 03-03 plus nine new)"
  - "tests/unit/chat_bot/test_events.py: normalizer table over every fixture plus malformed and non-mapping payloads"
  - "test_tracer.py end-to-end test for an add-on @mention in a room"
affects: [03-05, 03-09, 03-10, 03-12]

actuals:
  tokens: 6300
  tasks: 2
  commits: 3
plan_head_before: 64d4bf378d703b6a647f85900939ed315592cd83
commits: 3
plan_head_after: 8b44e49

tech-stack:
  added: []
  patterns:
    - "Anti-Corruption Layer: both Google payload shapes become one internal ChatEvent; nothing past normalize_event reads a raw payload"
    - "Lifecycle kinds selected from typed tables (_LEGACY_LIFECYCLE, _ADDON_LIFECYCLE) so mypy --strict checks the Literal kinds"

key-files:
  created:
    - tests/unit/chat_bot/test_events.py
    - tests/fixtures/chat_events/addon_room_mention.json
    - tests/fixtures/chat_events/addon_dm_message.json
    - tests/fixtures/chat_events/addon_added_to_space.json
    - tests/fixtures/chat_events/addon_removed_from_space.json
    - tests/fixtures/chat_events/addon_app_command.json
    - tests/fixtures/chat_events/legacy_room_mention.json
    - tests/fixtures/chat_events/legacy_added_to_space.json
    - tests/fixtures/chat_events/legacy_removed_from_space.json
    - tests/fixtures/chat_events/legacy_slash_command.json
    - tests/fixtures/chat_events/legacy_bot_sender.json
  modified:
    - services/chat_bot/buddy_bot/events.py
    - tests/unit/chat_bot/test_tracer.py

key-decisions:
  - "normalize_event takes `object`, not Mapping: the plan requires it never raises on any JSON-decoded value, so list, str, int and None inputs return None instead of relying on the caller's type"
  - "A message event needs a `message` mapping, and a command event needs a usable command id (str or int, never bool); otherwise None. A mistyped slashCommand drops the event rather than degrading it to a plain message"
  - "Mention fallback removes one leading `@word` token (plan wording). A two-word display name such as `@AI Buddy` leaves `Buddy` when argumentText is absent; argumentText is the primary path and 03-12 live checkpoint confirms it (RESEARCH A13)"
  - "User e-mail is lowercased in the normalizer, so the service allowlist compare stays case-insensitive without a second pass"

requirements-completed: [BOT-01, BOT-10]

coverage:
  - id: D1
    description: "An add-on format @mention in a room from an allowlisted sender gets the placeholder in the event's thread, then the answer patched onto it; the workflow receives the question without the @mention"
    requirement: BOT-01
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_addon_room_mention_gets_placeholder_in_thread_then_answer"
        status: pass
    human_judgment: false
  - id: D2
    description: "Legacy and add-on fixtures for DM message, room @mention, added, removed and slash/app command normalize to ChatEvent kinds message, added, removed, command"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_message_fixtures_normalize_to_message_events"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_added_to_space_is_kind_added_without_a_message"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_removed_from_space_is_kind_removed_without_a_message"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_slash_and_app_commands_carry_the_command_id_as_a_string"
        status: pass
    human_judgment: false
  - id: D3
    description: "normalize_event returns None, never raises, on {}, CARD_CLICKED, non-mapping chat values, non-mapping payloads and a message without a space name"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_malformed_payloads_return_none_and_never_raise"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_non_mapping_json_values_return_none"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_events.py#test_message_without_space_name_returns_none"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every event fixture holds synthetic values only (users/1111 and users/2222 ids, @example.invalid e-mails, spaces/AAAAsynthetic names)"
    requirement: BOT-10
    verification:
      - kind: other
        ref: "grep -lE '@digitiamo\\.com|@gmail\\.com' tests/fixtures/chat_events/*.json | wc -l -> 0; ls tests/fixtures/chat_events/*.json | wc -l -> 11"
        status: pass
    human_judgment: false
  - id: D5
    description: "Real Google Chat add-on event delivery matches the recorded add-on shape and argumentText behaviour"
    requirement: BOT-01
    verification: []
    human_judgment: true
    rationale: "Fixtures are synthetic reconstructions from the Google docs; only the 03-12 live checkpoint with Joshua's Chat app confirms the real payloads and RESEARCH A13 (argumentText)."

duration: 10min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 04: Event Normalizer Summary

**normalize_event maps legacy and add-on Google Chat payloads (message, @mention, added, removed, slash/app command) to one ChatEvent and ignores malformed input without raising; an add-on room @mention now gets placeholder then cited answer in its thread.**

## Performance

- **Duration:** about 10 min
- **Completed:** 2026-11-07
- **Tasks:** 2 (tracer + TDD)
- **Files modified:** 13 (11 created, 2 modified)

## Accomplishments

- Add-on `chat.messagePayload` @mention from an allowlisted user in a room: placeholder created in `spaces/AAAAsyntheticRoom/threads/t-1`, then the same message updated with the answer and `handbook://02-ferie`; the reformulate prompt holds "Come richiedo le ferie?" and not "@AI Buddy".
- All event kinds the bot handles arrive as the same ChatEvent from both shapes: message, added, removed, command (legacy `slashCommand.commandId`, add-on `appCommandMetadata.appCommandId` as str).
- Hostile or malformed JSON (`{}`, `CARD_CLICKED`, non-mapping `chat`, mistyped fields, non-mapping top-level values, missing space name) returns None; 46 tests in the two chat_bot event files pass, `--all` gives 683 passed, 18 skipped (emulator and local-only), events.py at 100% coverage, ruff, ruff format and mypy --strict clean.
- Nine new synthetic fixtures; no real ids, names or domains.

## Task Commits

1. **Task 1: Tracer, add-on @mention to placeholder then answer** - `0f90952` (feat)
2. **Task 2 RED: failing normalizer table and nine fixtures** - `0060eda` (test)
3. **Task 2 GREEN: normalize every kind from both shapes** - `8b44e49` (feat)

**Plan metadata:** committed with this SUMMARY (docs).

## TDD Gate Compliance

Task 1 (tracer): the new test failed first on `len(chat.created) == 1` (0 created, the add-on shape was unrecognised), then passed after the add-on branch; one commit per the tracer task type.

Task 2 (tdd):

- **RED** (`0060eda`): 10 of 45 test cases failed on planned assertions: kind `added`/`removed` returning None, `command` returning `message` or None, `test_email_is_lowercased` returning `Utente@Example.Invalid`, and four malformed cases returning a ChatEvent instead of None. `gsd_run check tdd-red-evidence` (pytest `--junitxml` report, target `tests.unit.chat_bot.test_events#test_email_is_lowercased`) returned `RED_EVIDENCE_OK`, reason `target_test_failed`. Semantic assessment: the target ran, was not skipped, and failed on the planned assertion for the intended reason; no import, collection or fixture fault (35 other cases passed in the same run).
- **GREEN** (`8b44e49`): all 45 cases pass; one extra malformed case (`appCommandId: true`) added to cover the bool branch, 46 total.
- **REFACTOR:** none needed (typed lifecycle tables were folded into the GREEN commit after the first mypy-oriented pass).

## Files Created/Modified

- `services/chat_bot/buddy_bot/events.py` - anti-corruption layer for both event shapes
- `tests/unit/chat_bot/test_events.py` - normalizer table, mention fallback, email, malformed and non-mapping cases
- `tests/unit/chat_bot/test_tracer.py` - add-on room @mention end-to-end test (existing tests unchanged)
- `tests/fixtures/chat_events/*.json` - ten recorded fixtures total, synthetic values only

## Decisions Made

See `key-decisions` in the frontmatter. The most consequential: strict `None` for malformed shapes (a mistyped slashCommand or a messagePayload without `message` is dropped, not degraded) and the single-token mention fallback.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Parameter type widened to `object`**
- **Found during:** Task 1
- **Issue:** the plan requires "never raises on any JSON-decoded value", but the 03-03 signature `Mapping[str, Any]` made a list or string input a type error and an AttributeError at run time.
- **Fix:** `normalize_event(payload: object)`; non-Mapping input returns None. Callers passing a Mapping are unaffected.
- **Files modified:** services/chat_bot/buddy_bot/events.py
- **Verification:** `test_non_mapping_json_values_return_none`; mypy --strict clean
- **Committed in:** 0f90952

**2. [Rule 1 - Bug] Test expectation vs plan wording for the mention fallback**
- **Found during:** Task 2 RED
- **Issue:** my first fallback test used the two-word mention `@AI Buddy` and expected full removal, which the plan's "leading `@<word>` token" rule cannot produce.
- **Fix:** the test uses a one-word mention (`@Buddy`); behaviour follows the plan. Recorded as a decision above, with RESEARCH A13 left for 03-12.
- **Files modified:** tests/unit/chat_bot/test_events.py
- **Committed in:** 0060eda

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 test correction)
**Impact on plan:** no scope change; no dependency added or changed.

## Issues Encountered

- The first `ruff check` flagged import order in events.py (`import re` placement); fixed before the Task 1 commit.
- Acceptance check `git diff --quiet 7d772e2 -- services/mcp_server jobs/sync` exits 0.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None. T-03-09 (hostile event JSON) is mitigated by the None-on-any-malformed-field contract and the parametrized malformed cases.

## Next Phase Readiness

- 03-05 and 03-09 can rely on ChatEvent kinds added, removed and command and on the ten fixtures; `BotService._handle` still ignores non-message kinds (03-09 adds the rules).
- Open for 03-12: confirm real add-on payloads and `argumentText` behaviour (A13) with the live Chat app; a multi-word bot display name only matters if argumentText is ever absent.

---
*Phase: 03-google-chat-bot*
*Completed: 2026-11-07*

## Self-Check: PASSED

All 11 created fixture and test files exist; commits 0f90952, 0060eda, 8b44e49 are ancestors of HEAD.
