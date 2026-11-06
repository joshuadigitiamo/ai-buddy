---
phase: 02-mcp-server-and-skill
plan: 07
subsystem: infra
tags: [fastmcp, streamable-http, firestore-emulator, docker, google-oauth, composition-root]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "server, auth, gap log, OAuth storage and Skill from plans 02-01 to 02-06"
provides:
  - "python -m buddy_mcp composition root (cli.main) wiring every real adapter"
  - "real-process end-to-end test on the Firestore emulator (five tools, cited search, gap document)"
  - "Dockerfile mcp_server stage (non-root uid 10001, buddy_core and buddy_mcp only)"
  - ".env.example server keys plus layout tests that keep secrets and the emulator host out"
  - "services/mcp_server/README.md operator documentation"
  - "live Google OAuth flow verified through an MCP client (claude.ai connector check deferred)"
affects: [phase-03-chat-bot, phase-04-infra-deploy]

plan_head_before: 105343fb32e97495fcc3b5ee900879c1453d04ff
plan_head_after: e9a5b0965fa63dcd41f1a7ce875e0f5b639d2dc3

actuals:
  tokens: 7666
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "composition root: cli.main is the only place real adapters are built; serve is injectable for offline tests"
    - "startup failures: one ERROR line naming variables, exit 1, never values or tracebacks"
    - "lazy Firestore client: startup makes no network call"

key-files:
  created:
    - services/mcp_server/buddy_mcp/cli.py
    - services/mcp_server/buddy_mcp/__main__.py
    - services/mcp_server/README.md
    - tests/unit/mcp_server/test_main.py
    - tests/integration/test_server_process.py
  modified:
    - services/mcp_server/buddy_mcp/config.py
    - Dockerfile
    - .env.example
    - tests/unit/test_repo_layout.py

key-decisions:
  - "Live-login check closed as partially verified: full MCP OAuth flow proven with a fastmcp OAuth client; claude.ai connector and non-digitiamo rejection deferred to Phase 4"
  - "Runtime image does not bake the index; ARTIFACT_DIR points at a mounted directory (handoff decided in Phase 4)"

requirements-completed: [MCP-01, MCP-05, MCP-07]

coverage:
  - id: D1
    description: "python -m buddy_mcp runs as a real process, stateless JSON HTTP, five tools, cited handbook_search, gap document with six D-10 keys in the emulator"
    requirement: "MCP-01"
    verification:
      - kind: integration
        ref: "tests/integration/test_server_process.py (./run-unit-tests.sh --emulator, 4 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "buddy_report_gap writes the gap document end to end from a real server process"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/integration/test_server_process.py (./run-unit-tests.sh --emulator)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Startup refuses bad configuration with one ERROR line, no traceback, no secret values"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_main.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "mcp_server image builds and runs as uid 10001"
    verification:
      - kind: other
        ref: "docker build --target mcp_server -t ai-buddy-mcp . && docker run --rm --network none ai-buddy-mcp python -c 'import buddy_mcp.cli; import os; print(os.getuid())'"
        status: pass
    human_judgment: false
  - id: D5
    description: ".env.example holds only non-secret contract keys; README documents every server variable and the auth setup"
    verification:
      - kind: unit
        ref: "tests/unit/test_repo_layout.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "Live Google login with an @digitiamo.com account (MCP-07 live check)"
    requirement: "MCP-07"
    verification:
      - kind: manual_procedural
        ref: "Task 3 section: OAuth flow with fastmcp client passed; claude.ai connector and non-digitiamo account deferred to Phase 4"
        status: unknown
    human_judgment: true
    rationale: "Needs a public HTTPS URL, a Google OAuth client and a claude.ai organization owner; only part of it could run"

duration: n/a
completed: 2026-11-06
status: complete
---

# Phase 2 Plan 07: Runnable Server, Image and Live Login Summary

**`python -m buddy_mcp` composition root serving five tools over stateless JSON HTTP, proven as a real process on the Firestore emulator, a non-root `mcp_server` image, an env contract with README, and the Google OAuth flow verified live through an MCP client.**

## Performance

- **Duration:** not tracked across the checkpoint pause
- **Completed:** 2026-11-06
- **Tasks:** 3 (tracer, auto, checkpoint)
- **Files modified:** 9 (753 insertions, no deletions)

## Accomplishments

- `cli.main` builds the index snapshot once, the lazy Firestore gap log, the OAuth store and auth provider (when auth is on) and the server, logs one INFO line (counts, build id, auth mode) and serves with `stateless_http=True, json_response=True`.
- Real-process test on the emulator: initialize returns 200 JSON without a session id, a bad Host is rejected, a fastmcp client lists five tools, `handbook_search` returns a `handbook://` source, `buddy_report_gap` writes a document with the six D-10 keys, and stderr never contains the question.
- Startup failures (missing variables, missing or empty artifact directory, `AUTH_MODE=off` with `K_SERVICE`, missing `GOOGLE_CLOUD_PROJECT`, missing signing key) exit 1 with one ERROR line; a secret sentinel never appears in output.
- Docker `mcp_server` stage: `USER 10001`, only `buddy_core` and `buddy_mcp` code, no new packages.
- `.env.example` extended with fifteen non-secret keys; layout tests reject secret-named keys and `FIRESTORE_EMULATOR_HOST`.
- Operator README: variables, Google OAuth client and Internal consent screen, bot contract (D-12), TTL command, rate-limit semantics, logging policy, local run commands.

## Verification (from the implementing executor)

- `./run-unit-tests.sh --all`: 603 passed, 18 skipped, coverage 97.68%.
- `./run-unit-tests.sh --emulator`: 4 passed.
- Image build succeeded; the container uid is 10001.

These were not re-run in this continuation (no code changed).

## Task Commits

1. **Task 1 (tracer): real-process server, five tools over HTTP on the emulator** - `9144432` (feat)
2. **Task 2: env contract and operator README** - `e9a5b09` (docs)
3. **Task 3: live Google login checkpoint** - no commit (verification only)

**Plan metadata:** recorded in the docs commit that adds this SUMMARY.

## Task 3: Live Google login (checkpoint) - PARTIALLY VERIFIED

Performed with Joshua on 2026-11-06.

**Setup:** GCP project `ai-buddy-dev` under the digitiamo.com organization; Google Auth Platform consent screen user type Internal; Web OAuth client `ai-buddy-mcp` with redirect URI `<public tunnel URL>/auth/callback`. The server ran as the `ai-buddy-mcp` image with `AUTH_MODE=on`, `OAUTH_STORAGE=memory` and the Firestore emulator for gaps, exposed through a temporary Cloudflare quick tunnel (torn down afterwards). Secrets lived only in a file outside the repository; none were committed or displayed.

**Passed:**

- Unauthenticated `POST /mcp` returns 401 with `WWW-Authenticate: Bearer ... resource_metadata=<url>/.well-known/oauth-protected-resource/mcp`; protected-resource and authorization-server metadata are served (issuer, `/authorize`, `/token`, `/register`).
- `claude mcp add --transport http` registered the server and Claude Code reported "Needs authentication", so OAuth discovery works. The interactive `/mcp` login was not clicked through.
- Full MCP OAuth flow end to end with a fastmcp OAuth client (the same protocol Claude Code uses): dynamic client registration, server consent page, Google login with an @digitiamo.com account (Internal app), callback, token. `list_tools` returned exactly the five tools; `handbook_search("ferie")` returned the "Ferie e Permessi" page with a `handbook://` source; `handbook_get()` returned the table of contents with `source_url` and revision dates.

**Not run (deferred to Phase 4):**

- claude.ai custom connector and the Skill-in-claude.ai answer check: the claude.ai organization only lets an organization owner add custom connectors ("Chiedi a un proprietario dell'organizzazione").
- Login with a non-digitiamo Google account: not attempted. The Internal consent screen should block it at Google; the server-side domain rule is covered by offline tests.
- Restart persistence: not applicable, storage was `memory`.

The live check is **not** marked fully passed.

**MCP-07 status:** marked complete by user decision (Joshua, 2026-11-06). Auth is implemented and the Google OAuth flow was verified live through an MCP client; the two live checks above (claude.ai connector, non-digitiamo account rejection) are carried to Phase 4 as pending items in STATE.md.

## Deferred to Phase 4

| Item | Reason | Needs |
|------|--------|-------|
| claude.ai connector live check (login, five tools, Skill answer citing `handbook://` and a revision date) | custom connectors can only be added by an organization owner | an org owner adds the connector against the Phase 4 host |
| non-digitiamo account rejection tested live | not performed | a second Google account outside digitiamo.com |
| Firestore-backed OAuth store: restart persistence and latency within claude.ai limits (A7) | storage was `memory` | run with `OAUTH_STORAGE=firestore` on the Phase 4 host |

## Files Created/Modified

- `services/mcp_server/buddy_mcp/cli.py` - composition root, `main(argv, *, serve)`
- `services/mcp_server/buddy_mcp/__main__.py` - `python -m buddy_mcp`
- `services/mcp_server/buddy_mcp/config.py` - adds `google_cloud_project`
- `Dockerfile` - `mcp_server` stage, non-root
- `tests/unit/mcp_server/test_main.py` - offline startup and failure-mode tests
- `tests/integration/test_server_process.py` - real-process emulator test
- `.env.example` - non-secret server keys
- `tests/unit/test_repo_layout.py` - secret and emulator guards on `.env.example`
- `services/mcp_server/README.md` - operator documentation

## Decisions Made

- The live-login checkpoint closes as partially verified with the deferrals above; MCP-07 is marked complete by user decision on 2026-11-06, with the claude.ai connector check and the non-digitiamo rejection test carried to Phase 4.
- The index is not baked into the image; it is read from a mounted `ARTIFACT_DIR` at cold start (handoff decided in Phase 4).

## Deviations from Plan

None recorded - the implementing executor reported no deviations. Task 3 ended in a partial result rather than "approved" or "deferred"; this is a checkpoint outcome, not an auto-fix.

## Issues Encountered

- claude.ai connector setup was blocked by organization permissions, not by the server. The same protocol was exercised with an MCP client instead.

## User Setup Required

External services were configured for the live check (GCP project, OAuth client, Internal consent screen); values stayed outside the repository. See `services/mcp_server/README.md` for the steps.

## Threat Flags

None. The only new surface is the process entry point and image already covered by T-02-28 to T-02-32.

## Known Stubs

None.

## Next Phase Readiness

- The server runs from the environment and from the image; Phase 3 (chat bot) can consume the documented bot contract.
- Phase 4 owns hosting, the claude.ai connector check, the non-digitiamo rejection test, Firestore OAuth storage and the TTL policy.

---
*Phase: 02-mcp-server-and-skill*
*Completed: 2026-11-06*

## Self-Check: PASSED

- FOUND: services/mcp_server/buddy_mcp/cli.py, `__main__.py`, services/mcp_server/README.md, tests/unit/mcp_server/test_main.py, tests/integration/test_server_process.py
- FOUND commits: 9144432, e9a5b09
