---
phase: 03-google-chat-bot
plan: 11
subsystem: bot-composition
tags: [composition-root, cli, google-id-token, httpx2, docker, env-contract, log-hygiene, tdd]

requires:
  - phase: 03-google-chat-bot (03-06)
    provides: "BotSettings, build_llm_client"
  - phase: 03-google-chat-bot (03-07)
    provides: "FirestoreThreadMemory with lazy client factory"
  - phase: 03-google-chat-bot (03-09)
    provides: "BotService.handle (never raises, allowlist, dedupe)"
  - phase: 03-google-chat-bot (03-10)
    provides: "PubSubIntake, HttpIntake, ChatTokenVerifier, GoogleChatApi, build_chat_client"
provides:
  - "buddy_bot.cli.main(argv=None, *, run=None) and python -m buddy_bot: the only place real adapters are built, all values from the environment"
  - "buddy_bot.cli.floor_content_loggers(): raises the fastmcp and anthropic loggers to INFO at startup"
  - "buddy_bot.mcp_client.GoogleIdTokenAuth(audience, *, fetch, lifetime_seconds=3000.0, clock): httpx2.Auth with the bot's own Google ID token for MCP_AUDIENCE"
  - "Dockerfile target chat_bot: uid 10001, LANGSMITH_TRACING=false, buddy_core + buddy_bot + buddy_mcp/__init__.py and models.py only"
  - ".env.example bot block (placeholders only) enforced by tests/unit/test_repo_layout.py (CONTRACT_KEYS, _API_KEY suffix, no emulator host)"
  - "Real-process test on the Firestore and Pub/Sub emulators; BOT-11 log sentinel test over six reply paths and six loggers"
affects: [03-12, phase-04-deploy]

actuals:
  tokens: 10915
  tasks: 3
  commits: 4
plan_head_before: 11e11b4c096b6063bf14a3a2fe238c66404f6169
commits: 4
plan_head_after: 0695a4b9c06cee96c384ff199022d3192fc62285

tech-stack:
  added: []
  patterns:
    - "Composition root mirrors buddy_mcp.cli: handler attached and removed in finally, _describe_validation_error copied, injectable runner"
    - "Startup builds no client that touches the network; Firestore, Chat API and ID token are created on first use inside the intake loop"
    - "httpx2.Auth overriding sync_auth_flow and async_auth_flow; async path fetches in asyncio.to_thread only when the cache is cold"
    - "Dockerfile stage copies two files of the server package instead of the package"
    - "Hygiene sentinels plus a capture-wiring probe; content-writing libraries floored at INFO at startup"

key-files:
  created:
    - services/chat_bot/buddy_bot/cli.py
    - services/chat_bot/buddy_bot/__main__.py
    - tests/unit/chat_bot/test_main.py
    - tests/unit/chat_bot/test_id_token_auth.py
    - tests/unit/chat_bot/test_log_hygiene.py
    - tests/integration/test_bot_process.py
  modified:
    - services/chat_bot/buddy_bot/mcp_client.py
    - Dockerfile
    - .env.example
    - tests/unit/test_repo_layout.py

key-decisions:
  - "GoogleIdTokenAuth is created in the tracer task (plan step 1 says so) so the composition root imports a real class; Task 2 adds its unit tests"
  - "fastmcp and anthropic loggers are floored at INFO in main(): both write request content (question, prompts) at DEBUG and each has an env switch that turns DEBUG on (Rule 2, BOT-11)"
  - "Startup logs exactly one INFO line: intake, LLM backend, allowed-user count, memory turns; no identifier, no secret"
  - "Unexpected startup errors limited to ValidationError, EscalationTableError and OSError, as the plan's _EXPECTED_ERRORS"

patterns-established:
  - "Process tests build the child environment from os.environ minus every BotSettings variable, so an env file loaded into the container never leaks settings into the child"
  - "Log tests watch non-propagating loggers by attaching caplog.handler by hand and prove it with a probe"

requirements-completed: [BOT-01, BOT-02, BOT-07, BOT-08, BOT-11]

coverage:
  - id: D1
    description: "python -m buddy_bot builds every adapter from the environment, logs one counts-only INFO line and runs the intake chosen by INTAKE"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_pubsub_intake_receives_the_service_handler"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_http_intake_is_selected_by_configuration"
        status: pass
    human_judgment: false
  - id: D2
    description: "Startup makes no network call: Firestore client, Chat API client and ID token are lazy"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_startup_makes_no_network_call"
        status: pass
    human_judgment: false
  - id: D3
    description: "Bad configuration exits 1 with one ERROR line naming variables, never values or tracebacks (missing variables, meridian with two users, vertex, tracing, MCP_AUTH=none on Cloud Run, short secret)"
    requirement: BOT-08
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_main.py#test_refused_configurations_exit_one_with_one_safe_line"
        status: pass
      - kind: integration
        ref: "tests/integration/test_bot_process.py#test_missing_allowed_users_exits_one_naming_the_variable"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real process on the emulators: HTTP intake answers 401 without a token and 405 on GET; Pub/Sub intake drops a stranger and keeps running without identifiers in stderr"
    requirement: BOT-02
    verification:
      - kind: integration
        ref: "tests/integration/test_bot_process.py#test_http_intake_rejects_a_request_without_a_token"
        status: pass
      - kind: integration
        ref: "tests/integration/test_bot_process.py#test_pubsub_intake_drops_a_stranger_and_keeps_running"
        status: pass
    human_judgment: false
  - id: D5
    description: "GoogleIdTokenAuth sets the bearer header for the audience, caches 50 minutes, fetches off the event loop, never leaks the token"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_id_token_auth.py"
        status: pass
    human_judgment: true
    rationale: "The live token call (service-account file or metadata server) and the MCP server's BOT_SA_EMAILS check are not exercised offline; checked at 03-12 or deferred with it"
  - id: D6
    description: "chat_bot image stage runs as uid 10001 with tracing off and no server code beyond the output models; .env.example holds exactly the contract keys and no secret key"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/test_repo_layout.py#test_chat_bot_stage_disables_tracing"
        status: pass
      - kind: other
        ref: "docker build --target chat_bot -t ai-buddy-bot . && docker run --rm --network none ai-buddy-bot python -c ... prints '10001 false'"
        status: pass
    human_judgment: false
  - id: D7
    description: "No captured log record from buddy_bot, fastmcp, langgraph, httpx2, mcp or anthropic loggers or root contains sender, space, thread, question or answer on six reply paths"
    requirement: BOT-11
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_log_hygiene.py#test_no_log_record_carries_identity_question_or_answer"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_log_hygiene.py#test_capture_wiring_sees_every_watched_logger"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 11: Composition root, bot-to-MCP ID token, chat_bot image and log hygiene Summary

**`python -m buddy_bot` assembles every adapter from the environment alone, authenticates to the MCP server with its own Google ID token, ships as a non-root chat_bot image with tracing off, and a six-path sentinel test proves no log record pairs a person with a question or answer.**

## Performance

- **Duration:** about 25 min (start time not captured; first task commit 13:28 +0100, last 13:34 +0100)
- **Completed:** 2026-11-07
- **Tasks:** 3
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments

- Composition root `cli.py`: `BotSettings()` read once, LLM client, `FastMcpConnector` (with `GoogleIdTokenAuth` when `MCP_AUTH=google_id_token`), `FirestoreThreadMemory`, `GoogleChatApi`, `WorkflowDeps` with the escalation table, `BotService` and the intake chosen by `INTAKE`; default runner is `asyncio.run(intake.run(handler))`, `KeyboardInterrupt` returns 0.
- Startup refusals exit 1 with one variable-only ERROR line (missing variables, meridian with two users, vertex, tracing, `MCP_AUTH=none` with `K_SERVICE`, short secret). A socket-connect guard in the unit test proves startup makes no network call.
- Real process on both emulators: HTTP intake gives 401 without a token (also for a malformed bearer) and 405 on GET; a stranger's Pub/Sub event is consumed and dropped with the process still running and no `users/` or e-mail in stderr.
- `GoogleIdTokenAuth`: bearer header for the audience, 3000 s cache, worker-thread fetch on async clients, fetch errors keep their type, token absent from error chains and logs.
- `chat_bot` Docker stage (uid 10001, `LANGSMITH_TRACING=false`, only `buddy_mcp/__init__.py` and `models.py` of the server) built and run: prints `10001 false`, imports `buddy_bot.cli`, exits 1 with one ERROR line when started without configuration.
- `.env.example` bot block (placeholders; `VIDEO_THUMBNAIL_URL` is `https://example.invalid/video-thumbnail.png`, the real value arrives at 03-12); `test_repo_layout` enforces contract keys, `_API_KEY` as a secret suffix and no emulator host.
- Log hygiene over answer, refusal with gap, sensitive referral, workflow error, dropped stranger and memory-write failure, with a capture-wiring probe.

## Task Commits

1. **Task 1: Tracer, `python -m buddy_bot` as a real process** - `535f468` (feat)
2. **Task 2: ID token, chat_bot stage, env contract (TDD)** - RED `4bd40d5` (test), GREEN `ac72d7a` (feat)
3. **Task 3: Log hygiene across every reply path** - `0695a4b` (test, includes the cli.py logger floor fix)

**Plan metadata:** recorded by the final docs commit of this plan.

## Files Created/Modified

- `services/chat_bot/buddy_bot/cli.py` - composition root, logger floor, startup refusals
- `services/chat_bot/buddy_bot/__main__.py` - `python -m buddy_bot`
- `services/chat_bot/buddy_bot/mcp_client.py` - `GoogleIdTokenAuth`
- `tests/unit/chat_bot/test_main.py` - 15 offline tests of the composition root
- `tests/unit/chat_bot/test_id_token_auth.py` - 6 tests of the ID token auth
- `tests/unit/chat_bot/test_log_hygiene.py` - 6 scenario runs plus the wiring probe
- `tests/integration/test_bot_process.py` - 3 real-process tests on the emulators
- `Dockerfile` - `chat_bot` stage
- `.env.example` - bot keys
- `tests/unit/test_repo_layout.py` - contract keys, `_API_KEY`, emulator hosts, stage test

## Decisions Made

- Followed the plan for `GoogleIdTokenAuth` placement (created with the tracer, tested in Task 2).
- Flooring the `fastmcp` and `anthropic` loggers at startup is the only code decision beyond the plan (see deviation 1).
- Left SIGTERM to the interpreter default (no handler): not in the plan, and Pub/Sub redelivers unacked messages; Phase 4 may revisit for Cloud Run drain.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Floor fastmcp and anthropic loggers at INFO**
- **Found during:** Task 3 (log hygiene), first run of the sentinel test with all loggers at DEBUG
- **Issue:** fastmcp logs `Handler called: call_tool buddy_report_gap with {'question': ...}` and the client-side tool names at DEBUG, so with `FASTMCP_LOG_LEVEL=DEBUG` the question text reaches the log sink (2 of 6 scenarios failed). The anthropic SDK logs `Request options: ...` (prompts) at DEBUG when `ANTHROPIC_LOG=debug`. Both are library logs, so the plan's "fix the log call in buddy_bot" had nothing to fix in buddy_bot. At the default INFO level nothing leaks (verified: default fastmcp level is INFO).
- **Fix:** `floor_content_loggers()` in `cli.py`, called from `main()`, raises both loggers to INFO when their effective level is lower. The hygiene fixture starts the libraries at DEBUG and applies the same function; the probe asserts DEBUG records of exactly these two loggers are dropped. `test_main` asserts the floor for both libraries.
- **Files modified:** services/chat_bot/buddy_bot/cli.py, tests/unit/chat_bot/test_main.py, tests/unit/chat_bot/test_log_hygiene.py
- **Verification:** 22 tests pass in the two files; `./run-unit-tests.sh --all` exits 0
- **Committed in:** 0695a4b

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** closes a BOT-11 leak that only appears when an operator turns on library debug logging; no scope creep beyond one small function.

## TDD Gate Compliance

- **Task 2 (RED `4bd40d5`, GREEN `ac72d7a`):** RED evidence: `test_chat_bot_stage_disables_tracing` failed on its own assertion ("Dockerfile has no chat_bot stage") and `test_env_example_holds_exactly_the_contract_keys` failed on the key-set comparison; both then passed after the Dockerfile and `.env.example` changes. Semantic assessment: both failures are the planned assertions failing for the intended reason, no import, collection or fixture fault. `gsd_run check tdd-red-evidence` was not run (`workflow.tdd_mode` is not enabled in config.json). The six `test_id_token_auth.py` tests were committed in the RED commit but were green on arrival, because the plan has the tracer task ship `GoogleIdTokenAuth`; they are regression tests for that class, not RED evidence.
- **Task 3:** the sentinel test was run once before the logger floor existed and failed in two scenarios (refusal with gap, sensitive referral: the fastmcp DEBUG record carrying the question). That RED was observed locally but not committed separately; the test and the fix share commit `0695a4b`. No separate `feat` commit exists for Task 3.

## Issues Encountered

- `PORT=8000` in `.env.example` is the MCP server's value; `BotSettings.port` defaults to 8080 and reads the same variable name. The `chat_bot` container must not inherit that line (it is not baked into the image, and the Dockerfile sets no PORT). For the HTTP intake in dev compose or Cloud Run, set PORT explicitly for the bot.

## Known Stubs

None. The `VIDEO_THUMBNAIL_URL` placeholder in `.env.example` is an intentional example value (decided at the 03-01 checkpoint: supplied via `.env` at 03-12); `BotSettings` requires the variable and rejects non-HTTPS values.

## Threat Flags

None. The new surface (process entry point, container image, bot-to-MCP bearer token) is covered by T-03-29 to T-03-33 of the plan's threat model.

## User Setup Required

None in this plan. For the 03-12 live checkpoint: `.env` needs `THREAD_KEY_SECRET` (at least 32 characters), the real `VIDEO_THUMBNAIL_URL`, `ALLOWED_USERS`, and the LLM keys; the bot service account e-mail must be in the MCP server's `BOT_SA_EMAILS` and `MCP_AUDIENCE` must equal its `MCP_PUBLIC_BASE_URL` if `MCP_AUTH=google_id_token` is used.

## Next Phase Readiness

- Ready for 03-12 (live checkpoint). Not checked offline and deferred with it: the live ID token call from the bot to the MCP server (service-account file or metadata server) and the server's issuer, audience and `BOT_SA_EMAILS` verification against it; the live Chat API calls.
- Verification evidence: `./run-unit-tests.sh --all` exit 0 (922 passed, 26 skipped emulator tests, coverage 97.89%, ruff and mypy clean); `./run-unit-tests.sh --emulator` exit 0 (12 passed, 3 from `test_bot_process.py`); `git diff --quiet 7d772e2 -- services/mcp_server jobs/sync` exits 0; no pin added or changed.

## Self-Check: PASSED

- Files exist: cli.py, `__main__.py`, test_main.py, test_id_token_auth.py, test_log_hygiene.py, test_bot_process.py (verified below), Dockerfile stage and `.env.example` keys by grep.
- Commits exist on main: 535f468, 4bd40d5, ac72d7a, 0695a4b.

---
*Phase: 03-google-chat-bot*
*Completed: 2026-11-07*
