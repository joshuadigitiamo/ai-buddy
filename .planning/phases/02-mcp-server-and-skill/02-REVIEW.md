---
phase: 02-mcp-server-and-skill
reviewed: 2026-11-06T00:00:00Z
depth: standard
files_reviewed: 51
files_reviewed_list:
  - docker-compose.test.yml
  - Dockerfile
  - docs/install-guide.md
  - .env.example
  - pyproject.toml
  - requirements-dev.txt
  - run-unit-tests.sh
  - services/mcp_server/buddy_mcp/auth.py
  - services/mcp_server/buddy_mcp/cli.py
  - services/mcp_server/buddy_mcp/config.py
  - services/mcp_server/buddy_mcp/gaplog.py
  - services/mcp_server/buddy_mcp/gap_tool.py
  - services/mcp_server/buddy_mcp/guides_tools.py
  - services/mcp_server/buddy_mcp/handbook_tools.py
  - services/mcp_server/buddy_mcp/__init__.py
  - services/mcp_server/buddy_mcp/__main__.py
  - services/mcp_server/buddy_mcp/models.py
  - services/mcp_server/buddy_mcp/oauth_storage.py
  - services/mcp_server/buddy_mcp/server.py
  - services/mcp_server/buddy_mcp/snapshot.py
  - services/mcp_server/buddy_mcp/stemming.py
  - services/mcp_server/README.md
  - services/mcp_server/requirements.txt
  - skills/digitiamo-buddy/SKILL.md
  - tests/integration/conftest.py
  - tests/integration/test_firestore_gaplog.py
  - tests/integration/test_firestore_oauth_store.py
  - tests/integration/test_server_process.py
  - tests/unit/mcp_server/conftest.py
  - tests/unit/mcp_server/test_auth_mode.py
  - tests/unit/mcp_server/test_auth.py
  - tests/unit/mcp_server/test_config.py
  - tests/unit/mcp_server/test_gaplog.py
  - tests/unit/mcp_server/test_gap_tool.py
  - tests/unit/mcp_server/test_guides_tools.py
  - tests/unit/mcp_server/test_handbook_get.py
  - tests/unit/mcp_server/test_handbook_resource.py
  - tests/unit/mcp_server/test_handbook_search.py
  - tests/unit/mcp_server/test_http_transport.py
  - tests/unit/mcp_server/test_log_hygiene.py
  - tests/unit/mcp_server/test_main.py
  - tests/unit/mcp_server/test_models.py
  - tests/unit/mcp_server/test_no_results.py
  - tests/unit/mcp_server/test_oauth_storage.py
  - tests/unit/mcp_server/test_rate_limit.py
  - tests/unit/mcp_server/test_read_only.py
  - tests/unit/mcp_server/test_skill_package.py
  - tests/unit/mcp_server/test_snapshot.py
  - tests/unit/mcp_server/test_source_fields.py
  - tests/unit/mcp_server/test_tool_surface.py
  - tests/unit/test_repo_layout.py
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-11-06
**Depth:** standard
**Files Reviewed:** 51
**Status:** issues_found

## Summary

The production code (`buddy_mcp/*`, Dockerfile, compose, runner script, Skill, docs) was read in full. The
auth boundary is sound: the domain check is done in `verify_token` (not only the `hd` hint), `email_verified`
is parsed defensively, the bot verifier requires an allowlisted verified e-mail and an expiry, and storage is
always injected. I checked `GoogleTokenVerifier` in the fastmcp source: `client_id` is the Google `sub`, the
audience is enforced, and `email_verified` is taken from tokeninfo or userinfo, so the `_is_true` handling is
correct. No injection, path-traversal or secret-leak issue was found; `handbook_get(section)` is an exact dict
lookup, `guides_permalink` quotes the path, and logging is restricted to counts and exception type names.

The findings are hardening gaps and a behavioural contradiction between the tool descriptions and the Skill.
Test files were only skimmed (conftest, the process test, skip markers), not reviewed assertion by assertion. The
necessity pass (`necessity-review.md`) was not run, so no `necessity:` count is reported.
Fallow structural findings were not provided.

## Warnings

### WR-01: AUTH_MODE=off guard fails open on any host other than Cloud Run

**File:** `services/mcp_server/buddy_mcp/config.py:94-97` (also `.env.example:20-21`)
**Issue:** The only protection against an unauthenticated deployment is `"K_SERVICE" in os.environ`. The
README states the Phase 4 host is undecided (free hosting is the goal), so on any other host (Fly, Render, a VM,
kind exposed through a tunnel) `AUTH_MODE=off` starts normally and serves the handbook to anyone. `.env.example`
ships `AUTH_MODE=off`, and `run-unit-tests.sh` uses it as the fallback env file, so copying it to a deployed
`.env` gives an open server. The code default is `on`, which limits the risk, but the guard is the stated D-13
control and it is host-specific.
**Fix:** Refuse `off` whenever the configuration looks public, not only on Cloud Run:
```python
if self.auth_mode == "off" and (
    "K_SERVICE" in os.environ
    or (self.mcp_public_base_url and self.mcp_public_base_url.startswith("https://"))
):
    raise ValueError("AUTH_MODE=off is refused for a deployed or public https server")
```
Alternatively require an explicit `ALLOW_INSECURE_LOCAL=1` for `off`, and drop `AUTH_MODE=off` from `.env.example`.

### WR-02: Loopback prefix check on MCP_PUBLIC_BASE_URL accepts attacker-style hostnames

**File:** `services/mcp_server/buddy_mcp/config.py:17,68`
**Issue:** `value.startswith(("http://localhost", "http://127.0.0.1"))` also accepts
`http://localhost.evil.example` and `http://127.0.0.1.evil.example`. The value becomes the OAuth proxy
`base_url`, the allowed `Host`/`Origin` entry in `host_kwargs`, and the bot token audience, so a plain-http
public hostname passes the "https only" rule. The input is operator-set, so this is a validator defect rather
than a remote exploit.
**Fix:** Parse the URL and compare the hostname exactly:
```python
parts = urlsplit(value)
if not (parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1"})):
    raise ValueError("mcp_public_base_url must start with https:// (http only for localhost)")
```

### WR-03: Gap log stores raw question text for topics the Skill declares sensitive

**File:** `services/mcp_server/buddy_mcp/gaplog.py:34-65`, `skills/digitiamo-buddy/SKILL.md` ("When there is no answer", "Temi da escalare")
**Issue:** D-10 removes the asker's identity, but `question` is stored verbatim for 90 days. The Skill escalates
personal topics (health, pay, disputes, discipline, contract), and when the handbook has no answer it also
instructs "call `buddy_report_gap` once, with the question". A question such as "ho un certificato medico,
posso ..." or one naming a colleague is then persisted in Firestore, and the README's "nothing that identifies
the asker" claim is not true when the question text names the asker or a third party. No redaction is applied.
**Fix:** Pick one of: (a) the Skill tells Claude to paraphrase to a generic topic and omit names/personal facts
in `question`, and to skip `buddy_report_gap` for escalated personal topics; (b) run the buddy_core redaction
(e-mail/name) on `question` and `tried` before writing. Document the retention and content decision in the
README.

### WR-04: Tool descriptions and server instructions contradict the Skill, causing spurious gap records

**File:** `services/mcp_server/buddy_mcp/server.py:20-23`, `guides_tools.py:26-31`, `handbook_tools.py:19-24`, `gap_tool.py:30-35` vs `skills/digitiamo-buddy/SKILL.md` ("If a search returns `no_results`, try one more query", "Reply exactly")
**Issue:** Every search tool and the server `instructions` say that on `no_results` the model should refuse and
call `buddy_report_gap` immediately. The Skill says to retry with a synonym first, and to log a gap only when
"every search" returned nothing. For a question that needs both sources, a single empty search from one source
satisfies the tool text and writes a gap even when the other source answered. The refusal phrase also differs:
`gap_tool.py` says `'non lo so, chiedi a ...'` while the Skill requires exactly `Non lo so, chiedi a <referente>.`
Clients without the Skill (the Phase 3 bot, Claude Code without the skill installed) follow only the tool text,
so the gap log fills with false positives.
**Fix:** Align the descriptions with the Skill: "if no_results persists after a retry and no source supports an
answer, reply 'Non lo so, chiedi a <referente>.' then call buddy_report_gap once". Add a test in
`test_skill_package.py` or `test_tool_surface.py` that compares the refusal phrase in both places.

### WR-05: OAUTH_JWT_SIGNING_KEY length is documented as 32 bytes minimum but never enforced

**File:** `services/mcp_server/buddy_mcp/config.py:42`, `services/mcp_server/README.md` (env table)
**Issue:** The README says the value is "at least 32 bytes", yet `oauth_jwt_signing_key` is an unconstrained
`SecretStr`. A short or placeholder key is accepted and signs the server's own access tokens, so anyone able to
guess it can mint tokens that pass proxy verification. The test fixture key is already 31 characters, so the
unit tests would not catch a regression.
**Fix:**
```python
oauth_jwt_signing_key: SecretStr | None = None

@field_validator("oauth_jwt_signing_key")
@classmethod
def _check_signing_key(cls, value: SecretStr | None) -> SecretStr | None:
    if value is not None and len(value.get_secret_value()) < 32:
        raise ValueError("oauth_jwt_signing_key must be at least 32 characters")
    return value
```
and lengthen the fake key in `tests/unit/mcp_server/conftest.py`.

## Info

### IN-01: Unbounded query, id and tried inputs

**File:** `services/mcp_server/buddy_mcp/guides_tools.py:101-123`, `handbook_tools.py:81-120`, `gap_tool.py:55-66`
**Issue:** `question` is capped at 2000 characters, but `query`, `id` and `section` have no length limit and are
echoed back in `query` and in the text block. `tried` is truncated only after the whole list is materialised.
Bounded in practice by the request size limit and the rate limiter, but the contract is inconsistent.
**Fix:** Apply the same cap to search queries (reject or truncate at, say, 500 characters) and slice `tried[:MAX_TRIED_ITEMS]` before normalising.

### IN-02: Runtime image has no health check and uses floating, unhashed inputs

**File:** `Dockerfile:18-31`
**Issue:** The `mcp_server` stage has no `HEALTHCHECK`, uses the floating `python:3.12-slim` tag, and installs
with plain `pip install` (no `--require-hashes`). Because `host_origin_protection` rejects unknown `Host`
headers, a probe that hits the pod IP will get a 4xx unless the platform sends the public host; this should be
settled before Phase 4.
**Fix:** Pin the base image by digest, and document or add a probe (or an allowed-host entry) for the chosen host.

### IN-03: Host/Origin allowlist omits the portless loopback origin and IPv6

**File:** `services/mcp_server/buddy_mcp/server.py:60-71`
**Issue:** Origins are `http://localhost:*` and `http://127.0.0.1:*`. A browser client on a default port sends
`http://localhost` with no port, and `[::1]` is not allowed. This causes false rejections for local use only.
**Fix:** Add `http://localhost` and `http://127.0.0.1` without a port if local browser clients matter.

### IN-04: Verified-token cache keeps an offboarded user valid for up to five minutes

**File:** `services/mcp_server/buddy_mcp/auth.py:35,134`
**Issue:** `cache_ttl_seconds=300` means a revoked Google token or a removed account still passes
`verify_token` until the cache entry expires. This is an acceptable trade-off, but it is not stated in the
README's Authentication section.
**Fix:** Note the five-minute window in the README, or lower the TTL.

---

_Reviewed: 2026-11-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
