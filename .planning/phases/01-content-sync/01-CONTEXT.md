# Phase 1: Content Sync - Context

**Gathered:** 2026-11-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Repo foundation (D11 layout, Python 3.12 tooling, Dockerized `run-unit-tests.sh`) plus a sync job that turns the ClickUp test handbook (`xkwgt-39975`, id from env) and the Guides repo into one redacted, incremental, versioned index artifact with a Guides section → video map. Requirements: FND-01, FND-02, GUIDE-01, SYNC-01..07.

Out of this phase: serving the index (Phase 2), hosting/deploy and the concrete artifact handoff (Phase 4), retrieval quality measurement (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Video mapping (SYNC-06)
- **D-01:** Link target = full video URL + timestamp fragment (e.g. `rag-chatbot.mp4#t=312`). No per-scene clip assets in Milestone 1. Literal D15 "single-scene clip" is relaxed to "scene start in the full video".
- **D-02:** Section → scene matching via an explicit, hand-maintained map file (no heuristic text matching).
- **D-03:** Map lives in the Guides repo, next to the video sources: `videos/<topic>/sections.yaml` (scene id → guide file + heading). — **Reversibility:** costly — format becomes a cross-repo contract between the Guides video pipeline and `jobs/sync`.
- **D-04:** Scene start times are computed by sync from each video's `durations.json` (committed to the Guides repo per video), summing scene durations per part. No hand-typed timestamps.
- **D-05:** Multi-part videos: the map resolves a scene to the correct part file (`<topic>_partN.mp4`) plus the offset inside that part.
- **D-06:** Fallbacks: section of a guide that has a video but no map entry → full video URL (correct part if determinable, else part 1), no timestamp. Guide with no video → no video. Full-video URLs are read from the Guides `README.md` table.
- **D-07:** Phase 1 scope for maps: define the `sections.yaml` format, the sync loader and tests, and fill real maps for 1-2 videos (e.g. `rag-chatbot`, `mcp-servers`). Everything else uses the D-06 fallback.

### Index artifact (SYNC-05, SYNC-07)
- **D-08:** Artifact = single SQLite file `index.db` with tables for handbook pages (full markdown, ClickUp deep-link URL, title, `date_edited`, content hash), Guides chunks (FTS5), video map, and `meta` (schema_version, build id, Guides commit SHA, source doc id). — **Reversibility:** one-way — published contract read by `mcp_server` in Phase 2; format changes need a schema_version major bump.
- **D-09:** Versioning = `schema_version` (semver; consumer refuses a mismatched major) + build id = UTC timestamp + content hash. Unchanged content → same hash → no new artifact written.
- **D-10:** Incremental state lives inside the previous artifact: sync loads the last `index.db` and compares per-page `date_edited` + content hash. No separate state file.
- **D-11:** Consumers load the artifact at cold start only; no hot reload (constrains Phase 2).
- **D-12:** Handoff is host-agnostic in Phase 1: an `ArtifactStore` interface with a **local-directory implementation only** (path from env). Bucket vs baked-into-image, and the hosting platform itself, are decided in Phase 4. Reason: user wants hosting free if possible, which reopens D7 (Cloud Run needs a billing account even at ~0 cost). **SYNC-07 is satisfied in Phase 1 by the documented format + this recorded deferral; REQUIREMENTS.md SYNC-07 / INFRA-04 wording should be updated to match.**

### Redaction (SYNC-03)
- **D-13:** Excluded pages identified by a page-id denylist from config/env (e.g. `REDACT_PAGE_IDS`), containing the Wi-Fi page id. Test asserts the denylisted page never reaches `index.db`. No title matching.
- **D-14:** Detector hit on a non-denylisted page → mask the span with `[REDATTO]`, index the rest, log page id + rule name. Never log the matched value.
- **D-15:** Detector rules (all enabled): password/PIN labels with a value (IT + EN labels, e.g. password, pwd, PIN, codice accesso); token/key formats (API key prefixes, JWTs, private-key blocks, high-entropy strings); private personal data (non-company emails, mobile numbers, IBANs); signed URLs (query-string tokens stripped).
- **D-16:** Work contacts are kept: names, roles, `@digitiamo.com` emails and office numbers stay (needed for "chiedi a ..." referrals). Company data (P.IVA, SDI, addresses) is legitimate content and is kept.
- **D-17:** ClickUp attachment image links are dropped; alt text is kept.
- **D-18:** The same redaction filter runs on Guides content too (one pipeline for all sources).

### Guides scope and chunking (SYNC-04)
- **D-19:** Indexed files: include glob for `*_GUIDE.md` + `AI-Engineering/MULTI_AGENT_ARCHITECTURE_DESIGN.md`. Excluded: `README.md` (read only for video URLs), all `CLAUDE.md`, `videos/`.
- **D-20:** Chunk = one per `###`, carrying its parent `##` title, file and line range; an `##` with no `###` is one chunk; oversized chunks are split at paragraph boundaries and keep the same heading.
- **D-21:** The index stays English (FTS5, porter + unicode61 tokenizer). The Italian → English bridge is the caller's job (Skill / bot sends English keywords to `guides_search`); Phase 5 Recall@5 validates it.
- **D-22:** Guides source = `git clone/pull` of `GUIDES_REPO_URL` with a read-only token from env, pinned branch (`master`); commit SHA stored in `meta`. Tests use a local fixture repo.
- **D-23:** `GUIDES_INDEX.md` (assumed by D5) does not exist yet. Decision: create it **in the Guides repo** (section → file:line map), generated rather than hand-written; sync reads it. — **Reversibility:** costly — second cross-repo contract alongside `sections.yaml`.
- **D-24:** Guides incremental: skip the Guides rebuild when the commit SHA is unchanged; otherwise rebuild the Guides tables fully.

### Scope change 2026-11-03 (during plan 01-08 execution)
- **D-25:** ClickUp is being shut down. No live or recurring ClickUp sync. The handbook source is the existing 23-page raw snapshot (`docs/research/handbook-raw/`), maintained by us from now on. No `CLICKUP_TOKEN` is needed. Supersedes the live-sync parts of D-13 (denylist stays, keyed by page file instead of ClickUp page id), SYNC-01 and the ClickUp deep-link part of SYNC-05.
- **D-26:** Handbook Markdown lives in a gitignored local folder of this repo, mounted read-only into the sync like the Guides. It is never committed (public repo).
- **D-27:** Guides are read from the local checkout `~/Desktop/WORK/Guides` mounted read-only; no `GUIDES_REPO_TOKEN`. Supersedes the token/https part of D-22 for Milestone 1.
- **Follow-up:** a gap plan adds a local-folder handbook source, removes the live ClickUp path from the pipeline and CLI, defines the replacement citation for handbook pages, rewrites SYNC-01/SYNC-05 accordingly, and reworks plan 01-08 Task 3 (live run) to use the local sources only.

### Claude's Discretion
- How `GUIDES_INDEX.md` is generated (script location: Guides repo vs `jobs/sync` tool) and what sync does when it disagrees with actual headings (fail vs regenerate vs warn). Drift risk must be covered by a test.
- `sections.yaml` exact schema and `durations.json` reading details.
- ClickUp client: REST API v3 docs endpoints with a token from env (the names `list_document_pages` / `get_document_pages` in SYNC-01 are ClickUp MCP tool names; equivalent REST calls are fine). Tests use recorded fixtures; no live API in the unit suite.
- Sync job CLI shape and logging, SQLite schema details beyond D-08, high-entropy threshold.
- Repo foundation details (FND-01/02) follow the user's standard template; nothing was discussed beyond REQUIREMENTS.md.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope and locked decisions
- `.planning/PROJECT.md` — D1-D16, constraints (Docker-only, test runner, tooling, redaction, repo layout)
- `.planning/REQUIREMENTS.md` — FND-01, FND-02, GUIDE-01, SYNC-01..07 (SYNC-07/INFRA-04 wording to align with D-12)
- `.planning/ROADMAP.md` — Phase 1 success criteria
- `docs/PLAN.md` — sections 2 and 2.1 (2.1 overrides), D5 rationale, architecture diagram, ClickUp sync notes
- `.planning/intel/decisions.md` — decision rationale and confidence tags

### Source data
- `docs/research/handbook-raw/` — 23-page raw snapshot the test doc `xkwgt-39975` was copied from; fixture source for sync and redaction tests (contains the Wi-Fi page; never copy its values into artifacts or plans)
- `~/Desktop/WORK/Guides/README.md` — full-video URL table per guide (fallback video source, D-06)
- `~/Desktop/WORK/Guides/videos/<topic>/scenes.py`, `narration.py` — scene ids (S01..Snn) and chapter kickers for `sections.yaml`
- `~/Desktop/WORK/Guides/videos/<topic>/out/durations.json` — scene durations (currently local, uncommitted; e.g. present for `multi-agent-design`)

### Standards (D16 / GUIDE-01)
- `~/Desktop/WORK/Guides/AI-Engineering/RAG_CHATBOT_GUIDE.md` — chunking by heading, ingestion provenance, retrieval basics (section numbers to be verified by the plan)
- `~/Desktop/WORK/Guides/Foundations/DESIGN_PATTERNS_GUIDE.md` — source adapters, `ArtifactStore` interface
- `~/Desktop/WORK/TURISANDA/turisanda-ai-travel-assistant-NEW/run-unit-tests.sh` — template for FND-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None in this repo: only a PyCharm stub `main.py` (delete) and a bare `pyproject.toml` (`requires-python >=3.11`; must move to 3.12).

### Established Patterns
- User-wide: pip + requirements files, ruff, pytest `-v --tb=short --cov`, `mypy --strict`, everything in Docker, `run-unit-tests.sh` template above.

### Integration Points
- `index.db` is the contract consumed by `services/mcp_server` (Phase 2) and by Recall@5 eval (Phase 5).
- Guides repo gains two contracts: `videos/<topic>/sections.yaml` (+ committed `durations.json`) and `GUIDES_INDEX.md`.

</code_context>

<specifics>
## Specific Ideas

- User goal: host the whole project for free if possible. Keep Phase 1 free of any cloud dependency.
- Repo `ai-buddy` is public: no handbook content, credentials or index artifacts get committed; fixtures must use synthetic secrets.

</specifics>

<deferred>
## Deferred Ideas

- Revisit D7 hosting in Phase 4: no-card hosts (Hugging Face Spaces, Render EU, Oracle Always Free, self-hosted k3s) vs Cloud Run free tier, under GDPR EU residency, Google Chat public HTTPS and public-repo constraints (no public image containing handbook content). Decide artifact handoff (bucket vs baked image) there.
- Fill `sections.yaml` maps for the remaining videos.
- Per-scene clip assets (literal D15) if timestamps prove unreliable in Google Chat / browsers.
- Italian synonyms per chunk at sync time, only if Phase 5 Recall@5 < 0.8.

</deferred>

---

*Phase: 01-content-sync*
*Context gathered: 2026-11-03*
