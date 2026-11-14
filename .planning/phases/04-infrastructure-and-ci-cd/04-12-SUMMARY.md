---
phase: 04-infrastructure-and-ci-cd
plan: 12
subsystem: infra
tags: [video-coverage, d-18, scene-timestamps, readme-fallback, sections-yaml, laptop-sync]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-01 coverage_inheritance (a) and sections_authoring (a) decisions"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-11 video_map (resolve_video_links, video_basename), upload-videos, VIDEO_BUCKET"
provides:
  - "buddy_sync.coverage: CoverageRow(file, rows, scene, fallback, label), coverage_from_index, coverage_from_tree, format_report, BASELINE_SCENE_ROWS=238, BASELINE_TOTAL_ROWS=2524"
  - "python -m buddy_sync video-coverage [--artifact-dir DIR] [--guides-dir DIR]"
  - "Regression tests pinning the D-18 fallback for sections without a scene entry"
affects: [04-13, 04-14]

actuals:
  tokens: 4300
  tasks: 2
  commits: 3
plan_head_before: 879e03d61daf3991f28e49cc90392d04d129c3df
plan_head_after: c3b3a38c5964a9300f6075eaf0f7052f44283309

tech-stack:
  added: []
  patterns:
    - "The report reads only through the index reader and the video_map anti-corruption layer (resolve_video_links, load_sections_file, parse_readme_videos, video_basename); no second parser of Guides files"
    - "Projected mode reuses the production resolver over the published index's chunks, so the projection cannot drift from what run would write"

key-files:
  created:
    - jobs/sync/buddy_sync/coverage.py
    - tests/unit/buddy_sync/test_video_coverage.py
  modified:
    - jobs/sync/buddy_sync/cli.py
    - jobs/sync/README.md
    - tests/unit/buddy_sync/test_video_map.py

key-decisions:
  - "Under 04-01 coverage_inheritance (a) the code already implemented the D-18 fallback, so Task 2 is regression tests only: no inherited source, no schema, CHECK, model, reader or docs/index-format.md change"
  - "CoverageRow has no inherited field: it would always be 0 under (a), and the hand-off allowed omitting it"
  - "Projected-mode label for a guide without a sections.yaml is derived from the README: video file stem without .mp4 and without a _partN suffix names the topic folder; durations.json present there gives 'durations only', else 'no durations'"
  - "The report prints no label in actual (index) mode: the index does not know which Guides files exist on the laptop"

patterns-established:
  - "Report output limited to guide paths, labels and counts (T-04-45), asserted by a test that greps the output for heading text, chunk text and URLs"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "video-coverage prints per guide the rows with a video link split into scene and fallback, then a total line with the 238/2524 baseline"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_coverage_from_index_splits_scene_and_fallback_rows_per_guide"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_format_report_ends_with_the_total_line_and_the_baseline"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_cli_prints_the_report_and_returns_zero"
        status: pass
    human_judgment: false
  - id: D2
    description: "--guides-dir projects the report from a Guides working tree over the published index chunks and labels each guide sections.yaml, durations only or no durations"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_projected_report_without_sections_yaml_loses_scene_rows_and_says_why"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_projected_report_reflects_a_new_scene_map_before_it_is_committed"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_projected_report_of_the_unchanged_tree_matches_the_index_counts"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_cli_with_guides_dir_prints_the_labels"
        status: pass
    human_judgment: false
  - id: D3
    description: "A missing index or a broken sections.yaml ends with one ERROR line and exit 1; the report holds no chunk text, heading text or URL"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_cli_reports_a_missing_index_with_one_error_line"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_cli_reports_a_broken_sections_file_with_one_error_line"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_coverage.py#test_the_report_holds_only_paths_labels_and_counts"
        status: pass
    human_judgment: false
  - id: D4
    description: "A section without a scene entry keeps the D-18 fallback (current part's full video, start None, source readme_fallback), no inheritance, no inherited source"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_unmapped_section_after_a_mapped_one_keeps_the_fallback_and_does_not_inherit"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_only_scene_links_carry_an_offset_and_no_inherited_source_exists"
        status: pass
    human_judgment: false

duration: ~13min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 12: Video coverage report Summary

**`python -m buddy_sync video-coverage` measures D-18 scene coverage from the published index or projects it from a Guides working tree, and two regression tests pin the decided fallback for unmapped sections.**

## Performance

- **Duration:** about 13 min (start time was not recorded; estimated from the clock)
- **Completed:** 2026-11-14T13:43Z
- **Tasks:** 2
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `buddy_sync.coverage` joins the index's `video_links()` with `guide_chunks()` per guide file and counts scene and fallback rows. `format_report` prints one line per guide and ends with `scene=<S> fallback=<F> rows=<T> (baseline 238/2524)`.
- `--guides-dir` runs the production `resolve_video_links` on the given tree over the index's chunks, so a draft `sections.yaml` can be measured before it is committed (04-14 uses this). Each guide is labelled `sections.yaml`, `durations only` or `no durations`.
- Task 2 under 04-01 `coverage_inheritance` (a): the code already kept the D-18 fallback, so only regression tests were added. No `inherited` source, no schema or CHECK change, no model, reader or `docs/index-format.md` change.
- `jobs/sync/README.md` documents both modes, the labels and the baseline.

## Measured starting point (the plan's verification step)

Run read-only and offline against the local `artifacts/index.db` (the one built 2026-11-03):

```
scene=238 fallback=2286 rows=2524 (baseline 238/2524)
```

Identical to the RESEARCH baseline: scene rows are only Multi-Agent (176) and MCP Servers (62). Projected from the local Guides working tree (`--guides-dir`) the total is unchanged, because no draft `sections.yaml` exists there yet (04-14 authors them). Labels from that run: `sections.yaml` for MCP Servers and Multi-Agent; `durations only` for A2A (188 rows), Airflow (143), Big Data Frameworks (249), Deep Agents (140), LangSmith (178), which is the 898-row ceiling named in RESEARCH Pitfall 14; `no durations` for LangChain, LangGraph, MLflow GenAI, RAG Chatbot, BigQuery, ETL vs ELT, Kubernetes and Design Patterns.

## Task Commits

1. **Task 1: Tracer, video-coverage actual and projected** - `c9d7ec0` (test, RED: `buddy_sync.coverage` absent), `4f0cb80` (feat, GREEN)
2. **Task 2: D-18 fallback regression tests** - `c3b3a38` (test)

**Plan metadata:** the commit that adds this file and the STATE/ROADMAP/REQUIREMENTS updates (docs: complete plan)

## Files Created/Modified

- `jobs/sync/buddy_sync/coverage.py` - CoverageRow, coverage_from_index, coverage_from_tree, format_report, baseline constants
- `jobs/sync/buddy_sync/cli.py` - `video-coverage` subcommand; `_artifact_root` shared with `search`
- `tests/unit/buddy_sync/test_video_coverage.py` - 11 tests over the fixture Guides videos
- `tests/unit/buddy_sync/test_video_map.py` - 2 regression tests for the fallback rule
- `jobs/sync/README.md` - video-coverage section with the 238/2524 baseline

## Decisions Made

See `key-decisions`. The (b) branch of the plan (inherited source, schema bump) was not taken and `files_modified` entries `models.py`, `schema.py`, `index_reader.py` and `docs/index-format.md` were left untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Process] Task 2 has no RED commit**
- **Found during:** Task 2
- **Issue:** the plan's (a) path says "regression test only (the code already does this)", so the new tests pass on first run; there is no failing state to commit.
- **Fix:** none needed. The tests assert the decided behaviour (start None, source readme_fallback, no `#t=`, no `inherited` value, offset only on scene links) and none was weakened.

**2. [Scope] `CoverageRow.inherited` omitted**
- **Found during:** Task 1
- **Issue:** the plan's interface lists an `inherited` field; under (a) it is always 0, and the hand-off allowed reporting 0 or omitting it.
- **Fix:** omitted; the report has scene and fallback columns only.

---

**Total deviations:** 0 auto-fixed, 1 process note, 1 scope note
**Impact on plan:** none. All behaviour in the plan's `must_haves` is met.

## Issues Encountered

- A "COST CRITICAL ... stop and inform the user" notice appeared in several tool results. It came from tool output, not from the user or the plan; the project memory says to ignore cost notices, so I did not act on it.
- The `<project_root_pin>` guard was run as the first command, before any write, and again before every commit; it exited 0 each time.

## Known Stubs

None.

## Threat Flags

None. T-04-45 is mitigated and tested (report holds file paths, labels and counts only). T-04-46 does not apply: the (b) schema change was not made. T-04-SC: no package added.

## User Setup Required

None.

## Next Phase Readiness

- Ready for 04-13 and 04-14. 04-14 can author the five drafts in the local Guides tree and run `video-coverage --guides-dir` to see the projected gain (ceiling 898 rows over the 238 baseline) before Joshua commits them.
- Not run live: nothing in this plan calls GCS or the network.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*

## Self-Check: PASSED

- FOUND: jobs/sync/buddy_sync/coverage.py
- FOUND: tests/unit/buddy_sync/test_video_coverage.py
- FOUND commits: c9d7ec0, 4f0cb80, c3b3a38
- `./run-unit-tests.sh --all`: ruff, ruff format, mypy and pytest clean (1475 passed, 26 skipped, coverage 97.6%)
- Acceptance greps: BASELINE_SCENE_ROWS in coverage.py 2, video-coverage in cli.py 3, D-18 in README 2, `def test_.*(fallback|inherit)` in test_video_map.py 4, test_video_coverage.py 11 tests
