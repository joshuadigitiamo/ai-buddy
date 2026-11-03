---
phase: 01-content-sync
verified: 2026-11-03T21:20:00Z
status: passed
score: 8/8 must-haves verified
covered_files:
  - ".env.example"
  - ".gitignore"
  - ".planning/phases/01-content-sync/01-01-PLAN.md"
  - ".planning/phases/01-content-sync/01-01-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-02-PLAN.md"
  - ".planning/phases/01-content-sync/01-02-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-03-PLAN.md"
  - ".planning/phases/01-content-sync/01-03-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-04-PLAN.md"
  - ".planning/phases/01-content-sync/01-04-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-05-PLAN.md"
  - ".planning/phases/01-content-sync/01-05-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-06-PLAN.md"
  - ".planning/phases/01-content-sync/01-06-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-07-PLAN.md"
  - ".planning/phases/01-content-sync/01-07-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-08-PLAN.md"
  - ".planning/phases/01-content-sync/01-08-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-09-PLAN.md"
  - ".planning/phases/01-content-sync/01-09-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-10-PLAN.md"
  - ".planning/phases/01-content-sync/01-10-SUMMARY.md"
  - ".planning/phases/01-content-sync/01-11-PLAN.md"
  - ".planning/phases/01-content-sync/01-11-SUMMARY.md"
  - "Dockerfile"
  - "docs/adr/0001-index-handoff.md"
  - "docs/guides-contract.md"
  - "docs/index-format.md"
  - "jobs/sync/README.md"
  - "jobs/sync/buddy_sync/__init__.py"
  - "jobs/sync/buddy_sync/__main__.py"
  - "jobs/sync/buddy_sync/chunker.py"
  - "jobs/sync/buddy_sync/cli.py"
  - "jobs/sync/buddy_sync/config.py"
  - "jobs/sync/buddy_sync/guides.py"
  - "jobs/sync/buddy_sync/guides_git.py"
  - "jobs/sync/buddy_sync/guides_index.py"
  - "jobs/sync/buddy_sync/handbook.py"
  - "jobs/sync/buddy_sync/handbook_files.py"
  - "jobs/sync/buddy_sync/pipeline.py"
  - "jobs/sync/buddy_sync/redaction.py"
  - "jobs/sync/buddy_sync/video_map.py"
  - "packages/buddy_core/buddy_core/__init__.py"
  - "packages/buddy_core/buddy_core/index_reader.py"
  - "packages/buddy_core/buddy_core/index_writer.py"
  - "packages/buddy_core/buddy_core/models.py"
  - "packages/buddy_core/buddy_core/schema.py"
  - "packages/buddy_core/buddy_core/store.py"
  - "pyproject.toml"
  - "requirements-dev.txt"
  - "requirements.txt"
  - "run-unit-tests.sh"
  - "tests/conftest.py"
  - "tests/fixtures/guides_repo/AI-Engineering/DEMO_GUIDE.md"
  - "tests/fixtures/guides_videos/README.md"
  - "tests/fixtures/guides_videos/videos/demo/out/durations.json"
  - "tests/fixtures/guides_videos/videos/demo/sections.yaml"
  - "tests/fixtures/guides_videos/videos/multi/out/durations.json"
  - "tests/fixtures/guides_videos/videos/multi/sections.yaml"
  - "tests/fixtures/handbook/01-benvenuto.md"
  - "tests/fixtures/handbook/02-ferie.md"
  - "tests/fixtures/handbook/03-accesso-ufficio.md"
  - "tests/fixtures/handbook/04-rete-ospiti.md"
  - "tests/unit/buddy_core/conftest.py"
  - "tests/unit/buddy_core/test_artifact_store.py"
  - "tests/unit/buddy_core/test_index_format.py"
  - "tests/unit/buddy_core/test_index_roundtrip.py"
  - "tests/unit/buddy_core/test_search_guides.py"
  - "tests/unit/buddy_sync/test_chunker.py"
  - "tests/unit/buddy_sync/test_cli.py"
  - "tests/unit/buddy_sync/test_config.py"
  - "tests/unit/buddy_sync/test_corpus_local.py"
  - "tests/unit/buddy_sync/test_guides_git.py"
  - "tests/unit/buddy_sync/test_guides_index.py"
  - "tests/unit/buddy_sync/test_guides_local.py"
  - "tests/unit/buddy_sync/test_guides_scope.py"
  - "tests/unit/buddy_sync/test_guides_source.py"
  - "tests/unit/buddy_sync/test_handbook_files.py"
  - "tests/unit/buddy_sync/test_handbook_sync.py"
  - "tests/unit/buddy_sync/test_live_artifact.py"
  - "tests/unit/buddy_sync/test_readme_videos.py"
  - "tests/unit/buddy_sync/test_redaction.py"
  - "tests/unit/buddy_sync/test_redaction_pipeline.py"
  - "tests/unit/buddy_sync/test_sync_e2e.py"
  - "tests/unit/buddy_sync/test_video_map.py"
  - "tests/unit/test_repo_layout.py"
  - "tests/unit/test_toolchain.py"
covered_digest: "v4:sha256:5dffbdc0ab8ba464c03d2e4f13a1afc8bbd48738f51435861c98f0321363e07c"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 1: Content Sync Verification Report

**Phase Goal:** The developer can build a clean, citable knowledge index from the local handbook snapshot and the Guides repo, and run all tests in Docker from day one.
**Verified:** 2026-11-03T21:20:00Z
**Status:** passed
**Re-verification:** No, initial verification

Evidence was produced by this verifier in its own Docker runs (image `ai-buddy-test`, `--network none`), not copied from SUMMARY.md. Privacy rule applied: no handbook line, title, page id, Wi-Fi content or `.env` value was printed; live checks reported counts and booleans only.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ROADMAP SC1: `./run-unit-tests.sh --all` builds the test image and runs ruff, mypy and pytest+coverage in Docker; `--single` and `--single-file` run only the targeted tests; no host Python | VERIFIED | `--all` exit 0: ruff check "All checks passed", ruff format --check clean, `mypy` strict "no issues found in 44 source files", pytest 317 passed / 14 skipped, coverage 97.25% (gate 80). `--single test_toolchain.py test_runs_python_312 tests/unit` collected exactly 1 item. `--single-file test_repo_layout.py tests/unit` ran 6 tests. No args, `--bogus`, and `--single a b` each print usage and exit 1. Script uses `set -euo pipefail`, `log()`, `docker build --target test` then `docker run --rm --env-file --network none -v cwd`. |
| 2 | ROADMAP SC2: sync on the local handbook folder (env path, read-only mount, no token, no network) yields a snapshot with `handbook://` URI, title and revision date per page; Wi-Fi page and credential-like text absent from every artifact | VERIFIED | Live run, `--network none`, handbook mounted `:ro`, Guides `:ro`, `.env.example` only: exit 0, `pages_seen 23, pages_denied 1, pages_processed 22, guides_index_drift 0`. Own SQL check: 22 `handbook_pages` rows, 0 rows with url not `handbook://%`, empty title or empty `revision_date_iso`. Wi-Fi stem absent from `index.db` + `index.manifest.json` bytes; 10 of its page-specific body lines, 0 found in the artifact. `test_live_artifact.py`: 7 passed (stored pages = non-denied files; 0 residual labelled_secret / private_key_block / token_prefix / jwt / iban hits over every stored title, body and chunk). `handbook_files.read_handbook_dir` never opens a denylisted file and fails on an unknown denylist entry; `pipeline.run_sync` refuses an empty denylist without an explicit flag. |
| 3 | ROADMAP SC3: re-run with no edits processes 0 pages; editing one page re-processes only it; mtime-only change is not re-indexed | VERIFIED | Live second run: `pages_processed 0, pages_unchanged 22, guides_rebuilt false, artifact_written false`, same `content_hash` as the first run (deterministic across two independent builds, also equal to the executor's recorded hash). `test_sync_e2e.py::test_end_to_end` (passes in the full suite) exercises unchanged re-run (byte-identical index.db), `os.utime` mtime-only change (0 processed, no write), one appended page (exactly 1 processed), and a failed build leaving the previous artifact intact. `handbook.sync_handbook` keys on `date_edited` and the redacted-content hash only; no code path reads mtime. |
| 4 | ROADMAP SC4: keyword query on the Guides index returns the heading chunk with file and line reference plus scene-clip or README full-video URL, and nothing for sections without video | VERIFIED | Live `search "tool surface"` returned `AI-Engineering/MCP_SERVERS_GUIDE.md:351-363  4. Connecting to a Client > 4.3 ...` with a release-asset mp4 URL, and `MULTI_AGENT_ARCHITECTURE_DESIGN.md:327-329 ... #t=353`. Live artifact: 2795 chunks, 238 `scene` links, 2286 `readme_fallback` links. `test_guides_local.py` run with `GUIDES_LOCAL_DIR=/guides-src`: 7 passed, including "every video-guide chunk has a link and dash rows have none" and no GUIDES_INDEX drift. `test_video_map.py` covers scene offsets, part restart, README fallback, guide without video gets no entry. |
| 5 | ROADMAP SC5: index artifact has a documented, versioned format and a recorded decision on how it reaches the MCP container | VERIFIED | `docs/index-format.md` (schema 1.0.0, tables, versioning, manifest, changelog, live-verification section); live `index.db` has `user_version 1`, journal mode `delete`, no sidecars, meta keys incl. `schema_version`. `docs/adr/0001-index-handoff.md` Accepted: `ArtifactStore` interface + `LocalDirArtifactStore` now; bucket vs baked image chosen with the hosting platform in Phase 4 (D-12). This is the decision SYNC-07 as amended asks for. |
| 6 | FND-01: D11 layout, Python 3.12, pinned pip requirements, ruff/pytest/mypy strict configured | VERIFIED | `test_repo_layout.py` (6 tests) passes. Layout present (`packages/buddy_core`, `jobs/sync`, `services/{mcp_server,chat_bot}`, `deploy/{k8s,cloudrun}`, `.github/workflows`, `tests/`; empty dirs held by `.gitkeep`). `pyproject.toml`: `requires-python >=3.12`, `[tool.mypy] strict = true`, ruff, pytest, coverage. `requirements*.txt` all `==` pinned. Dockerfile `FROM python:3.12-slim`. |
| 7 | GUIDE-01: every phase plan cites Guides sections or justifies exceptions | VERIFIED | `grep -L '^## Guides applied' 01-*-PLAN.md` prints nothing: all 11 plans carry the block. |
| 8 | D-25..D-27: no ClickUp / network / token dependency remains in code, dependencies or env contract | VERIFIED | `grep -riE "clickup|httpx|CLICKUP_TOKEN|requests|socket"` over `jobs packages requirements*.txt Dockerfile .env.example` finds nothing (only `urllib.parse` in `guides_git.py`). `.env.example` has no token key (`test_env_example_has_no_token_variable`). `requirements.txt` holds only markdown-it-py, pydantic, pydantic-settings, PyYAML. Live run succeeded under `--network none`. |

**Score:** 8/8 truths verified (0 present, behavior-unverified)

### Accepted by the user (not a gap)

- `tests/unit/buddy_sync/test_live_artifact.py::test_denied_pages_absent_from_every_byte` checks only Wi-Fi body lines that no kept page also contains. One boilerplate line is shared by all 22 kept pages and therefore legitimately appears in the artifact. Independently confirmed: 12 substantial denied-page lines, 10 unique to it (0 leaked), 1 shared and present. The stem, the not-stored-as-page-id check and a non-vacuity guard remain. Decision recorded by the user.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `run-unit-tests.sh` | three modes, Docker only | VERIFIED | Exercised (see truth 1) |
| `Dockerfile` | python:3.12-slim, `test` stage with dev deps and git | VERIFIED | Built by `--all` |
| `packages/buddy_core/*` | schema, writer, reader/search, models, ArtifactStore | VERIFIED | 5 modules, 169+142+116+65+62 lines, round-trip, FTS5, format and store tests pass |
| `jobs/sync/buddy_sync/*` | config, redaction, handbook(+files), guides(+git, index), chunker, video_map, pipeline, cli | VERIFIED | 13 modules, all wired through `pipeline.run_sync` and `cli`; live run exercises every one |
| `docs/index-format.md`, `docs/adr/0001-index-handoff.md`, `docs/guides-contract.md`, `jobs/sync/README.md` | documented format, handoff decision, operator guide | VERIFIED | Present and consistent with code (SYNC-07) |
| Guides repo maps + `GUIDES_INDEX.md` (plan 01-08, commit 810efdd) | scene maps and index committed in Guides | VERIFIED | Guides HEAD `810efdd...`; live run `guides_index_drift 0`; `GUIDES_INDEX.md` and two `sections.yaml` tracked. Commit and push made by Claude on the user's explicit instruction (noted). Not modified by this verification. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli.run` | `pipeline.run_sync` | settings from env, GitGuidesSource, LocalDirArtifactStore, Redactor | WIRED | live run exit 0 |
| `pipeline` | `handbook_files.read_handbook_dir` -> `handbook.sync_handbook` -> `Redactor` | local folder -> redacted rows | WIRED | live counts above |
| `pipeline` | `guides.sync_guides` -> `video_map.resolve_video_links` -> `check_guides_index` | chunks, links, drift | WIRED | 2795 chunks, 2524 links, drift 0 |
| `pipeline` | `index_writer.build_index` -> `store.publish` | atomic publish, skip when hash unchanged | WIRED | second run wrote nothing |
| `cli.search` | `index_reader.search_guides` | FTS5 query -> chunk with file:line and VideoLink | WIRED | live search output |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `index.db` handbook_pages | 22 rows | `/handbook` snapshot (23 files minus 1 denied) | Yes | FLOWING |
| `index.db` guide_chunks / video_map | 2795 chunks, 2524 links | Guides checkout at `810efdd` + README + sections.yaml + durations.json | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full gate | `./run-unit-tests.sh --all` | exit 0, 317 passed, 14 skipped, 97.25% | PASS |
| Live sync, strict | `buddy_sync run --strict` (ro mounts, no network) | exit 0, artifact_written true | PASS |
| Live idempotence | same, second run | 0 processed, no write, identical hash | PASS |
| Live privacy/format checks | `test_live_artifact.py` with `LIVE_ARTIFACT_DIR` | 7 passed; `pages=22 denied=1 chunks=2795 scene_links=238 readme_fallback_links=2286` | PASS |
| Guides local checks | `test_guides_local.py` with `GUIDES_LOCAL_DIR` | 7 passed | PASS |
| Live search | `buddy_sync search "tool surface"` | file:line + heading + video URL | PASS |

The 14 skips in the plain `--all` run are the local-only live and Guides-checkout modules, which skip by design without their env vars (CI-safe); this verifier ran them live above.

### Probe Execution

Step 7c: SKIPPED. No `probe-*.sh` declared or present.

### Requirements Coverage

All ten IDs from the phase are accounted for in plan frontmatter and in REQUIREMENTS.md (all `[x]`, traceability "Complete"). No orphaned Phase 1 requirement in REQUIREMENTS.md.

| Requirement | Source Plans | Status | Evidence |
|-------------|-------------|--------|----------|
| FND-01 | 01-01 | SATISFIED | Truth 6 |
| FND-02 | 01-01 | SATISFIED | Truth 1 |
| GUIDE-01 | 01-01..01-11 | SATISFIED | Truth 7 |
| SYNC-01 | 01-03, 01-04, 01-07, 01-09, 01-10, 01-11 | SATISFIED | `HANDBOOK_DIR` env, one file per page with YAML front matter, read-only mount, no token (truths 2, 8) |
| SYNC-02 | 01-04, 01-07, 01-09, 01-10, 01-11 | SATISFIED | Truth 3 |
| SYNC-03 | 01-03, 01-04, 01-07, 01-09, 01-10, 01-11 | SATISFIED | Truth 2; synthetic-secret fixture tests (`test_redaction*.py`, `test_sync_e2e.py` FORBIDDEN list) pass |
| SYNC-04 | 01-05, 01-07, 01-08, 01-11 | SATISFIED | Truth 4: heading chunks with file/h2/h3/line range, `GUIDES_INDEX` drift 0 |
| SYNC-05 | 01-02, 01-04, 01-09, 01-10, 01-11 | SATISFIED | `handbook://<page_id>` (stem), title, revision date on all 22 rows |
| SYNC-06 | 01-06, 01-07, 01-08 | SATISFIED | Truth 4: scene links with `#t=`, README fallback, none when no video |
| SYNC-07 | 01-02, 01-07, 01-10 | SATISFIED | Truth 5 |

### Anti-Patterns Found

Debt-marker scan (`TBD|FIXME|XXX|TODO|HACK|NotImplemented`) over `jobs packages tests run-unit-tests.sh Dockerfile docs/*.md`: none. No stubs, empty implementations or placeholder returns found in the sync or core modules read (pipeline, handbook, handbook_files). Gitignore holds `docs/research/handbook-raw/`, `*.db`, `artifacts/`, `.cache/`, `.env`; `git ls-files` lists no handbook, db or artifact file. Working tree clean after the live runs (ignored dirs `artifacts/` and `.cache/` were created locally by this verification's live run).

### Warnings (non-blocking)

1. `run-unit-tests.sh` is mode `100644` in the git index (`git ls-files -s`); it is executable only locally because `core.fileMode=false` hides the difference. A fresh clone must run `bash ./run-unit-tests.sh` or `chmod +x`. Fix with `git update-index --chmod=+x run-unit-tests.sh` (executor also hit this).
2. ROADMAP.md still shows Phase 1 as `[ ]` in the phase list while the 11 plans are `[x]` and REQUIREMENTS traceability says Complete. Orchestrator should tick it on completion.
3. `.planning/PROJECT.md` line 32 still describes the content-sync objective in ClickUp terms (stale after D-25); documentation only.
4. Known follow-up, not a Phase 1 gap: `buddy_sync run` logs redaction hits on stderr with `source=<handbook file stem>`. Relevant only if logs become public (Phase 4 hosting). The first live run wrote 68 stderr lines; this verifier discarded them unread.

### Human Verification Required

None required for the goal. Optional UAT note: the scene-clip URLs point to release assets in the private Guides repo (e.g. `.../mcp-servers.mp4#t=444`); that they play for a given viewer is the ROLL-02 concern (deferred), not a Phase 1 criterion.

### Gaps Summary

No gaps. Every ROADMAP success criterion and every requirement ID is backed by code read and by runs executed by this verifier: full gate green, live sync reproduced with the same content hash as the recorded run, second run idempotent, Wi-Fi page absent, zero residual secret hits, Guides search returns file:line and video URLs.

---

_Verified: 2026-11-03T21:20:00Z_
_Verifier: Claude (gsd-verifier)_
