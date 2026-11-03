---
phase: 01-content-sync
plan: 05
subsystem: sync
tags: [git, markdown-it-py, chunking, fts5, redaction, drift-check, tdd]

requires:
  - phase: 01-02
    provides: GuideChunk, make_chunk_key, IndexContent, build_index, LocalDirArtifactStore, open_index/IndexReader
  - phase: 01-03
    provides: SyncSettings, Redactor, log_hits, REDACTION_VERSION
provides:
  - "buddy_sync.chunker: PIPELINE_VERSION, MAX_CHUNK_CHARS, Heading, heading_outline, chunk_markdown, assign_chunk_keys"
  - "buddy_sync.guides_git: GuidesCheckout, GuidesSource, GitGuidesSource, GuidesGitError, MARKER_NAME"
  - "buddy_sync.guides: EXTRA_FILES, select_guide_files, build_guide_chunks, GuidesSyncResult, sync_guides"
  - "buddy_sync.guides_index: GUIDES_INDEX_NAME, IndexEntry, Drift, GuidesIndexDriftError, render/parse/compare/check/write_guides_index"
  - "tests/conftest.py git_repo_factory and git_commit fixtures; synthetic DEMO_GUIDE.md fixture"
affects: [01-06, 01-07, 01-08, phase-02]

plan_head_before: 95df199f28cd5b8cb64a9a9191d8aded1e6b2ed5
plan_head_after: 749bab735aee25a89c7104366d07ed855e41ce86

actuals:
  tokens: 13700
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Ports and adapters: GuidesSource port, GitGuidesSource adapter; tests drive the same adapter against a local fixture repo"
    - "Single heading parser (heading_outline over markdown-it tokens) shared by chunker and GUIDES_INDEX generator"
    - "Git credentials only as GIT_CONFIG_COUNT/KEY_n/VALUE_n in the child env; stderr scrubbed of token and base64 before it reaches a message"
    - "Destructive git (fetch, reset --hard) gated by an on-disk ownership marker"

key-files:
  created:
    - jobs/sync/buddy_sync/chunker.py
    - jobs/sync/buddy_sync/guides_git.py
    - jobs/sync/buddy_sync/guides.py
    - jobs/sync/buddy_sync/guides_index.py
    - tests/conftest.py
    - tests/fixtures/guides_repo/AI-Engineering/DEMO_GUIDE.md
    - tests/unit/buddy_sync/test_guides_source.py
    - tests/unit/buddy_sync/test_chunker.py
    - tests/unit/buddy_sync/test_guides_scope.py
    - tests/unit/buddy_sync/test_guides_git.py
    - tests/unit/buddy_sync/test_guides_index.py
  modified: []

key-decisions:
  - "assign_chunk_keys is public in chunker.py and runs again after redaction, so a chunk key is always derived from the redacted headings and duplicate keys always get the ~N occurrence suffix (base key counted per slug, so slug collisions such as a literal '_' heading also disambiguate)"
  - "heading_outline collapses whitespace in titles (multi-line setext headings), so the index table and the chunks agree on one-line titles"
  - "Absent GUIDES_INDEX.md in non-strict mode logs a warning and returns no drifts; a declared file that no longer exists is one absent_file drift per file, not one missing per heading"
  - "Path filter excludes any 'videos' or '.git' directory component, not only a top-level one"
  - "The token header is attached only for https URLs; a local-path URL never gets one"

requirements-completed: [SYNC-04, GUIDE-01]

coverage:
  - id: D1
    description: "A git-sourced fixture guide becomes searchable heading chunks whose file, h2, h3 and 1-based line range match the source; meta.guides_commit_sha is the cloned HEAD"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_source.py#test_fixture_guide_becomes_searchable_chunks_with_exact_lines"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_source.py#test_checkout_reports_the_repo_head_commit"
        status: pass
    human_judgment: false
  - id: D2
    description: "Chunker rules D-20: one chunk per ### with parent ##, preamble only when prose precedes the first ###, no chunk for empty ###, fences (``` and ~~~) never start a chunk, #### stays inside, nothing above the first ##, empty and no-## files give []"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_chunker.py (18 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Oversized sections split only at top-level block boundaries into numbered parts that keep the heading; fences, tables and single oversized blocks stay whole; output ordered by (line_start, part_index); duplicate headings get distinct keys"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_chunker.py#test_oversized_h3_splits_at_paragraph_boundaries_and_tiles_the_section"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_chunker.py#test_duplicate_headings_get_distinct_keys_with_occurrence_suffix"
        status: pass
    human_judgment: false
  - id: D4
    description: "File scope D-19: **/*_GUIDE.md plus MULTI_AGENT_ARCHITECTURE_DESIGN.md; README.md, CLAUDE.md, videos/, .git/ and symlinks resolving outside the checkout excluded"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_scope.py#test_globs"
        status: pass
    human_judgment: false
  - id: D5
    description: "Token hygiene and safety: token only in the child env as http.extraHeader (never argv, never .git/config), stderr scrubbed of token and base64, marker required before fetch/reset with no git command run otherwise, option-like or credentialed URLs and branches rejected"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_git.py (11 test functions, 16 cases)"
        status: pass
    human_judgment: true
    rationale: "The https header path is proven against a recording fake runner only; the live GitHub clone and GIT_CONFIG_COUNT behaviour on the real remote are exercised in plan 08"
  - id: D6
    description: "D-24: unchanged commit SHA with matching pipeline and redaction versions reuses the previous chunks; a changed SHA or version rebuilds"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_git.py#test_unchanged_sha_and_versions_reuse_previous_chunks"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_git.py#test_new_sha_rebuilds"
        status: pass
    human_judgment: false
  - id: D7
    description: "D-23: GUIDES_INDEX.md renders from the chunker outline, round-trips through parse, drift (missing, extra, moved, absent_file) is warned and strict mode raises; absolute or .. paths rejected"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_guides_index.py (12 test functions, 14 cases)"
        status: pass
    human_judgment: false
  - id: D8
    description: "GUIDE-01: the plan's Guides-applied table (RAG chunking and metadata, ports and adapters, idempotent pipelines) is realised in code"
    requirement: GUIDE-01
    verification: []
    human_judgment: true
    rationale: "Convention compliance is a review judgment; the 'Guides applied' block is in the plan itself"

duration: 6min
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 05: Guides Source and Chunker Summary

**Git-acquired Guides repo (marker-guarded clone/fetch/reset, token only as an env-carried `http.extraHeader`) split by markdown-it into heading chunks with exact line ranges, redacted, reused when the commit SHA and versions are unchanged, plus a generated `GUIDES_INDEX.md` with drift detection.**

## Performance

- **Duration:** ~6 min (2026-11-03T19:28:04Z to ~19:34Z)
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 TDD)
- **Files:** 11 created, 0 modified; `./run-unit-tests.sh --all`: ruff, ruff format, mypy strict clean, 248 passed, coverage 97.2%

## Accomplishments

- Tracer verified end to end: local fixture repo, `git clone`, chunk, redact, publish, open, `search_guides("chunking")` returns `AI-Engineering/DEMO_GUIDE.md`, `1. Basics` / `Chunking`, lines 10-12; the fenced `## fake heading inside fence` line is body text of the `Code` chunk.
- Full D-20 chunker with preamble, oversize splitting and per-file occurrence keys; D-19 file scope including the outside-symlink and `.git/` cases.
- Token cannot reach argv, `.git/config` or exception text; a `.git` without `.buddy-sync-checkout` runs zero git commands (T-01-21 to T-01-23).
- SHA/version skip (D-24) and `GUIDES_INDEX.md` render/parse/compare/check/write (D-23); the table format is the costly-to-change cross-repo contract named in the plan.

## Task Commits

1. **Task 1: Tracer** - `75444e9` (feat)
2. **Task 2 RED** - `9eb5fc1` (test); **GREEN** - `f208fed` (feat)
3. **Task 3 RED** - `317fb72` (test); **GREEN** - `749bab7` (feat)

**Plan metadata:** committed separately (docs: complete plan).

## TDD Gate Compliance

Tasks 2 and 3 are task-level `tdd="true"` tasks inside a `type: execute` plan; `workflow.tdd_mode` is not enabled and the `check tdd-red-evidence` classifier has no pytest adapter, so it was not run (same as plans 01-02 and 01-03).

- **Task 2 RED (`9eb5fc1`):** 4 target tests failed on planned assertions (`test_oversized_h3_splits...`, `test_fenced_block_longer...`, `test_output_is_ordered...` got one unsplit chunk instead of parts; `test_globs` got `.git/`, `videos/` and the outside symlink in the list). The other 15 chunker tests passed immediately because the tracer already implemented those rules; they pin them. Semantic assessment: no import, collection or fixture faults.
- **Task 2 GREEN (`f208fed`):** 18 chunker tests and 3 scope tests pass.
- **Task 3 RED (`317fb72`):** 3 of 16 `test_guides_git.py` cases failed on the planned assertions (missing `http.extraHeader`, stderr text not in the message, `rebuilt` True on unchanged SHA); 13 of 14 `test_guides_index.py` cases failed against a skeleton module whose functions return empty values (`""`, `[]`, unwritten path), so they fail on assertions rather than at import. The skeleton `guides_index.py` was committed inside the RED commit for that reason. The marker, URL and branch tests passed immediately (Task 1 already enforced them).
- **Task 3 GREEN (`749bab7`):** all pass. No REFACTOR commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Multi-line setext headings broke title agreement**
- **Found during:** Task 3 design (index table rows are single-line)
- **Issue:** `inline.content` of a setext heading can contain a newline, so a title could not round-trip through the table or match the chunker.
- **Fix:** `heading_outline` collapses whitespace in titles.
- **Files modified:** `jobs/sync/buddy_sync/chunker.py`; **Commit:** `749bab7`

**2. [Rule 2 - Missing critical] Chunk keys must come from redacted headings**
- **Found during:** Task 1 (key derived at chunk time from raw headings, redaction runs afterwards)
- **Issue:** a secret inside a heading would have survived in `chunk_key`.
- **Fix:** public `assign_chunk_keys(file, chunks)` in `chunker.py` (an addition beyond the interfaces block); `chunk_markdown` and `build_guide_chunks` both call it, the latter after redaction.
- **Files modified:** `chunker.py`, `guides.py`; **Commit:** `75444e9`

**3. [Rule 2 - Missing critical] Subprocess timeout**
- `GitGuidesSource` passes `timeout=300` and maps `TimeoutExpired` to `GuidesGitError`, so a hung remote cannot stall the job forever.

**4. [Process] RED commit carries a skeleton module**
- See TDD Gate Compliance (Task 3); `guides_index.py` first appears in `317fb72` as a no-behaviour skeleton.

**5. [Process] Test helper types**
- `from conftest import ...` and `from tests.conftest import ...` are unreliable under `--import-mode=importlib` (same finding as plan 01-02), so the two test files that use the fixtures declare their own `RepoFactory`/`CommitFn` `Callable` aliases.

**6. [Process] Formatting**
- ruff E501 and format findings fixed with `ruff check --fix` / `ruff format` inside the test image (runner only has `--check`).

**7. [Process] Commits on protected branch `main`**
- As instructed (sequential executor, `branching_strategy=none`); nothing pushed, no branch created.

**Total deviations:** 3 auto-fixed (1 bug, 2 missing-critical), 4 process notes. **Impact:** none on interfaces; one extra public name (`assign_chunk_keys`).

## Authentication Gates

None. No network access was used; the https/token path is covered with a fake runner.

## Issues Encountered

- `git clone --depth 1` on a local path prints "--depth is ignored in local clones" and works; real shallow behaviour is only seen against the remote in plan 08.
- `test_local_clone_leaves_neither_token_nor_header_in_git_config` is weak by construction: the header is attached only for https, and the local fixture URL is a path, so the config can never contain it. The meaningful token assertions are the recording-runner tests; the real https clone and `.git/config` check belong to plan 08.
- If `GUIDES_REPO_URL` changes after the first run, fetch still targets the stored `origin`; the plan specifies `fetch origin`, so this was left as is. Delete the checkout dir to re-clone.

## Known Stubs

None.

## Threat Flags

None. T-01-21 to T-01-24 are mitigated as planned (env-only token with scrubbed stderr, marker guard, argv/URL/branch validation, resolved-path containment plus `..`/absolute row rejection); T-01-25 is transferred to Phase 2/3 (index text is untrusted input); T-01-SC: no packages installed.

## Next Phase Readiness

Ready for 01-06/01-07. Plan 07 wires `GitGuidesSource` + `sync_guides` into the CLI (it must pass `versions_match` from the previous artifact's pipeline and redaction versions, call `check_guides_index` and `write_guides_index`). Plan 08 must confirm the flagged assumptions: text above the first `##` is not indexed, `GIT_CONFIG_*` `http.extraHeader` works on the real https remote, and the entropy rule on real Guides code blocks (carried over from 01-03).

## Self-Check: PASSED

- All 11 created files exist; commits `75444e9`, `9eb5fc1`, `f208fed`, `317fb72`, `749bab7` are ancestors of HEAD; `git rev-list --count 95df199..HEAD` = 5.
- Acceptance greps: `MarkdownIt` in chunker.py 3, `GIT_CONFIG_COUNT` 1, `.buddy-sync-checkout` 2, `def git_repo_factory` 1, `MULTI_AGENT_ARCHITECTURE_DESIGN.md` in guides.py 1, `x-access-token` 2, generated-file comment 1; test function counts chunker 18, git 11, index 12.
- `./run-unit-tests.sh --all` exit 0: 248 passed, coverage 97.2%; `--single test_guides_scope.py test_globs` passed.
