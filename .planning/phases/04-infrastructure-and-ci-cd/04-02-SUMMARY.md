---
phase: 04-infrastructure-and-ci-cd
plan: 02
subsystem: infra
tags: [fastmcp, pydantic-settings, host-guard, healthz, deploy-env, auth-guard]

requires:
  - phase: 02-mcp-server-and-skill
    provides: McpSettings, host_kwargs, build_app, AUTH_MODE guard (D-13), 02-REVIEW findings WR-01/02/05
provides:
  - "McpSettings.deploy_env (DEPLOY_ENV local|production, default production) as the explicit marker every auth-off guard reads"
  - "McpSettings.mcp_allowed_hosts (MCP_ALLOWED_HOSTS CSV of bare hostnames) appended to the Host guard list"
  - "GET /healthz on the MCP ASGI app: constant {status: ok}, unauthenticated, Host-guarded, dependency-free"
  - "WR-02 (parsed loopback hostname check) and WR-05 (signing key >= 32 chars) enforced in config"
  - "Env contract: DEPLOY_ENV and MCP_ALLOWED_HOSTS in .env.example, CONTRACT_KEYS, dev compose, server README"
affects: [04-03, 04-06, 04-07, 04-08]

actuals:
  tokens: 9600
  tasks: 3
  commits: 3
plan_head_before: 011406876a2550733cc8c349fe90acce30b5f4dc
plan_head_after: 5152034863ff93521734f3dc0a61d4c8f7abb5f1

tech-stack:
  added: []
  patterns:
    - "Explicit deploy marker that fails closed (default production); K_SERVICE only forces production"
    - "Host guard widened only by an exact-match, strictly validated allow-list; never disabled, never auto-admitting the request Host"
    - "Liveness route registered with FastMCP.custom_route; reads no setting or dependency"

key-files:
  created: []
  modified:
    - services/mcp_server/buddy_mcp/config.py
    - services/mcp_server/buddy_mcp/server.py
    - tests/unit/mcp_server/test_http_transport.py
    - tests/unit/mcp_server/test_config.py
    - tests/unit/mcp_server/test_auth_mode.py
    - tests/unit/mcp_server/test_main.py
    - tests/unit/mcp_server/test_gap_tool.py
    - tests/unit/mcp_server/conftest.py
    - tests/unit/chat_bot/conftest.py
    - tests/integration/test_server_process.py
    - tests/unit/test_repo_layout.py
    - tests/unit/test_dev_compose.py
    - .env.example
    - docker-compose.dev.yml
    - services/mcp_server/README.md

key-decisions:
  - "DEPLOY_ENV defaults to production on every host; AUTH_MODE=off is accepted only with an explicit DEPLOY_ENV=local, and DEPLOY_ENV=local is refused whenever K_SERVICE is set"
  - "MCP_ALLOWED_HOSTS entries must be bare lowercase DNS hostnames; errors name the variable and never echo the value"
  - "/healthz stays a FastMCP custom route: the Task 1 test with AUTH_MODE=on proved it is not behind the auth provider, so build_app did not need a Starlette route"
  - "allowed_origins is unchanged by MCP_ALLOWED_HOSTS: server-to-server calls carry no Origin"

patterns-established:
  - "Invariant test: every value of DEPLOY_ENV except local refuses auth-off, with and without K_SERVICE"
  - "Public base URL is parsed with urlsplit and compared by exact hostname, never by string prefix"

requirements-completed: [INFRA-01, INFRA-03]

coverage:
  - id: D1
    description: "A pod-to-pod request with Host mcp-server:8000 is served (guides_search returns a cited result) when MCP_ALLOWED_HOSTS lists mcp-server, gets 421 when it does not, and other hosts still get 421"
    requirement: "INFRA-03"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_allowed_host_pod_to_pod_call_is_served"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_unlisted_service_host_gets_421_without_the_allow_list"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_allowed_host_list_does_not_admit_other_hosts"
        status: pass
    human_judgment: false
  - id: D2
    description: "MCP_ALLOWED_HOSTS accepts only bare lowercase hostnames; refusals name the variable and never the value; default allowed_hosts list unchanged"
    requirement: "INFRA-03"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_mcp_allowed_hosts_refuses_anything_but_a_bare_hostname"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_host_kwargs_default_allowed_hosts_are_unchanged"
        status: pass
    human_judgment: false
  - id: D3
    description: "GET /healthz answers 200 with a constant body, needs no token with AUTH_MODE=on, and is subject to the Host guard"
    requirement: "INFRA-03"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_healthz_answers_a_constant_body"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_healthz_needs_no_token_when_auth_is_on"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_healthz_is_subject_to_the_host_guard"
        status: pass
    human_judgment: false
  - id: D4
    description: "deploy_env fails closed on every host: auth-off only with DEPLOY_ENV=local, local refused under K_SERVICE"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_every_value_but_local_refuses_auth_off"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_deploy_env_local_is_refused_when_k_service_is_set"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_main.py#test_auth_off_without_deploy_env_is_refused_on_any_host"
        status: pass
    human_judgment: false
  - id: D5
    description: "WR-02 loopback hostname parsing and WR-05 signing-key length are enforced without echoing values"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_public_base_url_refuses_plain_http_to_lookalike_hosts"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_signing_key_shorter_than_32_characters_is_refused_without_echo"
        status: pass
    human_judgment: false
  - id: D6
    description: "Env contract and docs name DEPLOY_ENV, MCP_ALLOWED_HOSTS and /healthz; dev compose sets DEPLOY_ENV local on mcp_server and chat_bot"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_repo_layout.py#test_env_example_holds_exactly_the_contract_keys"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dev_compose.py#test_dev_stack_declares_deploy_env_local_for_server_and_bot"
        status: pass
      - kind: integration
        ref: "./run-unit-tests.sh --emulator (tests/integration/test_server_process.py with DEPLOY_ENV=local)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 02: MCP Deploy Marker, Pod-to-Pod Hosts and Health Route Summary

**One MCP server image now fails closed on every host through an explicit `DEPLOY_ENV` marker, answers on allow-listed pod-to-pod hostnames behind the unchanged Host guard, and exposes an unauthenticated dependency-free `GET /healthz`, with 02-REVIEW WR-02 and WR-05 enforced.**

## Performance

- **Duration:** about 15 min
- **Completed:** 2026-11-14T11:25Z
- **Tasks:** 3 of 3
- **Files modified:** 15 (2 source, 10 test, 3 config and docs)

## Accomplishments

- Tracer: a request with `Host: mcp-server:8000` reaches `guides_search` (cited result) and `/healthz` through the real ASGI app when `MCP_ALLOWED_HOSTS=mcp-server`; without the variable it gets 421, and foreign hosts still get 421 on both routes. The default allowed-host list is byte-identical when nothing is set.
- `DEPLOY_ENV` (local | production, default production) replaces the K_SERVICE-only guard: `AUTH_MODE=off` needs an explicit `local`, and `local` is refused whenever `K_SERVICE` is set (audit warning 4, WR-01).
- WR-02: `MCP_PUBLIC_BASE_URL` over plain http is accepted only for hostname `localhost` or `127.0.0.1` (parsed, so `http://localhost.evil.example` is refused). WR-05: with `AUTH_MODE=on` an `OAUTH_JWT_SIGNING_KEY` under 32 characters is refused, naming the variable only.
- Env contract, dev compose and the server README document both knobs and the health route; `./run-unit-tests.sh --all` (1074 passed, coverage 97.53%) and `--emulator` (12 passed, real server process with `DEPLOY_ENV=local`) are green.

## Task Commits

1. **Task 1: Tracer, pod-to-pod host allow-list and /healthz** - `d15eb4c` (feat)
2. **Task 2: DEPLOY_ENV fails closed; WR-02 and WR-05; fixtures opt into local** - `21afbfd` (feat)
3. **Task 3: Env contract and docs** - `5152034` (chore)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

_Note: tests were written and seen failing before each implementation (RED run observed for Tasks 1 and 3; Task 2 tests were written against the new messages first), but each task is committed as one test-plus-code commit, not as separate test and feat commits._

## Files Created/Modified

- `services/mcp_server/buddy_mcp/config.py` - `deploy_env`, `mcp_allowed_hosts`, hostname pattern, parsed public-URL check, signing-key length, fail-closed auth guard
- `services/mcp_server/buddy_mcp/server.py` - `/healthz` custom route; `host_kwargs` appends sorted allowed hosts
- `tests/unit/mcp_server/test_http_transport.py` - pod-to-pod Host, 421, healthz and host_kwargs tests
- `tests/unit/mcp_server/test_config.py` - hostname, deploy_env invariant, WR-02, WR-05 tests
- `tests/unit/mcp_server/test_auth_mode.py`, `test_main.py`, `test_gap_tool.py`, `conftest.py` (mcp_server and chat_bot), `tests/integration/test_server_process.py` - opt into `DEPLOY_ENV=local`, new message assertions
- `.env.example`, `tests/unit/test_repo_layout.py`, `docker-compose.dev.yml`, `tests/unit/test_dev_compose.py`, `services/mcp_server/README.md` - env contract and docs

## Decisions Made

- `DEPLOY_ENV` defaults to production on every host, so a host that sets nothing (kind, VM, Cloud Run) refuses auth-off. `K_SERVICE` only forces production.
- `MCP_ALLOWED_HOSTS` is validated strictly (bare lowercase DNS names), exact-match, and never touches `allowed_origins`; the Host guard stays on and never admits the request's own Host.
- `/healthz` stays a FastMCP custom route. The flagged assumption (custom routes bypass the auth provider) was proven by the `AUTH_MODE=on` test, so the fallback of a Starlette route in `build_app` was not needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] chat_bot test fixture also builds `McpSettings(auth_mode="off")`**
- **Found during:** Task 2
- **Issue:** `tests/unit/chat_bot/conftest.py` constructs the server settings with auth off; it would fail under the new guard. It was not in the plan's file list.
- **Fix:** pass `deploy_env="local"`.
- **Files modified:** tests/unit/chat_bot/conftest.py
- **Verification:** `./run-unit-tests.sh --all`
- **Committed in:** 21afbfd

**2. [Rule 1 - Bug] `FAKE_SIGNING_KEY` fixture was 31 characters**
- **Found during:** Task 2 (WR-05)
- **Issue:** the shared fake key would be refused by the new 32-character rule, as would the `sentinel + "-key"` value in the secret-hygiene test.
- **Fix:** lengthened the fixture to 36 characters and padded the sentinel key to 32+.
- **Files modified:** tests/unit/mcp_server/conftest.py, tests/unit/mcp_server/test_config.py
- **Committed in:** 21afbfd

**3. [Rule 2 - Missing critical] Unparsable `MCP_PUBLIC_BASE_URL` must be a clean refusal**
- **Found during:** Task 2 (WR-02)
- **Issue:** `urlsplit` raises `ValueError` on inputs such as an unbalanced IPv6 bracket; that would surface as an unnamed parse error rather than the variable-naming refusal.
- **Fix:** small `_scheme_and_hostname` helper returns no scheme and no hostname on `ValueError`, so the standard refusal applies.
- **Files modified:** services/mcp_server/buddy_mcp/config.py
- **Committed in:** 21afbfd

**4. [Rule 3 - Blocking] Task boundary adjustments**
- Hostname-validation tests live in `test_config.py` (a Task 2 file) but were committed in Task 1 with the validator they test. `_LOOPBACK_PREFIXES` was kept through Task 1 and removed in Task 2 (acceptance criterion `== 0` holds at the end).
- Added one test to `tests/unit/test_dev_compose.py` pinning `DEPLOY_ENV: local` on `mcp_server` and `chat_bot`.

---

**Total deviations:** 4 (1 Rule 1, 1 Rule 2, 2 Rule 3). **Impact on plan:** all necessary to keep the suite green or to make a refusal clean; no scope creep.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required. A developer who already has a `.env` and runs the server by hand must add `DEPLOY_ENV=local` (the README run command now passes it); the dev compose stack sets it already.

## Next Phase Readiness

- 04-03 can mirror the `DEPLOY_ENV` rule in the bot (`MCP_AUTH=none` needs `DEPLOY_ENV=local`); the dev compose already passes it to `chat_bot`.
- 04-06 (compose), 04-07 (kind) and 04-08 (Cloud Run) have the seams: set `MCP_ALLOWED_HOSTS=mcp-server` for pod-to-pod calls, keep `DEPLOY_ENV` unset (production) outside local development. 04-07 must set `Host: mcp-server` on `httpGet` probes; Cloud Run uses tcpSocket probes (RESEARCH Pitfall 9). This plan proves only that `/healthz` obeys the Host guard.
- 04-01 (paused human gate) was not touched.

## Self-Check: PASSED

All listed files exist; commits d15eb4c, 21afbfd, 5152034 are ancestors of HEAD; plan acceptance greps and `./run-unit-tests.sh --all` and `--emulator` pass.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
