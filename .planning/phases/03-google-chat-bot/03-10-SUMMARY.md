---
phase: 03-google-chat-bot
plan: 10
subsystem: bot-intake
tags: [google-chat, pubsub, http, jwt, chat-api, gapic, emulator, tdd]

requires:
  - phase: 03-google-chat-bot (03-01)
    provides: "http_ack decision (b): await the run up to 25 s, then return {}; approved pins google-cloud-pubsub 2.43.0 and google-apps-chat 0.10.9"
  - phase: 03-google-chat-bot (03-03)
    provides: "IntakePort and ChatApi ports, FakeLlm/FakeChatApi/RecordingConnector fixtures"
  - phase: 03-google-chat-bot (03-08)
    provides: "render.py cardsV2 REST JSON (converted to GAPIC here)"
  - phase: 03-google-chat-bot (03-09)
    provides: "BotService.handle (never raises, message-name dedupe, allowlist)"
provides:
  - "intake.pubsub.PubSubIntake(subscription, *, subscriber_factory=SubscriberClient, max_messages=2) and make_callback(handler, loop)"
  - "intake.http.ChatTokenVerifier(audience, issuer_email, *, request=None).verify(token) (async), build_http_app(handler, verifier, *, ack_seconds, max_body_bytes), HttpIntake(verifier, *, host, port, ack_seconds=ACK_SECONDS) with uvicorn_config(handler), ACK_SECONDS=25.0, MAX_BODY_BYTES=1_048_576"
  - "chat_api.GoogleChatApi(client_factory), build_chat_client(), ChatApiError, ChatClient protocol, CHAT_BOT_SCOPE"
  - "docker-compose.test.yml pubsub service; ./run-unit-tests.sh --emulator runs firestore or pubsub tests; pytest marker pubsub"
affects: [03-11, 03-12]

actuals:
  tokens: 12305
  tasks: 3
  commits: 6
plan_head_before: 2f55bac3d9b9c7f41c128a2a680af090bf6f3c87
commits: 6
plan_head_after: bb6cd94f892e75385ee83c647339d82857943dec

tech-stack:
  added: []
  patterns:
    - "Streaming-pull callback blocks its worker thread on run_coroutine_threadsafe(...).result(), acks in finally"
    - "HTTP intake keeps handler tasks in a set on app.state with done-callback discard; asyncio.wait with timeout is the ack window"
    - "Real google-auth verify_oauth2_token exercised through a fake Request that serves a locally generated key as Google's cert map"
    - "Chat REST JSON converted to GAPIC through the Message protobuf (ParseDict) behind a ChatClient protocol"

key-files:
  created:
    - services/chat_bot/buddy_bot/intake/__init__.py
    - services/chat_bot/buddy_bot/intake/pubsub.py
    - services/chat_bot/buddy_bot/intake/http.py
    - services/chat_bot/buddy_bot/chat_api.py
    - tests/integration/test_pubsub_intake.py
    - tests/unit/chat_bot/test_pubsub_intake_unit.py
    - tests/unit/chat_bot/test_http_intake.py
    - tests/unit/chat_bot/test_chat_api.py
  modified:
    - docker-compose.test.yml
    - run-unit-tests.sh
    - pyproject.toml

key-decisions:
  - "http_ack option (b) is implemented as ACK_SECONDS = 25.0 in build_http_app; ack_seconds 0 gives option (a). The D-09 amendment already in 03-CONTEXT.md is honoured, no new decision"
  - "ChatTokenVerifier refuses an empty audience at construction: google-auth skips the audience check when audience is None, so an unset CHAT_JWT_AUDIENCE must fail loudly, not open the endpoint"
  - "Rejections log one fixed line each (unauthorized, body too large, not a JSON object); no token, claim, e-mail or body text is ever logged"
  - "GoogleChatApi takes Callable[[], ChatClient] where ChatClient is a two-method protocol that ChatServiceAsyncClient satisfies, so tests use a plain fake and build_chat_client still plugs in unchanged"
  - "Chat API errors are re-raised with `from None` and the exception type name as the message, so no cause chain carries response text"

patterns-established:
  - "Intake adapters never import BotService; they receive only the EventHandler callable"
  - "Integration tests reuse unit-conftest fixtures by import (noqa F401/F811), as the existing integration tests reuse unit helpers"

requirements-completed: [BOT-01, BOT-02, BOT-10]

coverage:
  - id: D1
    description: "A recorded Chat DM event published on the Pub/Sub emulator is pulled by PubSubIntake, handled by BotService and produces the placeholder then the answer update on the same message; the message is acked and not redelivered"
    requirement: BOT-01
    verification:
      - kind: integration
        ref: "tests/integration/test_pubsub_intake.py#test_dm_event_gets_placeholder_then_answer_and_is_acked"
        status: pass
    human_judgment: false
  - id: D2
    description: "Undecodable and non-object Pub/Sub payloads, and a raising handler, are acked and logged by type only, so a poison message cannot loop"
    requirement: BOT-01
    verification:
      - kind: integration
        ref: "tests/integration/test_pubsub_intake.py#test_undecodable_message_is_acked_and_makes_no_call"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_pubsub_intake_unit.py#test_undecodable_or_non_object_payload_is_acked_without_calling_the_handler"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_pubsub_intake_unit.py#test_a_raising_handler_still_acks_and_logs_the_type_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "HTTP intake accepts POST / only with a Google ID token whose signature, issuer, expiry, exact aud and e-mail verify; missing, non-Bearer, empty, wrong-audience (trailing slash), expired, wrong-issuer, other-account, unverified-e-mail and wrong-key tokens get 401 with empty body and never reach the handler"
    requirement: BOT-02
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_valid_token_returns_empty_object_and_hands_the_event_over"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_missing_or_malformed_authorization_is_401_with_empty_body"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_token_failing_a_check_is_401"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_token_signed_by_another_key_is_401"
        status: pass
    human_judgment: false
  - id: D4
    description: "Empty, non-JSON and non-object bodies return 400, bodies over 1 MiB (declared or streamed) return 413, GET returns 405; the handler is not called in any of these cases"
    requirement: BOT-02
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_verified_request_with_unusable_body_is_400"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_declared_oversized_body_is_413"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_streamed_oversized_body_is_413"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_get_is_405"
        status: pass
    human_judgment: false
  - id: D5
    description: "The endpoint awaits the run up to the ack window then returns {} while a slower run continues in a referenced task; ack_seconds 0 returns at once; uvicorn runs with access logging off and stops cleanly on cancel"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_slow_run_is_acked_after_the_window_and_still_completes"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_ack_window_zero_returns_at_once"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_http_intake_turns_access_logging_off"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_http_intake_serves_over_a_real_socket_and_stops_on_cancel"
        status: pass
    human_judgment: false
  - id: D6
    description: "Concurrent events are handled independently with no ordering between distinct events (backstop; duplicates are absorbed by the service dedupe from 03-09)"
    requirement: BOT-02
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_http_intake.py#test_concurrent_events_are_handled_independently"
        status: pass
    human_judgment: false
  - id: D7
    description: "GoogleChatApi creates the placeholder in the event thread with REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD, patches the same message with mask text and cards_v2 from render's REST JSON, builds its client lazily, and reports Google errors by type only"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_create_message_replies_in_the_event_thread"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_update_message_sends_text_and_the_video_card_with_the_field_mask"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_google_api_errors_become_chat_api_error_naming_only_the_type"
        status: pass
    human_judgment: false
  - id: D8
    description: "The mask names text and cards_v2, and the real Chat API accepts them and renders the card, are only confirmed against the live API (RESEARCH A5); the Pub/Sub topic IAM that authenticates events (T-03-26) is a deployment setting"
    requirement: BOT-10
    verification: []
    human_judgment: true
    rationale: "Needs the live Chat app and topic IAM, covered by the 03-12 live checkpoint; offline tests only prove the request shape"

duration: "about 12 min"
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 10: Pub/Sub intake, HTTP intake with Google JWT checks, Chat API adapter Summary

**Both transports now feed the same `BotService.handle`: a Pub/Sub streaming-pull adapter (proven on the emulator, ack-always), a Starlette HTTP adapter that accepts only Google-signed Chat requests for its own audience and e-mail and holds the request open up to 25 s, and a Chat API adapter that posts the placeholder in the event thread and patches it with text and the converted video card.**

## Performance

- **Duration:** about 12 min (start estimated from the 03-09 close-out at 12:10Z; end 12:22Z)
- **Tasks:** 3 (1 tracer, 2 TDD)
- **Files:** 11 (8 created, 3 modified)
- **Commits:** 6 code commits

## RED / GREEN / REFACTOR

Task 1 was a tracer: its test and code share one commit (`a531d64`), proven end to end on the emulator (2 integration tests).

**Task 2 (HTTP intake)**
- RED (`43a1903`): `test_http_intake.py` (32 tests) plus a skeleton `http.py` (right names, 404 on every route, `verify` returns False). Run result: 30 failed on status-code and behavior assertions (`assert 404 == 200`, `AttributeError: 'HttpIntake' ... no attribute 'uvicorn_config'`), 2 passed vacuously (the constants test and the log-content test). Semantic assessment: the target tests executed and failed on the planned assertions; no import, collection or fixture fault.
- GREEN (`780b0aa`): `http.py` implemented; 32 passed. Required changing the test `AUDIENCE` to a value without a trailing slash so the "audience plus trailing slash" case is really that case.
- REFACTOR: none.

**Task 3 (Chat API adapter)**
- RED (`e6824b1`): `test_chat_api.py` (9 tests) plus a skeleton `chat_api.py`. Run result: 9 failed (empty return values, `IndexError` on unrecorded calls, `DID NOT RAISE`, and one `AttributeError` for the not-yet-imported `google` module in the build-client test). Semantic assessment: eight failed on planned behavior; the build-client test failed on the missing import in the stub, which is a stub artifact rather than a wrong assertion.
- GREEN (`e7cc1c6`): `chat_api.py`; 9 passed.
- `test_pubsub_intake_unit.py` (11 tests, `bb6cd94`) pins the Task 1 adapter and passed on first run, so it has no RED phase: the adapter already existed, and the plan's behavior list matched it with no gap found.
- REFACTOR: none.

`gsd_run check tdd-red-evidence` was not run: it has no pytest adapter and this plan is `type: execute` with `tdd="true"` tasks, not `type: tdd`.

## Accomplishments

- Pub/Sub: DM event from the recorded fixture published on the emulator yields one placeholder then one update on that message containing `handbook://02-ferie`; a final pull returns nothing. `b"not json"` is acked with no Chat call. Lease extension while the callback blocks (A9) held for the emulator run.
- HTTP: real `verify_oauth2_token` runs against a fake `Request` serving the test key as the cert map, so signature, issuer and expiry are checked by google-auth itself; audience and e-mail are checked here. 401 bodies are empty, nothing is logged from the token.
- Ack window: `ACK_SECONDS = 25.0`; the run continues in a referenced task after the early `{}`.
- Chat API: REST cardsV2 from `render_reply` converts through `Message.pb`/`ParseDict` and `Message.wrap`; the test reads back `card_id == "video-sources"` and both button URLs.
- Full gate: `./run-unit-tests.sh --all` exit 0, 893 passed, 23 skipped (emulator-only), coverage 98.05%, `http.py`, `chat_api.py` 100%, `pubsub.py` 100%. `./run-unit-tests.sh --emulator`: 9 passed (7 earlier plus 2 new).

## Task Commits

1. **Task 1 (tracer): Pub/Sub emulator end to end** - `a531d64` (feat)
2. **Task 2: HTTP intake** - `43a1903` (test, RED), `780b0aa` (feat, GREEN)
3. **Task 3: Chat API adapter and Pub/Sub offline tests** - `e6824b1` (test, RED), `e7cc1c6` (feat, GREEN), `bb6cd94` (test, adapter coverage)

**Plan metadata:** the docs commit with this SUMMARY, STATE.md, ROADMAP.md, REQUIREMENTS.md.

## Files Created/Modified

- `services/chat_bot/buddy_bot/intake/pubsub.py` - streaming-pull adapter, `make_callback`
- `services/chat_bot/buddy_bot/intake/http.py` - JWT verifier, Starlette app, uvicorn runner
- `services/chat_bot/buddy_bot/chat_api.py` - Chat API adapter, `ChatClient` protocol, `build_chat_client`
- `docker-compose.test.yml`, `run-unit-tests.sh`, `pyproject.toml` - pubsub emulator, `--emulator` runs `firestore or pubsub`, marker, two narrow mypy overrides
- Four test files (see key-files)

## Decisions Made

See key-decisions. Honoured from 03-01: http_ack (b). No pin was added or changed; the emulator image reuses `google/cloud-sdk:592.0.0-emulators`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy needs two narrow overrides for untyped Google modules**
- **Found during:** Tasks 1 and 3
- **Issue:** `google.cloud.pubsub_v1` and `google.protobuf` ship no `py.typed` marker/stubs, so `mypy --strict` failed with import-untyped
- **Fix:** two `[[tool.mypy.overrides]]` blocks, each `ignore_missing_imports` for the exact module, as the plan allows; `verify_oauth2_token` (unannotated in google-auth) uses one inline `# type: ignore[no-untyped-call]`
- **Files modified:** pyproject.toml, services/chat_bot/buddy_bot/intake/http.py
- **Commits:** a531d64, e7cc1c6, 780b0aa

**2. [Rule 2 - Missing critical] Empty audience would disable the audience check**
- **Found during:** Task 2
- **Issue:** `verify_oauth2_token(audience=None)` skips the audience check; an unset `CHAT_JWT_AUDIENCE` would silently accept any Google token with the right e-mail (T-03-25)
- **Fix:** `ChatTokenVerifier` raises ValueError for an empty audience; covered by `test_verifier_without_audience_is_refused`
- **Commit:** 780b0aa

**3. [Rule 3 - Blocking] Integration test cannot see unit-conftest fixtures**
- **Found during:** Task 1
- **Issue:** `make_service` and its dependencies live in `tests/unit/chat_bot/conftest.py`; the emulator run failed with `fixture 'make_service' not found`
- **Fix:** the test imports the five fixtures by name with `# noqa: F401`/`F811`, the same reuse pattern `test_server_process.py` uses for unit helpers
- **Commit:** a531d64

**4. [Rule 1 - Bug] mypy rejected `run_coroutine_threadsafe(handler(event), ...)`**
- **Found during:** Task 1
- **Issue:** `EventHandler` returns `Awaitable[None]`, but `run_coroutine_threadsafe` requires a coroutine
- **Fix:** a small inner `async def run_handler()` awaits the handler; the grep acceptance count (1) still holds
- **Commit:** a531d64

### Additions beyond the plan text (no behavior contradicting it)

- `HttpIntake.uvicorn_config(handler)` is public so a unit test can assert `access_log is False`; `HttpIntake.run` stops uvicorn gracefully on cancel (sets `should_exit`, awaits the server) so the port is released, covered by a real-socket test.
- `ChatClient` protocol in `chat_api.py` so the adapter's factory type accepts both the real GAPIC client and a test fake.

**Total deviations:** 4 auto-fixed (2 Rule 3, 1 Rule 2, 1 Rule 1). **Impact:** none on scope; all inside the planned files.

## Authentication Gates

None.

## Issues Encountered

- `verify_oauth2_token` does not cache Google's certificates: every Chat request fetches them (RESEARCH said google-auth caches them; the source of `id_token._fetch_certs` shows no cache). Acceptable for one user. If latency matters, 03-11 can pass a `request` object that caches the certs response; the plan did not ask for one, so none was added.

## Known Stubs

None. No placeholder data reaches any rendered output from these files.

## Threat Flags

None beyond the plan's threat model: `HttpIntake` binds a listening port (T-03-25/27/28 cover it).

## User Setup Required

None for this plan. Carried to 03-11/03-12: set `CHAT_JWT_AUDIENCE` (endpoint URL mode only) and `CHAT_JWT_ISSUER_EMAIL` (add-on service account `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`, or `chat@system.gserviceaccount.com` for non-add-on apps); restrict the Pub/Sub topic's publish IAM to the Chat service account (T-03-26); confirm the `text`/`cards_v2` mask against the live API (A5).

## Next Phase Readiness

- 03-11 wires: `PubSubIntake(subscription)` or `HttpIntake(ChatTokenVerifier(audience, issuer_email), host, port)` as the IntakePort chosen by `INTAKE`; `GoogleChatApi(build_chat_client)`; uvicorn access log is already off inside `HttpIntake`.
- `HttpIntake` passes `ACK_SECONDS` by default; 03-11 can expose it only if a setting is wanted.

## Self-Check: PASSED

- FOUND: services/chat_bot/buddy_bot/intake/__init__.py, intake/pubsub.py, intake/http.py, chat_api.py, tests/integration/test_pubsub_intake.py, tests/unit/chat_bot/test_pubsub_intake_unit.py, test_http_intake.py, test_chat_api.py
- FOUND commits a531d64, 43a1903, 780b0aa, e6824b1, e7cc1c6, bb6cd94 on HEAD (`git rev-list --count 2f55bac..HEAD` = 6)
- Acceptance criteria re-run: `pubsub` in docker-compose.test.yml 4 (>=3), `firestore or pubsub` in run-unit-tests.sh 1, `pubsub:` in pyproject.toml 1, `run_coroutine_threadsafe` in pubsub.py 1, `verify_oauth2_token` in http.py 1, `access_log=False` 1, `MAX_BODY_BYTES` 2, `REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD` 1, `ParseDict` 1, `chat.bot` 3; `git diff --quiet 7d772e2 -- services/mcp_server jobs/sync` exit 0.
- Verification: `--emulator` 9 passed incl. 2 pubsub tests; `--single-file` test_http_intake 32 passed, test_chat_api 9 passed, test_pubsub_intake_unit 11 passed; `--all` exit 0, 893 passed, coverage 98.05%.
