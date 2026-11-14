---
phase: 04-infrastructure-and-ci-cd
plan: 03
subsystem: infra
tags: [pydantic-settings, chat-adapter, deploy-env, hexagonal, recording-adapter, smoke]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-02 McpSettings.deploy_env fail-closed rules (AUTH_MODE=off only with DEPLOY_ENV=local, local refused under K_SERVICE)"
  - phase: 03-google-chat-bot
    provides: "ChatApi port, GoogleChatApi, BotService, BotSettings, cli composition root"
provides:
  - "RecordingChatApi: second adapter of the ChatApi port, appends create and update calls as JSON lines to a file, no Google API call"
  - "BotSettings.deploy_env (DEPLOY_ENV, default production), chat_api (CHAT_API google|recording), chat_record_path (CHAT_RECORD_PATH)"
  - "Bot-side fail-closed guards: MCP_AUTH=none and CHAT_API=recording need DEPLOY_ENV=local; local refused when K_SERVICE is set"
  - "cli._build_chat_api selects the adapter from settings; startup log line carries the chat api mode"
affects: [04-06, 04-07, 04-08]

actuals:
  tokens: 7200
  tasks: 3
  commits: 3
plan_head_before: 93bbbacb9cfd7ce644a8a36e12683748d5d21b24
plan_head_after: 3620f22b34ae1b8b8af6d573b773b978645bafc0

tech-stack:
  added: []
  patterns:
    - "Config-selected adapter behind an existing port, chosen only in the composition root"
    - "Same explicit deploy marker on bot and server: default production, local unlocks local-only knobs, K_SERVICE forces production"

key-files:
  created: []
  modified:
    - services/chat_bot/buddy_bot/chat_api.py
    - services/chat_bot/buddy_bot/config.py
    - services/chat_bot/buddy_bot/cli.py
    - services/chat_bot/README.md
    - tests/unit/chat_bot/test_chat_api.py
    - tests/unit/chat_bot/test_config.py
    - tests/unit/chat_bot/test_main.py
    - tests/unit/chat_bot/conftest.py
    - tests/unit/chat_bot/test_llm_client.py
    - tests/integration/test_bot_process.py
    - docker-compose.dev.yml

key-decisions:
  - "The bot mirrors the server rule: DEPLOY_ENV defaults to production; MCP_AUTH=none and CHAT_API=recording are accepted only with an explicit DEPLOY_ENV=local; DEPLOY_ENV=local is refused whenever K_SERVICE is set"
  - "RecordingChatApi writes one fixed shape per line (op, name, space, thread, text, cards_v2); update lines carry space and thread as null so a smoke can parse every line the same way"
  - "CHAT_API and CHAT_RECORD_PATH stay out of .env.example (smoke-only knobs); documented in the bot README and set by compose and kind only"

patterns-established:
  - "Invariant test: every DEPLOY_ENV value except local refuses the local-only knobs, with and without K_SERVICE"
  - "Startup log names modes only (chat api google|recording), never the record path"

requirements-completed: [INFRA-02, INFRA-01]

coverage:
  - id: D1
    description: "With CHAT_API=recording the DM fixture event goes through the real BotService and leaves a create (placeholder) then an update whose text holds the answer and its Fonte line, with no Google Chat call"
    requirement: "INFRA-02"
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_recording_round_trip_of_the_dm_fixture_through_bot_service"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_recording_create_message_returns_a_name_under_the_space_and_records_it"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_recording_update_message_records_name_text_and_cards"
        status: pass
    human_judgment: false
  - id: D2
    description: "RecordingChatApi appends in UTF-8, never creates directories, and surfaces an OSError as ChatApiError naming only the exception type"
    requirement: "INFRA-02"
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_recording_missing_parent_directory_is_a_chat_api_error_naming_the_type"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_chat_api.py#test_recording_appends_to_an_existing_file"
        status: pass
    human_judgment: false
  - id: D3
    description: "BotSettings deploy_env, chat_api and chat_record_path fail closed: auth-none and recording need DEPLOY_ENV=local, recording needs CHAT_RECORD_PATH, local is refused under K_SERVICE; refusals name variables only"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_every_value_but_local_refuses_the_local_only_knobs"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_deploy_env_local_is_refused_when_k_service_is_set"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_chat_api_recording_without_a_record_path_is_refused"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_refused_configurations_exit_one_with_one_safe_line"
        status: pass
    human_judgment: false
  - id: D4
    description: "python -m buddy_bot builds GoogleChatApi by default and RecordingChatApi for CHAT_API=recording without ever building the Google Chat client"
    requirement: "INFRA-02"
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_google_chat_api_is_the_default_adapter"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_recording_chat_api_is_wired_and_google_is_never_built"
        status: pass
    human_judgment: false
  - id: D5
    description: "Bot README documents DEPLOY_ENV, CHAT_API and CHAT_RECORD_PATH (README contract covers every BotSettings field); real bot process still starts and drops strangers with DEPLOY_ENV=local"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_readme_contract.py"
        status: pass
      - kind: integration
        ref: "./run-unit-tests.sh --emulator (tests/integration/test_bot_process.py with DEPLOY_ENV=local)"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 03: Bot Deploy Marker and Recording Chat Adapter Summary

**The bot now fails closed on every host through an explicit `DEPLOY_ENV` marker (mirroring the MCP server), and a config-selected `RecordingChatApi` behind the existing `ChatApi` port lets compose and kind prove a chat round trip through the real composition root with no Google Chat call.**

## Performance

- **Duration:** about 5 min
- **Started:** 2026-11-14T11:48:02Z
- **Completed:** 2026-11-14T11:53Z
- **Tasks:** 3 of 3
- **Files modified:** 11 (3 source, 7 test, 1 compose comment) plus the bot README

## Accomplishments

- Tracer: the legacy DM fixture event handled by the real `BotService` over the real MCP server fixtures leaves exactly two JSON lines, a create (placeholder) then an update whose text holds the answer and `Fonte: Manuale`. Record names are deterministic (`<space>/messages/rec-N`).
- `BotSettings` gained `deploy_env`, `chat_api` and `chat_record_path`. `MCP_AUTH=none` and `CHAT_API=recording` are accepted only with an explicit `DEPLOY_ENV=local`; `DEPLOY_ENV=local` is refused whenever `K_SERVICE` is set; `CHAT_API=recording` needs `CHAT_RECORD_PATH`. Messages name variables only (closes audit warning 4 for the bot).
- `cli._build_chat_api` picks `RecordingChatApi(path)` or `GoogleChatApi(build_chat_client)`; nothing else in the composition root changed. A test proves `build_chat_client` is never called in recording mode.
- README rows for the three variables; the `MCP_AUTH` row now states the `DEPLOY_ENV` rule. `./run-unit-tests.sh --all` (1099 passed, 26 skipped, coverage 97.55%, ruff and mypy clean) and `--emulator` (12 passed, real bot process with `DEPLOY_ENV=local`) are green.

## Task Commits

1. **Task 1: Tracer, RecordingChatApi and the DM round trip** - `dfd0e2c` (feat)
2. **Task 2: DEPLOY_ENV, CHAT_API, CHAT_RECORD_PATH guards and cli selection** - `488d551` (feat)
3. **Task 3: README documents the new settings** - `3620f22` (docs)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

_Note: tests and implementation for Tasks 1 and 2 were written in one pass and committed as one test-plus-code commit each; a RED run was not observed before the implementation existed, so the `tdd="true"` RED gate is not evidenced for these two tasks._

## Files Created/Modified

- `services/chat_bot/buddy_bot/chat_api.py` - `RecordingChatApi` (JSON lines, UTF-8 append, `ChatApiError(type name)` on `OSError`)
- `services/chat_bot/buddy_bot/config.py` - three settings and the new guards replacing the K_SERVICE-only branch
- `services/chat_bot/buddy_bot/cli.py` - `_build_chat_api`, chat api mode in the startup line
- `services/chat_bot/README.md` - DEPLOY_ENV, CHAT_API, CHAT_RECORD_PATH rows; MCP_AUTH wording; compose variable list
- `tests/unit/chat_bot/test_chat_api.py`, `test_config.py`, `test_main.py`, `test_llm_client.py`, `conftest.py`, `tests/integration/test_bot_process.py` - new tests, cleanup lists, `DEPLOY_ENV=local` wherever `MCP_AUTH=none` is used
- `docker-compose.dev.yml` - stale comment ("the bot ignores this until 04-03") replaced; no behavior change

## Decisions Made

- The bot copies the server rule exactly, so one `DEPLOY_ENV` vocabulary covers both images and 04-06, 04-07 and 04-08 set it the same way (unset outside local).
- Record lines have one fixed key set. `update_message` has no space or thread in the port, so those keys are `null` on update lines rather than absent.
- Guards raise in order (K_SERVICE, MCP_AUTH, CHAT_API, then the required-variable checks), so an environment with several mistakes reports one at a time; each message still names its variables.
- `CHAT_API` and `CHAT_RECORD_PATH` are not added to `.env.example` (flagged assumption in the plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `make_service` typed `chat: FakeChatApi | None`**
- **Found during:** Task 1
- **Issue:** the tracer test passes a `RecordingChatApi` into the shared `make_service` fixture; mypy would reject it.
- **Fix:** widened the parameter to the `ChatApi` port type.
- **Files modified:** tests/unit/chat_bot/conftest.py (already in the plan's file list)
- **Verification:** `./run-unit-tests.sh --all` (mypy clean)
- **Committed in:** dfd0e2c

**2. [Rule 3 - Blocking] Stale compose comment**
- **Found during:** Task 2
- **Issue:** `docker-compose.dev.yml` said the bot ignores `DEPLOY_ENV` until 04-03; after this plan that is false.
- **Fix:** comment rewritten; the `DEPLOY_ENV: local` line (pinned by `test_dev_compose.py`) is unchanged.
- **Files modified:** docker-compose.dev.yml (not in the plan's file list)
- **Verification:** `test_dev_compose.py` 16 passed
- **Committed in:** 488d551

**3. [Rule 3 - Blocking] Existing tests relied on the old guard message**
- The startup log assertion in `test_main.py` and the K_SERVICE cases in `test_config.py` and `test_main.py` were rewritten for the new messages (planned in the task action); one added `test_main.py` refusal case needed `MCP_AUTH=google_id_token` so the recording guard, not the MCP_AUTH guard, was the first to fire.

---

**Total deviations:** 3 (all Rule 3). **Impact on plan:** none on scope; all needed to keep the suite green.

## Issues Encountered

- The working tree held uncommitted edits to many `.planning/`, `docs/` and `jobs/sync/README.md` files that this plan did not make (they appeared while the plan ran, an apparent concurrent edit by another process). They were left untouched and never staged; every commit of this plan lists its files explicitly.

## Known Stubs

None.

## Threat Flags

None. The new surface (a local file write) is the plan's accepted T-04-11 and is refused outside `DEPLOY_ENV=local`. The Cloud Run YAML assertion that `CHAT_API` is absent or `google` (T-04-10 second half) belongs to 04-08.

## User Setup Required

None - no external service configuration required. A developer who runs the bot by hand with `MCP_AUTH=none` must now also set `DEPLOY_ENV=local`; the dev compose stack sets it already.

## Next Phase Readiness

- 04-06 (compose) and 04-07 (kind) can set `DEPLOY_ENV=local`, `CHAT_API=recording` and `CHAT_RECORD_PATH=<container-local path>` on the bot and read the final JSON line for the round-trip assertion; the parent directory of the path must exist.
- 04-08 (Cloud Run) must leave `DEPLOY_ENV` unset and `CHAT_API` absent or `google`, and assert that in its YAML test.

## Self-Check: PASSED

Source and test files listed above exist; commits dfd0e2c, 488d551, 3620f22 are ancestors of HEAD (`git rev-list --count` from the ledger base = 3); acceptance greps (RecordingChatApi 1, recording tests 5, deploy_env 4, chat_api 3, cli RecordingChatApi 2, DEPLOY_ENV in integration test 1, README CHAT_RECORD_PATH 2 and DEPLOY_ENV 4) meet their thresholds; `./run-unit-tests.sh --all` and `--emulator` exit 0.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
