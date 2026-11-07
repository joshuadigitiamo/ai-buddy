---
phase: 03-google-chat-bot
plan: 07
subsystem: bot-thread-memory
status: complete
tags: [firestore, hmac, privacy, thread-memory, ports-and-adapters, tdd, tracer]

requires:
  - phase: 03-google-chat-bot (03-03)
    provides: "ports.ThreadMemory (recent/append) and ports.Turn"
  - phase: 03-google-chat-bot (03-06)
    provides: "BotSettings.thread_key_secret (>= 32 chars), memory_turns, memory_collection"
provides:
  - "memory.thread_key(secret, key_source): HMAC-SHA256 over UTF-8 bytes, lowercase hex"
  - "memory.memory_document(turns, *, now): the exact stored document, keys turns, updated_at, expire_at"
  - "memory.FirestoreThreadMemory(client_factory, *, secret, collection, max_turns, clock=utc_now): lazy client"
  - "memory.InMemoryThreadMemory(*, secret, max_turns, clock=utc_now) with .documents for assertions"
  - "memory.MEMORY_TTL (24 h), MAX_QUESTION_CHARS (2000), MAX_ANSWER_CHARS (4000)"
  - "Public helpers live_turns, next_document, utc_now shared by both adapters"
affects: [03-11]

actuals:
  tokens: 4500
  tasks: 2
  commits: 3
plan_head_before: a4ddffc965eefab3af6a79a56338f9d636829d22
commits: 3
plan_head_after: fd9573368c129b4cf6e253c8bc66e089832653d5

tech-stack:
  added: []
  patterns:
    - "Ports and adapters: Firestore adapter and in-memory twin implement ThreadMemory and share module-level rules (no duplicated logic)"
    - "Lazy Firestore client built on the first call, inside the running event loop (pattern of FirestoreGapLog)"
    - "Document shape as a function (memory_document) so tests assert the exact key set"
    - "Read-side expiry check so the 24 h guarantee does not depend on the Firestore TTL policy"

key-files:
  created:
    - services/chat_bot/buddy_bot/memory.py
    - tests/unit/chat_bot/test_memory.py
    - tests/integration/test_firestore_thread_memory.py
  modified: []

key-decisions:
  - "The caller supplies the key source (DM space name or room thread name, per 03-01 memory_key 3b); the adapter only hashes it, so the HMAC rule lives in one place and the choice stays in the service (03-11)"
  - "Expiry is 'expire_at <= now' reads as empty (boundary inclusive); every append refreshes updated_at and expire_at, so the 24 h window slides with the last write"
  - "A missing, malformed or non-datetime expire_at reads as empty instead of raising: stored data can never break a run"
  - "max_turns below 1 raises ValueError at construction; recent(key, n<=0) returns [] (a bare turns[-0:] would return everything)"
  - "No validation of the secret inside memory.py: the 32-character floor is enforced once, by BotSettings (03-06)"

requirements-completed: [BOT-11]

coverage:
  - id: D1
    description: "On the Firestore emulator a turn round-trips; the document id is the HMAC hex of the key source; the document has exactly turns, updated_at, expire_at; each turn has exactly q and a; expire_at - updated_at is 24 h; no identity-like key; the raw space name appears in no stored value"
    requirement: BOT-11
    verification:
      - kind: integration
        ref: "tests/integration/test_firestore_thread_memory.py#test_turns_round_trip_under_hmac_key_with_only_three_fields"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only the last max_turns turns are kept, on the emulator and offline; recent(n) returns at most n turns oldest first"
    requirement: BOT-11
    verification:
      - kind: integration
        ref: "tests/integration/test_firestore_thread_memory.py#test_only_the_last_max_turns_are_kept"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_in_memory_keeps_the_last_max_turns_oldest_first"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_firestore_keeps_the_last_max_turns_and_ignores_an_expired_document"
        status: pass
    human_judgment: false
  - id: D3
    description: "A document whose expire_at has passed reads as empty before Firestore TTL deletes it, and the next append starts a fresh list; an append refreshes the window"
    requirement: BOT-11
    verification:
      - kind: integration
        ref: "tests/integration/test_firestore_thread_memory.py#test_an_expired_document_reads_empty"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_in_memory_reads_empty_after_expiry_and_append_starts_fresh"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_append_refreshes_the_expiry_window"
        status: pass
    human_judgment: false
  - id: D4
    description: "The key is HMAC-SHA256 over the UTF-8 bytes of the source, hex encoded; different sources and secrets give different ids; a blank source makes recent return [] and append do nothing (no client call)"
    requirement: BOT-11
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_thread_key_hashes_the_utf8_bytes_of_the_source"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_thread_key_is_64_lowercase_hex_and_depends_on_source_and_secret"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_blank_key_source_reads_empty_and_stores_nothing"
        status: pass
    human_judgment: false
  - id: D5
    description: "Question and answer text are truncated to 2000 and 4000 characters; the Firestore client is created on the first call only; naive clocks are rejected"
    requirement: BOT-11
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_question_and_answer_are_stored_truncated"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_firestore_client_is_created_on_the_first_call_only"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_memory.py#test_a_naive_clock_is_rejected"
        status: pass
    human_judgment: false
  - id: D6
    description: "Concurrent runs in one conversation may lose one turn (last write wins); accepted for the single-user scope (backstop truth, T-03-21)"
    requirement: BOT-11
    verification: []
    human_judgment: true
    rationale: "Accepted limitation by design; no test asserts a race. It can only drop history, never store an identifier."
---

# Phase 3 Plan 07: Thread Memory Summary

**Thread memory behind the ThreadMemory port: one Firestore document per conversation, keyed by HMAC-SHA256 of the DM space or thread name, holding only the last N Q/A pairs under the exact keys turns, updated_at and expire_at, read as empty after 24 h.**

## Performance

- **Duration:** about 4 min of execution after context load
- **Started:** 2026-11-07T11:50:31Z
- **Completed:** 2026-11-07T11:54:21Z (code); SUMMARY committed after
- **Tasks:** 2 (1 tracer, 1 TDD)
- **Files created:** 3

## Accomplishments

- `memory.py`: `thread_key`, `memory_document`, `FirestoreThreadMemory` and `InMemoryThreadMemory`. Both adapters share `live_turns`, `next_document` and the cap logic; there is no duplicated rule.
- The stored document cannot hold an identifier: its shape is produced only by `memory_document` (three keys; turns carry `q` and `a`), and the id is a keyed hash.
- Emulator test asserts the exact key set, the HMAC id, no identity-like key (`IDENTITY_KEY` regex), the raw space name absent from every stored value, a 24 h expiry span, the N-turn cap and the read-side expiry.
- Offline test (14 tests) covers the Firestore adapter against a fake async client, so `--all` exercises it without the emulator.

## Task Commits

1. **Task 1 (tracer): HMAC-keyed Firestore round trip** - `eaf2d81` (feat)
2. **Task 2 RED: failing tests for the in-memory twin and offline rules** - `7d97bb7` (test)
3. **Task 2 GREEN: InMemoryThreadMemory** - `fd95733` (feat)

No REFACTOR commit: the only cleanup (importing the twin directly and ruff formatting the test file) was folded into the GREEN commit. The tracer feedback gate passed: `./run-unit-tests.sh --emulator` ran green (3 thread-memory tests, none skipped) before Task 2 started.

## TDD Gate Compliance

- **RED:** `test(03-07)` commit `7d97bb7`. 14 tests, 7 failed, 7 passed. The 7 failing tests (in-memory cap, expiry, append refresh, text caps, blank key, naive clock, `max_turns` rejection) failed with `AttributeError: module 'buddy_bot.memory' has no attribute 'InMemoryThreadMemory'`. The test module referenced the twin as `memory.InMemoryThreadMemory` so the missing class failed each test at call time instead of as a collection error. The 7 passing tests cover behavior the Task 1 tracer already delivered (key, lazy client, three-key document, malformed documents); they are characterization tests, not new behavior.
- **RED evidence:** JUnit XML from `pytest --junitxml`, record validated with `gsd_run check tdd-red-evidence`: `RED_EVIDENCE_OK`, reason `target_test_failed`, target `test_in_memory_keeps_the_last_max_turns_oldest_first`. `semanticAssessment`: the target executed and failed because the feature was absent (the intended reason), not on a syntax, import or fixture fault. The failure is an `AttributeError` on the missing class rather than an `assert` mismatch.
- **GREEN:** `feat(03-07)` commit `fd95733`, 14 of 14 pass.
- **REFACTOR:** none.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test file failed `ruff format --check` in the `--all` gate**
- **Found during:** Task 2 GREEN verification
- **Issue:** the RED test file used `# fmt: skip` and a string return annotation (a RED-only workaround to avoid an import error); `ruff format --check` rejected it
- **Fix:** imported `InMemoryThreadMemory` directly once it existed, dropped the `fmt: skip`, ran `ruff format`
- **Files modified:** `tests/unit/chat_bot/test_memory.py`
- **Commit:** `fd95733`

**Total deviations:** 1 auto-fixed (1 blocking). **Impact:** none on behavior; the plan's `--all` gate is green.

### Plan wording note

The plan's Task 2 verify says "fewer than 9 tests in the passed count" fails; the file has 14 tests, all passing. The acceptance grep `grep -c 'def test_'` returns 14 (needs at least 8).

## Issues Encountered

None.

## Verification

- `./run-unit-tests.sh --single-file test_memory.py tests/unit/chat_bot`: 14 passed.
- `./run-unit-tests.sh --emulator`: 7 passed (including 3 from `test_firestore_thread_memory.py`, none skipped).
- `./run-unit-tests.sh --all`: ruff, ruff format, mypy --strict (111 files) and pytest clean; 790 passed, 21 skipped; coverage 97.18% (gate 80%); `memory.py` 99% (only `utc_now`'s body, the default clock, is not run offline).
- Acceptance greps: `def thread_key` 1, `hours=24` 1, `pytest.mark.firestore` 1, `class InMemoryThreadMemory` 1, `def test_` 14, identity-literal grep on `memory.py` 0.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path or file access; the only trust-boundary surface (conversation text at rest, the HMAC secret) is T-03-19 and T-03-20 in the plan's threat model, mitigated as planned.

## Hand-off notes

- **03-11 (composition root):** build `FirestoreThreadMemory(factory, secret=settings.thread_key_secret.get_secret_value(), collection=settings.memory_collection, max_turns=settings.memory_turns)` and pass the key source per 03-01 memory_key 3b: the space name for a DM space, the thread name for a room. The adapter never inspects the source beyond blank.
- **Phase 4:** apply the Firestore TTL policy: `gcloud firestore fields ttls update expire_at --collection-group=<MEMORY_COLLECTION> --enable-ttl`. Until then the read-side check is the only enforcement and expired documents stay at rest. Record the D-11 privacy re-check in the rollout checklist before a second user.
- The emulator does not enforce TTL; the expired-document test relies on the read-side check by design.

## Self-Check: PASSED

- FOUND: services/chat_bot/buddy_bot/memory.py, tests/unit/chat_bot/test_memory.py, tests/integration/test_firestore_thread_memory.py
- FOUND commits: eaf2d81, 7d97bb7, fd95733 (ancestors of HEAD)
