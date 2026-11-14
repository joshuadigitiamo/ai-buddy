---
phase: 04-infrastructure-and-ci-cd
plan: 11
subsystem: infra
tags: [video-hosting, gcs, storage-cloud-google-com, upload-videos, md5-skip, video-map, laptop-sync]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-01 README video table contract, sections.yaml coverage inheritance, video_fetch hand-off (.cache/videos filled on the host with gh)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-04 BucketPort, GcsBucket, check_bucket_name, FakeBucket"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-10 CLI bucket factory injection, scripts/sync-and-publish.sh, publish step"
provides:
  - "buddy_sync.video_upload: upload_videos(readme_videos, video_dirs, bucket) -> UploadReport(uploaded, unchanged), VideoUploadError"
  - "buddy_sync.video_map: gcs_video_url(bucket), video_basename, video_names, rewrite_links, resolve_video_links(..., url_for=...)"
  - "SyncSettings.video_bucket (env VIDEO_BUCKET, optional, validated with check_bucket_name)"
  - "python -m buddy_sync upload-videos --guides-dir DIR --videos-dir DIR [--videos-dir DIR ...] (env VIDEO_BUCKET required; prints uploaded=N unchanged=M)"
  - "scripts/sync-and-publish.sh uploads videos before run and passes VIDEO_BUCKET to run only after an upload"
  - "GCS object layout videos/<name>.mp4 in <PROJECT_ID>-ai-buddy-videos; index video links https://storage.cloud.google.com/<bucket>/videos/<name>.mp4#t=<seconds>"
affects: [04-12, 04-13, 04-14]

actuals:
  tokens: 13100
  tasks: 3
  commits: 4
plan_head_before: c2e069ce125c7768ffb85e5d9f7af92b8a93c22f
plan_head_after: 73fce87869ef020f918f74b66679ba6b2cda310f

tech-stack:
  added: []
  patterns:
    - "Upload logic depends on BucketPort only; the URL rewrite is a function (url_for) passed into the video_map anti-corruption layer"
    - "One validated source of object names (video_names): the README basename must be a plain *.mp4 name and two different URLs may not share it; used by both the upload and the rewrite"
    - "Missing files are collected and reported after the found ones are uploaded, so a re-run after downloading the rest only uploads the remainder"

key-files:
  created:
    - jobs/sync/buddy_sync/video_upload.py
    - tests/unit/buddy_sync/test_video_upload.py
  modified:
    - jobs/sync/buddy_sync/video_map.py
    - jobs/sync/buddy_sync/pipeline.py
    - jobs/sync/buddy_sync/config.py
    - jobs/sync/buddy_sync/cli.py
    - tests/unit/buddy_sync/test_video_map.py
    - tests/unit/buddy_sync/test_config.py
    - scripts/sync-and-publish.sh
    - .env.example
    - tests/unit/test_repo_layout.py
    - jobs/sync/README.md
    - docs/guides-contract.md

key-decisions:
  - "The README table stays the source of the part list and names; with VIDEO_BUCKET set only the base URL of each part is replaced by https://storage.cloud.google.com/<bucket>/videos/<basename>, with no query string (D-16, T-04-42)"
  - "Links kept from the previous artifact when the Guides did not change are re-pointed with rewrite_links, so setting or changing VIDEO_BUCKET takes effect without a Guides commit; the GCS URL form is idempotent"
  - "gcs_video_url validates the bucket name with check_bucket_name, so a malformed bucket can never be formatted into a link"
  - "The laptop script validates PROJECT_ID and the ADC file before the first bucket step (the upload now runs before the sync) and passes VIDEO_BUCKET to run only when the upload step ran, so a --local-only or project-less index keeps README URLs and never links to an object that was not uploaded (T-04-44)"
  - "upload-videos is idempotent by md5 only: the BucketPort exposes no header metadata, so an object whose bytes match but whose headers were changed out of band is not re-uploaded"

patterns-established:
  - "VideoUploadSettings in cli.py mirrors PublishSettings: required env for one subcommand, names-only validation errors"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "upload-videos uploads every README mp4 to videos/<name>.mp4 with video/mp4, inline, private headers and skips unchanged files by md5"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_upload_stores_every_readme_video_with_private_inline_headers"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_a_second_upload_of_unchanged_files_uploads_nothing"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_a_changed_local_file_is_uploaded_again"
        status: pass
    human_judgment: false
  - id: D2
    description: "With VIDEO_BUCKET set the index video links carry the authenticated storage.cloud.google.com URL with the scene offset and no query string; without it the README URLs are kept"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_pipeline_run_with_video_bucket_publishes_the_rewritten_links"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_pipeline_run_without_video_bucket_keeps_the_readme_urls"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_url_for_rewrite_leaves_no_query_string_and_keeps_the_scene_offset"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_pipeline_run_repoints_kept_links_when_video_bucket_is_set_later"
        status: pass
    human_judgment: false
  - id: D3
    description: "A README video without a local file, a non plain mp4 name, duplicate files with different bytes, or two README URLs sharing a name fail with names and counts only before the index can point at a missing object"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_a_missing_local_file_fails_with_the_names_and_count_after_the_others_upload"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_a_readme_name_that_is_not_a_plain_mp4_name_touches_no_bucket"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_upload.py#test_the_same_name_with_different_bytes_in_two_directories_is_a_duplicate_error"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_video_map.py#test_url_for_with_two_readme_urls_sharing_a_basename_is_a_map_error"
        status: pass
    human_judgment: false
  - id: D4
    description: "scripts/sync-and-publish.sh runs upload-videos before run when a project is set, and VIDEO_BUCKET is in the env contract and docs"
    requirement: INFRA-04
    verification:
      - kind: other
        ref: "bash -n scripts/sync-and-publish.sh, plus a stubbed-docker dry run of the four paths (project, local-only, no project, bad project id)"
        status: pass
      - kind: unit
        ref: "tests/unit/test_repo_layout.py#test_env_example_holds_exactly_the_contract_keys"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live upload, authenticated inline playback and #t= seeking on storage.cloud.google.com after the Google login redirect"
    verification: []
    human_judgment: true
    rationale: "Needs the real bucket, Joshua's IAM grant and a browser; first real use is plan 04-13 (RESEARCH A1, A7, Pitfall 13)"

duration: 7min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 11: Video upload and video map Summary

**`upload-videos` puts the README's mp4 files in the private bucket by md5, and `run` rewrites every video link to an authenticated `storage.cloud.google.com/<bucket>/videos/<name>.mp4#t=<seconds>` URL, all from the one laptop command.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-11-14T13:30:02Z
- **Completed:** 2026-11-14T13:37:08Z
- **Tasks:** 3
- **Files modified:** 13 (2 created, 11 modified)

## Accomplishments

- `buddy_sync.video_upload.upload_videos` finds each README mp4 by name under the given directories (recursive), compares its base64 md5 with the object, and uploads only when absent or different, with `video/mp4`, `inline` and `private`. A second run uploads nothing.
- Every missing README video fails the command with the count and names (no paths), after the files found are uploaded. Plain `*.mp4` names only, one URL per name, identical-bytes duplicates upload once, different-bytes duplicates fail.
- `video_map.resolve_video_links(..., url_for=...)` and `gcs_video_url(bucket)` rewrite the base URL of every part; `video_link` still appends `#t=<whole seconds>`. No query string is ever produced.
- `run` honors `VIDEO_BUCKET`, including links kept from the previous artifact when the Guides did not change, so adding the variable later re-points the index without a Guides commit.
- `scripts/sync-and-publish.sh` uploads videos before the sync (Guides `videos/` tree plus `./.cache/videos` when it exists), and passes `VIDEO_BUCKET` to `run` only after that upload ran.
- `.env.example` and `CONTRACT_KEYS` carry `VIDEO_BUCKET`; `jobs/sync/README.md` has the upload-videos section; `docs/guides-contract.md` states the README stays the source of names and the index stores the bucket URL.

## Task Commits

1. **Task 1: Tracer, upload plus URL rewrite plus CLI** - `f0a71e5` (test, RED: import failure), `cbd6bbc` (feat, GREEN)
2. **Task 2: Upload edge cases and the script step** - `8f389dc` (feat)
3. **Task 3: Env contract and docs** - `73fce87` (docs)

**Plan metadata:** the commit that adds this file and the STATE/ROADMAP/REQUIREMENTS updates (docs: complete plan)

## Files Created/Modified

- `jobs/sync/buddy_sync/video_upload.py` - upload_videos, UploadReport, VideoUploadError
- `jobs/sync/buddy_sync/video_map.py` - video_basename, video_names, gcs_video_url, rewrite_links, url_for hook
- `jobs/sync/buddy_sync/pipeline.py` - passes url_for; re-points kept links
- `jobs/sync/buddy_sync/config.py` - video_bucket setting
- `jobs/sync/buddy_sync/cli.py` - upload-videos subcommand, VideoUploadSettings, VideoUploadError in _EXPECTED_ERRORS; still one GcsBucket construction site (the shared bucket factory)
- `scripts/sync-and-publish.sh` - upload step, early project/credentials validation, VIDEO_BUCKET to run
- `tests/unit/buddy_sync/test_video_upload.py` - 22 tests; `test_video_map.py` +2; `test_config.py` +2
- `.env.example`, `tests/unit/test_repo_layout.py`, `jobs/sync/README.md`, `docs/guides-contract.md`

## Decisions Made

See `key-decisions` above. Two worth repeating: the script passes `VIDEO_BUCKET` to `run` only when it uploaded first (T-04-44), and md5 is the only skip signal because `BucketPort` has no header metadata.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tests/unit/buddy_sync/test_config.py lists the exact SyncSettings fields**
- **Found during:** Task 1
- **Issue:** `test_settings_hold_exactly_the_documented_fields` failed once `video_bucket` was added; the file is not in the plan's `files_modified`.
- **Fix:** added `video_bucket` to the expected set and two tests (optional/empty means unset, malformed name rejected without echoing the value).
- **Files modified:** tests/unit/buddy_sync/test_config.py
- **Committed in:** cbd6bbc

**2. [Rule 2 - Missing Critical] Links kept from the previous artifact were not rewritten**
- **Found during:** Task 1 (reading pipeline.py)
- **Issue:** when the Guides did not change, `run` reuses `previous.video_links()`. With the plan's rewrite only inside `resolve_video_links`, setting `VIDEO_BUCKET` on an unchanged repo would keep README URLs and report "content unchanged", so the index would never point at the bucket.
- **Fix:** `rewrite_links(previous_links, url_for)` on that branch (idempotent for the GCS URL form); test `test_pipeline_run_repoints_kept_links_when_video_bucket_is_set_later`.
- **Files modified:** jobs/sync/buddy_sync/video_map.py, jobs/sync/buddy_sync/pipeline.py
- **Committed in:** cbd6bbc

**3. [Rule 1 - Bug in plan example] `gcs_video_url("b")` is not a valid bucket name**
- **Found during:** Task 1
- **Issue:** the plan's behavior line uses bucket `b`; `check_bucket_name` (GCS rule, at least 3 characters) rejects it, and I chose to validate the name so a malformed value cannot be formatted into a link.
- **Fix:** the tests use `demo-ai-buddy-videos`; added `test_gcs_video_url_refuses_an_invalid_bucket_name`.
- **Committed in:** cbd6bbc

**4. [Rule 3 - Blocking] The script validated PROJECT_ID and the ADC file only after the sync**
- **Found during:** Task 2
- **Issue:** the upload step now runs before `run` and needs both, so the checks had to move earlier.
- **Fix:** validated before the first bucket step, only when a bucket step will run (project set, not `--local-only`); the original later checks were removed (they could no longer fail).
- **Files modified:** scripts/sync-and-publish.sh
- **Committed in:** 8f389dc

**5. [Process] Task 2 had no separate RED run**
- The Task 1 implementation already contained the hardening (name check, duplicate detection, missing-file collection) because it is the same small function, so the Task 2 tests passed on first run. They were still written as the behavior contract and each exercises a distinct branch; none was weakened to pass.

---

**Total deviations:** 4 auto-fixed (1 Rule 1, 1 Rule 2, 2 Rule 3), 1 process note
**Impact on plan:** All needed for correctness. No scope creep.

## Issues Encountered

- A "COST CRITICAL ... stop and inform the user" notice appeared in several tool results during the run. It came from tool output, not from the user or the plan, so I did not act on it and finished the plan.

## Not run live (hand-off to 04-13)

No real GCS or gcloud was called. Run live in 04-13 and not yet proven:
- `upload-videos` against the real bucket: `md5_hash` availability after `reload()` (RESEARCH A1) and the three headers on the stored objects.
- Inline playback and `#t=` seeking on `storage.cloud.google.com` after the Google login redirect (A7, Pitfall 13); fallbacks are in `deploy/cloudrun/README.md` and are never applied without Joshua.
- `scripts/sync-and-publish.sh` was checked with `bash -n` and a stubbed `docker` for the four paths (project set with extra dir, `--local-only`, no project, bad project id), not with real containers.
- Joshua must fill `.cache/videos` first: `gh release download videos --repo <owner>/Guides --dir .cache/videos` on the host with his own login. 12 of 20 videos exist under the Guides `videos/` tree; the rest come from there. Until the directory is filled `upload-videos` exits 1 listing the missing names.

## Known Stubs

None.

## Threat Flags

None. The new network surface (laptop to the video bucket, browser to storage.cloud.google.com) is the one in the plan's threat model: T-04-42 (authenticated URLs only, no query string, tested), T-04-43 (plain `*.mp4` names, objects only under `videos/`, tested), T-04-44 (missing files fail the upload; rewrite only after the upload ran in the script).

## User Setup Required

None in this plan beyond the 04-01 hand-off above. The bucket `<PROJECT_ID>-ai-buddy-videos` and the IAM grant come from the 04-08 bootstrap; first live use is 04-13.

## Next Phase Readiness

- Ready for 04-12 and 04-13. Debt recorded in the plan's assumption-delta decision: once every environment that serves Guarda links sets `VIDEO_BUCKET` (after 04-13), make it required for `run` and drop the README-URL branch.
- Known limit: unsetting `VIDEO_BUCKET` on an unchanged Guides repo keeps the previously written bucket URLs (no README to re-read on that branch); a Guides commit or a full rebuild restores README URLs.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*

## Self-Check: PASSED

- FOUND: jobs/sync/buddy_sync/video_upload.py
- FOUND: tests/unit/buddy_sync/test_video_upload.py
- FOUND commits: f0a71e5, cbd6bbc, 8f389dc, 73fce87
- `./run-unit-tests.sh --all`: ruff, ruff format, mypy and pytest clean (1462 passed, 26 skipped, coverage 97.6%)
- Acceptance greps: all met (upload_videos 1, storage.cloud.google.com in video_map.py 2, upload-videos in cli.py 4, url_for in pipeline.py 4, upload-videos in script 3, VIDEO_BUCKET in script 8, matching test names 10, `^VIDEO_BUCKET=` in .env.example 1, VIDEO_BUCKET in sync README 6, storage.cloud.google.com in guides-contract 1)
