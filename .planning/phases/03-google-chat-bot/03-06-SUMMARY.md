---
phase: 03-google-chat-bot
plan: 06
subsystem: bot-llm-config
tags: [anthropic, meridian, pydantic-settings, structured-output, startup-guards, tdd]

requires:
  - phase: 03-google-chat-bot (03-01)
    provides: "anthropic==2.6.0 pin; VIDEO_THUMBNAIL_URL is a required HTTPS setting (bot09_rendering 2c)"
  - phase: 03-google-chat-bot (03-03)
    provides: "ports.LlmClient, LlmOutputError, LlmUnavailableError, schemas.Reformulation"
provides:
  - "config.BotSettings: the complete bot env contract (25 variables) with BOT-07/BOT-08 guards"
  - "llm.AnthropicMessagesClient: one client for every backend, JSON-in-prompt structured output, one capped repair, typed errors"
  - "llm.build_llm_client(settings, *, http_client=None): api and meridian differ only in base_url, key and retries"
  - "llm.extract_json and llm.MERIDIAN_PLACEHOLDER_KEY = 'meridian-local'"
affects: [03-07, 03-08, 03-09, 03-11, 03-12]

actuals:
  tokens: 7900
  tasks: 3
  commits: 5
plan_head_before: 1f1c491bf6a84057ddf0bee19f3664b9dcdc8d73
commits: 5
plan_head_after: 5cc6c57d60174d9242a1a7bff3b8d1d1318ff7eb

tech-stack:
  added: []
  patterns:
    - "One Strategy client; a factory picks base_url and key from LLM_BACKEND; callers see only the LlmClient port"
    - "Repair message carries error locations and types only, never model output or input values"
    - "Exceptions raised `from None` with the exception type name only, so transport detail and model text stay out of logs"
    - "Single model_validator holding every startup refusal in a fixed order; messages name variables, never values"

key-files:
  created:
    - services/chat_bot/buddy_bot/config.py
    - services/chat_bot/buddy_bot/llm.py
    - tests/unit/chat_bot/test_llm_client.py
    - tests/unit/chat_bot/test_config.py
  modified: []

key-decisions:
  - "anthropic 2.6.0 sends api_key as 'Authorization: Bearer <key>' and never sets 'x-api-key'; tests assert the Bearer header and the factory adds no extra header"
  - "Timeout is the client's per-phase timeout (LLM_TIMEOUT_SECONDS passed to AsyncAnthropic); no extra overall deadline in the client (the run deadline is 03-09)"
  - "build_llm_client takes an optional keyword http_client so tests inject a mock transport; production callers omit it"
  - "'More than one user' counts distinct normalized ALLOWED_USERS entries, as the plan flagged: users/<id> and an e-mail of the same person count as two"
  - "VIDEO_THUMBNAIL_URL is required and must start with https:// (03-01 bot09_rendering option c); no value was invented, the real value comes at 03-12"

requirements-completed: [BOT-07, BOT-08]

coverage:
  - id: D1
    description: "LLM_BACKEND=api settings build the Messages client; one POST to /v1/messages with model from REFORMULATE_MODEL, key sent, no sampling parameters, validated Reformulation returned"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_api_backend_returns_validated_reformulation"
        status: pass
    human_judgment: false
  - id: D2
    description: "Meridian is the same client class with LLM_BASE_URL and the placeholder or configured key; vertex refuses startup with 'not enabled'"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_meridian_uses_the_same_client_with_placeholder_key"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_meridian_sends_the_configured_key"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_vertex_is_not_enabled"
        status: pass
    human_judgment: false
  - id: D3
    description: "Invalid model output gets exactly one repair (locations and types only), then LlmOutputError; transport, timeout and status errors raise LlmUnavailableError naming the exception type; concurrent calls share one client"
    requirement: BOT-07
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_missing_field_is_repaired_once_with_locations_only"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_two_invalid_outputs_raise_output_error_after_exactly_two_requests"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_connect_error_raises_unavailable_with_exception_type_only"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_llm_client.py#test_concurrent_calls_share_one_client_without_mixing_results"
        status: pass
    human_judgment: false
  - id: D4
    description: "The bot refuses to start with LLM_BACKEND=meridian and more than one distinct ALLOWED_USERS entry (entries trimmed, lowercased, de-duplicated), and with an empty allowlist"
    requirement: BOT-08
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_meridian_with_two_users_is_refused"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_duplicate_entries_count_once"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_api_backend_allows_two_users"
        status: pass
    human_judgment: false
  - id: D5
    description: "Other startup refusals (MCP_AUTH=none under K_SERVICE, true tracing flags, short THREAD_KEY_SECRET, missing mode variables, non-HTTPS or missing thumbnail) name variables only; no secret sentinel appears in any refusal"
    requirement: BOT-08
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_no_refusal_echoes_a_secret"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_true_tracing_is_refused"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_config.py#test_no_mcp_auth_on_cloud_run_is_refused"
        status: pass
    human_judgment: false
  - id: D6
    description: "Meridian accepts the Bearer-style key header that anthropic 2.6.0 sends when MERIDIAN_API_KEY gates it"
    requirement: BOT-07
    verification: []
    human_judgment: true
    rationale: "Meridian's gate behaviour is only observable against the real Meridian container at the 03-12 live checkpoint"

duration: 7min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 06: LLM client and bot settings Summary

**One Anthropic Messages client (api and Meridian differ only in base URL and key) with JSON-in-prompt structured output, one capped repair and typed errors, plus a 25-variable BotSettings that refuses startup for Meridian with more than one user, vertex, MCP_AUTH=none on Cloud Run, true tracing flags, weak secrets and missing mode variables.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-11-07T11:40:57Z
- **Completed:** 2026-11-07T11:48:05Z
- **Tasks:** 3 (tracer, two TDD)
- **Files modified:** 4 (all created)

## Accomplishments

- `BotSettings` holds the full bot env contract so 03-11 wires adapters without new env decisions; one `model_validator` applies the refusals in the plan's order, field validators cover secret length, thumbnail scheme and collection name.
- `AnthropicMessagesClient.structured()` appends the schema's JSON schema to the system prompt, accepts JSON in prose or a code fence, repairs once with locations and types only, then raises `LlmOutputError`; every `anthropic.APIError` becomes `LlmUnavailableError(<type name>)`. The instance holds only the SDK client, so concurrent runs share it.
- Full gate green: ruff, ruff format, mypy --strict, 776 passed and 18 skipped, coverage 97.11%.

## Task Commits

1. **Task 1: Tracer, api settings to Messages client** - `ffbbf1a` (feat)
2. **Task 2 RED: repair, error mapping, backend switch tests** - `6d26181` (test)
3. **Task 2 GREEN: repair retry and typed errors** - `b0bd1c0` (feat)
4. **Task 3 RED: BotSettings guard tests** - `dbce622` (test)
5. **Task 3 GREEN: BotSettings guards** - `5cc6c57` (feat)

**Plan metadata:** the docs commit that follows this file.

## TDD Gate Compliance

RED then GREEN for both TDD tasks; no REFACTOR commit (nothing to clean up).

- **Task 2 RED (`6d26181`):** 6 of 12 tests failed on the planned assertions: both repair tests and the two-invalid test raised a raw `pydantic ValidationError` instead of repairing or raising `LlmOutputError`; the connect, timeout and 500-status tests raised raw `anthropic` errors instead of `LlmUnavailableError`. Semantic assessment: the target tests ran and failed for the intended reason (no import, collection or fixture fault). The 6 passing tests (tracer, meridian x2, fence parsing, timeout setting, concurrency) are characterization tests: the plan's Task 1 action already builds both backends and `extract_json`, and a stateless client is concurrent by construction.
- **Task 3 RED (`dbce622`):** 18 of 42 tests failed with "DID NOT RAISE" for the guards the plan assigns to Task 3 (single-user Meridian, blank allowlist, vertex, `LLM_BASE_URL`, `MCP_AUDIENCE`, `PUBSUB_SUBSCRIPTION`, intake http variables, K_SERVICE, tracing, short secret, collection name, https thumbnail, sentinel cases for those refusals). The passing ones are characterization: field bounds and required fields exist from Task 1 as the plan specifies.
- `workflow.tdd_mode` is not enabled in `.planning/config.json` and pytest emits neither TAP nor JUnit by default through `run-unit-tests.sh`, so the machine classifier `gsd_run check tdd-red-evidence` was not run; the semantic assessment above stands in for it.

## Files Created/Modified

- `services/chat_bot/buddy_bot/config.py` - BotSettings: env contract and startup refusals
- `services/chat_bot/buddy_bot/llm.py` - AnthropicMessagesClient, build_llm_client, extract_json, MERIDIAN_PLACEHOLDER_KEY
- `tests/unit/chat_bot/test_llm_client.py` - 12 tests over an httpx2 mock transport
- `tests/unit/chat_bot/test_config.py` - 42 cases (parametrized) over the guards and the no-secret-echo sweep

## Decisions Made

See `key-decisions` in the frontmatter. The two that matter downstream: the key reaches Anthropic and Meridian as `Authorization: Bearer`, and the client relies on the SDK's per-phase timeout rather than a total deadline.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan assumption] anthropic 2.6.0 does not send x-api-key**
- **Found during:** Task 1 (tracer test)
- **Issue:** The plan's tracer asserts header `x-api-key` equals the key. Introspection of the installed SDK shows `_api_key_auth` returns `{"Authorization": f"Bearer {api_key}"}`; `x-api-key` is never set.
- **Fix:** The test asserts `authorization == "Bearer <key>"` (same for the Meridian tests). No header was added to make the original assertion true, because the official SDK's behaviour against the real API is the known-good path.
- **Files modified:** tests/unit/chat_bot/test_llm_client.py
- **Verification:** all 12 client tests pass; header probe printed the Bearer header.
- **Committed in:** ffbbf1a

**2. [Rule 3 - Blocking] Timeout test cannot sleep past the client timeout**
- **Found during:** Task 2 (RED design)
- **Issue:** The plan's behavior says a handler that sleeps beyond a 0.05 s client timeout raises `LlmUnavailableError`. `httpx2.MockTransport` does not enforce the request timeout, so a sleeping handler would simply return late.
- **Fix:** The mock handler raises `httpx2.ReadTimeout`, which the SDK turns into `APITimeoutError` (mapped to `LlmUnavailableError("APITimeoutError")`); a separate test proves `LLM_TIMEOUT_SECONDS` reaches the SDK client (`client.timeout == 7`). Together they cover the mapping and the wiring, not the real elapsed-time enforcement, which belongs to httpx2.
- **Files modified:** tests/unit/chat_bot/test_llm_client.py
- **Verification:** `test_timeout_raises_unavailable`, `test_timeout_setting_reaches_the_client` pass.
- **Committed in:** 6d26181

**3. [Rule 3 - Blocking] build_llm_client needed a way to inject the HTTP client**
- **Found during:** Task 1
- **Issue:** The signature in the plan, `build_llm_client(settings)`, gives tests no way to use a mock transport for the real factory path (backend, base URL and key selection).
- **Fix:** Added keyword-only `http_client: httpx2.AsyncClient | None = None`, passed straight to `AsyncAnthropic`. `httpx2` is imported only under `TYPE_CHECKING` in `llm.py`; tests import it directly. No new pin: `httpx2` is already installed as a dependency of `anthropic`/`fastmcp`.
- **Files modified:** services/chat_bot/buddy_bot/llm.py
- **Committed in:** ffbbf1a

---

**Total deviations:** 3 auto-fixed (1 plan-assumption bug, 2 blocking)
**Impact on plan:** No scope change and no pinned dependency change. Deviation 1 leaves one open question for the live check (below).

## Issues Encountered

- `ruff format` rejected a trailing blank line in `config.py` and `mypy` flagged an unused `type: ignore` in a test (the pydantic mypy plugin accepts `BotSettings()` with env-only required fields); both fixed before the first commit.
- Error-path tests build the client with `max_retries=0`; through `build_llm_client` the api backend retries twice with backoff, which would slow the suite.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required. `VIDEO_THUMBNAIL_URL` has no default: Joshua supplies its value through `.env` at 03-12 (03-01 decision 2c); nothing was invented here.

## Next Phase Readiness

- 03-07 to 03-11 can read every setting from `BotSettings`; 03-11 builds the client with `build_llm_client(settings)`.
- **Open for 03-12 live check [Unknown]:** with `MERIDIAN_API_KEY` set, Meridian's gate may expect `x-api-key` rather than `Authorization: Bearer`, which is all anthropic 2.6.0 sends. If the live request is rejected, add `default_headers={"x-api-key": <key>}` for the meridian branch in `build_llm_client`; with the placeholder key and no gate nothing changes. Not verified offline.
- The bot README (03-12) must say that with Meridian Joshua lists exactly one ALLOWED_USERS form (`users/<id>` or e-mail), since two forms of the same person count as two entries.

## Self-Check: PASSED

All four created files exist; commits ffbbf1a, 6d26181, b0bd1c0, dbce622, 5cc6c57 are ancestors of HEAD; `./run-unit-tests.sh --all` passed (776 passed, 18 skipped, coverage 97.11%); every acceptance-criteria grep returned its expected count.

---
*Phase: 03-google-chat-bot*
*Completed: 2026-11-07*
