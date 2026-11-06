# Phase 2: MCP Server and Skill - Research

**Researched:** 2026-11-06
**Domain:** Remote MCP server (Python, streamable-http, stateless JSON), Google OAuth for claude.ai/Claude Code, in-memory Italian FTS, Firestore gap log, Claude Skill packaging
**Confidence:** HIGH on server library/API behaviour (smoke-tested in Docker against the real packages), MEDIUM on live Google/claude.ai OAuth (cannot be exercised in this environment)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Carried forward (not re-discussed)**
- Phase 1 D-11: index loaded at cold start only, no hot reload. D-12: `ArtifactStore` local-dir only; host handoff decided in Phase 4.
- Phase 1 D-21: Guides index is English; the caller (Skill/bot) bridges Italian -> English keywords for `guides_search`.
- Phase 1: handbook citation is `handbook://<page_id>`, page_id = file stem; `index.db` schema 1.0.0. No ClickUp anywhere (D-25..D-27).
- Public repo: no handbook content, no employee names committed.

**Handbook search and citations**
- **D-01:** `handbook_search` uses an **in-memory SQLite FTS5 table built at cold start** from `handbook_pages`. `index.db` schema stays 1.0.0; `jobs/sync` untouched. Query building reuses the safe `to_match_query` approach (quoted tokens, bound MATCH parameter).
- **D-02:** Italian stemming: apply an Italian Snowball stemmer (e.g. `snowballstemmer`, Python) to page text and query before FTS indexing/matching. New runtime dependency, pinned like the Phase 1 pins. Phase 5 Recall validates.
- **D-03:** A `handbook_search` hit = **whole page** (full markdown + citation). Pages are small (~170 words avg).
- **D-04:** Handbook source URL = `handbook://<page_id>` only (no web URL; no base-URL env). Revision date from `revision_date_iso`.
- **D-05:** Guides source URL = GitHub permalink pinned to the index's `guides_commit_sha`: `https://github.com/<owner>/<repo>/blob/<sha>/<file>#L<start>-L<end>`. Repo web base from config/env. Private repo -> 404 for others until rollout (consistent with D15).

**Tool output contract**
- **D-06:** Results are **structured** (typed return models -> `outputSchema` + `structuredContent`: e.g. `source_url`, `revision_date`, `video_url`, `title`, `text`) **plus a short text rendering** for clients that ignore structured output. The Phase 3 bot parses fields, not prose. - **Reversibility:** costly - output schema is the contract consumed by the Phase 3 bot and the Skill.
- **D-07:** `handbook_get()` with no section returns a **table of contents** (page_id, title, revision date); with a section returns that page.
- **D-08:** No match -> `{results: [], status: "no_results", query}`; not an MCP error (`isError` false). Skill instructs refuse + `buddy_report_gap`.
- **D-09:** Search tools return 5 results by default with an optional `limit` parameter capped at 10.
- **D-10:** Gap log document: `question`, timestamp, marker `"nessuna fonte trovata"`, `expire_at` (Firestore TTL, default **90 days**, configurable by env), plus optional queries/tools tried and the index `build_id`. **Never** any user identity (no user id, email, IP, session id).

**Auth, bot-to-server, storage**
- **D-11:** Server library chosen by the researcher: standalone `fastmcp` (built-in Google OAuth proxy) vs official `mcp` SDK FastMCP (resource-server only). Criterion: claude.ai custom connector, Claude Desktop and Claude Code can complete the Google login restricted to `@digitiamo.com`, while still stateless + JSON responses.
- **D-12:** Bot-to-server auth (resolves STATE.md Phase 2 blocker): the bot's **service account mints a Google-signed ID token**; server verifies signature, audience and an allowlist of SA emails from env. No shared secret. Tests use a fake verifier.
- **D-13:** Auth off via env flag (e.g. `AUTH_MODE=off`) for local/kind only; server **refuses to start with auth off when `K_SERVICE` is set** (Cloud Run marker) and logs a loud warning. Covered by a test.
- **D-14:** Rate limiting = **in-memory token bucket per caller identity, per instance**, limits from env. Inexact across instances - accepted for single user. No database involvement.
- **D-15:** Gap log behind a **`GapLog` port** with a **Firestore adapter** (keeps PLAN D10 and MCP-05). Adapter tested against the Firestore emulator in Docker; tools tested with a fake. Mirrors the Phase 1 `ArtifactStore` pattern. - **Reversibility:** reversible - backend swap is a new adapter.

**Skill `digitiamo-buddy`**
- **D-16:** Referral contacts: the Skill commits a **topic -> role map** only; the model resolves the actual person/email via `handbook_search` (handbook keeps work contacts, Phase 1 D-16). No names in the repo.
- **D-17:** Escalation topic list: **Claude drafts** (from the test handbook + usual sensitive areas: salary, health/sickness, harassment, disciplinary, contract changes, personal data), **Joshua reviews and approves** before execution of the Skill task (checkpoint).
- **D-18:** SKILL.md instructions in **English**; answer templates and refusal phrases in **Italian** (answer, fonte, owner/referente, data di revisione; "non lo so, chiedi a ..."). Includes the Italian -> English keyword bridge for `guides_search`.
- **D-19:** One-page install guide covers **claude.ai custom connector + Skill upload, Claude Desktop, Claude Code** (`claude mcp add --transport http` + skill folder).

### Claude's Discretion
- Exact field names of the output models; text rendering format.
- Server config shape (pydantic-settings like `jobs/sync`), env var names, logging (no question text in INFO logs beyond what gap log stores - planner decides).
- `handbook://` resource listing behaviour (resource template vs listed resources).
- Default rate-limit numbers; snowball token handling details (stopwords, prefix match on top of stemming).
- `guides_get_section(id)` id = existing `chunk_key`.

### Deferred Ideas (OUT OF SCOPE)
- Gap log backend Firestore vs Postgres (Neon/Supabase EU free tier) - decide in Phase 4 with hosting (free-hosting goal).
- Vector search (`sqlite-vec` or pgvector) - only if Phase 5 Guides Recall@5 < 0.8 (D5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-01 | streamable-http, stateless, JSON responses, no persistent SSE, no state on container FS | `fastmcp` 4.1.6 `http_app(stateless_http=True, json_response=True)` verified: `initialize` -> 200 `application/json`, no `mcp-session-id`, `GET /mcp` -> 405. OAuth proxy default file store MUST be overridden (Pitfall 1) |
| MCP-02 | Exactly five namespaced tools | `@mcp.tool` x5 + test asserting the exact set; tool annotations via `ToolAnnotations` |
| MCP-03 | Source URL + revision date (+ `video_url`) on every output | Typed pydantic models + `ToolResult(content=..., structured_content=...)` with `output_schema`; Guides revision-date semantics is an Open Question |
| MCP-04 | No-results explicit | `{status:"no_results", results:[], query}` shape (D-08), `isError` false verified |
| MCP-05 | Gap log -> Firestore doc, no user id | `google-cloud-firestore` 2.34.1 `AsyncClient`; emulator image + roundtrip verified |
| MCP-06 | Resource `handbook://{pagina}` | `@mcp.resource("handbook://{pagina}")` listed via `resources/templates/list` (verified) |
| MCP-07 | Google OAuth `@digitiamo.com`, read-only, rate limit, auth off for local only, bot auth defined | `OAuthProxy` (Google endpoints) + `MultiAuth` + SA ID-token verifier + `RateLimitingMiddleware`; 401/403/rate-limit behaviour verified |
| MCP-08 | Skill `digitiamo-buddy` + one-page install guide | SKILL.md format, claude.ai upload constraints, `claude mcp add` syntax cited |
</phase_requirements>

## Summary

The decisive finding is that **both candidate Python SDKs changed major version**. The official `mcp` package is at **2.3.0** and renamed `FastMCP` to `MCPServer` (`from mcp.server import MCPServer`); `mcp.server.fastmcp` now raises `ModuleNotFoundError`. Standalone `fastmcp` is at **4.1.6**, built on `mcp>=2.3.0,<3`, and still exposes `FastMCP`. Training-data snippets (mcp 1.x, fastmcp 2.x) are wrong in several places (constructor args, `stateless_http` placement, `ToolAnnotations` field names, httpx -> `httpx2`). Every API in this document was exercised in a throwaway `python:3.12-slim` container against the real packages.

**Library decision (D-11): standalone `fastmcp==4.1.6`.** The official SDK is a resource server only; Google has no Dynamic Client Registration and no CIMD, and claude.ai requires one of DCR/CIMD/Anthropic-held credentials. `fastmcp`'s `OAuthProxy` fronts Google with a DCR + CIMD facade (verified: AS metadata advertises `registration_endpoint`, `client_id_metadata_document_supported: true`, `code_challenge_methods_supported: ["S256"]`). It also provides `MultiAuth` (OAuth proxy + a JWT verifier for the bot's Google ID tokens), a built-in per-client token-bucket `RateLimitingMiddleware`, and passes `mypy --strict` with the project's settings.

**The central design risk is not in the requirements text:** `OAuthProxy` is *stateful*. Access-token validation needs a JTI-mapping store and an upstream-token store (read from `load_access_token` source). Its default store is an encrypted `FileTreeStore` under a platformdirs home, which violates MCP-01 ("no state on the container filesystem"). The plan must pass an explicit `client_storage`: `MemoryStore` (loses all logins on every cold start / scale-to-zero) or a Fernet-wrapped Firestore store (survives, reuses the Firestore dependency already required for MCP-05). This is flagged as Open Question 1.

**Primary recommendation:** Build `services/mcp_server/buddy_mcp` on `fastmcp==4.1.6` with `async def` tools (sync tools run in a threadpool and would break the single-thread SQLite connection), typed pydantic output models returned as `ToolResult(content=<short Italian text>, structured_content=model.model_dump())` with `output_schema=Model.model_json_schema()`, an `OAuthProxy` built directly with Google endpoints and a domain-restricting token verifier, wrapped in `MultiAuth` with a Google-ID-token verifier for the bot, an explicit `client_storage`, and the built-in `RateLimitingMiddleware`.

## Project Constraints (from CLAUDE.md)

No project-level `./CLAUDE.md` or `.claude/CLAUDE.md` exists (only `.claude/settings.local.json` and `worktrees`). The user's global `~/.claude/CLAUDE.md` directives apply and are treated as locked:
- Python only; all code runs in Docker, never host Python. Mount cwd `-v "$PWD:/app" -w /app`; secrets via `--env-file .env`.
- Tests through `./run-unit-tests.sh` (`--all`, `--single <file> <test_name> <dir>`, `--single-file <file> <dir>`); builds the test image first; `set -euo pipefail` and `log()` helper.
- `pip` + `requirements.txt` / `requirements-dev.txt`; `ruff` (lint+format); `pytest -v --tb=short`, `--cov`; type hints on all public functions, `mypy --strict` where feasible.
- No commits/pushes without an explicit ask (memory: commit directly on `main`, no branches, push only on ask).
- Never echo `.env` contents/keys/tokens; never invent file paths/APIs (grep/read first).
- Public repo: internal docs only under `docs/internal/`; no handbook content or employee names committed (memory + CONTEXT).
- No speculative abstractions: ports only where CONTEXT mandates (`GapLog`); no extra layers.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Index load (handbook + Guides) | MCP server process (cold start) | Artifact store (local dir) | D-11: load once at start; `ArtifactStore.latest_path()` then `open_index` |
| Handbook Italian FTS | MCP server (in-memory SQLite) | - | D-01: built from `handbook_pages` at start; no schema change |
| Guides BM25 search | MCP server via `IndexReader.search_guides` | index.db file | Reuse Phase 1 reader; no new SQL |
| Tool/resource contract | MCP server | - | `fastmcp` tools + resource template, typed outputs |
| Human authentication | Google (IdP) + server OAuth proxy facade | claude.ai/Claude Code clients | Google lacks DCR/CIMD; proxy bridges |
| Domain restriction `@digitiamo.com` | MCP server token verifier | Google consent screen "Internal" (manual) + `hd` hint | Server-side check is the only enforceable layer |
| Bot-to-server auth | MCP server `JWTVerifier` subclass | Bot service account (Phase 3 mints ID token) | D-12 |
| Rate limiting | MCP server in-memory middleware | - | D-14 |
| Gap log persistence | Firestore (behind `GapLog` port) | Fake in tests | D-15 / D10 |
| OAuth state (clients, tokens) | Pluggable key-value store | Firestore (deployed) / memory (dev) | Open Question 1 |
| Skill / install guide | Static files in repo (`skills/`, `docs/`) | claude.ai / Claude Code | Consumed by the client, not the server |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastmcp | 4.1.6 (2026-11-03) | MCP server, OAuth proxy, MultiAuth, middleware | Only option with a Google OAuth proxy (DCR+CIMD facade). Depends on `fastmcp-slim[client,server]==4.1.6` -> `mcp>=2.3.0,<3`. [VERIFIED: pip install in python:3.12-slim; PyPI JSON] |
| snowballstemmer | 3.1.1 (2026-06-03) | Italian stemming for handbook FTS (D-02) | Pure Python, `stemmer('italian').stemWords(...)` verified. Requires Python >=3.3 [VERIFIED: PyPI + smoke test] |
| google-cloud-firestore | 2.34.1 (2026-10-08) | Gap log adapter (`AsyncClient`) | Official client; emulator roundtrip verified [VERIFIED: emulator run] |
| pydantic / pydantic-settings | already pinned (2.14.2 / 2.16.2) | Output models, `McpSettings` | Already in `requirements.txt`; satisfy fastmcp's `pydantic>=2.12`, `pydantic-settings>=2.0` |

Transitive, installed by `fastmcp` (do not pin separately unless imported directly): `mcp 2.3.0`, `mcp-types 2.3.0`, `httpx2 2.16.0`, `starlette 1.10.0`, `uvicorn 0.54.0`, `Authlib 1.9.5`, `cryptography 50.0.2`, `PyJWT 2.15.1`, `joserfc 1.8.0`, `py-key-value-aio 0.4.6` (has a `firestore` store and `FernetEncryptionWrapper`). [VERIFIED: `pip list` in container]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| anyio pytest plugin | bundled with anyio 4.16.0 | Async tests (`@pytest.mark.anyio` + `anyio_backend` fixture) | Avoids adding `pytest-asyncio`; verified passing under `--import-mode=importlib` |
| `google-auth` | 2.62.1 (transitive of firestore) | `id_token.fetch_id_token` in Phase 3 bot; not needed server-side | Server verifies via `fastmcp` `JWTVerifier` + Google JWKS |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fastmcp` 4.1.6 | official `mcp` 2.3.0 `MCPServer` | Smaller dependency surface and the Guides' own examples use it, but no OAuth AS facade: claude.ai could not log in via Google. Rejected per D-11 criterion |
| `pytest-asyncio` 1.4.1.post1 | anyio plugin | pytest-asyncio is more familiar; anyio plugin already installed, zero new pin |
| `google.oauth2.id_token.verify_oauth2_token` (sync, `requests`) | `JWTVerifier(jwks_uri=...)` subclass | google-auth path needs a sync HTTP transport inside an async server; `JWTVerifier` is async and already in the stack |

**Installation (requirements split recommended):**
```bash
# services/mcp_server/requirements.txt (new; copied by the mcp_server Dockerfile stage)
fastmcp==4.1.6
snowballstemmer==3.1.1
google-cloud-firestore==2.34.1
# requirements-dev.txt gains:  -r services/mcp_server/requirements.txt
```
The Dockerfile `base` stage currently only copies `requirements.txt requirements-dev.txt`; the new file must be copied too, `PYTHONPATH` extended with `/app/services/mcp_server`, and `pyproject.toml` (`pythonpath`, `mypy_path`, `files`, ruff `src`, `isort known-first-party`, coverage `source`) extended with `services/mcp_server` / `buddy_mcp`. [VERIFIED: Dockerfile, pyproject.toml read]

**Version verification:** versions confirmed from `https://pypi.org/pypi/<pkg>/json` on 2026-11-06 (`mcp` 2.3.0, `fastmcp` 4.1.6, `snowballstemmer` 3.1.1, `google-cloud-firestore` 2.34.1, `google-auth` 2.62.1, `uvicorn` 0.54.0, `anyio` 4.16.0, `pytest-asyncio` 1.4.1.post1).

## Package Legitimacy Audit

`gsd_run query package-legitimacy check --ecosystem pypi ...` returned **SUS for every package**. The reasons are tool-signal limits (`unknown-downloads` because the seam has no download counts; `too-new` because fastmcp/google-auth/google-cloud-firestore/httpx2 published a release within the last weeks). None is `SLOP`; all exist; none has a postinstall. PyPI metadata confirms legitimate source repos for the ones I could cross-check.

| Package | Registry | Latest published | Source Repo | Verdict | Disposition |
|---------|----------|------------------|-------------|---------|-------------|
| fastmcp | PyPI | 2026-11-03 | github.com/PrefectHQ/fastmcp (PyPI project_urls) | SUS (too-new, unknown-downloads) | Flagged - checkpoint |
| fastmcp-slim (transitive) | PyPI | 2026-11-03 | gofastmcp.com | SUS (too-new, unknown-downloads) | Flagged (transitive) |
| mcp, mcp-types (transitive) | PyPI | 2026-10-02 | modelcontextprotocol.io (python-sdk) | SUS (unknown-downloads) | Flagged (transitive) |
| httpx2 (transitive) | PyPI | 2026-10-21 | github.com/pydantic/httpx2 | SUS (too-new, unknown-downloads) | Flagged (transitive) |
| py-key-value-aio (transitive) | PyPI | 2026-09-18 | none in seam | SUS (no-repository, unknown-downloads) | Flagged (transitive) |
| snowballstemmer | PyPI | 2026-06-03 | github.com/snowballstem/snowball | SUS (unknown-downloads) | Flagged - checkpoint |
| google-cloud-firestore | PyPI | 2026-10-08 | github.com/googleapis/google-cloud-python | SUS (too-new, unknown-downloads) | Flagged - checkpoint |
| google-auth (transitive) | PyPI | 2026-11-03 | github.com/googleapis/google-cloud-python | SUS (too-new, unknown-downloads) | Flagged (transitive) |
| uvicorn (transitive) | PyPI | 2026-09-25 | github.com/Kludex/uvicorn | SUS (unknown-downloads) | Flagged (transitive) |

**Packages removed due to SLOP verdict:** none.
**Packages flagged SUS:** all of the above. Planner: add **one** `checkpoint:human-verify` task ahead of the first `pip install` covering the three direct new pins (`fastmcp`, `snowballstemmer`, `google-cloud-firestore`); transitives ride on `fastmcp`'s own requirement set (inspected: `requires_dist` of `fastmcp`, `fastmcp-slim`, `mcp`). Joshua's established Phase 1 posture is "latest verified on PyPI, pin with ==". [VERIFIED: gsd package-legitimacy seam; PyPI JSON]

## Architecture Patterns

### System Architecture Diagram

```
 claude.ai / Claude Desktop            Claude Code            Phase 3 chat bot
 (custom connector, callback           (claude mcp add         (service account ->
  https://claude.ai/api/mcp/            --transport http,       Google ID token,
  auth_callback; CIMD or DCR)           loopback redirect)      aud = server URL)
        |                                   |                        |
        |  POST /mcp  (JSON-RPC, Bearer)    |                        |
        +-----------------+-----------------+------------------------+
                          v
              [ ASGI app: fastmcp http_app(stateless_http=True, json_response=True) ]
                          |
        no/invalid token -+-> 401 + WWW-Authenticate resource_metadata=...
                          |
   /.well-known/oauth-protected-resource/mcp, /authorize, /token, /register, /auth/callback
        (OAuthProxy facade  <---redirect--->  Google accounts.google.com, hd=digitiamo.com)
                          |
              MultiAuth.verify_token(token):
                 1) OAuthProxy.load_access_token  (FastMCP JWT -> JTI store -> upstream Google token
                                                   -> DomainRestricted verifier: email @digitiamo.com)
                 2) ServiceAccountIdTokenVerifier (Google JWKS, iss accounts.google.com, aud=server URL,
                                                   email in BOT_SA_EMAILS, email_verified)
                          v
              RateLimitingMiddleware  (token bucket per identity, in memory)
                          v
        +------------------------- tools (all async, read from RAM) -------------------------+
        | handbook_get(section?)  -> TOC | page        (pages dict from IndexReader)          |
        | handbook_search(q)      -> in-memory FTS5 (snowball-stemmed) -> whole pages          |
        | guides_search(q)        -> IndexReader.search_guides (BM25, English)  + video_url    |
        | guides_get_section(id)  -> chunk dict by chunk_key                                   |
        | buddy_report_gap(q)     -> GapLog port -> FirestoreGapLog (AsyncClient)              |
        | resource handbook://{pagina} -> page markdown                                        |
        +--------------------------------------------------------------------------------------+
            ^ cold start only: ArtifactStore.latest_path() -> open_index() -> RAM snapshot
            ^ Firestore: gap docs (TTL expire_at), optional OAuth state store
```

### Recommended Project Structure
```
services/mcp_server/
├── requirements.txt          # fastmcp, snowballstemmer, google-cloud-firestore
├── README.md
└── buddy_mcp/
    ├── __init__.py
    ├── __main__.py           # python -m buddy_mcp: load settings, build_server, run
    ├── config.py             # McpSettings (pydantic-settings, errors name variables not values)
    ├── snapshot.py           # IndexSnapshot: pages dict, chunk dict, videos, handbook FTS5
    ├── stemming.py           # tokenize + snowball + (small) Italian stopword set
    ├── models.py             # pydantic output models (the D-06 contract)
    ├── tools.py              # register_tools(mcp, snapshot, gaplog)
    ├── gaplog.py             # GapLog Protocol, FirestoreGapLog, InMemoryGapLog (test fake)
    ├── auth.py               # build_auth(settings): verifiers, OAuthProxy, MultiAuth, K_SERVICE guard
    └── server.py             # build_server(settings, *, gaplog, store...) -> FastMCP; build_app()
skills/digitiamo-buddy/SKILL.md          # + optional reference files
docs/install-guide.md                    # one page; public-safe
docker-compose.test.yml                  # Firestore emulator + test runner
tests/unit/mcp_server/...  tests/integration/test_firestore_*.py
```

### Pattern 1: Stateless JSON app (verified)
**What:** build the ASGI app with both flags; no SSE stream, no session id.
```python
# Source: smoke test against fastmcp 4.1.6 (python:3.12-slim), 2026-11-06
app = mcp.http_app(stateless_http=True, json_response=True)   # path defaults to /mcp
# POST /mcp initialize -> 200, content-type application/json, mcp-session-id: None
# GET  /mcp            -> 405   (no held-open stream)
```
Run in Docker with `mcp.run(transport="http", host="0.0.0.0", port=..., stateless_http=True, json_response=True)` (signature `run_http_async(..., transport, host, port, ..., json_response, stateless_http, host_origin_protection, allowed_hosts, allowed_origins)` read from source). In the official SDK these flags moved from the constructor to `run()`/`streamable_http_app()`; `stateless_http` only affects 2025-era clients. [CITED: py.sdk.modelcontextprotocol.io/whats-new/, /v2/migration/]

### Pattern 2: Typed result + short text rendering (D-06, verified)
```python
# Source: smoke test fastmcp 4.1.6
from typing import Literal
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations      # same object as mcp_types.ToolAnnotations
from pydantic import BaseModel

class SearchResult(BaseModel):
    status: Literal["ok", "no_results"]
    query: str
    results: list[PageHit]

RO = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                     idempotent_hint=True, open_world_hint=False)   # snake_case: camelCase kwargs fail mypy

@mcp.tool(annotations=RO, output_schema=SearchResult.model_json_schema())
async def handbook_search(query: str, limit: int = 5) -> ToolResult:
    result = ...                                             # SearchResult
    return ToolResult(content=render_it(result), structured_content=result.model_dump())
```
Verified: `outputSchema` is advertised; a structured payload that violates the schema raises (`Invalid structured content returned by tool`); missing arguments raise `ToolError` (validation). With a plain pydantic return type, `content` is the JSON dump instead (no short rendering).

### Pattern 3: Auth composition (verified pieces)
```python
# Source: fastmcp 4.1.6 source (oauth_proxy/proxy.py, providers/google.py, auth.py) + smoke tests
oauth = OAuthProxy(
    upstream_authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
    upstream_token_endpoint="https://oauth2.googleapis.com/token",
    upstream_client_id=s.google_client_id, upstream_client_secret=s.google_client_secret,
    token_verifier=DomainRestrictedGoogleVerifier(allowed_domain="digitiamo.com",
                       audience=s.google_client_id, cache_ttl_seconds=300,
                       required_scopes=["openid", "https://www.googleapis.com/auth/userinfo.email"]),
    base_url=s.public_base_url, jwt_signing_key=s.oauth_jwt_signing_key,
    client_storage=storage,                                   # NEVER default (file store)
    allowed_client_redirect_uris=["https://claude.ai/api/mcp/auth_callback",
                                  "http://localhost:*", "http://127.0.0.1:*"],
    extra_authorize_params={"access_type": "offline", "prompt": "consent", "hd": "digitiamo.com"},
    require_authorization_consent=True,
)
auth = MultiAuth(server=oauth, verifiers=[ServiceAccountIdTokenVerifier(...)])
mcp = FastMCP("digitiamo-buddy", auth=auth, instructions=..., middleware=[RateLimitingMiddleware(...)])
```
`GoogleProvider` does the same wiring but builds its own `GoogleTokenVerifier` with no domain check and no hook to swap it without touching a private attribute (`_token_validator`); constructing `OAuthProxy` directly keeps to public API. `GoogleTokenVerifier.verify_token` calls Google `tokeninfo` **and** `userinfo` on every request unless `cache_ttl_seconds` is set - set it.

### Pattern 4: GapLog port (D-15)
```python
class GapLog(Protocol):
    async def record(self, gap: GapRecord) -> str: ...   # returns document id
```
`FirestoreGapLog(client: firestore.AsyncClient, collection="gaps")` writes `{question, marker: "nessuna fonte trovata", created_at (server timestamp), expire_at (UTC datetime now+TTL), build_id, tried?}`; `InMemoryGapLog` fake for tool tests. TTL policy is an infra step: `gcloud firestore fields ttls update expire_at --collection-group=gaps --enable-ttl` (field must be a timestamp; deletion typically within 24 h; TTL deletes count toward delete costs). [CITED: docs.cloud.google.com/firestore/native/docs/ttl]

### Anti-Patterns to Avoid
- **Sync `def` tools touching SQLite.** fastmcp runs sync tools via `call_sync_fn_in_threadpool` (source: `tools/function_tool.py`); `open_index` uses `sqlite3.connect` with the default `check_same_thread=True`. Use `async def` and open the index on the loop thread.
- **Calling `LocalDirArtifactStore.staging_path()` / `publish()` from the server.** `staging_path` deletes `.index.*.tmp` files and the constructor does `root.mkdir(parents=True, exist_ok=True)`; the server only reads `latest_path()`. [VERIFIED: packages/buddy_core/buddy_core/store.py read]
- **Letting `OAuthProxy`/`GoogleProvider` pick its default storage** (file tree under platformdirs home).
- **Leaving the fastmcp `LoggingMiddleware` / DEBUG logs on:** they log request payloads (question text).
- **Token passthrough:** never forward the incoming bearer token anywhere; the server uses its own Firestore credential (Guide §18.1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth AS facade (DCR/CIMD, PKCE, consent, token swap) | Custom `/authorize` `/token` `/register` | `fastmcp.server.auth.OAuthProxy` | Security-critical; metadata/PKCE/redirect validation verified in smoke test |
| Verifying Google ID tokens (bot) | Manual JWT parsing | `JWTVerifier(jwks_uri="https://www.googleapis.com/oauth2/v3/certs", issuer="https://accounts.google.com", audience=<server URL>)` + email allowlist subclass | JWKS caching/rotation, alg pinning (RS256) |
| Token bucket | Own limiter | `fastmcp.server.middleware.rate_limiting.RateLimitingMiddleware(max_requests_per_second, burst_capacity, get_client_id=...)` | Verified per-client behaviour |
| FTS query sanitising | Own escaping | `buddy_core.index_reader.to_match_query` | Phase 1 tested against `"`, `:`, `-`, `*`, NUL |
| Guides search + video join | New SQL | `IndexReader.search_guides` (`SearchHit(chunk, score, video)`) | Only supported SQL surface (index-format.md) |
| Video URL composition | String concat | `buddy_core.models.video_link(VideoLink)` | `url#t=<int seconds>` rule lives there |
| Italian stemming | Suffix rules | `snowballstemmer.stemmer("italian")` | D-02 |
| Encrypting OAuth state at rest | Own crypto | `FernetEncryptionWrapper` (py-key-value-aio) | Used by fastmcp itself |
| Firestore TTL | Cron deleter | Firestore TTL policy on `expire_at` | Native, free of code |

**Key insight:** every security-sensitive or protocol-sensitive piece (OAuth, JWT, rate limit, query escaping) already exists in the stack; the new code is glue plus the tool/output contract.

## Runtime State Inventory

Not a rename/refactor/migration phase - omitted. (Greenfield `services/mcp_server`; Phase 1 files untouched.)

## Common Pitfalls

### Pitfall 1: OAuth proxy writes to the container filesystem by default
**What goes wrong:** `OAuthProxy(client_storage=None)` creates an encrypted `FileTreeStore` under `settings.home/oauth-proxy/<fingerprint>` (read from `proxy.py` lines ~592-623). Violates MCP-01 and is lost on Cloud Run restart anyway.
**How to avoid:** `McpSettings.oauth_storage: Literal["memory","firestore"]`, no default file option; pass the store explicitly. Test: build the server with `HOME`/cwd pointed at an empty `tmp_path` and assert it stays empty after a full initialize + tools/call + OAuth metadata fetch.
**Warning signs:** a `~/.local/share/fastmcp` (or similar) directory appearing in the container.

### Pitfall 2: In-memory OAuth state = re-login on every cold start
**What goes wrong:** `load_access_token` needs the JTI mapping and upstream-token entries (source verified); with `MemoryStore` a restart/scale-to-zero invalidates all FastMCP JWTs and refresh tokens, so users re-authenticate after every idle period. claude.ai gives token/discovery endpoints only 10 s (30 s for refresh) [CITED: claude.com/docs/connectors/building/authentication.md], so a Firestore-backed store must be fast; cold start + store latency must stay well under that.
**How to avoid:** `OAUTH_STORAGE=firestore` for deployed runs (Fernet-wrapped `FirestoreStore`, key from env); `memory` for tests/local. See Open Question 1.

### Pitfall 3: `MultiAuth` inherits the OAuth proxy's required scopes -> bot gets 403
**What goes wrong:** verified: with the proxy's `required_scopes=["openid", ".../userinfo.email"]`, a valid bot token from the second verifier gets `403 insufficient_scope` ("Required scope: openid"). With `MultiAuth(required_scopes=[])` it passes (200) but the 401 then advertises no `scope`.
**How to avoid:** make `ServiceAccountIdTokenVerifier.verify_token` return an `AccessToken` whose `scopes` equal the proxy's required scopes (only after signature/aud/email-allowlist checks). Add a test for both token sources through `MultiAuth`.

### Pitfall 4: Domain restriction is not enforced by `GoogleProvider`
**What goes wrong:** `hd=digitiamo.com` is only a UI hint; any Google account can complete login and the stock `GoogleTokenVerifier` accepts any valid token whose `aud` matches the app (`audience=client_id`).
**How to avoid:** `DomainRestrictedGoogleVerifier(GoogleTokenVerifier)`: call `super().verify_token`, then require `claims["email_verified"]` truthy and `claims["email"].lower().endswith("@digitiamo.com")` (and `google_user_data["hd"] == "digitiamo.com"` when present). Request scope `https://www.googleapis.com/auth/userinfo.email` or `tokeninfo` carries no email. Also set the Google Cloud OAuth consent screen user type to **Internal** (manual; documented in the install/ops notes) [ASSUMED: Internal restricts sign-in to the Workspace org]. Test: token with `email="x@gmail.com"` -> None -> 401.

### Pitfall 5: Two Google calls per MCP request
`GoogleTokenVerifier` hits `tokeninfo` + `userinfo` each time unless `cache_ttl_seconds` is set (default None). With claude.ai issuing `tools/list` + `tools/call` bursts this doubles latency and risks Google quota. Set `cache_ttl_seconds=300`, `max_cache_size` small.

### Pitfall 6: Rate-limit errors are JSON-RPC errors, and every request counts
Verified: over-limit returns HTTP 200 with `{"error":{"code":-32000,"message":"Rate limit exceeded for client: <id>"}}`, not 429. The middleware hooks `on_request`, so `initialize`/`tools/list`/`resources/*` also consume tokens. Defaults must be generous (e.g. 5 rps sustained, burst 30) and env-configurable. The error message embeds the identity string (the Google `sub`, `client_id=sub` in `GoogleTokenVerifier`): acceptable (not persisted), but never log it with question text. `limiters` dict grows per identity (fine at single-user scale).

### Pitfall 7: Claude requires a real 401 and public HTTPS
claude.ai ignores `WWW-Authenticate` on a 200, uses only the first `authorization_servers` entry, and its egress is `160.79.104.0/21`. claude.ai cannot reach localhost: local/kind testing uses `AUTH_MODE=off` via Claude Code or the in-memory client; a real claude.ai login needs a public HTTPS URL (Phase 4 / tunnel). Verified server side: 401 carries `resource_metadata=".../.well-known/oauth-protected-resource/mcp"` and PRM `resource` equals the `/mcp` URL (must equal what the user types in the connector).

### Pitfall 8: Italian stemmer does not unify derivations; stopwords with OR queries
Verified: `richiedere -> richied` but `richiesta -> richiest`; `chiedere -> chied`. Tokenise with `\w+` (Unicode), lowercase, stem both page text and query, and drop a small Italian stopword set from queries (`il le di che per a in ...`; the stemmer ships none) because `to_match_query` ORs every token and a 22-page corpus gives unstable IDF. Optional prefix match is Claude's discretion; Phase 5 Recall@5 validates. Keep tokenizer `unicode61 remove_diacritics 2` (same as the Guides FTS) so accents fold consistently.

### Pitfall 9: Guides "revision date" does not exist in the index
Schema 1.0.0 stores `guides_commit_sha` and `created_at_utc` (build time) in `meta`, no commit date; `jobs/sync` must stay untouched. MCP-03 still demands a date. See Open Question 2.

### Pitfall 10: Pydantic validation of `limit`
Use clamp (`max(1, min(limit, 10))`), consistent with `search_guides`'s own clamp (`_MAX_LIMIT = 50`), rather than a `Field(le=10)` that surfaces as a `ToolError` the model must parse.

### Pitfall 11: Tests run with `--network none`
`run-unit-tests.sh` runs containers with `--network none`. ASGI in-process tests (`httpx2.ASGITransport`, `fastmcp.Client(mcp)`) need no network; the Firestore emulator tests do. Add an emulator mode (compose) and auto-skip when `FIRESTORE_EMULATOR_HOST` is unset, so `--all` stays offline. MCP-05 is only "verified" when the emulator mode ran.

### Pitfall 12: `K_SERVICE` guard must run before the server builds
Put it in `McpSettings` (`model_validator`) so both `__main__` and tests hit it; also refuse `AUTH_MODE=off` with a public base URL scheme `https` only if you want extra safety (optional).

## Code Examples

### Cold-start snapshot (reuses Phase 1 reader)
```python
# Source: packages/buddy_core/buddy_core/index_reader.py (read this session)
store = LocalDirArtifactStore(settings.artifact_dir)         # read-only use: latest_path() only
path = store.latest_path()                                   # Path | None  -> fail fast on None
reader = open_index(path)                                    # IndexVersionError / IndexFormatError / FileNotFoundError
pages = {p.page_id: p for p in reader.load_handbook()}       # HandbookPage(page_id, title, url, revision_date_iso, content_md, ...)
chunks = {c.chunk_key: c for c in reader.guide_chunks()}     # GuideChunk(chunk_key, file, h2, h3, heading, line_start, line_end, part_index, text)
videos = reader.video_links()                                # dict[chunk_key, VideoLink]
meta = reader.meta                                           # IndexMeta(build_id, guides_commit_sha, created_at_utc, ...)
hits = reader.search_guides(query, limit)                    # list[SearchHit(chunk, score, video)]
```
Real local artifact (gitignored `artifacts/index.db`, read in Docker): schema 1.0.0, 22 handbook pages (avg 178 words, max 5025 chars), 2795 Guides chunks, 2524 video-mapped. Pages load comfortably in RAM.

### Handbook FTS (verified shape)
```python
st = snowballstemmer.stemmer("italian")
def stems(text: str) -> list[str]:
    return st.stemWords(re.findall(r"\w+", text.lower()))
con = sqlite3.connect(":memory:")            # same thread as the event loop (async tools)
con.execute("CREATE VIRTUAL TABLE p USING fts5(title, body, tokenize='unicode61 remove_diacritics 2')")
# insert with rowid = position; text = " ".join(stems(...))
match = to_match_query(" ".join(drop_stopwords(stems(query))))   # None -> no_results
con.execute("SELECT rowid, bm25(p, 5.0, 1.0) FROM p WHERE p MATCH ? ORDER BY 2, rowid LIMIT ?", (match, limit))
```
Verified outputs: "quando posso chiedere una feria?" and "richiedo ferie" both retrieve the "Ferie" page; SQLite 3.46.1 in `python:3.12-slim` has FTS5.

### Guides citation
```python
url = f"{settings.guides_web_base}/blob/{meta.guides_commit_sha}/{quote(c.file, safe='/')}#L{c.line_start}-L{c.line_end}"
video_url = video_link(v) if v else None      # buddy_core.models.video_link
```

### Rate limit keyed by identity (verified)
```python
def caller(ctx) -> str:
    t = get_access_token()                    # fastmcp.server.dependencies
    return t.client_id if t else "anonymous"
RateLimitingMiddleware(max_requests_per_second=..., burst_capacity=..., get_client_id=caller)
```

### Async test (verified under project pytest config)
```python
@pytest.fixture
def anyio_backend() -> str: return "asyncio"

@pytest.mark.anyio
async def test_surface() -> None:
    async with Client(build_server(settings, gaplog=InMemoryGapLog(), ...)) as c:   # fastmcp.Client in-memory
        assert sorted(t.name for t in await c.list_tools()) == [...five names...]
```
HTTP-level tests: `async with app.router.lifespan_context(app): httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://localhost")` with headers `Accept: application/json, text/event-stream`.

### Skill (`skills/digitiamo-buddy/SKILL.md`) constraints
Frontmatter limited to `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` for claude.ai upload (any other key breaks packaging); keep `description` <= 200 chars (claude.ai cap per third-party sources; Claude Code allows more) with the trigger first; body < 500 lines; English instructions, Italian templates; zip must contain the skill folder, folder name == `name`. Claude Code install: copy folder to `~/.claude/skills/digitiamo-buddy/`; MCP: `claude mcp add --transport http digitiamo-buddy <url>` then `/mcp` to log in (or `claude mcp login <name>`). claude.ai/Desktop: Customize > Connectors > Add custom connector (Team/Enterprise: Owner adds under Organization settings > Connectors; members then Connect). Remote servers are not added through `claude_desktop_config.json`. [CITED: code.claude.com/docs/en/mcp, code.claude.com/docs/en/skills, claude.com/docs/connectors/custom/add-unlisted.md, claude.com/docs/skills/how-to]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mcp.server.fastmcp.FastMCP` | `mcp.server.MCPServer` (official); standalone `fastmcp` keeps `FastMCP` | mcp 2.0 | Old imports raise `ModuleNotFoundError`; don't copy 1.x snippets |
| `stateless_http`/`json_response`/`host`/`port` on constructor | on `run()` / `http_app()` | mcp 2.0 | Constructor args raise `TypeError` |
| `httpx` | `httpx2` (TLS via OS trust store) | mcp 2 / fastmcp 4 | Minimal containers: ensure CA certs (python:3.12-slim bundles certs via `certifi` in fastmcp server extra; test Google calls in the image) |
| `ToolAnnotations(readOnlyHint=...)` | `ToolAnnotations(read_only_hint=...)` | mcp-types 2.x | camelCase fails `mypy --strict` (verified) |
| `Tool.outputSchema`, `uriTemplate` | `output_schema`, `uri_template` | SDK v2 | camelCase accessors emit `FastMCPDeprecationWarning` |
| DCR as the client-registration path | CIMD preferred, DCR retained | MCP spec 2025-11-25 | Proxy advertises both; claude.ai picks CIMD when `none` auth + `client_id_metadata_document_supported` |
| Sessions (`Mcp-Session-Id`, SSE resumability) | Per-request stateless (spec 2026-07-28) | 2026-07 | SDK serves both eras; stateless flags matter for 2025-era clients |

**Deprecated/outdated:** HTTP+SSE transport (do not build); `langchain-mcp-adapters` archived (Phase 3 concern, Guides note); Context logging helpers deprecated (SEP-2577).

## Guides Applied (D16) and exceptions

| Guide section | Applied as |
|---------------|-----------|
| MCP_SERVERS_GUIDE §5 Tools, §5.7 structured output | typed outputs + `outputSchema` + text rendering |
| §6.3 Resources vs tools | resource `handbook://{pagina}` for attach, tools for model search |
| §11 Statelessness (esp. 11.6 checklist) | no per-connection state; `tools/list` deterministic |
| §12 Transports (12.2 Streamable HTTP) | `http_app`, no SSE |
| §17 Authorization (17.3-17.5) | PRM + 401 + audience/issuer validation; **exception:** §17.5 "do not build an AS" - `OAuthProxy` is an AS facade, justified because Google offers neither DCR nor CIMD and claude.ai requires one |
| §18 Security (18.1 token passthrough, 18.2 confused deputy, 18.5 checklist) | own JWTs with server audience; consent screen kept (`require_authorization_consent=True`); redirect URI allowlist; no token forwarding |
| §19 Scaling | per-instance in-memory limiter (accepted inexactness, D-14) |
| §20 Tool surface (20.1-20.5) | 5 tools, namespaced, descriptions as prompts (cross-reference tools, state "empty is not an error"), `ToolError` for anticipated failures |
| §22 Testing (22.1 in-memory client, 22.3 list) | `Client(server)` tests; description-length contract test; `tools/list` stability test |
| RAG_CHATBOT_GUIDE §10 prompt assembly/citations, §20 prompt engineering for RAG, §24 guardrails ("test with empty context") | source-carrying outputs; refuse + gap on no results |
| DESIGN_PATTERNS_GUIDE §9 Hexagonal (Ports & Adapters), Adapter / Repository sections | `GapLog` port + Firestore adapter (mirrors `ArtifactStore`) |

Other exceptions: Guides §12 assumes `server/discover` etc. - handled by the SDK, not by project code. The Guides code samples use `mcp.server.MCPServer`; this phase uses standalone `fastmcp` per D-11 (same protocol layer underneath).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Google OAuth consent screen user type "Internal" restricts login to the Workspace org | Pitfall 4 | Only the server-side domain check remains (still sufficient) |
| A2 | Google `tokeninfo` returns `email`/`email_verified` when scope `userinfo.email` is granted; `userinfo` v2 returns `hd` for Workspace accounts | Pitfall 4 | Domain check relies on email suffix only; unit-test with fakes, confirm in a live login |
| A3 | Firestore emulator does not enforce TTL deletion (tests assert only that `expire_at` is a timestamp) | Pattern 4 / Validation | Test might see unexpected deletion (low) |
| A4 | claude.ai skill `description` cap is 200 characters (third-party sources; spec allows 1024) | Skill | Upload rejected; keep <= 200 to be safe |
| A5 | Google service-account ID tokens carry `email` + `email_verified` and `aud` = requested audience | Auth | SA verifier must be adapted (use `sub`/`azp`); test with a real SA in Phase 3/4 |
| A6 | `K_SERVICE` is set on Cloud Run (CONTEXT D-13 states it as the marker) | D-13 | Guard ineffective on another host; add an optional second flag later |
| A7 | claude.ai refresh-time / 10 s endpoint limits hold for the Firestore-backed store latency | Pitfall 2 | Re-login loops; measure in Phase 4 |
| A8 | Cloud Run public HTTPS URL used as `base_url` also equals the URL users paste into the connector | Pitfall 7 | PRM `resource` mismatch -> claude.ai discovery fails |

## Open Questions

1. **OAuth state store: `memory` only, or `memory` + `firestore` in this phase?**
   - Known: default file store is forbidden by MCP-01; memory loses logins on every restart; `FirestoreStore` + `FernetEncryptionWrapper` exist and can be tested against the same emulator; Phase 4 may swap Firestore for Postgres (deferred idea).
   - Recommendation: implement both behind `OAUTH_STORAGE`, default `memory`, Firestore tested on the emulator; document that production on scale-to-zero needs `firestore`. If scope must shrink, ship `memory` and move `firestore` to Phase 4 - but then the Phase 2 success criterion 4 is only demonstrated for a warm instance.

2. **What is "revision date" for a Guides result (MCP-03)?**
   - Known: index has no per-chunk or commit date; only `meta.created_at_utc` (index build time) and `guides_commit_sha`.
   - Recommendation: emit `revision_date = meta.created_at_utc` date, named/documented as "indexed on", and keep `source_url` pinned to the commit. A true commit date needs a minor schema bump in `jobs/sync` (contradicts D-01 "sync untouched") - defer. Needs user confirmation.

3. **Is `buddy_report_gap` "read-only"?** MCP-07 says tools are read-only. It writes the gap log. Recommendation: annotate it `read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False` and test that it is the only non-read-only tool and never touches handbook/Guides. Clients may prompt for approval on it.

4. **`handbook_get` with an unknown section** - recommend `status: "no_results"` (same shape as search, D-08) rather than a `ToolError`; and accept the exact `page_id` only.

5. **Resource listing** - recommend the template only (`resources/templates/list`); listing 22 static resources adds no value. Resource text should start with a `Fonte: handbook://<id> - Revisione: <date>` line.

6. **Real Google OAuth path cannot be exercised here.** Plan a manual verification checkpoint (public HTTPS URL, real Google client, claude.ai + Claude Code login) - likely finished in Phase 4 hosting; Phase 2 proves the flow with fakes and the metadata/401/403 behaviour.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | all code/tests | yes | 29.9.1 | - |
| Docker Compose | emulator tests | yes | v5.6.0 | - |
| `ai-buddy-test` image | `run-unit-tests.sh` | yes (cached) | python 3.12 | rebuilt by script |
| Firestore emulator image `google/cloud-sdk:592.0.0-emulators` | MCP-05 test | yes (pulled, 1.69 GB, started in ~25 s) | gcloud 592.0.0 | `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` [ASSUMED same content] |
| PyPI network (build time) | `pip install` | yes | - | - |
| Public HTTPS endpoint + Google OAuth client + real claude.ai login | live OAuth check | no | - | fakes in tests; manual checkpoint (Open Question 6) |
| Real artifact `artifacts/index.db` | manual smoke | yes (gitignored) | schema 1.0.0 | fixtures under `tests/fixtures` |

**Missing with no fallback:** live Google/claude.ai OAuth (cannot be automated here).
Emulator start command verified: `gcloud emulators firestore start --host-port=0.0.0.0:8080`; client connects via `FIRESTORE_EMULATOR_HOST=<host>:8080` with only `project="demo-..."` (no credentials). Java 21 is bundled in the image.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 + pytest-cov 7.1.0, anyio plugin for async; ruff 0.17.3; mypy 2.4.1 `--strict` (pydantic plugin) |
| Config file | `pyproject.toml` (extend `pythonpath`, `mypy_path`, `files`, `src`, coverage `source`, add marker `firestore`) |
| Quick run command | `./run-unit-tests.sh --single-file <test_file> tests/unit/mcp_server` |
| Full suite command | `./run-unit-tests.sh --all` (ruff check, ruff format --check, mypy, pytest --cov-fail-under=80, network none) |
| Emulator suite | new `./run-unit-tests.sh --emulator` (compose: emulator service + test runner on one network, `FIRESTORE_EMULATOR_HOST` set) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-01 | `initialize` -> 200 `application/json`, no `mcp-session-id`, `GET /mcp` 405; building+serving writes nothing under HOME/cwd | integration (ASGI) | `./run-unit-tests.sh --single-file test_http_transport.py tests/unit/mcp_server` | Wave 0 |
| MCP-02 | exactly 5 tool names, descriptions > 40 chars, `tools/list` stable across calls, annotations, outputSchema present | unit (in-memory Client) | `./run-unit-tests.sh --single-file test_tool_surface.py tests/unit/mcp_server` | Wave 0 |
| MCP-03 | every result of every tool on fixture index has non-empty `source_url` + `revision_date`; mapped Guides chunk has `video_url`, unmapped none; fails if a model lacks them | unit | `./run-unit-tests.sh --single-file test_source_fields.py tests/unit/mcp_server` | Wave 0 |
| MCP-04 | no-match handbook/guides search -> `status=="no_results"`, `results==[]`, `isError` false, text is not filler; punctuation-only query safe | unit | `./run-unit-tests.sh --single-file test_no_results.py tests/unit/mcp_server` | Wave 0 |
| MCP-05 | gap doc has `question`, `created_at`, marker `nessuna fonte trovata`, `expire_at` = now+TTL, `build_id`; no key among user/email/ip/session; fake-based tool test too | unit (fake) + integration (emulator) | `./run-unit-tests.sh --single-file test_gap_tool.py tests/unit/mcp_server`; `./run-unit-tests.sh --emulator` | Wave 0 |
| MCP-06 | resource template `handbook://{pagina}` listed; read known page returns markdown with source+date; unknown id -> not found error | unit | `./run-unit-tests.sh --single-file test_handbook_resource.py tests/unit/mcp_server` | Wave 0 |
| MCP-07a | no token -> 401 + `resource_metadata`; bad token 401; non-`@digitiamo.com` / unverified email -> rejected; allowlisted SA token accepted through `MultiAuth` (scopes satisfied); SA not on allowlist or wrong aud -> 401 | unit (fake verifiers, ASGI) | `./run-unit-tests.sh --single-file test_auth.py tests/unit/mcp_server` | Wave 0 |
| MCP-07b | rate limit: N+1th request in burst -> JSON-RPC error; per identity isolation | unit | `./run-unit-tests.sh --single-file test_rate_limit.py tests/unit/mcp_server` | Wave 0 |
| MCP-07c | `AUTH_MODE=off` works locally; with `K_SERVICE` set the settings/server refuse to start | unit | `./run-unit-tests.sh --single-file test_auth_mode.py tests/unit/mcp_server` | Wave 0 |
| MCP-07d | tools read-only: only `buddy_report_gap` has `read_only_hint=False`; handbook/Guides never mutated (index file hash unchanged) | unit | `./run-unit-tests.sh --single-file test_read_only.py tests/unit/mcp_server` | Wave 0 |
| MCP-07e | settings: missing/invalid env names variables not values; explicit OAuth storage required | unit | `./run-unit-tests.sh --single-file test_config.py tests/unit/mcp_server` | Wave 0 |
| (support) | Italian FTS: stemmed query finds page; accents fold; stopword-only query -> no_results; FTS operators inert | unit | `./run-unit-tests.sh --single-file test_handbook_search.py tests/unit/mcp_server` | Wave 0 |
| (support) | cold start fails fast on missing/incompatible index (`IndexVersionError`) | unit | `./run-unit-tests.sh --single-file test_snapshot.py tests/unit/mcp_server` | Wave 0 |
| MCP-08 | SKILL.md frontmatter only allowed keys, `name == folder`, description <= 200 chars; body mentions all five tools, answer-format fields (risposta/fonte/referente/data di revisione), "non lo so, chiedi a", escalation topics, IT->EN bridge; no e-mail addresses/person names; install guide covers claude.ai, Desktop, Claude Code and fits one page | unit (file contract) | `./run-unit-tests.sh --single-file test_skill_package.py tests/unit/mcp_server` | Wave 0 |

Manual-only (justified, cannot be automated here): live Google login from claude.ai and Claude Code (needs public HTTPS + real OAuth client), Skill behaviour in a real Claude session (Phase 5 EVAL-03 measures it), Joshua's approval of the escalation list (D-17 checkpoint).

### Sampling Rate
- **Per task commit:** `./run-unit-tests.sh --single-file <touched test> tests/unit/mcp_server`
- **Per wave merge:** `./run-unit-tests.sh --all`
- **Phase gate:** `--all` green + `./run-unit-tests.sh --emulator` green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/mcp_server/` test files above + `conftest.py` (fixture index built with `buddy_core.index_writer` from `tests/fixtures`, synthetic only; `anyio_backend` fixture; fake `GapLog`; fake verifiers)
- [ ] `tests/integration/test_firestore_gaplog.py` (skipped without `FIRESTORE_EMULATOR_HOST`)
- [ ] `docker-compose.test.yml` + `--emulator` mode in `run-unit-tests.sh` (keeps the three required modes)
- [ ] `pyproject.toml`, `Dockerfile` (`services/mcp_server` on `PYTHONPATH`, per-service requirements copy, `mcp_server` runtime stage), `.env.example` additions
- [ ] Framework install: via `requirements-dev.txt -r services/mcp_server/requirements.txt`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Google OAuth via `OAuthProxy` (PKCE S256, consent screen, redirect allowlist) + SA ID-token verifier; audience/issuer validated |
| V3 Session Management | yes (stateless) | No server sessions; FastMCP JWTs signed with `jwt_signing_key` from env secret; refresh rotation by proxy |
| V4 Access Control | yes | `@digitiamo.com` + `email_verified`; bot SA email allowlist; read-only tools; no per-section ACL (out of scope) |
| V5 Input Validation | yes | pydantic arg schemas; `to_match_query` for FTS; bound MATCH param; limit clamp; page_id looked up in a dict (no path use) |
| V6 Cryptography | yes | JWT/Fernet from libraries (`Authlib`/`cryptography`/`PyJWT`); never hand-rolled; keys via env |
| V7 Error handling/logging | yes | No question text or identity at INFO; no request-payload logging middleware |
| V13 API/Web service | yes | Host/Origin protection (`allowed_hosts`/`allowed_origins` on `http_app`), 401 semantics |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Any Google account logs in | Spoofing/EoP | Server-side domain + verified-email check; consent "Internal"; `hd` hint |
| Token passthrough / confused deputy | EoP | Proxy-issued JWT with server audience; consent screen; never forward bearer (Guide §18.1-18.2) |
| Open redirect via DCR/CIMD client redirect URIs | Spoofing | `allowed_client_redirect_uris` = claude.ai callback + loopback only |
| Prompt injection through handbook/Guides text returned by tools | Tampering | Content is redacted at sync (Phase 1); Skill instructs to treat tool text as data; no write tools beyond gap log |
| FTS query injection | Tampering | `to_match_query` quoting; test with operators/NUL |
| PII in gap log / logs (Statuto art. 4 posture) | Information disclosure | Gap doc has no identity fields; TTL 90 d; INFO logs omit question; rate-limit identity memory-only |
| Auth accidentally off in production | EoP | `AUTH_MODE=off` refused when `K_SERVICE` set; test |
| Brute-force/abuse | DoS | Per-identity token bucket, request body limits from SDK |
| Secrets in public repo | Disclosure | Google client secret/JWT key/Fernet key only via env/secret manager; `.env.example` placeholders |

## Sources

### Primary (HIGH confidence)
- Real packages exercised in `python:3.12-slim` (fastmcp 4.1.6, mcp 2.3.0, snowballstemmer 3.1.1, google-cloud-firestore 2.34.1) - APIs, HTTP behaviour, auth composition, rate limit, mypy strict, anyio tests
- fastmcp-slim 4.1.6 and mcp 2.3.0 wheel sources (read): `server/auth/providers/google.py`, `oauth_proxy/proxy.py`, `auth.py` (`MultiAuth`), `middleware/rate_limiting.py`, `server/http.py`, `tools/function_tool.py`; py-key-value-aio 0.4.6 `stores/firestore`, `wrappers/encryption`
- Repo files read: `packages/buddy_core/buddy_core/{index_reader,models,store}.py`, `docs/index-format.md`, `docs/adr/0001-index-handoff.md`, `Dockerfile`, `pyproject.toml`, `run-unit-tests.sh`, `requirements*.txt`, `jobs/sync/buddy_sync/config.py`
- Firestore emulator run (image `google/cloud-sdk:592.0.0-emulators`) with a write/read roundtrip
- https://www.googleapis.com/oauth2/v3/certs and https://accounts.google.com/.well-known/openid-configuration (issuer `https://accounts.google.com`, `jwks_uri` verified)

### Secondary (MEDIUM confidence - official docs, partially read)
- https://py.sdk.modelcontextprotocol.io/whats-new/ and /v2/migration/ (MCPServer rename, transport settings moved)
- https://claude.com/docs/connectors/building/authentication.md (DCR/CIMD, callback URLs, 401 requirement, latency limits, egress range)
- https://claude.com/docs/connectors/custom/add-unlisted.md (custom connector steps)
- https://code.claude.com/docs/en/mcp and /skills (`claude mcp add --transport http`, SKILL.md format)
- https://docs.cloud.google.com/firestore/docs/emulator and /firestore/native/docs/ttl
- `~/Desktop/WORK/Guides/AI-Engineering/MCP_SERVERS_GUIDE.md` (§11, 12, 17, 18, 20, 22), `RAG_CHATBOT_GUIDE.md` (§24), `Foundations/DESIGN_PATTERNS_GUIDE.md` (§9)

### Tertiary (LOW confidence)
- Third-party summaries of claude.ai skill upload limits (200-char description, 50 MB) - treat as unverified (A4)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - installed and executed; versions from PyPI today
- Architecture: HIGH for server/tool/test design; MEDIUM for OAuth state handling (design choice, Open Question 1)
- Pitfalls: HIGH where reproduced (scope 403, rate-limit shape, annotations naming, thread issue from source); MEDIUM for Google-side behaviour (A1, A2, A5)

**Research date:** 2026-11-06
**Valid until:** 2026-11-20 (fast-moving: fastmcp and mcp both released majors within the last 6 weeks; re-check pins before install)

## Resolved Open Questions (user decisions, 2026-11-06)

1. **OAuth state store:** ship BOTH `memory` (default) and a Fernet-wrapped Firestore `client_storage` in Phase 2; Firestore store tested against the emulator.
2. **Guides revision date (MCP-03):** use `meta.created_at_utc` labelled "indexed on". No Phase 1 schema change.
3. **`buddy_report_gap` annotation:** non-read-only (`read_only_hint=False`); a test asserts it is the only non-read-only tool of the five.
4. **Live Google / claude.ai login:** manual checkpoint (needs public HTTPS); may close in Phase 4.
