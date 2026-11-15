---
phase: 04-infrastructure-and-ci-cd
plan: 19
subsystem: infra
tags: [sync, publish, gcs, pointer, video-links, gap-closure]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: GcsArtifactStore pointer-last publish, BucketPort.md5_base64, VIDEO_BUCKET link rewrite (04-11)
provides:
  - publish_index returns unchanged only after the pointer's db object is confirmed in the bucket
  - a run without VIDEO_BUCKET re-resolves video links from the Guides README
affects: [04-infrastructure-and-ci-cd verification, scripts/sync-and-publish.sh recovery path]

actuals:
  tokens: 2900
  tasks: 2
  commits: 4
plan_head_before: 35cb52381c759395a7f8a7ea287c409612b53d35
plan_head_after: a53265f6aaf46d15501af9b0c84fdf46d4a1cdc6

tech-stack:
  added: []
  patterns:
    - "Confirm the object a pointer names through BucketPort before trusting the pointer (no google-cloud-storage call in publish.py)"

key-files:
  created: []
  modified:
    - jobs/sync/buddy_sync/publish.py
    - tests/unit/buddy_sync/test_publish.py
    - jobs/sync/buddy_sync/pipeline.py
    - tests/unit/buddy_sync/test_sync_e2e.py

key-decisions:
  - "A pointer whose object name is not index-<build_id>.db is treated as unusable and replaced by a full publish"
  - "md5 comparison against the local db only when the pointer build_id equals the local build_id; another build with the same content needs only its object present"
  - "New video-link tests live in test_sync_e2e.py (the plan's file) with a small self-contained env helper, not in test_video_upload.py"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "publish re-uploads the db and rewrites the pointer when the object the pointer names is missing (WR-07)"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_publish.py#test_unchanged_pointer_with_a_missing_db_object_republishes"
        status: pass
    human_judgment: false
  - id: D2
    description: "publish re-uploads when the same-build db object differs from the local db by md5"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_publish.py#test_unchanged_pointer_with_a_damaged_same_build_object_republishes"
        status: pass
    human_judgment: false
  - id: D3
    description: "A pointer from another build with the same content and its object present stays unchanged; an unexpected object name is not trusted"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_publish.py#test_same_content_from_another_build_with_its_object_present_is_unchanged"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_publish.py#test_a_pointer_naming_an_unexpected_object_is_not_trusted"
        status: pass
    human_judgment: false
  - id: D4
    description: "A local-only run after a bucket-linked run drops private-bucket video links even when the Guides commit is unchanged (WR-08, T-04-44)"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_local_only_run_after_a_published_run_drops_bucket_links"
        status: pass
    human_judgment: false
  - id: D5
    description: "Runs with VIDEO_BUCKET set keep or re-point links as before"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_two_runs_with_the_same_video_bucket_keep_the_links_on_it"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_sync_e2e.py#test_a_changed_video_bucket_with_the_same_commit_repoints_the_links"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-11-15
status: complete
---

# Phase 4 Plan 19: Publish pointer check and local-only video links Summary

**publish_index confirms the pointer's db object (md5 via BucketPort) before answering "unchanged", and a run without VIDEO_BUCKET re-resolves video links from the Guides README instead of keeping private-bucket URLs.**

## Performance

- **Duration:** 14 min
- **Completed:** 2026-11-15
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- WR-07: re-running the publish command recovers a deleted or damaged `index-<build_id>.db` object; the db is uploaded first and the pointer rewritten last, so an interruption still leaves the previous pointer in place.
- WR-08 / T-04-44: a local-only index carries README links only; bucket links appear only when the same run has VIDEO_BUCKET set.
- Existing behaviour kept: same-content pointer with its object present is `unchanged` with no upload; VIDEO_BUCKET set with an unchanged commit still re-points links.

## Task Commits

1. **Task 1: lost index object is re-uploaded** - `cd875c1` (test, RED), `6913425` (fix, GREEN)
2. **Task 2: local-only run re-resolves video links** - `f06897f` (test, RED), `a53265f` (fix, GREEN)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified
- `jobs/sync/buddy_sync/publish.py` - `_pointer_object_is_current` and `_md5_base64_of`; `unchanged` gated on the object check
- `tests/unit/buddy_sync/test_publish.py` - four new tests (missing object, damaged same-build object, unexpected object name, other build with same content)
- `jobs/sync/buddy_sync/pipeline.py` - three-way video link branch: rebuilt, bucket set (rewrite), bucket unset (re-resolve)
- `tests/unit/buddy_sync/test_sync_e2e.py` - three video-link tests with a self-contained env helper

## Decisions Made
- A pointer whose `object` is not `index-<build_id>.db` is unusable and falls through to a full publish (matches the reader's own `_Pointer` validation).
- md5 compare against the local db only for the same build id; a pointer from another build with the same content hash needs only its object present, so a mere build-id change does not force a republish.
- The new video-link tests went into `test_sync_e2e.py` as the plan lists, rather than `test_video_upload.py` where the older VIDEO_BUCKET tests sit; a small env helper was duplicated there.

## Deviations from Plan

None - plan executed exactly as written. (TDD: each task has a RED commit that failed for the expected reason, then a GREEN commit.)

## Issues Encountered
None. `./run-unit-tests.sh --all`: 1498 passed, 26 skipped, coverage 97.60% (gate 80%).

## Threat Flags
None. Mitigations T-04-60 (Task 1) and T-04-61 (Task 2) are implemented and tested. No md5 or object content is logged.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- WR-07 and WR-08 closed. `scripts/sync-and-publish.sh` stays the single recovery path for a damaged index object.
- INFRA-04 is declared by sibling gap plans; the ready-ids gate decides whether it is marked complete.

## Self-Check: PASSED

- publish.py, test_publish.py, pipeline.py, test_sync_e2e.py exist; commits cd875c1, 6913425, f06897f, a53265f are ancestors of HEAD; `commits: 4` measured from the ledger.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-15*
