---
phase: 04-infrastructure-and-ci-cd
plan: 06
subsystem: infra
tags: [docker-compose, pubsub-emulator, firestore-emulator, stub-llm, smoke-test, meridian, profiles]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-02 DEPLOY_ENV=local, MCP_ALLOWED_HOSTS and /healthz on the MCP server"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-03 RecordingChatApi and the CHAT_API / CHAT_RECORD_PATH / DEPLOY_ENV bot settings"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-04 ARTIFACT_STORE local|gcs settings (README rows were left for this plan)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-05 sync image stage (uid 10001, /artifacts, git safe.directory)"
provides:
  - "docker-compose.yml: seven hermetic services (firestore, pubsub, pubsub-init, sync, mcp-server, stub-llm, chat-bot) plus profile live (meridian, chat-bot-live)"
  - "deploy/compose/stub_llm.py: Anthropic Messages stub that answers Reformulation, RetryPlan, ContactExtraction and AnswerDraft"
  - "scripts/compose-smoke.sh: offline Pub/Sub round trip that ends in a recorded answer with Fonte: Manuale and handbook://02-ferie"
  - "tests/unit/test_compose.py (24 tests) and tests/unit/test_stub_llm.py (15 cases, 10 test functions)"
affects: [04-07, 04-08, 04-09, 04-14]

actuals:
  tokens: 18169
  tasks: 3
  commits: 7
plan_head_before: 2014699d65a459c7d47a4ec3a4d1f0ff30c3ae21
plan_head_after: e63374bc56059452709451842e94b505ad7fa082

tech-stack:
  added: []
  patterns:
    - "Hermetic and live stacks differ only in adapters chosen by env (recording vs Google Chat, stub vs Meridian), selected by compose profile"
    - "Start order encoded as depends_on conditions: healthy emulators, completed one-shots, healthy server, then the bot"
    - "Long-syntax bind mounts for host paths a user may pass relative, so compose never reads them as named volumes"
    - "Stub server inspects the JSON schema title the real client appends to `system`, so it needs no model"

key-files:
  created:
    - docker-compose.yml
    - deploy/compose/stub_llm.py
    - scripts/compose-smoke.sh
    - tests/unit/test_compose.py
    - tests/unit/test_stub_llm.py
  modified:
    - pyproject.toml
    - .env.example
    - services/chat_bot/README.md
    - services/mcp_server/README.md
    - tests/unit/chat_bot/test_readme_contract.py
  deleted:
    - docker-compose.dev.yml
    - tests/unit/test_dev_compose.py

key-decisions:
  - "The Pub/Sub emulator REST surface works as assumed: PUT topics/chat-events and PUT subscriptions/chat-events from the emulator image (curl), and POST :publish, so no google-cloud-pubsub fallback was needed"
  - "Live-profile inputs cannot be compose-required: compose interpolates inactive-profile services, so ${VAR:?} there broke the default stack. MERIDIAN_API_KEY defaults to empty and BOT_SA_KEY_FILE to /dev/null, and chat-bot-live exits at once with a message when either is missing"
  - "Sync source folders use the long bind-mount syntax so a relative HANDBOOK_SRC_DIR (the plan's own verify uses one) is read as a path, never as a named volume"
  - "chat-bot depends on sync directly as well as through mcp-server, so a failed sync stops the bot even if the server's gate changes"
  - "The stub cites every <fonte id> in the user text; the gate accepts any id that is in the run's evidence"

patterns-established:
  - "Structural compose guard reads profiles from each service's `profiles` key and checks the default set is exactly the hermetic services"
  - "A compose smoke script owns its throwaway fixtures, a project name and a trap that runs `down -v`"

requirements-completed: [INFRA-02, INFRA-01]

coverage:
  - id: D1
    description: "docker compose up (no profile) starts firestore, pubsub, pubsub-init, sync, mcp-server, stub-llm and chat-bot from the per-service images, and a fixture chat event published to the Pub/Sub emulator returns a recorded final message with Fonte: Manuale and handbook://02-ferie"
    requirement: "INFRA-02"
    verification:
      - kind: integration
        ref: "scripts/compose-smoke.sh (exit 0, last log line 'round trip ok'; run three times, 35-52 s)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The smoke script exits non-zero with 'timeout after N s' when no cited final answer is recorded in time, and a failed sync keeps mcp-server and chat-bot from starting"
    requirement: "INFRA-02"
    verification:
      - kind: integration
        ref: "SMOKE_TIMEOUT_SECONDS=1 scripts/compose-smoke.sh (rc 1, 'timeout after 1 s'); compose up over an empty handbook folder (sync exit 1, chat-bot and mcp-server state created, never started)"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_start_order_is_fixed_by_depends_on_conditions"
        status: pass
    human_judgment: false
  - id: D3
    description: "The hermetic stack cannot reach a real service: default services have no env_file, no credentials, project demo-ai-buddy, CHAT_API=recording, the stub LLM and both emulators; no service publishes a port or shares a network namespace; every key ending _KEY/_SECRET/_TOKEN is a ${...} interpolation; mcp-server receives no bot secret"
    requirement: "INFRA-02"
    verification:
      - kind: unit
        ref: "tests/unit/test_compose.py#test_hermetic_chat_bot_cannot_reach_a_real_service"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_no_hermetic_service_carries_credentials_or_a_real_project"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_no_service_publishes_a_port_or_shares_a_network_namespace"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_secret_looking_environment_values_are_interpolations"
        status: pass
    human_judgment: false
  - id: D4
    description: "Profile live (meridian, chat-bot-live) replaces docker-compose.dev.yml: Meridian built from the SHA in deploy/meridian.version, writable meridian-claude volume, real Chat API, key mounted read-only; the dev compose file and its test are deleted"
    requirement: "INFRA-02"
    verification:
      - kind: unit
        ref: "tests/unit/test_compose.py#test_meridian_is_built_from_the_pinned_commit"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_live_chat_bot_is_wired_for_real_chat_and_meridian"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_meridian_credentials_follow_the_recorded_decision"
        status: pass
      - kind: other
        ref: "docker compose --profile live config --quiet (rc 0)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The stub LLM returns one text block that validates with the real schema class for each of the four workflow schemas, cites exactly the evidence ids in the user text, refuses unknown schemas with 400, logs no request text, and is accepted by the bot's real AnthropicMessagesClient"
    requirement: "INFRA-02"
    verification:
      - kind: unit
        ref: "tests/unit/test_stub_llm.py#test_each_workflow_schema_gets_one_text_block_the_real_class_accepts"
        status: pass
      - kind: unit
        ref: "tests/unit/test_stub_llm.py#test_the_real_client_gets_a_valid_answer_draft_through_structured"
        status: pass
      - kind: unit
        ref: "tests/unit/test_stub_llm.py#test_the_stub_never_logs_request_text"
        status: pass
    human_judgment: false
  - id: D6
    description: "The bot and server READMEs describe the live profile command, the hermetic smoke, the uid 10001 note, ARTIFACT_STORE / ARTIFACT_BUCKET / ARTIFACT_PREFIX and where the index comes from; .env.example MCP_URL calls the Service name"
    requirement: "INFRA-01"
    verification:
      - kind: other
        ref: "grep acceptance checks: 0 docker-compose.dev.yml in the bot README, 1 'Where the index comes from', 4 ARTIFACT_STORE, MCP_URL line present"
        status: pass
      - kind: unit
        ref: "tests/unit/test_compose.py#test_env_example_mcp_url_matches_the_live_wiring"
        status: pass
    human_judgment: false
  - id: D7
    description: "The live profile has not been run against the real Chat API, Joshua's Max session or a real service-account key"
    requirement: "INFRA-02"
    verification: []
    human_judgment: true
    rationale: "Needs Joshua's Claude login volume, the bot service-account key and a real Chat space; the plan verifies the live profile by config validation and structural test only"

duration: about 25min (start time not recorded; estimated from commit times)
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 06: Hermetic compose round trip and live profile Summary

**One `docker-compose.yml` runs the whole system from the per-service images with both emulators and a stub LLM, and `scripts/compose-smoke.sh` proves a Pub/Sub chat event ends as a recorded answer citing `handbook://02-ferie`; a `live` profile (Meridian plus the real-Chat bot) replaces the Phase 3 dev compose.**

## Performance

- **Duration:** about 25 min (start time was not recorded)
- **Completed:** 2026-11-14T12:32Z
- **Tasks:** 3 of 3 (Task 1 tracer, Tasks 2 and 3 auto/tdd)
- **Files:** 5 created, 5 modified, 2 deleted, excluding planning files

## Accomplishments

- **Tracer:** `scripts/compose-smoke.sh` builds a throwaway Guides git repo, starts the default services with `up -d --build --wait`, publishes `legacy_dm_message.json` through the emulator REST `:publish` endpoint and polls `/tmp/chat.jsonl` in the bot container until an `update` line holds `Fonte: Manuale` and `handbook://02-ferie`. It ends `round trip ok` (35 to 52 s warm). The tracer gate re-ran the verify after the first commit and it passed before expansion.
- **Stack:** firestore, pubsub, `pubsub-init` (curl PUTs, 200 or 409), `sync` one-shot into the named volume `artifacts`, `mcp-server` (local store, `MCP_ALLOWED_HOSTS=mcp-server`, `/healthz` healthcheck), `stub-llm` and `chat-bot` (recording adapter, no env_file, no credentials). Start order is fixed by `depends_on` conditions.
- **Stub LLM:** `deploy/compose/stub_llm.py`, a Starlette app on port 8090. It reads the schema `title` after the bot's fixed instruction, answers each step deterministically and logs counts only.
- **Live profile:** `meridian` built from the commit in `deploy/meridian.version` and `chat-bot-live` (real Chat API, key mounted read-only, host uid). `docker-compose.dev.yml` and its test are deleted.
- **Docs:** both READMEs updated; the server README carries the `ARTIFACT_STORE`, `ARTIFACT_BUCKET`, `ARTIFACT_PREFIX` rows and "Where the index comes from" (moved from 04-04).
- **Gates:** `./run-unit-tests.sh --all` green: 1273 passed, 26 skipped, ruff, ruff format and mypy clean (the stub is now in all three), coverage 97.6 percent.
- **Edges checked by hand:** `SMOKE_TIMEOUT_SECONDS=1` fails with `timeout after 1 s`; an empty handbook folder makes `sync` exit 1, `chat-bot` and `mcp-server` stay in state `created` and compose returns non-zero.

## Task Commits

1. **Task 1: Tracer, hermetic compose round trip** - `e1780f2` (feat), with `967875e` (fix) recording the executable bit
2. **Task 2: Live profile, structural guard, docs** - `7f9a2aa` (test, RED), `1528dab` (feat, GREEN)
3. **Task 3: Stub LLM tests and tooling wiring** - `7998231` (test, RED), `d82f939` (feat, GREEN)
4. **Fix found by the plan-level re-run** - `e63374b` (fix)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `docker-compose.yml` - the INFRA-02 stack and the live profile
- `deploy/compose/stub_llm.py` - Anthropic Messages stub for the hermetic run
- `scripts/compose-smoke.sh` - hermetic round trip (mode 100755 in the index)
- `tests/unit/test_compose.py` - structural guard, migrated from `test_dev_compose.py` plus hermetic, profile and ordering rules
- `tests/unit/test_stub_llm.py` - contract tests, including the real `AnthropicMessagesClient` over an ASGI transport
- `pyproject.toml` - `deploy/compose` on the pytest path, mypy files and path, ruff src
- `.env.example` - `MCP_URL=http://mcp-server:8000/mcp` and its comment
- `services/chat_bot/README.md`, `services/mcp_server/README.md` - live command, hermetic smoke, uid note, artifact settings
- `tests/unit/chat_bot/test_readme_contract.py` - follows the dropped shared network namespace

## Decisions Made

See `key-decisions` above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Relative HANDBOOK_SRC_DIR was read as a named volume**
- **Found during:** Task 1 (acceptance `docker compose config` with the plan's own relative fixture paths)
- **Issue:** `${HANDBOOK_SRC_DIR}:/handbook:ro` with the value `tests/fixtures/handbook` is a named volume to compose ("refers to undefined volume").
- **Fix:** the two source mounts of `sync` use the long bind syntax with `read_only: true`.
- **Files modified:** docker-compose.yml
- **Verification:** `docker compose config --quiet` rc 0 with relative paths; `test_sync_reads_its_sources_read_only`
- **Committed in:** e1780f2

**2. [Rule 1 - Bug] Executable bit not recorded in the git index**
- **Found during:** Task 1 commit (`git ls-files -s` showed 100644)
- **Issue:** `core.fileMode` is false in this checkout, so `chmod +x` did not reach the index.
- **Fix:** `git update-index --chmod=+x scripts/compose-smoke.sh`, committed separately.
- **Verification:** `git ls-tree HEAD scripts/` shows 100755 for both smoke scripts.
- **Committed in:** 967875e

**3. [Rule 1 - Bug] Required live variables stopped the default stack from loading**
- **Found during:** plan-level re-run of `scripts/compose-smoke.sh` after Task 2
- **Issue:** compose interpolates services in inactive profiles, so `${MERIDIAN_API_KEY:?}` and `${BOT_SA_KEY_FILE:?}` in the live profile aborted `docker compose up` with no profile. The plan's own smoke run sets neither.
- **Fix:** `MERIDIAN_API_KEY` defaults to empty, `BOT_SA_KEY_FILE` to `/dev/null`; `chat-bot-live` runs a small `sh -c` check that exits with a named message when the key or the mounted key file is empty, then `exec python -m buddy_bot`. Two tests added (`test_profile_services_require_nothing_at_load_time`, `test_live_bot_fails_fast_when_its_live_inputs_are_missing`); the old required-variable test narrowed to the default stack's inputs. README text corrected.
- **Files modified:** docker-compose.yml, tests/unit/test_compose.py, services/chat_bot/README.md
- **Verification:** smoke rc 0; `docker compose --profile live config --quiet` rc 0 with no live variables set
- **Committed in:** e63374b

**4. [Rule 3 - Blocking] README contract test asserted the shared network namespace**
- **Found during:** Task 2 (`--all`)
- **Issue:** `test_readme_documents_markdown_syntax_and_silent_meridian` required the phrase "network namespace", which the dev compose used and this plan removes (no service shares a namespace).
- **Fix:** the test now asserts `MCP_ALLOWED_HOSTS=mcp-server` is documented and the phrase is gone. File was not in the plan's list.
- **Files modified:** tests/unit/chat_bot/test_readme_contract.py
- **Verification:** `--all` exit 0
- **Committed in:** 1528dab

**5. [Rule 2 - Missing critical] chat-bot also depends on sync directly**
- **Found during:** Task 1 acceptance (`service_completed_successfully` count was 2, plan expects at least 3)
- **Issue:** truth 3 names both mcp-server and chat-bot as gated on the sync result; only mcp-server was, and the bot only transitively.
- **Fix:** direct `sync: service_completed_successfully` on `chat-bot`.
- **Committed in:** e1780f2

---

**Total deviations:** 5 auto-fixed (2 Rule 1, 2 Rule 3, 1 Rule 2). **Impact:** none on scope; each was needed for the plan's own verify or truths. Deviation 3 weakens one thing, noted below.

## Issues Encountered

- **Meridian without its key:** with `MERIDIAN_API_KEY` unset, Meridian starts without a key while `chat-bot-live` exits. The compose network is private and nothing is published, but Meridian is then open to other containers on it until stopped. The bot's message and the README tell the user to `docker compose --profile live down`. Closing this fully would need either a separate live compose file or a wrapper entrypoint on a third-party image; left as is and recorded here.
- The first smoke runs after Task 2 failed on deviation 3 only; the timeout-path and empty-sync checks were re-run after the fix and pass.

## Protected-branch guard

The commit guard treats `main` as protected; the project works on `main` by standing rule and the orchestrator instructed commits there, as in 04-01 to 04-05. No config was changed.

## Known Stubs

None. `deploy/compose/stub_llm.py` is a deliberate test double for the hermetic stack, not a placeholder in shipped behaviour.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: auth-gap-when-unset | docker-compose.yml | `meridian` runs without an API key if `MERIDIAN_API_KEY` is unset (see Issues Encountered); private network only, and the live bot refuses to start in that case |

## User Setup Required

None for the hermetic stack. The live profile needs `docker volume create meridian-claude` seeded as the bot README describes, `MERIDIAN_API_KEY` in `.env`, `BOT_SA_KEY_FILE`, `HANDBOOK_SRC_DIR` and `GUIDES_SRC_DIR`.

## Next Phase Readiness

- 04-07 (kind) can reuse the stub image path, the `mcp-server` Service name rule and `MCP_ALLOWED_HOSTS=mcp-server`; the recording file is `/tmp/chat.jsonl` in the bot container.
- 04-08 and 04-09 can call `scripts/compose-smoke.sh` in CI; it needs Docker and about a minute warm, longer on a cold build.
- Open: the live profile is verified by config and structure only, not run against real Chat or Max.

## Self-Check: PASSED

- FOUND: docker-compose.yml, deploy/compose/stub_llm.py, scripts/compose-smoke.sh (mode 100755 in the index), tests/unit/test_compose.py, tests/unit/test_stub_llm.py
- ABSENT as required: docker-compose.dev.yml, tests/unit/test_dev_compose.py
- FOUND: commits e1780f2, 967875e, 7f9a2aa, 1528dab, 7998231, d82f939, e63374b are ancestors of HEAD (7 commits since plan_head_before)
- Acceptance greps: 7 services, 0 `ports:`, 3 `service_completed_successfully`, `/v1/messages` in the stub, `round trip ok` 1, `profiles:` 2, `MCP_URL=http://mcp-server:8000/mcp` 1, 0 dev-compose references in the bot README, `ARTIFACT_STORE` 4, "Where the index comes from" 1, `deploy/compose` 4 in pyproject, 10 stub test functions
- `scripts/compose-smoke.sh` exit 0 after the final change; `./run-unit-tests.sh --all` exit 0 (1273 passed, 26 skipped)

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
