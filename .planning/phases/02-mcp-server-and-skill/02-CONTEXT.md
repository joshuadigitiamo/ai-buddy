# Phase 2: MCP Server and Skill - Context

**Gathered:** 2026-11-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver `services/mcp_server`: a Python MCP server on streamable-http (stateless, JSON responses, no held-open stream, no state on the container filesystem) that loads the Phase 1 `index.db` at cold start and exposes exactly five read-only tools (`handbook_get`, `handbook_search`, `guides_search`, `guides_get_section`, `buddy_report_gap`) plus the `handbook://{pagina}` resource. Every result carries source URL + revision date (+ `video_url` for mapped Guides sections). Auth: Google OAuth restricted to `@digitiamo.com`, bot-to-server auth defined here, rate limiting, auth switchable off for local/kind only. Also deliver the `digitiamo-buddy` Skill and a one-page install guide. Requirements MCP-01..MCP-08.

Not in this phase: Google Chat bot (Phase 3), hosting choice / deploy manifests / index handoff to the container (Phase 4), golden-set eval (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (not re-discussed)
- Phase 1 D-11: index loaded at cold start only, no hot reload. D-12: `ArtifactStore` local-dir only; host handoff decided in Phase 4.
- Phase 1 D-21: Guides index is English; the caller (Skill/bot) bridges Italian → English keywords for `guides_search`.
- Phase 1: handbook citation is `handbook://<page_id>`, page_id = file stem; `index.db` schema 1.0.0. No ClickUp anywhere (D-25..D-27).
- Public repo: no handbook content, no employee names committed.

### Handbook search and citations
- **D-01:** `handbook_search` uses an **in-memory SQLite FTS5 table built at cold start** from `handbook_pages`. `index.db` schema stays 1.0.0; `jobs/sync` untouched. Query building reuses the safe `to_match_query` approach (quoted tokens, bound MATCH parameter).
- **D-02:** Italian stemming: apply an Italian Snowball stemmer (e.g. `snowballstemmer`, Python) to page text and query before FTS indexing/matching. New runtime dependency, pinned like the Phase 1 pins. Phase 5 Recall validates.
- **D-03:** A `handbook_search` hit = **whole page** (full markdown + citation). Pages are small (~170 words avg).
- **D-04:** Handbook source URL = `handbook://<page_id>` only (no web URL; no base-URL env). Revision date from `revision_date_iso`.
- **D-05:** Guides source URL = GitHub permalink pinned to the index's `guides_commit_sha`: `https://github.com/<owner>/<repo>/blob/<sha>/<file>#L<start>-L<end>`. Repo web base from config/env. Private repo → 404 for others until rollout (consistent with D15).

### Tool output contract
- **D-06:** Results are **structured** (typed return models → `outputSchema` + `structuredContent`: e.g. `source_url`, `revision_date`, `video_url`, `title`, `text`) **plus a short text rendering** for clients that ignore structured output. The Phase 3 bot parses fields, not prose. — **Reversibility:** costly — output schema is the contract consumed by the Phase 3 bot and the Skill.
- **D-07:** `handbook_get()` with no section returns a **table of contents** (page_id, title, revision date); with a section returns that page.
- **D-08:** No match → `{results: [], status: "no_results", query}`; not an MCP error (`isError` false). Skill instructs refuse + `buddy_report_gap`.
- **D-09:** Search tools return 5 results by default with an optional `limit` parameter capped at 10.
- **D-10:** Gap log document: `question`, timestamp, marker `"nessuna fonte trovata"`, `expire_at` (Firestore TTL, default **90 days**, configurable by env), plus optional queries/tools tried and the index `build_id`. **Never** any user identity (no user id, email, IP, session id).

### Auth, bot-to-server, storage
- **D-11:** Server library chosen by the researcher: standalone `fastmcp` (built-in Google OAuth proxy) vs official `mcp` SDK FastMCP (resource-server only). Criterion: claude.ai custom connector, Claude Desktop and Claude Code can complete the Google login restricted to `@digitiamo.com`, while still stateless + JSON responses.
- **D-12:** Bot-to-server auth (resolves STATE.md Phase 2 blocker): the bot's **service account mints a Google-signed ID token**; server verifies signature, audience and an allowlist of SA emails from env. No shared secret. Tests use a fake verifier.
- **D-13:** Auth off via env flag (e.g. `AUTH_MODE=off`) for local/kind only; server **refuses to start with auth off when `K_SERVICE` is set** (Cloud Run marker) and logs a loud warning. Covered by a test.
- **D-14:** Rate limiting = **in-memory token bucket per caller identity, per instance**, limits from env. Inexact across instances — accepted for single user. No database involvement.
- **D-15:** Gap log behind a **`GapLog` port** with a **Firestore adapter** (keeps PLAN D10 and MCP-05). Adapter tested against the Firestore emulator in Docker; tools tested with a fake. Mirrors the Phase 1 `ArtifactStore` pattern. — **Reversibility:** reversible — backend swap is a new adapter.

### Skill `digitiamo-buddy`
- **D-16:** Referral contacts: the Skill commits a **topic → role map** only; the model resolves the actual person/email via `handbook_search` (handbook keeps work contacts, Phase 1 D-16). No names in the repo.
- **D-17:** Escalation topic list: **Claude drafts** (from the test handbook + usual sensitive areas: salary, health/sickness, harassment, disciplinary, contract changes, personal data), **Joshua reviews and approves** before execution of the Skill task (checkpoint).
- **D-18:** SKILL.md instructions in **English**; answer templates and refusal phrases in **Italian** (answer, fonte, owner/referente, data di revisione; "non lo so, chiedi a ..."). Includes the Italian → English keyword bridge for `guides_search`.
- **D-19:** One-page install guide covers **claude.ai custom connector + Skill upload, Claude Desktop, Claude Code** (`claude mcp add --transport http` + skill folder).

### Claude's Discretion
- Exact field names of the output models; text rendering format.
- Server config shape (pydantic-settings like `jobs/sync`), env var names, logging (no question text in INFO logs beyond what gap log stores — planner decides).
- `handbook://` resource listing behaviour (resource template vs listed resources).
- Default rate-limit numbers; snowball token handling details (stopwords, prefix match on top of stemming).
- `guides_get_section(id)` id = existing `chunk_key`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and plan
- `.planning/REQUIREMENTS.md` — MCP-01..MCP-08
- `.planning/ROADMAP.md` — Phase 2 goal and 5 success criteria
- `.planning/PROJECT.md` — locked D1-D16 (esp. D3, D4, D5, D10, D11, D15, D16), constraints (MCP, gap log, secrets, public repo)
- `docs/PLAN.md` §3 "Architettura / Fase 1" — tool contract, resource, Skill, gap log

### Phase 1 contract
- `.planning/phases/01-content-sync/01-CONTEXT.md` — D-08..D-12 (index.db contract, cold start, ArtifactStore), D-21 (English index), D-25..D-27 (local sources)
- `packages/buddy_core/buddy_core/schema.py`, `index_reader.py`, `models.py` — index.db 1.0.0 reader API

### Best practices (D16) — `~/Desktop/WORK/Guides/AI-Engineering/MCP_SERVERS_GUIDE.md`
- §5 Tools, §6 Resources (§6.3 tool vs resource), §11 Statelessness, §12 Transports, §17 Authorization, §18 Security, §19 Scaling, §20 Tool surface design, §22 Testing, §26 Common mistakes
- Also RAG_CHATBOT_GUIDE (source-carrying retrieval output) and DESIGN_PATTERNS_GUIDE (ports/adapters) in `~/Desktop/WORK/Guides/` — plan cites exact sections and exceptions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `buddy_core.index_reader.open_index(path)` → `IndexReader`: `load_handbook()`, `get_page(page_id)`, `guide_chunks()`, `video_links()`, `search_guides(query, limit)` → `SearchHit(chunk, score, video)`; raises `IndexFormatError` / `IndexVersionError` (major mismatch).
- `to_match_query(query)` — safe FTS5 query builder; reuse for the in-memory handbook FTS.
- `models.video_link(VideoLink)` — composes `url#t=<s>`; `HandbookPage.revision_date_iso`, `IndexMeta.guides_commit_sha` / `build_id`.
- `buddy_core.store` `ArtifactStore` / `LocalDirArtifactStore` — how the server locates `index.db` (path from env).

### Established Patterns
- Ports + single adapter (ArtifactStore) → same for GapLog.
- Config via pydantic-settings; validation errors name variables, never values (`jobs/sync/buddy_sync/config.py`).
- Dependencies pinned `==` to latest verified on PyPI; ruff, mypy --strict, pytest in Docker via `run-unit-tests.sh`.

### Integration Points
- `services/mcp_server/` is empty (`.gitkeep`) — new package, own Dockerfile stage.
- Phase 3 bot is an MCP client over HTTP using D-12 auth and D-06 structured output.
- Firestore emulator needs a docker compose service for tests.

</code_context>

<specifics>
## Specific Ideas

- User asked whether pgvector/Postgres could replace Firestore: answered that pgvector is for embeddings (not needed, D5) and Postgres could hold the gap log; kept Firestore behind a port, backend revisited in Phase 4.

</specifics>

<deferred>
## Deferred Ideas

- Gap log backend Firestore vs Postgres (Neon/Supabase EU free tier) — decide in Phase 4 with hosting (free-hosting goal).
- Vector search (`sqlite-vec` or pgvector) — only if Phase 5 Guides Recall@5 < 0.8 (D5).

</deferred>

---

*Phase: 02-mcp-server-and-skill*
*Context gathered: 2026-11-06*
