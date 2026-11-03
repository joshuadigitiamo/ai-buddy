---
phase: 01-content-sync
plan: 06
subsystem: sync
tags: [video-map, sections-yaml, pydantic, pyyaml, readme-parser, contract-docs, tdd]

requires:
  - phase: 01-02
    provides: GuideChunk, VideoLink, video_link, make_chunk_key, IndexContent, build_index, LocalDirArtifactStore, open_index/search_guides
  - phase: 01-05
    provides: chunker heading model, GUIDES_INDEX.md format and drift policy (documented here)
provides:
  - "buddy_sync.video_map: SECTIONS_GLOB, DURATIONS_RELPATH, MAX_SECTIONS_BYTES, VideoPart, SectionEntry, SectionsFile, VideoMapError, parse_readme_videos, load_sections_file, scene_offsets, resolve_video_links (plus README_NAME)"
  - "tests/fixtures/guides_videos: synthetic README table and demo (single part) and multi (two parts) video maps"
  - "docs/guides-contract.md: cross-repo contract for sections.yaml, durations.json, README table, GUIDES_INDEX.md, fallbacks"
affects: [01-07, 01-08, phase-02, phase-03]

plan_head_before: fbff4844254f460c65b1f732ac192b94c988969e
plan_head_after: 09d6772587d99b79a1358a9c5fdee08c0b46c1be

actuals:
  tokens: 9250
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Anti-corruption layer: README table, sections.yaml and durations.json are validated at the boundary and converted into VideoLink rows"
    - "sections.yaml is yaml.safe_load plus a pydantic schema with extra=forbid, a size cap and a versioned `schema: 1` key"
    - "Video URL, part and offset resolved at sync time and stored per chunk; the reader only joins"

key-files:
  created:
    - jobs/sync/buddy_sync/video_map.py
    - tests/fixtures/guides_videos/README.md
    - tests/fixtures/guides_videos/videos/demo/sections.yaml
    - tests/fixtures/guides_videos/videos/demo/out/durations.json
    - tests/fixtures/guides_videos/videos/multi/sections.yaml
    - tests/fixtures/guides_videos/videos/multi/out/durations.json
    - tests/unit/buddy_sync/test_video_map.py
    - tests/unit/buddy_sync/test_readme_videos.py
    - docs/guides-contract.md
  modified: []

key-decisions:
  - "README_NAME is an extra public constant in video_map (beyond the interfaces block); resolve_video_links needs the file name and tests and later plans may reuse it"
  - "A guide that appears in two README rows, or that is mapped by two sections.yaml files, raises VideoMapError instead of silently overriding (silent drift is what D-02 forbids)"
  - "An empty video cell is drift (VideoMapError); only a dash (em dash, en dash or hyphen) means no video"
  - "resolve_video_links needs the chunks of every guide that has a sections.yaml: a map whose guide is not among the passed chunks fails as 'not an indexed Guides file'. Callers must pass all chunks, not a subset"

requirements-completed: [SYNC-06, GUIDE-01]

coverage:
  - id: D1
    description: "A section mapped in sections.yaml is stored with the README part URL and a start offset from durations.json, and search_guides returns it so video_link composes `demo.mp4#t=30` (S03 at 30.5 s); the mapped h2 preamble ends `#t=10`; an unmapped section has source readme_fallback and no #t="
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_mapped_section_has_timestamped_link"
        status: pass
    human_judgment: false
  - id: D2
    description: "Multi-part videos: scene ids P<n> resolve to part n, offsets restart at 0 in each part (first scene of part 2 starts at 0.0); offsets follow durations.json key order; most specific entry wins (h3 over h2-only; h2-only covers preamble and sibling ###)"
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_multi_part_offsets_restart_in_each_part"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_h3_entry_beats_h2_only_entry_and_h2_covers_siblings"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_reordering_durations_changes_offsets"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_scene_offsets_follow_key_order_and_part_prefix"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fallbacks (D-06): guide with a README video but no map gets readme_fallback part 1 with no offset; unmapped chunk takes the part of the nearest preceding mapped chunk (part 2 after a part-2 chunk), else part 1; dash guide gets no rows; `sections: []` makes every chunk a fallback; duplicate target keeps the first and logs a warning"
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_guide_with_video_but_no_map_uses_readme_fallback"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_unmapped_chunk_takes_part_of_nearest_preceding_mapped_chunk"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_guide_without_video_gets_no_entry"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_empty_sections_list_makes_every_chunk_a_fallback"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_duplicate_target_keeps_first_and_warns"
        status: pass
    human_judgment: false
  - id: D4
    description: "Fail loudly (D-02, T-01-26 to T-01-28): 20 contract breaks raise VideoMapError naming the file and key: unknown scene, h2 or h3 without chunk, guide with .., absolute, backslash or not indexed, guide without README video, video slug differs, part missing from README, durations missing/list/not JSON/non-number, unknown key, schema 2, !!python/object tag, oversize file, same guide mapped twice, README absent"
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_contract_break_fails_loudly_and_names_the_file"
        status: pass
    human_judgment: false
  - id: D5
    description: "README table parser: single link is part 1, multi-part with <br> gives ordered parts, dash gives no key, non-table text and separator rows ignored, escaped pipe in a cell is safe; text-only, empty, non-.mp4, non-https, unlabelled multi and repeated-part cells and a guide listed twice raise VideoMapError (drift guard)"
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_readme_videos.py (9 test functions, 16 cases)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Prohibition SYNC-06: no scene link without an explicit sections.yaml entry; no heuristic matching exists in the code (unmapped sections get the untimed README URL or nothing)"
    requirement: SYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_guide_with_video_but_no_map_uses_readme_fallback"
        status: pass
    human_judgment: false
  - id: D7
    description: "docs/guides-contract.md documents the sections.yaml schema, durations.json location and meaning, the Guides .gitignore negation, the README table format and drift guard, GUIDES_INDEX.md format and drift policy, fallback rules and reversibility"
    requirement: SYNC-06
    verification:
      - kind: other
        ref: "plan task 3 verify: grep for sections.yaml, durations.json, '!videos/**/out/durations.json', GUIDES_INDEX.md; 8 `## ` sections"
        status: pass
    human_judgment: true
    rationale: "Whether the document is complete and accurate for the Guides-repo owner is a review judgment; only the required terms are mechanically checked. The CLI `python -m buddy_sync guides-index` and its `--strict` flag it names are delivered by plan 07"
  - id: D8
    description: "GUIDE-01: the plan's Guides-applied table (capture metadata at load time, anti-corruption layer, versioned data contract) is realised in code"
    requirement: GUIDE-01
    verification: []
    human_judgment: true
    rationale: "Convention compliance is a review judgment; the 'Guides applied' block is in the plan itself"

duration: 4min
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 06: Video Map Summary

**`buddy_sync.video_map` resolves every Guides chunk to its video: scene start inside the right part (README base URL plus a `durations.json` offset) when `sections.yaml` maps it, the untimed README URL otherwise, nothing for guides without a video, with a strict `safe_load` plus pydantic schema and loud failure on every contract break; `docs/guides-contract.md` documents the cross-repo formats.**

## Performance

- **Duration:** ~4 min (2026-11-03T19:35:06Z to ~19:39Z)
- **Tasks:** 3 (Task 1 tracer, Task 2 tdd, Task 3 auto)
- **Files:** 9 created (4 fixture files plus fixture README, module, two test files, contract doc); `./run-unit-tests.sh --all`: ruff, ruff format, mypy strict clean, 296 passed, coverage 97.5% (`video_map.py` 98%)

## Accomplishments

- Tracer verified end to end: fixture README, `sections.yaml` and `durations.json` resolve to links that go through `build_index`, `publish`, `open_index` and `search_guides`; the Chunking chunk returns `https://videos.example.invalid/demo.mp4#t=30`, the `1. Basics` preamble `#t=10`, and `2. Only Section` has source `readme_fallback` and no `#t=`.
- Multi-part resolution (D-05) with offsets restarting per part, most-specific-wins and first-listed-wins, fallback part taken from the nearest preceding mapped chunk (D-06).
- 20 contract-break cases fail with `VideoMapError` naming the file and key; the `!!python/object` case proves `safe_load` is the only loader and no file content leaks into messages.
- README table drift guard and `docs/guides-contract.md` (8 sections, including the `.gitignore` change needed to commit `durations.json`).

## Task Commits

1. **Task 1: Tracer** - `9114043` (feat)
2. **Task 2: Multi-part, fallbacks, contract breaks** - `64a15f8` (test)
3. **Task 3: README drift tests and contract document** - `09d6772` (docs)

**Plan metadata:** committed separately (docs: complete plan).

`commits: 3` is the measured `git rev-list --count` over the plan range and equals the three task commits.

## TDD Gate Compliance

Task 2 is a task-level `tdd="true"` task inside a `type: execute` plan. `workflow.tdd_mode` is not enabled; the `check tdd-red-evidence` classifier has no pytest adapter and was not run (same as plans 01-02, 01-03 and 01-05).

- **RED:** first run of the new Task 2 tests had 9 failures, all `VideoMapError: ... 'guide' ... is not an indexed Guides file`. This was a test-design fault, not an implementation fault: with two `sections.yaml` files in the fixture tree, every `resolve_video_links` call must receive the chunks of both guides (by design, T-01-26 requires the guide to be indexed). The tests were fixed to resolve against all fixture chunks; no implementation change was needed.
- **GREEN:** there is no separate `feat` commit for Task 2. Task 1's action text already specified the full resolver (part handling, most-specific selection, fallback part, every validation), so all 20 contract-break cases and the behaviour tests passed against the Task 1 implementation. The commit is a single `test(01-06)` commit that pins that behaviour. Task 3 likewise needed no implementation change: the drift guard was already in `parse_readme_videos` from Task 1 (the plan allowed "add it if Task 1 did not").
- No REFACTOR commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Duplicate README row and duplicate map for one guide raise**
- **Found during:** Task 1 (design of `parse_readme_videos` and `resolve_video_links`)
- **Issue:** a guide listed in two README rows, or mapped by two `sections.yaml` files, would silently override one entry with the other, which is the silent drift D-02 forbids.
- **Fix:** both raise `VideoMapError` ("more than once", "mapped by two files"); covered by `test_guide_listed_twice_raises` and the `same_guide_mapped_twice` case.
- **Files modified:** `jobs/sync/buddy_sync/video_map.py`
- **Commit:** `9114043`

**2. [Process] Extra public name `README_NAME`**
- One constant beyond the interfaces block; no consumer-visible name from the block changed.

**3. [Process] Test-design correction, no implementation change**
- See TDD Gate Compliance: tests had to pass all fixture chunks to the resolver. Callers in plan 07 must pass every guide's chunks (they do: `sync_guides` returns all chunks).

**4. [Process] Formatting**
- ruff E501 and format findings fixed with `ruff check --fix` / `ruff format` run inside the test image (runner only has `--check`).

**5. [Process] Commits on protected branch `main`**
- As instructed (sequential executor, `branching_strategy=none`); nothing pushed, no branch created.

**Total deviations:** 1 auto-fixed (missing-critical), 4 process notes. **Impact:** none on interfaces or scope.

## Authentication Gates

None.

## Issues Encountered

None remaining.

## Known Stubs

None.

## Threat Flags

None. T-01-26 (guide path: relative, no `..`, no backslash, must be indexed), T-01-27 (`yaml.safe_load` only, `!!python/object` test, `extra="forbid"`) and T-01-28 (size cap before parsing) are mitigated with tests; T-01-29 is accepted as planned (only `https://...mp4` links are parsed); T-01-SC: no packages installed (PyYAML and pydantic were already pinned by plan 01).

## Next Phase Readiness

Ready for 01-07 and 01-08. Plan 07 calls `resolve_video_links(checkout_root, result.chunks, logger=...)` after `sync_guides` (chunks of all guides, after redaction, so keys match) and passes the dict as `IndexContent.videos`; it also owns the `guides-index` CLI and `--strict` flag that `docs/guides-contract.md` describes. Plan 08 must write the real `sections.yaml` and `durations.json` for `mcp-servers` and `multi-agent-design`, change the Guides `.gitignore` as documented, and confirm the open assumptions: `#t=` on a release download URL may be ignored by the browser (offset is stored separately), and the real README table parses without tripping the drift guard.

## Self-Check: PASSED

- All 9 created files exist; commits `9114043`, `64a15f8`, `09d6772` are ancestors of HEAD; `git rev-list --count fbff484..HEAD` = 3.
- Acceptance greps: `safe_load` in video_map.py 2 and `yaml.load(` 0; `example.invalid` in fixture README 4 and private-URL grep 0; `P2S01Recap` in multi durations 1; `def test_` counts 13 (video_map) and 9 (readme_videos); `## ` sections in guides-contract.md 8; the four contract-topic greps pass.
- `./run-unit-tests.sh --all` exit 0 (296 passed); `--single test_video_map.py test_mapped_section_has_timestamped_link` passed (1 passed).
