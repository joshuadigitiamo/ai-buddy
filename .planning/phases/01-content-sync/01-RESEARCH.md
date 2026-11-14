# Phase 1: Content Sync - Research

**Researched:** 2026-11-03
**Domain:** Python 3.12 monorepo foundation (Docker-only tooling) + ClickUp Docs v3 sync + Git-sourced Markdown chunking into SQLite FTS5 + redaction + video-map resolution
**Confidence:** MEDIUM-HIGH (ClickUp API shape, SQLite FTS5, markdown parsing, Guides data and package versions verified this session; the unit of `date_edited`, the live response shape of `/pages` and the token-in-git-header pattern are not yet verified live)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Video mapping (SYNC-06)**
- **D-01:** Link target = full video URL + timestamp fragment (e.g. `rag-chatbot.mp4#t=312`). No per-scene clip assets in Milestone 1. Literal D15 "single-scene clip" is relaxed to "scene start in the full video".
- **D-02:** Section → scene matching via an explicit, hand-maintained map file (no heuristic text matching).
- **D-03:** Map lives in the Guides repo, next to the video sources: `videos/<topic>/sections.yaml` (scene id → guide file + heading). — **Reversibility:** costly — format becomes a cross-repo contract between the Guides video pipeline and `jobs/sync`.
- **D-04:** Scene start times are computed by sync from each video's `durations.json` (committed to the Guides repo per video), summing scene durations per part. No hand-typed timestamps.
- **D-05:** Multi-part videos: the map resolves a scene to the correct part file (`<topic>_partN.mp4`) plus the offset inside that part.
- **D-06:** Fallbacks: section of a guide that has a video but no map entry → full video URL (correct part if determinable, else part 1), no timestamp. Guide with no video → no video. Full-video URLs are read from the Guides `README.md` table.
- **D-07:** Phase 1 scope for maps: define the `sections.yaml` format, the sync loader and tests, and fill real maps for 1-2 videos (e.g. `rag-chatbot`, `mcp-servers`). Everything else uses the D-06 fallback.

**Index artifact (SYNC-05, SYNC-07)**
- **D-08:** Artifact = single SQLite file `index.db` with tables for handbook pages (full markdown, ClickUp deep-link URL, title, `date_edited`, content hash), Guides chunks (FTS5), video map, and `meta` (schema_version, build id, Guides commit SHA, source doc id). — **Reversibility:** one-way — published contract read by `mcp_server` in Phase 2; format changes need a schema_version major bump.
- **D-09:** Versioning = `schema_version` (semver; consumer refuses a mismatched major) + build id = UTC timestamp + content hash. Unchanged content → same hash → no new artifact written.
- **D-10:** Incremental state lives inside the previous artifact: sync loads the last `index.db` and compares per-page `date_edited` + content hash. No separate state file.
- **D-11:** Consumers load the artifact at cold start only; no hot reload (constrains Phase 2).
- **D-12:** Handoff is host-agnostic in Phase 1: an `ArtifactStore` interface with a **local-directory implementation only** (path from env). Bucket vs baked-into-image, and the hosting platform itself, are decided in Phase 4. Reason: user wants hosting free if possible, which reopens D7 (Cloud Run needs a billing account even at ~0 cost). **SYNC-07 is satisfied in Phase 1 by the documented format + this recorded deferral; REQUIREMENTS.md SYNC-07 / INFRA-04 wording should be updated to match.**

**Redaction (SYNC-03)**
- **D-13:** Excluded pages identified by a page-id denylist from config/env (e.g. `REDACT_PAGE_IDS`), containing the Wi-Fi page id. Test asserts the denylisted page never reaches `index.db`. No title matching.
- **D-14:** Detector hit on a non-denylisted page → mask the span with `[REDATTO]`, index the rest, log page id + rule name. Never log the matched value.
- **D-15:** Detector rules (all enabled): password/PIN labels with a value (IT + EN labels, e.g. password, pwd, PIN, codice accesso); token/key formats (API key prefixes, JWTs, private-key blocks, high-entropy strings); private personal data (non-company emails, mobile numbers, IBANs); signed URLs (query-string tokens stripped).
- **D-16:** Work contacts are kept: names, roles, `@digitiamo.com` emails and office numbers stay (needed for "chiedi a ..." referrals). Company data (P.IVA, SDI, addresses) is legitimate content and is kept.
- **D-17:** ClickUp attachment image links are dropped; alt text is kept.
- **D-18:** The same redaction filter runs on Guides content too (one pipeline for all sources).

**Guides scope and chunking (SYNC-04)**
- **D-19:** Indexed files: include glob for `*_GUIDE.md` + `AI-Engineering/MULTI_AGENT_ARCHITECTURE_DESIGN.md`. Excluded: `README.md` (read only for video URLs), all `CLAUDE.md`, `videos/`.
- **D-20:** Chunk = one per `###`, carrying its parent `##` title, file and line range; an `##` with no `###` is one chunk; oversized chunks are split at paragraph boundaries and keep the same heading.
- **D-21:** The index stays English (FTS5, porter + unicode61 tokenizer). The Italian → English bridge is the caller's job (Skill / bot sends English keywords to `guides_search`); Phase 5 Recall@5 validates it.
- **D-22:** Guides source = `git clone/pull` of `GUIDES_REPO_URL` with a read-only token from env, pinned branch (`master`); commit SHA stored in `meta`. Tests use a local fixture repo.
- **D-23:** `GUIDES_INDEX.md` (assumed by D5) does not exist yet. Decision: create it **in the Guides repo** (section → file:line map), generated rather than hand-written; sync reads it. — **Reversibility:** costly — second cross-repo contract alongside `sections.yaml`.
- **D-24:** Guides incremental: skip the Guides rebuild when the commit SHA is unchanged; otherwise rebuild the Guides tables fully.

### Claude's Discretion
- How `GUIDES_INDEX.md` is generated (script location: Guides repo vs `jobs/sync` tool) and what sync does when it disagrees with actual headings (fail vs regenerate vs warn). Drift risk must be covered by a test.
- `sections.yaml` exact schema and `durations.json` reading details.
- ClickUp client: REST API v3 docs endpoints with a token from env (the names `list_document_pages` / `get_document_pages` in SYNC-01 are ClickUp MCP tool names; equivalent REST calls are fine). Tests use recorded fixtures; no live API in the unit suite.
- Sync job CLI shape and logging, SQLite schema details beyond D-08, high-entropy threshold.
- Repo foundation details (FND-01/02) follow the user's standard template; nothing was discussed beyond REQUIREMENTS.md.

### Deferred Ideas (OUT OF SCOPE)
- Revisit D7 hosting in Phase 4: no-card hosts (Hugging Face Spaces, Render EU, Oracle Always Free, self-hosted k3s) vs Cloud Run free tier, under GDPR EU residency, Google Chat public HTTPS and public-repo constraints (no public image containing handbook content). Decide artifact handoff (bucket vs baked image) there.
- Fill `sections.yaml` maps for the remaining videos.
- Per-scene clip assets (literal D15) if timestamps prove unreliable in Google Chat / browsers.
- Italian synonyms per chunk at sync time, only if Phase 5 Recall@5 < 0.8.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-01 | D11 layout, Python 3.12, pip requirements, ruff/pytest/mypy configured | Standard Stack (pinned versions), Recommended Project Structure, Pattern 1 (Docker `test` stage), pyproject config in Code Examples |
| FND-02 | Dockerized `run-unit-tests.sh` with three modes | Template read in full; Pattern 1 lists the required deviations (ruff+mypy in `--all`, `--user`, cache dirs, `--network none`, coverage gate only on `--all`) |
| GUIDE-01 | Plans cite Guides sections + exceptions | "Guides Applied (D16)" table with verified section/line numbers and the exceptions to justify |
| SYNC-01 | Read ClickUp doc via env id, token from env | ClickUp API facts (verified from official OpenAPI): `/pages` returns tree + content + dates in one call; `workspace_id` is a required path parameter |
| SYNC-02 | Incremental by `date_edited` / content hash, not `date_updated` | Pattern 3 (incremental decision), Pitfalls 3, 4, 5 |
| SYNC-03 | Redaction before indexing | Pattern 4 (rule registry), Pitfall 6 (false positives measured on corpus), test-corpus strategy |
| SYNC-04 | Guides split by heading into FTS5 with file/heading/line | Pattern 5 (fence-aware chunker via markdown-it-py), measured chunk statistics, Pitfall 1, 2 |
| SYNC-05 | Handbook snapshot with URL, title, `date_edited` | Index schema (Pattern 2), deep-link format |
| SYNC-06 | Video mapping with fallback to README full URL | Pattern 6 (sections.yaml + durations + README parser), Pitfall 8 (download URLs and `#t=`) |
| SYNC-07 | Versioned artifact format + recorded handoff decision | Pattern 2 (schema/versioning/logical content hash), ADR plan, REQUIREMENTS wording update |
</phase_requirements>

## Summary

Phase 1 is greenfield (only a PyCharm stub `main.py` and a bare `pyproject.toml` with `requires-python = ">=3.11"` exist). Everything runs in Docker. The core of the phase is a deterministic pipeline: **sources** (ClickUp adapter, Guides git adapter) -> **redaction** -> **normalise/chunk** -> **SQLite index builder** -> **ArtifactStore (local dir)**. All shared code (schema, row models, reader/search, store interface, version check) belongs in `packages/buddy_core` because Phase 2's `mcp_server` must read the same file; the pipeline belongs in `jobs/sync`.

Four findings change how the locked decisions should be implemented and must reach the planner. (1) The ClickUp v3 `page_listing` endpoint returns **no dates**; only `/pages` returns `date_edited`, `date_updated` and content, so a single `/pages` call per run supplies everything (SYNC-01's two MCP tool names collapse to one REST call). (2) 548 heading-like lines in the Guides sit **inside code fences** (`# comment` in Python/bash blocks), and 174 `##` sections carry prose **before their first `###`**, which D-20 as worded would silently drop; the chunker must use a real Markdown parser and emit a preamble chunk. (3) Scene durations sum to the README video lengths within ~1 s, so computed offsets (D-04) are sound, but `rag-chatbot` (named in D-07) has **no `durations.json`** locally, and `videos/**/out/` is gitignored, so "committed durations.json" needs a gitignore change. (4) README video URLs are GitHub release-asset **download** links in a private repo, so a `#t=` fragment will likely not do anything there; store the offset as data and compose the fragment in the consumer.

**Primary recommendation:** Build the logical content hash and per-page change detection over normalised, canonical rows (never SQLite file bytes), use `markdown-it-py` for fence-aware heading/line extraction, use `httpx` + `httpx.MockTransport` for the ClickUp client (no extra mocking dependency), and make `run-unit-tests.sh --all` run ruff, mypy and pytest-cov as the template-compatible gate while the `--single*` modes run pytest only.

## Architectural Responsibility Map

This phase has no browser, SSR or CDN tier. Tiers here are the project's own components.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Index schema, row models, version check, read/search API | `packages/buddy_core` | — | Single shared contract; Phase 2 `mcp_server` imports it, never re-implements SQL |
| `ArtifactStore` interface + local-dir implementation | `packages/buddy_core` | `jobs/sync` (producer) | Interface shared by producer and consumer; Phase 4 adds bucket implementation without touching callers |
| ClickUp REST client + page tree flattening | `jobs/sync` | — | Only sync talks to ClickUp (token never reaches the server) |
| Guides git acquisition (clone/pull, SHA) | `jobs/sync` | — | Only sync needs git and the Guides token |
| Redaction filter | `jobs/sync` | — | Runs before anything is written; one pipeline for all sources (D-18) |
| Heading chunker, `GUIDES_INDEX.md` generator | `jobs/sync` | Guides repo (hosts the generated file) | The chunker is the line-number authority; the generated file is a derived view |
| Video map resolution (`sections.yaml`, `durations.json`, README) | `jobs/sync` | Guides repo (data owner) | Resolved at sync time and stored in `video_map`; the server only joins |
| Keyword search over Guides (`bm25`, query sanitising) | `packages/buddy_core` | — | Success criterion 4 needs a query function now; Phase 2 wraps it in a tool |
| Test runner / Docker image | repo root | — | FND-02 |
| Persistence of the built artifact | local directory (env path) | — | Bucket / image handoff deferred to Phase 4 (D-12) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python (image `python:3.12-slim`) | 3.12 | Runtime in Docker | Locked by FND-01. `sqlite3` in this image reports SQLite 3.46.1 with `ENABLE_FTS5` [VERIFIED: ran `docker run python:3.12-slim` this session] |
| `sqlite3` (stdlib) | 3.46.1 | Index artifact, FTS5 | Locked by D-08; no extension to install |
| `httpx` | 0.28.1 | ClickUp REST client | Typed, supports `httpx.MockTransport` so unit tests need no extra mock library [VERIFIED: `pip install` in python:3.12 container, 2026-11-03] |
| `markdown-it-py` | 4.2.0 | Fence-aware heading and block extraction with line maps | `Token.map` gives `[start, end)` line ranges; heading-looking lines inside fences are not tokenised as headings [VERIFIED: ran parse of a doc with `# not heading` inside a fence this session — only the real `h1/h2/h3` produced `heading_open`] |
| `pydantic` | 2.14.2 | Validate the ClickUp response (`extra="ignore"`) and Settings | External JSON must be validated at the boundary [VERIFIED: pip install] |
| `pydantic-settings` | 2.16.2 | Env-driven config with `SecretStr` so tokens never print in `repr`/logs | [VERIFIED: pip install] |
| `PyYAML` | 6.0.3 | Parse `sections.yaml` with `yaml.safe_load` only | [VERIFIED: pip install] |
| `git` CLI (apt in image) | Debian pkg | Clone/pull Guides via `subprocess` | `python:3.12-slim` has **no git** [VERIFIED: `git: command not found` in that image this session]; add `apt-get install -y --no-install-recommends git` |

### Supporting (dev)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.2.0 | Test runner (`-v --tb=short`) | All tests |
| `pytest-cov` | 7.1.0 | Coverage (`--cov`) | `--all` mode only for the fail-under gate |
| `ruff` | 0.17.3 | Lint + format (no black/isort) | `--all` mode: `ruff check` and `ruff format --check` |
| `mypy` | 2.4.1 | `--strict` | `--all` mode |
| `types-PyYAML` | 6.0.12.20261103 | Stubs so `mypy --strict` passes on `yaml` | Dev only |

Versions above all [VERIFIED: pip install / pip list inside `python:3.12` on 2026-11-03].

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx.MockTransport` | `respx` 0.23.1 | Extra dependency for no gain at one endpoint; MockTransport is built in |
| `markdown-it-py` | hand-rolled `^#{2,3} ` regex with a fence toggle | Breaks on `~~~` fences, indented code, HTML blocks; the corpus has 548 heading-like lines inside fences, so a regex needs exactly the logic the parser already has |
| `pydantic-settings` | plain `os.environ` + dataclass | Saves one dependency; loses `SecretStr` masking. Acceptable fallback if the user wants fewer deps |
| `detect-secrets` | curated regex rules | detect-secrets is file-scanner oriented and would still need the IT labels and `[REDATTO]` masking; a small table-driven rule registry is simpler and fully testable here |
| `GitPython` | `subprocess` + `git` | Extra dependency; only five git commands are needed |

**Installation (inside the Docker build, never on the host):**
```bash
pip install --no-cache-dir -r requirements-dev.txt
```
`requirements.txt` (runtime): `httpx==0.28.1`, `markdown-it-py==4.2.0`, `pydantic==2.14.2`, `pydantic-settings==2.16.2`, `PyYAML==6.0.3`.
`requirements-dev.txt`: `-r requirements.txt`, `pytest==9.2.0`, `pytest-cov==7.1.0`, `ruff==0.17.3`, `mypy==2.4.1`, `types-PyYAML==6.0.12.20261103`.

## Package Legitimacy Audit

Ran `query package-legitimacy check --ecosystem pypi ...` (the code seam) on all 11 candidate packages. Every package returned **SUS**, and the only reasons were `unknown-downloads` (the seam cannot get PyPI download counts) plus `too-new` on packages whose *latest release* is days old (pydantic, pydantic-settings, pytest, ruff, mypy, types-PyYAML) and `no-repository` for `pytest-cov` (PyPI metadata has no repo URL). None returned `SLOP`. All exist on PyPI (installed successfully in `python:3.12` this session) and all but `pytest-cov` expose a source repo. These are mainstream, long-lived projects; the `too-new` flag reflects release cadence, not a new project.

| Package | Registry | Latest release | Source Repo | Seam verdict | Disposition |
|---------|----------|----------------|-------------|--------------|-------------|
| httpx | PyPI | 2024-12-06 | github.com/encode/httpx | SUS (unknown-downloads) | Flagged — batch checkpoint |
| markdown-it-py | PyPI | 2026-05-07 | github.com/executablebooks/markdown-it-py | SUS (unknown-downloads) | Flagged — batch checkpoint |
| pydantic | PyPI | 2026-10-29 | github.com/pydantic/pydantic | SUS (too-new, unknown-downloads) | Flagged — batch checkpoint |
| pydantic-settings | PyPI | 2026-10-28 | github.com/pydantic/pydantic-settings | SUS (too-new, unknown-downloads) | Flagged — batch checkpoint |
| PyYAML | PyPI | 2025-09-25 | pyyaml.org | SUS (unknown-downloads) | Flagged — batch checkpoint |
| pytest | PyPI | 2026-10-27 | github.com/pytest-dev/pytest | SUS (too-new, unknown-downloads) | Flagged — batch checkpoint |
| pytest-cov | PyPI | 2026-03-21 | none in metadata | SUS (unknown-downloads, no-repository) | Flagged — batch checkpoint |
| ruff | PyPI | 2026-10-27 | docs.astral.sh/ruff | SUS (too-new, unknown-downloads) | Flagged — batch checkpoint |
| mypy | PyPI | 2026-10-28 | mypy-lang.org | SUS (too-new, unknown-downloads) | Flagged — batch checkpoint |
| types-PyYAML | PyPI | 2026-11-03 | github.com/python/typeshed | SUS (too-new, unknown-downloads) | Flagged — batch checkpoint |
| respx | PyPI | 2026-04-08 | lundberg.github.io/respx | SUS | Not recommended (MockTransport instead) |

**Packages removed due to SLOP verdict:** none.
**Packages flagged SUS:** all of the above. Because the seam is blind to download counts, the planner should insert **one** `checkpoint:human-verify` task covering the pinned `requirements*.txt` (a human glance at the 10 names and versions), not ten separate ones. Package names were chosen from training knowledge and registry-confirmed; per the provenance rule they stay `[ASSUMED]` as recommendations until that checkpoint passes. No `postinstall` scripts apply (PyPI wheels).

## Architecture Patterns

### System Architecture Diagram

```
                       env: CLICKUP_TOKEN, CLICKUP_WORKSPACE_ID, CLICKUP_DOC_ID,
                            REDACT_PAGE_IDS, GUIDES_REPO_URL, GUIDES_REPO_TOKEN,
                            GUIDES_BRANCH, ARTIFACT_DIR
                                         │
                                         ▼
                          ┌─────────────────────────────┐
                          │  jobs/sync  CLI (buddy_sync) │
                          └─────────────┬───────────────┘
              ┌─────────────────────────┴─────────────────────────┐
              ▼                                                   ▼
   ┌──────────────────────┐                           ┌──────────────────────────┐
   │ HandbookSource       │                           │ GuidesSource             │
   │ (ClickUp adapter)    │                           │ (git clone/pull adapter) │
   │ GET /v3/.../pages    │                           │ → checkout dir + SHA     │
   └─────────┬────────────┘                           └────────────┬─────────────┘
             │ flat pages (id, parent, name,                       │ files: *_GUIDE.md,
             │ content, date_edited)                               │ MULTI_AGENT_..., README.md,
             ▼                                                     │ videos/*/sections.yaml,
   denylist (REDACT_PAGE_IDS) ──drop──► (never stored)             │ videos/*/durations.json
             │                                                     ▼
             │                                          SHA == prev meta.sha
             │                                          and pipeline_version same?
             ▼                                               │yes            │no
   change detect vs previous index.db                        ▼               ▼
   (date_edited, raw content hash,                   copy Guides rows   chunker (markdown-it-py)
    redaction_version)                               via ATTACH         → preamble/### chunks
        │unchanged        │changed/new                                         │
        ▼                 ▼                                                    ▼
   copy prev row    Redactor (rules, [REDATTO]) ◄──────────────── Redactor (same filter, D-18)
        │                 │                                                    │
        └────────┬────────┘                                                    ▼
                 │                                              video resolver: README URLs +
                 │                                              sections.yaml + durations.json
                 ▼                                                    → video_map rows
        ┌─────────────────────────────────────────────────────────────────────┐
        │ IndexBuilder (buddy_core): temp file → tables → FTS5 rebuild →      │
        │ meta (schema_version, build_id, content_hash, guides_sha, doc id)   │
        └───────────────────────────────┬─────────────────────────────────────┘
                                        ▼
                  logical content_hash == previous? ──yes──► no artifact written
                                        │no
                                        ▼
                  ArtifactStore.publish()  (os.replace, atomic) ──► ARTIFACT_DIR/index.db
                                        │
                                        ▼
            consumer (Phase 2): load at cold start, refuse mismatched major, query via buddy_core
```

### Recommended Project Structure
```
.
├── Dockerfile                      # stages: base, test  (service images come in Phase 4)
├── run-unit-tests.sh               # FND-02
├── requirements.txt / requirements-dev.txt
├── pyproject.toml                  # ruff, mypy, pytest, coverage config; requires-python >=3.12
├── .env.example                    # placeholders only; used when .env is absent
├── packages/buddy_core/buddy_core/ # index schema, models, reader/search, ArtifactStore, version
├── jobs/sync/buddy_sync/           # cli, config, clickup, handbook, guides_git, chunker,
│                                   # guides_index, redaction/, video_map, builder orchestration
├── services/mcp_server/            # empty placeholder (Phase 2)
├── services/chat_bot/              # empty placeholder (Phase 3)
├── deploy/k8s/  deploy/cloudrun/   # empty placeholders (Phase 4)
├── .github/workflows/              # empty placeholder (Phase 4)
├── docs/index-format.md            # documented, versioned format (SYNC-07)
├── docs/adr/0001-index-handoff.md  # recorded decision (SYNC-07)
└── tests/unit/{buddy_core,buddy_sync}/ + tests/fixtures/ (synthetic only)
```
Import names: `buddy_core` and `buddy_sync` (not `sync`, which is a poor top-level module name). Use pytest `pythonpath = ["packages/buddy_core", "jobs/sync"]` and mypy `mypy_path` so no editable installs are needed when the repo is bind-mounted over `/app`.

### Pattern 1: Docker test stage and runner script
**What:** One root `Dockerfile` with `base` (python:3.12-slim + git + pinned deps) and `test` stages; code is **not** baked in, it is bind-mounted at runtime (template behaviour). Deviations from the template that the plan must include:
- `--all` runs `ruff check .`, `ruff format --check .`, `mypy`, then `pytest --cov ... --cov-fail-under=N tests/`. The `--single*` modes run pytest only, and must **not** apply `--cov-fail-under` (a one-test run would always fail the gate).
- `docker run --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1` and cache dirs under `/tmp` (`-p cache_dir`, `--cache-dir`, `MYPY_CACHE_DIR`, `COVERAGE_FILE`), otherwise root-owned `.pytest_cache`, `.mypy_cache`, `.coverage` and `__pycache__` appear in the host working tree.
- `--network none` instead of the template's `--network=host`: unit tests must never touch ClickUp or GitHub, and this enforces it. (A runner flag for network can come later if an integration mode is added.)
- Keep the template's contract: `set -euo pipefail`, `log()` helper, `.env` then `.env.example` fallback, `--single` builds `"$4/$2::$3"`, `--single-file` builds `"$3/$2"` [VERIFIED: read `~/Desktop/WORK/TURISANDA/turisanda-ai-travel-assistant-NEW/run-unit-tests.sh`, lines 8-83].
**Example:** see Code Examples.

### Pattern 2: Index artifact (schema, version, hash)
**What:** `index.db` with `PRAGMA user_version = <schema major>` (cheap pre-open guard) and `meta(schema_version, build_id, content_hash, guides_commit_sha, source_doc_id, pipeline_version, redaction_version, created_at_utc)`. Tables: `handbook_pages`, `guide_chunks` (+ external-content FTS5 table `guide_chunks_fts`), `video_map`, `meta`. Build into a temp file in the same directory, `journal_mode=DELETE`, `VACUUM`, close, then `os.replace` (atomic on the same filesystem, no `-wal`/`-shm` sidecar files — "single file" in D-08).
- `handbook_pages`: `page_id PK, parent_id, position, title, sub_title, url, date_edited_raw, date_edited_iso, content_md, content_hash`. **Do not store `date_updated`** (SYNC-02 says it must not influence anything; not storing it makes a regression impossible).
- `guide_chunks`: `id PK, file, h2, h3 NULL, heading, line_start, line_end, part_index, text`.
- `video_map`: `chunk_id, video_url, part, start_seconds NULL, source ('scene'|'readme_fallback')`. Resolved per chunk at sync time (rows only for chunks whose guide has a video).
- **Logical content hash** (D-09): sha256 over canonical JSON of `handbook_pages`, `guide_chunks`, `video_map` rows sorted by key, plus `schema_version`, `guides_commit_sha`, `source_doc_id`, `pipeline_version`. **Exclude `build_id`, `created_at`, and the file bytes** — SQLite file bytes are not a stable function of content, so hashing the file would make "unchanged content → same hash → no new artifact" fail.
- Reader API in `buddy_core`: `open_index(path)` (raises on `user_version`/major mismatch), `load_handbook()` (in-memory list), `search_guides(query, limit)` returning chunk + file + line range + video link.
- Optional but recommended: `index.manifest.json` beside `index.db` (build_id, schema_version, content_hash, size, sha256 of bytes) so a Phase 4 bucket reader can check freshness without opening the DB. It is for consumers, not incremental state (D-10 remains true).

### Pattern 3: Incremental handbook decision
**What:** Per page, compare against the previous `index.db` row: process when the page is new, or `date_edited` differs, or `content_hash` of the **raw upstream text** differs, or `meta.redaction_version`/`pipeline_version` differs. Otherwise copy the previous row. Pages absent upstream (or with `deleted`/`archived` true) are dropped. The run returns a `SyncReport(pages_seen, pages_processed, pages_unchanged, pages_removed, pages_denied, guides_rebuilt, artifact_written)`; success criterion 3 asserts `pages_processed == 0` on a re-run.
**Why a report object:** "processes 0 pages" must be observable in a test without scraping logs.

### Pattern 4: Redaction rule registry
**What:** `Rule(name, pattern, action)` table, applied in a fixed order; each hit returns `(masked_text, [RuleHit(rule_name, count)])`. Logging emits `page_id`, `rule_name`, `count` — never the match. Order: (1) strip attachment images but keep alt (`![alt](url)` → `alt`), (2) strip signed-URL query strings, (3) labelled secrets (`password|pwd|pass|pin|codice (di )?accesso|access code` + `:`/`=` + value), (4) token formats, (5) private personal data, (6) entropy rule last and **never inside URLs, UUIDs, or already-masked spans**. `[REDATTO]` is the fixed mask. Apply to `name`, `sub_title` and `content` of every page and to Guides text (D-18). A denylisted page id is dropped before fetch-processing and is never written, hashed or counted in the artifact.
**Tuning evidence (this session, corpus `docs/research/handbook-raw/`, values not reproduced):**
- The word "codice" alone appears in prose ("riceverai un codice via SMS", "CODICE FISCALE", "CODICE SDI") — a bare `codice` label rule would mask legitimate content and would violate D-16 (SDI is explicitly kept). Use only `codice (di )?accesso|codice sblocco`-style labels.
- Non-company email domains in the corpus include a calendar group address, a Factorial reply-to address and a third-party contact. D-15 as written masks all non-`@digitiamo.com` emails, which will blank legitimate non-personal addresses. Make the allowed-domain list configurable (`REDACT_EMAIL_ALLOW_DOMAINS`, default `digitiamo.com`) and decide in the plan whether `group.calendar.google.com` / `reply.factorial.co` are allowlisted.
- ClickUp attachment URLs (`*.p.clickup-attachments.com`) carry UUID path segments and, in one case, `?open=true`; they have no signature query. The entropy rule must skip URLs or it will mask them.
- No IBAN or mobile-number pattern matched in the raw snapshot; those rules are untested by the real corpus and need synthetic fixtures.

### Pattern 5: Fence-aware heading chunker (D-20 made precise)
**What:** Parse each file once with `MarkdownIt().parse(text)`. Take `heading_open` tokens with tag `h2`/`h3` and their `.map[0]`. Group the top-level (level 0) block tokens between headings into **atomic blocks** (paragraph, fence, table, list, blockquote). Chunk rules:
1. One chunk per `###` carrying its parent `##` title; `####` and deeper stay inside the chunk.
2. A `##` with no `###` is one chunk.
3. **A `##` that has prose before its first `###` gets an extra "preamble" chunk** (`h3 = NULL`). D-20 does not say this; without it 174 of the corpus's `##` sections lose their intro text [VERIFIED: computed over the 17 target files this session].
4. Text before the first `##` (title, TOC) is **not** indexed (TOC lines are link noise). State this in the plan.
5. Oversized chunks are split only at block boundaries (never inside a fence or table), up to `MAX_CHUNK_CHARS` (recommend 6000), keeping the same heading and giving `part_index`. A single block larger than the limit stays whole.
6. `line_start`/`line_end` are 1-based from `Token.map` (`map` is 0-based half-open).
**Corpus facts [VERIFIED: computed with markdown-it-py over the 17 files, this session]:** 17 files, 2600 chunks (by the D-20 rule without preamble chunks), median 666 chars, p90 1686, p99 4215, max 15402; 10 chunks exceed 6000 chars, 1 exceeds 12000.
**Scope facts:** `*_GUIDE.md` matches 16 files (including the four under `AI-Engineering/LangChain/`) plus `MULTI_AGENT_ARCHITECTURE_DESIGN.md` = 17 [VERIFIED: file loop this session]. Use `glob("**/*_GUIDE.md")` from the checkout root.

### Pattern 6: Video map resolution
**What:** Three inputs: README table (full-video URLs), `videos/<topic>/sections.yaml`, `videos/<topic>/durations.json`.
- **README parser:** rows look like `| [Name](Folder/X_GUIDE.md) | topic | [15:31](https://…/videos/rag-chatbot.mp4) |`; multi-part rows put several `[Part N · mm:ss](…_partN.mp4)` links separated by `<br>`; two guides have `—` (no video) [VERIFIED: read Guides README]. Key by the guide path in the first link. Parse with a regex over table rows; pin the format with a fixture copied in shape from the real README, and a drift test that fails loudly if a guide row yields zero parsed cells.
- **Offsets:** scene start = sum of durations of earlier scenes **in the same part**, in `durations.json` key order. Scene ids carry the part: `P2S03Counter` is part 2 for multi-part videos; single-part ids are `S01Title` [VERIFIED: key lists of `mcp-servers` and `multi-agent-design` `durations.json`]. Key order equals narration order because `common/tts.py` builds the dict by iterating scenes in order and `json.dumps(durations, indent=2)` does not sort keys [VERIFIED: read `videos/common/tts.py`].
- **Accuracy [VERIFIED: computed]:** `mcp-servers` scene durations sum to 883.2 s vs README 14:44 (884 s); `multi-agent-design` part sums 818.8 / 829.2 / 871.4 s vs README 13:39 / 13:49 / 14:32. Per-scene error is therefore well under a second.
- **`sections.yaml` schema (recommended, Claude's discretion):**
```yaml
schema: 1
guide: AI-Engineering/MCP_SERVERS_GUIDE.md   # path relative to the Guides repo root
video: mcp-servers                            # slug = folder name under videos/
sections:
  - scene: S05Layers                          # key that exists in durations.json
    h2: "3. The Core Model"                   # exact ## title text
    h3: null                                  # optional exact ### title; omit = whole ## section
```
  Most specific wins (`h3` entry beats `h2` entry); if several scenes map the same section, the first listed wins. A loader error (unknown scene id, heading not found in the guide, file outside the checkout) must **fail the sync** — silent drift is the failure mode D-02 exists to prevent.
- **Fallback (D-06):** guide has a video but no matching entry → `video_map` row with `source='readme_fallback'`, part 1 (or the only part), `start_seconds NULL`. Guide with no video → no row.

### Pattern 7: Guides acquisition and `GUIDES_INDEX.md`
**What:** `GuidesSource` Protocol with a git implementation (`clone --depth 1 --branch <branch>` first time, `fetch` + `reset --hard origin/<branch>` after). Record `git rev-parse HEAD` in `meta`. Authenticate with a per-command header, not a URL with an embedded token (see Pitfall 9). The Guides repo is private [VERIFIED: unauthenticated `api.github.com/repos/joshuadigitiamo/Guides` returned 404; CONTEXT/PLAN D15 also state it], so a read-only token is mandatory for the real run; dev can point `GUIDES_REPO_URL` at a local path.
**`GUIDES_INDEX.md` (recommended resolution of the discretion item):** put the generator in `jobs/sync` (it reuses the chunker, so there is exactly one heading parser) and expose it as `buddy-sync guides-index` which writes `GUIDES_INDEX.md` into the Guides checkout for a human to commit. At sync time the **chunker output is authoritative**; sync parses `GUIDES_INDEX.md` (D-23 says sync reads it), compares to the fresh headings, and on disagreement **warns and uses the fresh headings**; `--strict` turns the warning into a non-zero exit. The drift test builds a fixture repo, edits a heading, and asserts the disagreement is detected and reported. Honest note: because the generated file is derived from the same markdown, it is redundant with the chunker; D-23 is locked, so implement it as a derived artifact and do not let it become an input that can contradict the line numbers actually indexed.

### Anti-Patterns to Avoid
- **Hashing `index.db` bytes** for D-09: not stable; hash canonical logical rows.
- **Regex heading detection with a naive fence toggle**: 548 in-fence heading-like lines exist.
- **Chunking `##` as-is without a preamble chunk**: drops prose under 174 sections.
- **Putting the token in the clone URL** (`https://TOKEN@github.com/...`): persists in `.git/config` and leaks into process listings and error output.
- **Running pytest as root over the bind mount**: leaves root-owned caches on the host.
- **Using `date_updated` anywhere** (including as fallback): SYNC-02 forbids it.
- **Raw user text in `MATCH`**: FTS5 syntax errors (verified below).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown heading/fence/table detection and line numbers | Regex scanner with state machine | `markdown-it-py` `parse()` + `Token.map` | Handles `~~~`, indented code, nested structures; map gives exact lines |
| Full-text search ranking | Custom TF-IDF | SQLite FTS5 `bm25()` with column weights | Locked by D-08; built in |
| Env config + secret masking | `os.environ` plumbing with manual masking | `pydantic-settings` + `SecretStr` | Token cannot print in `repr`/logs by accident |
| External JSON validation | `dict.get` chains | `pydantic` models with `extra="ignore"` | API adds fields; only needed ones validated |
| Safe YAML | `yaml.load` | `yaml.safe_load` | Arbitrary-object construction otherwise |
| Atomic file publish | write-in-place | temp file + `os.replace` | Readers never see a half-written DB |
| HTTP mocking | monkeypatching `requests` | `httpx.MockTransport` (built in) | No extra dependency; exercises real request building |
| Shannon entropy / token regex catalogue | a giant home-grown ruleset | A short curated rule table (≈10 well-known prefixes + one entropy function) and a corpus test | The rules are small; the risk is false positives, which only a corpus test reveals |

**Key insight:** the deceptive complexity here is not any single library gap; it is that three "obvious" operations are wrong in subtle ways: change detection (which date, which hash, hashing what), heading detection (code fences), and "unchanged artifact" detection (file bytes vs logical content).

## Runtime State Inventory

Not a rename/refactor/migration phase. Omitted.

## Common Pitfalls

### Pitfall 1: Headings inside code fences
**What goes wrong:** Chunks start at `# comment` lines in code blocks; line refs point into code.
**Why:** 548 heading-like lines sit inside fences across the Guides (e.g. `# ─── OFFLINE: build the index` inside a Python block in RAG_CHATBOT_GUIDE) [VERIFIED: counted this session].
**How to avoid:** `markdown-it-py` tokens only. **Warning signs:** chunk headings that look like shell comments; a test fixture with a fenced `## fake` that must not create a chunk.

### Pitfall 2: Orphaned `##` preamble
**What goes wrong:** Intro prose between a `##` and its first `###` is in no chunk.
**Why:** D-20 wording covers `###` chunks and `##`-without-`###` only. 174 sections are in the gap [VERIFIED: computed].
**How to avoid:** Pattern 5 rule 3. **Warning signs:** a keyword known to appear in a section intro returns nothing.

### Pitfall 3: `date_edited` unit and nullability
**What goes wrong:** Comparing or rendering a timestamp in the wrong unit; a never-edited page has no `date_edited`.
**Why:** The official schema types `date_edited`, `date_updated`, `date_created` as plain `number` with no unit and no `required` list [VERIFIED: ClickUp OpenAPI `PublicDocsGetDocPagesPublic200Response` this session]. Millisecond epoch is likely (`[ASSUMED]`), not documented.
**How to avoid:** Store the raw number verbatim; derive ISO with a helper that treats values ≥ 1e12 as ms and smaller as s; compare raw numbers for equality only. If `date_edited` is null, rely on the content hash for change detection and show `date_created` as the revision date flagged as such (decide in the plan). Confirm the unit with one live call (Open Question 1).

### Pitfall 4: Over-fetching and "processed" semantics
**What goes wrong:** The plan counts HTTP fetches as "processed pages".
**Why:** `/pages` returns all content and dates in one call; `page_listing` has no dates [VERIFIED: OpenAPI]. Skipping fetches per page is impossible with the listing alone.
**How to avoid:** "Processed" means redact+store; unchanged pages are copied from the previous artifact. One `/pages` call per run.

### Pitfall 5: Redaction rule changes never propagating
**What goes wrong:** A page unchanged upstream keeps its old (possibly under-redacted) text after the rules improve.
**Why:** Change detection keys on upstream date/hash only.
**How to avoid:** Store `redaction_version` and `pipeline_version` in `meta`; a difference forces reprocessing of everything (handbook) and a Guides rebuild even when the Guides SHA is unchanged (this refines D-24, which keys only on the SHA).

### Pitfall 6: Redaction false positives on real content
**What goes wrong:** Masking company data the user wants kept (SDI, P.IVA, work contacts, non-personal addresses) or masking URLs.
**Why:** Bare `codice`, all-non-company-email, and entropy-on-URL rules (see Pattern 4 evidence).
**How to avoid:** Tight label patterns; configurable email allow-list; entropy rule skips URLs/UUIDs; add a **local-only corpus test** (skipped when `docs/research/handbook-raw/` is absent; the directory is gitignored so CI skips it) that runs the redactor over the 22 non-Wi-Fi snapshot pages and asserts SDI, P.IVA, `@digitiamo.com` addresses and office numbers survive, and that every masked span is reported by rule name. Corpus values must never be copied into committed fixtures.

### Pitfall 7: The Wi-Fi page id differs in the test doc
**What goes wrong:** `REDACT_PAGE_IDS` is set to the raw snapshot's Wi-Fi page id but the test doc [ClickUp doc ID removed] has different page ids (it is a copy).
**How to avoid:** A one-off human step after the token exists: list the test doc's pages (page_listing) and put the Wi-Fi page id in `.env`. A defence in depth is cheap: a unit test asserting the pipeline refuses to write an artifact when `REDACT_PAGE_IDS` is empty **and** `--allow-empty-denylist` is not passed. Never put real ids or values in committed files; `.env` is gitignored, `.env.example` holds placeholders.

### Pitfall 8: `#t=` on a GitHub release download URL
**What goes wrong:** The consumer shows a link whose timestamp is ignored.
**Why:** README links are `…/releases/download/videos/<x>.mp4` ("the links in the tables below download them", private repo) [VERIFIED: README text]. A media-fragment `#t=` only helps when the browser plays the file inline; a forced download ignores it (`[ASSUMED]` for browser/GitHub behaviour).
**How to avoid:** Store `video_url` (base) and `start_seconds` separately in `video_map`; expose a `video_link()` helper in `buddy_core` that composes `#t=<seconds>`. Then ROLL-02 (Drive) changes only the base URL map, and Phase 3 can choose the right syntax. This keeps D-01 satisfied and the deferred "per-scene clips" idea cheap.

### Pitfall 9: Token leakage through git
**What goes wrong:** The Guides token ends up in `.git/config`, logs or `ps`.
**How to avoid:** `git -c http.extraHeader="Authorization: Basic <base64(x-access-token:TOKEN)>" clone …` passes it per process without persisting it in config (pattern used by GitHub's checkout action; `[ASSUMED]`, verify against git docs in the plan). Wrap subprocess errors so stderr is scrubbed of the token; add a unit test that runs the git wrapper against a local fixture and asserts the token string is absent from `.git/config`, the logged argv and raised exception text. Also pass `-c safe.directory='*'` for local-path sources to avoid "dubious ownership" when the Guides checkout is bind-mounted from another uid.

### Pitfall 10: Committing durations and the gitignore
**What goes wrong:** `durations.json` can't be committed in the Guides repo.
**Why:** Guides `.gitignore` contains `videos/**/out/` [VERIFIED: read]; a file inside an ignored **directory** cannot be re-included.
**How to avoid:** In the Guides repo change the rule to `videos/**/out/*` plus `!videos/**/out/durations.json` (keeps D-04's location), or have `build.sh` copy it to `videos/<topic>/durations.json`. Recommend the negation. This is a **change in a different repository**; per the user's rule no commit happens without an explicit ask, so the plan should produce the edit and flag the commit as a human action.

### Pitfall 11: `rag-chatbot` has no durations
**What goes wrong:** D-07's example video cannot be mapped.
**Why:** `videos/rag-chatbot/` contains only `diagrams`, `narration.py`, `scenes.py`; no `out/` [VERIFIED: `ls`]. `mcp-servers` (27 scenes, single part) and `multi-agent-design` (62 scenes, 3 parts) have `durations.json`.
**How to avoid:** Map `mcp-servers` (single part) and `multi-agent-design` (exercises D-05 multi-part) in Phase 1; treat `rag-chatbot` as optional until its TTS step is run (`build.sh` TTS writes `durations.json`; the full render is not needed for durations but the script does both, so confirm before promising it).

### Pitfall 12: FTS5 query syntax errors and tokenisation
**What goes wrong:** A user query like `what: is-this?` raises `no such column: what` [VERIFIED: reproduced this session on SQLite 3.46.1].
**How to avoid:** `search_guides` quotes every whitespace-separated token as an FTS5 phrase (double any embedded `"`), joins with `OR`, ranks with `bm25(guide_chunks_fts, <h2 weight>, <heading weight>, 1.0)`; query empty-after-sanitising returns an empty result, never an exception. Identifiers like `create_agent` are quoted as a phrase and matched via the same tokenizer (verified: `"create_agent" OR "chunk"` matched a row containing `create_agent` and `Chunking`). Test queries containing `"`, `:`, `-`, `*`, unbalanced quotes and non-ASCII.

### Pitfall 13: Test environment parity
**What goes wrong:** Tests pass only with a real `.env`.
**How to avoid:** The runner passes `.env` or `.env.example` as `--env-file`; unit tests must construct `Settings` explicitly and pass with placeholder values. `docker --env-file` keeps quote characters literally, so `.env.example` values must be unquoted. Fixture git repos in tests need `GIT_AUTHOR_NAME/EMAIL` and `GIT_COMMITTER_*` env (container uid may have no passwd entry) and `HOME=/tmp`.

## Code Examples

### Dockerfile (test stage)
```dockerfile
# Source: pattern from ~/Desktop/WORK/TURISANDA/.../run-unit-tests.sh (code is mounted, not baked)
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./

FROM base AS test
RUN pip install -r requirements-dev.txt
```

### Runner script (delta against the template)
```bash
# Source: template lines 28-47 adapted. Key deltas: --user, cache dirs, --network none, all-mode gate.
run_in_container() {
  docker run --rm \
    --network none \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp -e MYPY_CACHE_DIR=/tmp/.mypy_cache -e COVERAGE_FILE=/tmp/.coverage \
    --env-file "${env_file}" \
    -v "${SCRIPT_DIR}:/app" -w /app \
    "${IMAGE_NAME}" "$@"
}
case "$1" in
  --all)
    build_image
    run_in_container ruff check .
    run_in_container ruff format --check .
    run_in_container mypy
    run_in_container python -m pytest tests/ -v --tb=short -p cache_dir=/tmp/.pytest_cache \
      --cov=buddy_core --cov=buddy_sync --cov-report=term-missing --cov-fail-under=80 ;;
  --single)       # pytest only, no coverage gate
    build_image
    run_in_container python -m pytest "$4/$2::$3" -v --tb=short ;;
esac
```
(The `--cov-fail-under` figure is a planning choice, not a researched value; set it once the first tests exist.)

### pyproject configuration skeleton
```toml
# Source: ruff/mypy/pytest standard config; values are recommendations, not verified defaults
[project]
name = "ai-buddy"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["packages/buddy_core", "jobs/sync"]
testpaths = ["tests"]
addopts = "-ra"

[tool.mypy]
strict = true
mypy_path = ["packages/buddy_core", "jobs/sync"]
explicit_package_bases = true
packages = ["buddy_core", "buddy_sync"]

[tool.ruff]
target-version = "py312"
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

### ClickUp client (official shape)
```python
# Source: ClickUp Public API v3 OpenAPI, https://developer.clickup.com/openapi/ClickUp_PUBLIC_API_V3.yaml
#   GET /api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages
#   query: max_page_depth (number, default -1), content_format ("text/md" | "text/plain", default "text/md")
#   auth: header "Authorization" (apiKey); personal tokens are sent without "Bearer" (docs: Authentication page)
def fetch_pages(client: httpx.Client, workspace_id: int, doc_id: str) -> list[ClickUpPage]:
    r = client.get(
        f"/api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages",
        params={"max_page_depth": -1, "content_format": "text/md"},
    )
    r.raise_for_status()
    return [ClickUpPage.model_validate(p) for p in r.json()]   # response is a JSON array, nested via "pages"
# client = httpx.Client(base_url="https://api.clickup.com", headers={"Authorization": token.get_secret_value()})
# tests:  httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.clickup.com")
```

### Fence-aware chunk boundaries
```python
# Source: markdown-it-py Token API (map = [start, end) 0-based line range); verified behaviour this session
from markdown_it import MarkdownIt

def heading_positions(text: str) -> list[tuple[int, int, str]]:
    tokens = MarkdownIt().parse(text)
    out = []
    for i, t in enumerate(tokens):
        if t.type == "heading_open" and t.tag in ("h2", "h3") and t.map:
            out.append((t.map[0], int(t.tag[1]), tokens[i + 1].content))  # inline token carries the title
    return out
```

### FTS5 table and query sanitiser
```python
# Source: SQLite FTS5 behaviour reproduced in python:3.12-slim (sqlite 3.46.1) this session
SCHEMA_FTS = """
CREATE VIRTUAL TABLE guide_chunks_fts USING fts5(
  h2, heading, text,
  content='guide_chunks', content_rowid='id',
  tokenize='porter unicode61 remove_diacritics 2');
"""  # after bulk insert: INSERT INTO guide_chunks_fts(guide_chunks_fts) VALUES('rebuild');

def to_match(query: str) -> str | None:
    toks = [t.replace('"', '""') for t in query.split() if t.strip('"')]
    return " OR ".join(f'"{t}"' for t in toks) or None   # None -> return no results, never raise
# SELECT c.*, bm25(guide_chunks_fts, 4.0, 6.0, 1.0) AS score
# FROM guide_chunks_fts JOIN guide_chunks c ON c.id = guide_chunks_fts.rowid
# WHERE guide_chunks_fts MATCH ? ORDER BY score LIMIT ?
```

### Scene offset from durations
```python
# Source: durations.json key order = narration order (videos/common/tts.py); sums match README lengths (verified)
def scene_offsets(durations: dict[str, float]) -> dict[str, tuple[int, float]]:
    """scene id -> (part number, start seconds within that part)."""
    out: dict[str, tuple[int, float]] = {}
    clock: dict[int, float] = {}
    for sid, dur in durations.items():                    # insertion order
        part = int(sid[1]) if sid.startswith("P") and sid[1].isdigit() else 1
        out[sid] = (part, clock.get(part, 0.0))
        clock[part] = clock.get(part, 0.0) + dur
    return out
```

### Incremental decision (core predicate)
```python
def needs_processing(prev: PageRow | None, cur: ClickUpPage, raw_hash: str, versions_match: bool) -> bool:
    if prev is None or not versions_match:
        return True
    # date_updated is deliberately never read here (SYNC-02)
    return prev.date_edited_raw != cur.date_edited or prev.content_hash != raw_hash
```

## Guides Applied (D16) and exceptions

Section numbers below were checked against the Guides files this session (headings read); the plan should still cite them verbatim.

| Guide | Section (verified) | Applied how |
|-------|--------------------|-------------|
| RAG_CHATBOT_GUIDE.md | §6 "Document Loading & Parsing", incl. "Capture metadata at load time" (≈lines 319-336) and "Clean before you chunk" (≈338-342) | Every chunk/page carries `document_id`-style lineage (file, heading, lines, commit SHA; page id, URL); redaction runs before chunking |
| RAG_CHATBOT_GUIDE.md | §7 "Chunking Deep-Dive" (line 344), "Chunking gotchas" (line 431): tables/code atomic, lineage tracking | Block-atomic splitting; lineage columns |
| RAG_CHATBOT_GUIDE.md | §10 "Basic Retrieval & Prompt Assembly" (line 550) | `search_guides` top-k with source-carrying rows |
| RAG_CHATBOT_GUIDE.md | §5 "The Golden Rule — Retrieval Quality Gates Everything" (line 256) | Justifies spending the phase on clean, line-referenced chunks |
| RAG_CHATBOT_GUIDE.md | §27 "EU GDPR & The Right to Erasure" (line 1348) | Chunk → document lineage so a source can be deleted; denylist drops pages before storage |
| DESIGN_PATTERNS_GUIDE.md | §4 "Structural Patterns", subsections "Adapter" (line 219) and "Repository" (line 309) | `HandbookSource`/`GuidesSource` Protocols with ClickUp/git adapters; `ArtifactStore` Protocol |
| DESIGN_PATTERNS_GUIDE.md | §9 "Hexagonal / Clean Architecture (Ports & Adapters)" (line 733) | `buddy_core` holds the port definitions; adapters live in `jobs/sync` |

**Exceptions to justify in the plan:** (a) RAG §7 "Overlap is not optional": chunks are heading-bounded (semantic boundaries), overlap is intended for fixed-size splitting; paragraph-split oversized chunks (≈10 of 2600) get no overlap in Milestone 1. (b) RAG §7 parent-child chunking and §11 hybrid/dense retrieval: out of scope by D5/D21; revisit if Phase 5 Recall@5 < 0.8. (c) RAG §6 per-chunk `acl`/`tenant_id` metadata: out of scope ("Per-section ACL" is Out of Scope in REQUIREMENTS.md). GUIDE-01's own deliverable is this table pattern plus a "Guides applied" line in every later plan; no code.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ClickUp v2 has no Docs read API | v3 Docs endpoints (`/api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages`, `page_listing`, `pages/{page_id}`) | v3 public API [CITED: developer.clickup.com OpenAPI] | Official REST path replaces the MCP tools named in SYNC-01 |
| Personal tokens in query string / OAuth only | Personal token in the `Authorization` header without `Bearer`; OAuth uses `Bearer` | [CITED: developer.clickup.com/docs/authentication] | Client sets the header from `SecretStr` |

**Rate limits:** per token, 100 requests/min on Free/Unlimited/Business, 1,000 on Business Plus, 10,000 Enterprise; HTTP 429 with `X-RateLimit-Limit/Remaining/Reset` (Reset is a Unix timestamp) [CITED: developer.clickup.com/docs/rate-limits via search summary]. One `/pages` call per run is far below this; still implement a bounded retry on 429/5xx with an injectable sleep so it is unit-testable.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `date_edited`/`date_updated` are epoch milliseconds | Pitfall 3 | Wrong ISO rendering; equality comparison unaffected. Confirm with one live call |
| A2 | Live `/pages` response matches the OpenAPI schema (top-level JSON array, nested `pages`, `id` like [ClickUp doc ID removed], `name`, `content`) | ClickUp client | Parse failure on first live run. Fixtures are synthetic and schema-derived, not recorded from the real API |
| A3 | `git -c http.extraHeader=...` avoids persisting the token and works for GitHub HTTPS with a fine-grained PAT | Pitfall 9 | Clone fails or token persists; verify against git/GitHub docs in the plan, and test it |
| A4 | A `#t=` fragment is ignored on a GitHub release-asset download URL | Pitfall 8 | Low; design (separate offset column) is correct either way |
| A5 | Page deep-link format `https://app.clickup.com/<workspace_id>/v/dc/<doc_id>/<page_id>` | Pattern 2 / SYNC-05 | Wrong links. Observed in the raw snapshot's `source:` front-matter field (which was produced by an earlier fetch of the real doc); confirm on the test doc |
| A6 | Skipping `deleted`/`archived` pages is desired | Pattern 3 | Archived content wrongly indexed or dropped |
| A7 | Missing `date_edited` falls back to `date_created` for display only | Pitfall 3 | Misleading revision date; decide in plan |
| A8 | `MAX_CHUNK_CHARS=6000`, cov fail-under 80, ruff rule set, entropy threshold ~4.0 bits/char on tokens ≥ 20 chars | Patterns 4, 5, Code Examples | Tuning only; D-15 lists the threshold as Claude's discretion |
| A9 | Well-known token prefixes (`pk_`, `sk-`, `ghp_`, `github_pat_`, `AKIA`, `xox[bp]-`, `AIza`, JWT `eyJ`, `-----BEGIN … PRIVATE KEY-----`) are sufficient for the D-15 "token/key formats" rule | Pattern 4 | A secret format slips through; mitigated by the entropy rule and the label rule |
| A10 | Dropping *all* `*.clickup-attachments.com` link targets (not just images) is consistent with D-17 | Pattern 4 | D-17 mentions image links only; non-image attachment links would otherwise survive. Confirm with the user |
| A11 | Package names/versions in the Standard Stack are legitimate | Package Legitimacy Audit | Seam says SUS for every package (blind to downloads); batch human check |

## Open Questions

1. **First live call (needs the ClickUp token)**
   - Known: official schema; the token and the workspace id are not yet available (STATE.md blocker: needs Admin ClickUp). The workspace id is a required path parameter (`workspace_id`, type number), so `CLICKUP_WORKSPACE_ID` is a new env var the requirements did not mention.
   - Unclear: `date_edited` unit/nullability, real `id` format, whether content contains attachment links as seen in the raw snapshot, and the test doc's page ids (for `REDACT_PAGE_IDS`).
   - Recommendation: schedule one human-run `buddy-sync` smoke step against [ClickUp doc ID removed] at the end of the phase, outside the unit suite; until then everything is built against schema-derived synthetic fixtures. Keep a throwaway local-only helper that feeds the gitignored raw snapshot through the pipeline (maps its `last_updated` to `date_edited`) so redaction can be tuned before the token exists.
2. **Which two videos get real maps?** `rag-chatbot` has no `durations.json`. Recommend `mcp-servers` + `multi-agent-design`, with `rag-chatbot` only if the user runs its TTS first. Needs a user call.
3. **Non-company email policy** (calendar group, Factorial reply-to, third-party contact): allow-list or mask? D-15/D-16 are silent on non-personal non-company addresses.
4. **Cross-repo edits** (Guides repo: `sections.yaml` x2, committed `durations.json` x2 plus gitignore negation, generated `GUIDES_INDEX.md`): who commits and where does the work happen? The user's rule forbids commits without an explicit ask, so these are human-action checkpoints.
5. **Text above the first `##` is not indexed**; confirm that is acceptable (it is TOC/title only).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | FND-02, all tests | ✓ | 29.9.1 | — |
| `python:3.12-slim` image | test stage | ✓ (pulled this session) | 3.12 / SQLite 3.46.1 with FTS5 | — |
| git on host | fixture-independent; not required | ✓ | 2.53.0 | git is installed inside the image |
| git inside `python:3.12-slim` | SYNC-04, tests | ✗ | — | `apt-get install git` in Dockerfile (planned) |
| Guides repo checkout | local dev source | ✓ `~/Desktop/WORK/Guides`, branch `master` | HEAD `a60b4cb` | clone URL needs a token (private repo) |
| ClickUp token + workspace id | SYNC-01 live run | ✗ (not in agent environment) | — | Synthetic fixtures for unit tests; live smoke is a human step |
| Guides read-only token | D-22 live clone | ✗ | — | Point `GUIDES_REPO_URL` at the local path in dev |
| Host Python | — | present (3.14.4) but irrelevant | — | Project rule: never used |

**Missing with no fallback:** none for the unit suite. **Missing with fallback:** ClickUp and Guides tokens (live runs only).

## Validation Architecture

(`workflow.nyquist_validation` is not set; `.planning/config.json` does not exist, so the section is enabled.)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 + pytest-cov 7.1.0; ruff 0.17.3; mypy 2.4.1 (strict) |
| Config file | `pyproject.toml` (none exists yet; Wave 0) |
| Quick run command | `./run-unit-tests.sh --single-file <test_file> <test_directory>` |
| Full suite command | `./run-unit-tests.sh --all` (ruff check, ruff format --check, mypy, pytest --cov) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-01 | pyproject/requirements/tooling load; `ruff`, `mypy --strict` pass on the skeleton; layout dirs exist | smoke | `./run-unit-tests.sh --all` | ❌ Wave 0 |
| FND-01 | Layout and `requires-python >=3.12` asserted | unit | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit` | ❌ Wave 0 |
| FND-02 | Runner modes: `--all`, `--single`, `--single-file`, bad args → usage exit 1, no host Python | manual-only (host shell; needs the Docker daemon, so it cannot run inside the test container) | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit`; `./run-unit-tests.sh --single test_repo_layout.py test_layout tests/unit`; `./run-unit-tests.sh --bogus; echo $?` | ❌ Wave 0 |
| FND-02 | No root-owned files after a run | manual | `find . -user root -not -path './.git/*' \| head` (expect empty) | — |
| GUIDE-01 | Plan lists verified Guides sections + exceptions | manual (plan-check) | plan checker reads the "Guides applied" block | — |
| SYNC-01 | Client calls `/pages` with `max_page_depth=-1`, `content_format=text/md`, `Authorization` header from secret; flattens nested tree; maps 429/5xx to bounded retry | unit (`httpx.MockTransport`) | `./run-unit-tests.sh --single-file test_clickup_client.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-01 | Doc id, workspace id, token come from env (`Settings`); token never in `repr`/log | unit | `... --single-file test_config.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-02 | Re-run with identical input → `pages_processed == 0`, `artifact_written == False` | unit | `... --single test_handbook_sync.py test_rerun_processes_zero tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-02 | One page's `date_edited` changed → only that page processed | unit | `... --single test_handbook_sync.py test_single_edit_reprocesses_one tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-02 | `date_updated`-only change → 0 processed, no new artifact | unit | `... --single test_handbook_sync.py test_date_updated_only_ignored tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-02 | Content-hash-only change (same `date_edited`) → processed; removed upstream page dropped; `redaction_version` bump → all processed | unit | `... --single-file test_handbook_sync.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-03 | Denylisted page id never appears in `index.db` (rows, FTS, meta, hashes) nor in any artifact file | unit (fixture with synthetic secrets) | `... --single test_redaction_pipeline.py test_denylisted_page_absent tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-03 | Each D-15 rule masks its synthetic positive with `[REDATTO]` and logs page id + rule name but never the value (caplog) | unit | `... --single-file test_redaction.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-03 | D-16 negatives survive (work contact, `@digitiamo.com`, SDI-like, P.IVA-like, URL with UUID, bare word "codice") | unit | `... --single test_redaction.py test_work_data_kept tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-03 | Image link dropped, alt kept (D-17); same filter applied to Guides text (D-18) | unit | `... --single-file test_redaction.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-03 | Corpus smoke over local gitignored raw snapshot: Wi-Fi page content absent from the produced DB; work data survives | local-only (skipped if corpus absent) | `... --single-file test_corpus_local.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-04 | Chunker: one chunk per `###` with parent `##`, `##`-without-`###` single chunk, preamble chunk, fenced `## fake` ignored, oversize split at block boundary keeps heading, line ranges correct | unit | `... --single-file test_chunker.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-04 | Include/exclude globs (`*_GUIDE.md` + MULTI_AGENT…; README, CLAUDE.md, `videos/` excluded) | unit | `... --single test_guides_scope.py test_globs tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-04 | Git adapter against a local fixture repo: clone, pull, SHA recorded, unchanged SHA → Guides rebuild skipped, `pipeline_version` change → rebuilt; token absent from `.git/config`/argv/errors | unit | `... --single-file test_guides_git.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-04 | `GUIDES_INDEX.md` drift: edited heading is detected and reported; `--strict` exits non-zero | unit | `... --single-file test_guides_index.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-04 | Keyword query returns heading chunk with file + line range; hostile queries (`"`, `:`, `-`, empty) never raise | unit | `... --single-file test_search_guides.py tests/unit/buddy_core` | ❌ Wave 0 |
| SYNC-05 | Every handbook row has deep-link URL, title, `date_edited`; `load_handbook()` returns full pages in tree order | unit | `... --single-file test_index_handbook.py tests/unit/buddy_core` | ❌ Wave 0 |
| SYNC-06 | Scene → part + offset (single and multi-part), unknown scene id / missing heading / path escape fails the load | unit | `... --single-file test_video_map.py tests/unit/buddy_sync` | ❌ Wave 0 |
| SYNC-06 | README parser (single, multi-part, `—`), fallback to README URL with `start_seconds NULL`, no-video guide → no row; search result carries `video_url` only when mapped | unit | `... --single-file test_readme_videos.py tests/unit/buddy_sync` and `test_search_guides.py` | ❌ Wave 0 |
| SYNC-07 | Schema/`user_version`/`meta` present; consumer refuses a mismatched major; identical logical content → identical `content_hash` across two builds at different times; atomic publish leaves one file | unit | `... --single-file test_index_format.py tests/unit/buddy_core` and `test_artifact_store.py` | ❌ Wave 0 |
| SYNC-07 | `docs/index-format.md` and `docs/adr/0001-index-handoff.md` exist; REQUIREMENTS.md SYNC-07/INFRA-04 reworded | manual (doc review) | plan-check | ❌ Wave 0 |
| (phase) | End to end on fixtures: sync → artifact → `search_guides` hit with video link → second run writes nothing | unit/integration (in-process) | `... --single test_sync_e2e.py test_end_to_end tests/unit/buddy_sync` | ❌ Wave 0 |
| (phase) | Live smoke against [ClickUp doc ID removed] with real token, Wi-Fi id in `REDACT_PAGE_IDS` | manual-only (needs credentials and network; unit suite runs with `--network none`) | `docker run … python -m buddy_sync` | — |

### Sampling Rate
- **Per task commit:** `./run-unit-tests.sh --single-file <file> <dir>` for the touched module
- **Per wave merge:** `./run-unit-tests.sh --all`
- **Phase gate:** `--all` green (ruff, mypy, pytest-cov) before `/gsd-verify-work`, plus the manual rows above

### Wave 0 Gaps
- [ ] `Dockerfile`, `run-unit-tests.sh`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` config, `.env.example`, `.gitignore` additions (`*.db`, `artifacts/`, caches, `.coverage`, Guides checkout dir) — nothing exists
- [ ] `tests/unit/buddy_core/`, `tests/unit/buddy_sync/`, `tests/fixtures/` (synthetic ClickUp JSON shaped from the OpenAPI schema; a tiny fixture Guides tree with a fenced fake heading, a preamble, an oversized section, a README table, a `sections.yaml`, a `durations.json`) and a shared `conftest.py` (fixture git repo builder with `GIT_*` env)
- [ ] Framework install is part of the Docker `test` stage (no host install)
- [ ] Delete `main.py` (gitignored PyCharm stub) and raise `requires-python` to `>=3.12` in `pyproject.toml`

## Security Domain

(`security_enforcement` is not set in config, so this section applies.)

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (client side only) | Tokens sent as headers, read from env |
| V3 Session Management | no | — |
| V4 Access Control | no | Read-only tokens; per-section ACL out of scope |
| V5 Input Validation | yes | `pydantic` on the ClickUp response; `yaml.safe_load`; FTS5 query quoting; parameterised SQL; resolved-path containment for `sections.yaml`/`GUIDES_INDEX.md` entries |
| V6 Cryptography | minimal | `hashlib.sha256` only; no custom crypto |
| V7 Logging | yes | Log page id + rule name only; never matched values or tokens |
| V8 Data Protection | yes | Redaction before indexing; denylist drops pages before storage; public-repo hygiene (artifacts, `.env`, handbook content never committed) |
| V14 Configuration / supply chain | yes | `SecretStr`; pinned `requirements*.txt`; token not in git config/URL |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential in handbook text reaches the index | Information disclosure | Denylist + rule-based masking + corpus test; rule/version bump forces reprocess |
| Token leaked via clone URL, argv, `.git/config`, exception text | Information disclosure | Per-command auth header; scrubbed errors; test asserting absence |
| Secret or handbook text committed to the public repo | Information disclosure | `.gitignore` for `.env`, `*.db`, `artifacts/`, `docs/research/handbook-raw/`; fixtures use obviously fake values on reserved/example domains |
| Path traversal via `sections.yaml` `guide:` or `GUIDES_INDEX.md` | Tampering | Resolve against the checkout root and reject anything outside |
| Unsafe YAML deserialisation | Elevation of privilege | `yaml.safe_load` only |
| FTS5 query injection / syntax errors | Tampering / DoS | Quote every token; parameter binding; empty result on empty query |
| Malformed/huge upstream response | DoS | Pydantic validation, request timeout, bounded retries |
| Prompt-injection text stored in handbook/Guides content | Tampering (downstream) | Not solvable in Phase 1; Phase 2/3 must treat index text as untrusted data |
| Partial/corrupt artifact read by consumer | Tampering | Temp file + `os.replace`; `user_version` and `meta.schema_version` checks on open |

## Suggested Plan Breakdown (for the planner)

1. **Foundation** (FND-01, FND-02, GUIDE-01 convention): layout dirs, pyproject, requirements, Dockerfile, runner, `.env.example`, `.gitignore`, test skeleton; one trivial green test through `--all`. Contains the single batched package-legitimacy checkpoint.
2. **Index format + `buddy_core`** (SYNC-05, SYNC-07): schema, models, builder, reader/search with sanitiser, `ArtifactStore` + local implementation, `docs/index-format.md`, ADR 0001, REQUIREMENTS.md wording update.
3. **Redaction** (SYNC-03): rule registry, denylist, logging discipline, fixtures, local corpus test. Parallel with 4 after 1.
4. **ClickUp source + incremental handbook sync** (SYNC-01, SYNC-02, SYNC-05): depends on 2 and 3.
5. **Guides source + chunker + `GUIDES_INDEX.md`** (SYNC-04): depends on 2 and 3.
6. **Video map** (SYNC-06): README parser, `sections.yaml` loader, durations offsets; Guides-repo contract edits and two real maps (human-commit checkpoint). Depends on 5.
7. **CLI + end-to-end** (success criteria 2-5): orchestration, `SyncReport`, e2e fixture test, manual live-smoke checkpoint (needs tokens, Wi-Fi page id).

## Sources

### Primary (HIGH confidence)
- ClickUp Public API v3 OpenAPI, `https://developer.clickup.com/openapi/ClickUp_PUBLIC_API_V3.yaml` (downloaded and parsed this session): paths `/api/v3/workspaces/{workspace_id}/docs/{doc_id}/page_listing`, `/pages`, `/pages/{page_id}`; parameters `max_page_depth`, `content_format`; response fields incl. `date_edited`, `date_updated`, `content`, nested `pages`; security scheme `authHeader` (header `Authorization`)
- Local files read this session: `01-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`, `ROADMAP.md` (Phase 1), `docs/PLAN.md` §2.1/§3, `pyproject.toml`, `.gitignore`, the TURISANDA `run-unit-tests.sh`, Guides `README.md`, `.gitignore`, `videos/common/tts.py`, `videos/*/out/durations.json`, RAG_CHATBOT_GUIDE and DESIGN_PATTERNS_GUIDE headings
- Executed this session: SQLite FTS5 + porter + external-content `rebuild` + bm25 in `python:3.12` and `python:3.12-slim`; `markdown-it-py` parse behaviour; pip installs and `pip list` for all pinned versions; chunk statistics over the 17 Guides files; durations vs README sums

### Secondary (MEDIUM confidence)
- ClickUp Authentication page (`https://developer.clickup.com/docs/authentication`): `Authorization: {personal_token}`, `pk_` prefix, no mention of read-only tokens
- ClickUp Rate Limits page (`https://developer.clickup.com/docs/rate-limits`) via search summary: per-plan limits, 429 headers

### Tertiary (LOW confidence)
- Third-party sources (clickup-cli source, MCP wrappers, windmill scripts) corroborating the `page_listing`/`pages` paths; superseded by the official OpenAPI
- Training knowledge: token prefix catalogue (A9), git `http.extraHeader` usage (A3), browser handling of `#t=` on downloads (A4)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version installed and imported this session; legitimacy seam is uninformative (SUS for all), hence one human checkpoint
- ClickUp API shape: MEDIUM-HIGH — official OpenAPI parsed; no live call, `date_edited` unit undocumented
- Architecture: MEDIUM-HIGH — follows locked decisions; refinements (preamble chunk, logical hash, version-aware skip) are justified by measured data
- Chunking/FTS5: HIGH — measured on the real Guides corpus and reproduced in the target image
- Video mapping: MEDIUM — durations arithmetic verified; download-URL/fragment behaviour and cross-repo workflow unverified
- Redaction: MEDIUM — rule design sound, real-corpus false-positive evidence gathered, IBAN/mobile rules untested on real data
- Pitfalls: HIGH for 1, 2, 5, 10, 11, 12; MEDIUM for 3, 8, 9

**Research date:** 2026-11-03
**Valid until:** 2026-12-03 for stack versions (pip pins move fast: pytest, ruff, mypy, pydantic released within the last week); ClickUp v3 surface re-check if the first live call disagrees with the schema.
