---
phase: 02-mcp-server-and-skill
plan: 05
subsystem: auth
tags: [mcp, fastmcp, oauth-proxy, multiauth, google-oidc, service-account, rate-limit, host-origin-guard]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "build_oauth_storage (memory or Fernet-encrypted Firestore) and OAuthStorageError (plan 02-03)"
  - phase: 02-mcp-server-and-skill
    provides: "five-tool build_server, McpSettings gap fields, conftest fixtures (plans 02-01, 02-04)"
provides:
  - "build_auth(settings, *, storage, sa_verifier): OAuthProxy for @digitiamo.com Google users, wrapped in MultiAuth with a Google service-account ID-token verifier for the bot (D-12); None with one WARNING when AUTH_MODE=off"
  - "DomainRestrictedGoogleVerifier (verified e-mail, exact domain, hd when present) and ServiceAccountIdTokenVerifier (JWKS, issuer, audience, e-mail allowlist, email_verified, mandatory exp)"
  - "McpSettings auth, OAuth storage and rate-limit fields; K_SERVICE guard refusing AUTH_MODE=off on Cloud Run (D-13); errors name variables only"
  - "caller_identity and a per-identity RateLimitingMiddleware in build_server (D-14)"
  - "host_kwargs(settings) and build_app(mcp, settings): strict Host/Origin guard (T-02-33)"
affects: [02-07 composition root (must pass host_kwargs to the process runner, build storage and auth, read the new env vars), 03 bot (D-12 contract), 04 deploy (K_SERVICE marker, MCP_PUBLIC_BASE_URL, consent screen Internal)]

actuals:
  tokens: 12200
  tasks: 3
  commits: 5
plan_head_before: 71d9a7ef0b44f0bc27efafb61a76533e00a3200d
plan_head_after: d4200233f6d0750ba8170b39cdd19fb4b1658ce2

tech-stack:
  added: []
  patterns:
    - "Auth provider composed outside the server: build_auth returns OAuthProxy or MultiAuth, build_server only receives it"
    - "Verifiers subclass fastmcp's GoogleTokenVerifier and JWTVerifier and add checks after the parent verdict"
    - "Tests sign bot ID tokens with fastmcp's RSAKeyPair and inject the public key; Google is never contacted"
    - "Settings model validator raises one error listing variable names only; hide_input_in_errors keeps values out"

key-files:
  created:
    - services/mcp_server/buddy_mcp/auth.py
    - tests/unit/mcp_server/test_auth.py
    - tests/unit/mcp_server/test_auth_mode.py
    - tests/unit/mcp_server/test_config.py
    - tests/unit/mcp_server/test_rate_limit.py
  modified:
    - services/mcp_server/buddy_mcp/config.py
    - services/mcp_server/buddy_mcp/server.py
    - tests/unit/mcp_server/conftest.py
    - tests/unit/mcp_server/test_http_transport.py
    - tests/unit/mcp_server/test_gap_tool.py

key-decisions:
  - "email_verified accepts the boolean True or the string 'true' only. Google tokeninfo returns the string form, and plain truthiness would admit the string 'false'. A test covers False, None, 'false', '' and 0."
  - "DomainRestrictedGoogleVerifier and the proxy verifier are built with audience=GOOGLE_CLIENT_ID so tokens minted for another OAuth client are rejected (the plan did not require it; research Pattern 3 shows it)."
  - "ServiceAccountIdTokenVerifier rejects tokens without exp: fastmcp's JWTVerifier accepts a missing exp, which would make a signed token immortal."
  - "The Host/Origin guard uses fastmcp's own options (http_app host_origin_protection=True, allowed_hosts, allowed_origins), not Starlette middleware. host_kwargs returns them as dict[str, Any] (the plan said dict[str, object], which mypy --strict rejects when unpacked into typed parameters)."
  - "The K_SERVICE guard triggers on the variable being present, even if empty, which is the stricter reading of 'set'."
  - "Loopback redirect patterns 'http://localhost:*' and 'http://127.0.0.1:*' are accepted as written by the proxy; registrations for claude.ai, localhost:6274 and 127.0.0.1:33418 succeed and https://evil.example/cb is refused."
  - "Requirements MCP-07 and MCP-01 stay as they are in REQUIREMENTS.md: requirements.ready-ids reports both blocked because a sibling plan of this phase (02-07) also declares them and has no SUMMARY yet. MCP-07 still needs the live checks (flagged assumptions A1, A2, A5, A8) in 02-07."

patterns-established:
  - "make_auth_server fixture builds the server with auth on, an in-memory store and a verifier pinned to a test key"
  - "Config tests delete every McpSettings variable first, because run-unit-tests.sh loads an env file into the container"
  - "A spy MemoryStore counts writes to prove the proxy persists into the store it was given"

requirements-completed: [MCP-07, MCP-01]

coverage:
  - id: D1
    description: "Anonymous and malformed or wrongly signed callers get 401 with resource_metadata; the bot's service-account ID token reaches tools/list through MultiAuth"
    requirement: MCP-07
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_no_token_is_401_with_resource_metadata"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_bot_token_lists_tools"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_bot_token_rejections"
        status: pass
    human_judgment: false
  - id: D2
    description: "Human path accepts only verified e-mails of exactly the allowed domain (case-insensitive), rejects subdomain, suffix and hd-mismatch cases"
    requirement: MCP-07
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_other_domains_are_rejected"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_hosted_domain_mismatch_is_rejected"
        status: pass
    human_judgment: false
  - id: D3
    description: "OAuth metadata advertises registration, S256 and CIMD; redirects limited to claude.ai and loopback; proxy uses the store it was given; serving writes nothing to disk"
    requirement: MCP-07
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_authorization_server_metadata"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth.py#test_registration_with_a_foreign_redirect_uri_is_rejected"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_serving_writes_nothing_to_disk"
        status: pass
    human_judgment: false
  - id: D4
    description: "Foreign Host and Origin are rejected before any tool; AUTH_MODE=off is refused when K_SERVICE is set; rate limit is per identity with burst N passing and N+1 refused"
    requirement: MCP-07
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_http_transport.py#test_foreign_host_is_rejected_before_any_tool"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_auth_mode.py#test_auth_off_is_refused_on_cloud_run"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_rate_limit.py#test_burst_passes_then_the_next_request_is_refused"
        status: pass
    human_judgment: false
  - id: D5
    description: "A real Google login restricted to the Workspace, and a real Google-signed service-account token, behave as the fakes assume (assumptions A1, A2, A5, A8)"
    requirement: MCP-07
    verification: []
    human_judgment: true
    rationale: "Fakes stand in for Google; the live checkpoint is scheduled in plan 02-07"

duration: ~8min
completed: 2026-11-06
status: complete
---

# Phase 2 Plan 5: Authentication, Domain Restriction and Rate Limiting Summary

**Google OAuth proxy restricted to verified `@digitiamo.com` accounts, Google-signed service-account ID tokens for the bot through MultiAuth, a Cloud Run-proof `AUTH_MODE=off` switch, a strict Host/Origin guard and a per-identity token bucket, all tested with fakes and no network.**

## Performance

- **Duration:** about 8 min (start 2026-11-06T21:16:44Z)
- **Completed:** 2026-11-06
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 TDD-flagged)
- **Files modified:** 10 (5 created, 5 modified)

## Accomplishments

- Tracer: with auth on, `POST /mcp` without a token returns 401 whose `WWW-Authenticate` carries `resource_metadata="http://localhost/.well-known/oauth-protected-resource/mcp"`. A bot token (iss `https://accounts.google.com`, aud = public base URL, allowlisted verified e-mail) reaches `tools/list` and sees the five tools. Wrong audience, e-mail off the allowlist, `email_verified` false, expired, wrong issuer, missing `exp` and a garbage token all give 401.
- Human path: the domain check takes the part after the last `@`, lowercases it and compares it exactly; `a@digitiamo.com` and `A@DIGITIAMO.COM` pass, while `x@gmail.com`, `a@sub.digitiamo.com`, `a@digitiamo.com.evil.example`, a missing or unverified e-mail and any `hd` (claims or profile) naming another domain are refused. Verification results are cached 300 s, 100 entries.
- OAuth facade: the protected-resource document names `http://localhost/mcp`; the authorization-server document advertises a registration endpoint, `S256` and client-ID metadata documents; registration with `https://evil.example/cb` is refused while claude.ai, `localhost` and `127.0.0.1` callbacks succeed. The proxy gets `require_authorization_consent=True` and `hd`, `access_type=offline`, `prompt=consent` as authorize parameters. A spy store records writes during a registration, so the store passed in is the one used.
- No state on disk: with `HOME` and the working directory in empty temp directories, an anonymous initialize, an authenticated `guides_search`, both metadata GETs and one registration leave HOME, cwd, the artifact directory and fastmcp's home untouched. A direct check showed the default proxy store does create `fastmcp/oauth-proxy/<id>` there, so the test is not vacuous.
- Host/Origin: foreign `Host` or `Origin` gets a 4xx before any tool; `localhost` without `Origin`, `https://claude.ai` and `http://localhost:6274` are served; a configured public host is served and others are not.
- Off switch and settings: `AUTH_MODE=off` builds no provider and logs one WARNING containing `AUTH_MODE=off`; with `K_SERVICE` set, settings refuse it with an error naming `AUTH_MODE` and `K_SERVICE` (by kwarg and by environment). Missing `MCP_PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_JWT_SIGNING_KEY` are each named; sentinel secrets appear in no error text or repr; `OAUTH_STORAGE` accepts only `memory` or `firestore`; `http://example.com` is refused, `http://localhost:8000` and `https://buddy.example` accepted; `BOT_SA_EMAILS` is split and lowercased; RPS must be above 0, burst at least 1.
- Rate limit: with burst 3 and a near-zero refill, three `tools/list` calls succeed and the fourth returns HTTP 200 with a JSON-RPC error containing `Rate limit exceeded`; a second bot is still served; with auth off the shared `anonymous` identity hits the same boundary. Refill timing is left to fastmcp (backstop in the plan).

## Task Commits

1. **Task 1 (tracer): bot token through MultiAuth, 401 with resource metadata** - `72bd752` (feat)
2. **Task 2: human path, OAuth facade, Host/Origin, no-disk** - RED `508aad9` (test), GREEN `eba9e76` (feat)
3. **Task 3: AUTH_MODE guard, settings bounds, rate limit** - RED `a123793` (test), GREEN `d420023` (feat)

## TDD Gate Compliance

- **Task 2:** `test(02-05)` `508aad9` precedes `feat(02-05)` `eba9e76`. RED run: 4 failed, 47 passed. The failures were `test_foreign_host_is_rejected_before_any_tool`, `test_foreign_origin_is_rejected` and `test_public_host_is_served_and_others_are_not` on `assert 400 <= 200` (a foreign Host or Origin was served), and `test_host_kwargs_cover_the_public_host_and_loopback` on `KeyError: 'allowed_hosts'` against the stub that returns `{}`. Semantic assessment: the targets ran and failed on the planned behavior; the stub (`host_kwargs` returning `{}`, `build_app(mcp, settings=None)`) kept imports valid so no failure is a collection error. The other 47 tests (domain, hd, redirect allowlist, store pass-through, no-disk, metadata) passed immediately because the tracer already delivered those behaviors; they are regression locks, not RED evidence.
- **Task 3:** `test(02-05)` `a123793` precedes `feat(02-05)` `d420023`. RED run: 12 failed, 29 passed. Failures: `test_auth_off_builds_no_provider_and_warns_once` (`assert 0 == 1`, no WARNING), the two K_SERVICE tests (`DID NOT RAISE ValidationError`), five RPS/burst bound tests (`DID NOT RAISE`), `test_rate_limit_defaults` and `test_rate_limit_from_the_environment` (missing field), and the two burst-boundary tests (`KeyError: 'error'`, the fourth request was served). Semantic assessment: every failure is the planned behavior missing. mypy also reported `attr-defined` for `rate_limit_rps` and `rate_limit_burst` at the RED commit; that is the same missing-field signal and was gone at GREEN. `test_another_identity_is_still_served` passed at RED because nothing was limited yet; it became meaningful at GREEN. After GREEN: 6 + 32 + 3 passed.
- `workflow.tdd_mode` is not enabled and the `tdd-red-evidence` classifier has no pytest adapter, so it was not run; RED evidence is the real pytest output above.
- Task 1 carries `type="tracer"` and is a single `feat` commit; the tracer `<verify>` (test file plus `--all`) was re-run green before Task 2 started.

## Verification

- `./run-unit-tests.sh --all`: exit 0. ruff check, ruff format --check and mypy --strict clean. **557 passed, 17 skipped** (the same 17 local-only or emulator-only skips as before), coverage 97.70% (gate 80%). `auth.py` 100%, `config.py` 98%, `server.py` 98%.
- Per-file runs: `test_auth.py` 40 passed, `test_http_transport.py` 11, `test_serving_writes_nothing_to_disk` 1, `test_auth_mode.py` 6, `test_config.py` 32, `test_rate_limit.py` 3.
- Acceptance greps: `client_storage=` 1, `MultiAuth(` 1, claude.ai callback 1, `SecretStr` in config.py 4, `def test_serving_writes_nothing_to_disk` 1, `cache_ttl_seconds` 1, `require_authorization_consent=True` 1, `def host_kwargs` 1, `K_SERVICE` in config.py 3, `RateLimitingMiddleware(` 1, `def caller_identity` 1.
- `./run-unit-tests.sh --emulator` was not run (no Firestore code changed in this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] email_verified string "false" would pass a plain truthiness check**
- **Found during:** Task 1 (reading `GoogleTokenVerifier`: it copies `tokeninfo["email_verified"]`, which Google returns as a string)
- **Issue:** the plan says "requires `email_verified` truthy"; the string `"false"` is truthy in Python.
- **Fix:** `_is_true` accepts the boolean `True` or the string `"true"` and nothing else; tests cover both spellings and the rejects.
- **Files modified:** `services/mcp_server/buddy_mcp/auth.py`, `tests/unit/mcp_server/test_auth.py`
- **Commit:** `72bd752`, `508aad9`

**2. [Rule 2 - Missing critical] Bot tokens without `exp` were accepted**
- **Found during:** Task 1 (read `JWTVerifier.load_access_token`: expiry is checked only when `exp` is present)
- **Fix:** `ServiceAccountIdTokenVerifier` returns None when the access token has no expiry; `no-expiry` case in `test_bot_token_rejections`.
- **Commit:** `72bd752`

**3. [Rule 2 - Missing critical] Google user tokens were not bound to this app's OAuth client**
- **Found during:** Task 1 (`GoogleTokenVerifier(audience=None)` accepts any valid Google token)
- **Fix:** the domain verifier is built with `audience=GOOGLE_CLIENT_ID`.
- **Commit:** `72bd752`

**4. [Rule 3 - Blocking] Existing tests built `McpSettings` without auth values**
- **Found during:** Task 1 (the code default for `AUTH_MODE` became `on`)
- **Fix:** `settings` and `server_for` fixtures and the `McpSettings(...)` calls in `test_gap_tool.py` pass `auth_mode="off"`; the env-based gap test sets `AUTH_MODE=off`.
- **Files modified:** `tests/unit/mcp_server/conftest.py`, `tests/unit/mcp_server/test_gap_tool.py`
- **Commit:** `72bd752`

**5. [Rule 3 - Blocking] `host_kwargs` return type**
- **Found during:** Task 2
- **Issue:** the plan's `dict[str, object]` fails `mypy --strict` when unpacked into `http_app(**...)`.
- **Fix:** return `dict[str, Any]`.
- **Commit:** `508aad9`, `eba9e76`

**6. [Rule 3 - Blocking] Wrong tool name in the tracer test**
- **Found during:** Task 1 (first run: `guides_get` expected, `guides_get_section` is the real name)
- **Fix:** test constant corrected before the commit.
- **Commit:** `72bd752`

**Total deviations:** 6 auto-fixed (1 bug, 2 missing critical, 3 blocking). **Impact:** 1 and 2 tighten the authentication boundary beyond the plan; nothing widened scope.

### Plan variance (not a deviation)

- Extra tests beyond the behavior list: `email_verified` as the string `"true"`, `hd` in the profile versus claims, a registration per allowed redirect (claude.ai, localhost, 127.0.0.1), loopback and claude.ai origins served, `allowed_email_domain` normalization, the `K_SERVICE` guard read from the environment.
- `K_SERVICE` presence (not value) triggers the guard, as noted in the decisions.

## Authentication Gates

None. No Google call was made; the verifiers are driven by a patched parent verifier and by tokens signed with a test RSA key.

## Bot-to-server contract for Phase 3 (D-12)

The bot sends `Authorization: Bearer <Google ID token minted by its service account, audience = MCP_PUBLIC_BASE_URL>`. Its service-account e-mail must be listed in `BOT_SA_EMAILS`. The server checks the signature against Google's JWKS, issuer (`https://accounts.google.com` or `accounts.google.com`), audience, expiry (required), e-mail allowlist and `email_verified`. This resolves the STATE.md blocker on the bot-to-MCP mechanism.

## Requirements

`requirements.ready-ids` returned both IDs as blocked: plan 02-07 also declares MCP-07 and MCP-01 and has no SUMMARY. REQUIREMENTS.md therefore keeps MCP-07 Pending and MCP-01 Complete; the shared-ID gate will release MCP-07 when 02-07 finishes. Frontmatter `requirements-completed` copies the plan's list as the workflow requires.

## Known Stubs

None.

## Threat Flags

None. The OAuth routes (`/register`, `/authorize`, `/token`, consent, callback, both well-known documents) come from fastmcp's OAuthProxy and are the surface T-02-16 to T-02-18 already cover.

## Open items for later plans

- 02-07 must read the new variables (`AUTH_MODE`, `MCP_PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_JWT_SIGNING_KEY`, `ALLOWED_EMAIL_DOMAIN`, `BOT_SA_EMAILS`, `OAUTH_STORAGE`, `OAUTH_STORAGE_ENCRYPTION_KEY`, `OAUTH_COLLECTION`, `RATE_LIMIT_RPS`, `RATE_LIMIT_BURST`), build the storage with `build_oauth_storage`, call `build_auth`, and pass `host_kwargs(settings)` to the process runner. `.env.example` does not list them yet.
- The host allowlist is the host of `MCP_PUBLIC_BASE_URL`; behind Cloud Run the request `Host` must equal it (custom domain or the service URL), which 02-07 and Phase 4 must keep aligned (A8).
- Flagged assumptions A1 (consent screen Internal), A2 (tokeninfo/userinfo claims for Workspace users), A5 (service-account ID token claims) and A8 stay unresolved until the live checkpoint in 02-07. A6: if Phase 4 picks a host other than Cloud Run it must add that host's marker next to `K_SERVICE`.
- The proxy warns when `OAUTH_JWT_SIGNING_KEY` is shorter than 12 characters; settings do not enforce a minimum length.

## Self-Check: PASSED
