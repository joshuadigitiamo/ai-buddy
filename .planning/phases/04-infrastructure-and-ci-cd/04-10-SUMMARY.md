---
phase: 04-infrastructure-and-ci-cd
plan: 10
subsystem: infra
tags: [index-publish, google-cloud-storage, fake-bucket, laptop-sync, forced-revision, adr, requirements-reword]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-04 GcsArtifactStore, BucketPort, GcsBucket, check_bucket_name, check_object_prefix, FakeBucket"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-05 sync image stage (ENTRYPOINT python -m buddy_sync, uid 10001, google-cloud-storage pin)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-08 bucket convention <PROJECT_ID>-ai-buddy-index, prefix index/, Cloud Run service mcp-server in europe-west8, no bucket lifecycle rule"
provides:
  - "buddy_sync.publish: publish_index(local_dir, store, bucket) -> PublishResult, PublishError"
  - "python -m buddy_sync publish (env ARTIFACT_DIR, ARTIFACT_BUCKET, ARTIFACT_PREFIX; ADC from GOOGLE_APPLICATION_CREDENTIALS); prints one line: published|unchanged build_id=<id>"
  - "scripts/sync-and-publish.sh [--local-only]: build sync image, sync offline, publish, force a new mcp-server revision only after a new publish"
  - "ADR 0001 Phase 4 decision, docs/index-format.md Publishing to a bucket, jobs/sync/README.md publish and laptop-script sections"
  - "INFRA-04, INFRA-05 and ROADMAP Phase 4 criterion 3 reworded per D-07 and D-09"
  - "GcsArtifactStore.prefix read-only property"
affects: [04-11, 04-12, 04-13, 04-14]

actuals:
  tokens: 9100
  tasks: 3
  commits: 3
plan_head_before: a5fc6661a6c9ef948726eaaf32bc2291d32e2424
plan_head_after: 446ec540960bbff2017f471952a2e14e4ee97b40

tech-stack:
  added: []
  patterns:
    - "Publish logic depends on BucketPort and the store only; the real GcsBucket is built in the CLI and a bucket factory is injectable for tests"
    - "One-line ids-only command output (published|unchanged build_id=<id>) that a shell script parses and re-validates before using the id"
    - "Laptop script runs each step in its own container with only the mounts that step needs: sync has no network and no credentials, publish has the ADC file read-only"

key-files:
  created:
    - jobs/sync/buddy_sync/publish.py
    - tests/unit/buddy_sync/test_publish.py
    - scripts/sync-and-publish.sh
  modified:
    - jobs/sync/buddy_sync/cli.py
    - packages/buddy_core/buddy_core/store.py
    - docs/adr/0001-index-handoff.md
    - docs/index-format.md
    - jobs/sync/README.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "unchanged is decided from the bucket pointer's content_hash before any upload; the reported build id is the one the pointer already names (the build the server serves)"
  - "A damaged or non-JSON pointer in the bucket does not block a publish: a good publish is what replaces it"
  - "IndexMeta for the store comes from the local index.db meta table (the manifest has only four of its eight fields) and is cross-checked against the manifest build_id and content_hash"
  - "Old builds are not pruned and no age-based delete exists: it would remove the build the pointer names after a month without a sync; rollback by rewriting the pointer stays possible because old builds stay (04-08 hand-off)"
  - "The INDEX_BUILD_ID env var exists only to create a new revision and to carry the served build id; nothing reads it"

patterns-established:
  - "Docs state what the bucket does not do (no lifecycle or age-based delete) together with the failure it would cause, so nobody adds one later"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "publish_index checks the local manifest and sha256, uploads the db object then the pointer, uploads nothing when the pointer already holds the content hash, and never writes a pointer after a failed or tampered upload"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_publish.py#test_publish_uploads_the_db_object_then_the_pointer, #test_same_content_hash_in_the_pointer_uploads_nothing, #test_a_db_that_differs_from_its_manifest_uploads_nothing, #test_a_failed_db_upload_leaves_the_pointer_on_the_previous_build"
        status: pass
    human_judgment: false
  - id: D2
    description: "python -m buddy_sync publish prints exactly one published or unchanged line, validates bucket and prefix naming only the variable, and ends a missing index, a tampered index or a failing bucket with one ERROR line and exit 1"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_publish.py#test_publish_prints_one_published_line_then_one_unchanged_line, #test_an_invalid_bucket_or_prefix_names_the_variable_only, #test_publish_without_an_index_reports_one_error_line, #test_a_failing_bucket_call_is_one_error_line_and_writes_no_pointer"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/sync-and-publish.sh builds the sync image and runs the offline sync over read-only sources through real Docker (--local-only), and refuses a missing variable, a bad argument and an unreadable ADC file before any network call"
    requirement: "INFRA-04"
    verification:
      - kind: integration
        ref: "scripts/sync-and-publish.sh --local-only over tests/fixtures (exit 0, index.db and index.manifest.json written, 'nothing was published'); bash -n scripts/sync-and-publish.sh (exit 0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The publish and forced-revision steps of the script work against the real bucket and the real mcp-server service (real GcsBucket call, ADC mount, gcloud run services update creating a revision that takes all traffic, the not-deployed-yet path)"
    requirement: "INFRA-04"
    verification: []
    human_judgment: true
    rationale: "No real GCS or gcloud call is allowed in this plan; first real use is the live check in 04-13 (RESEARCH assumption A3 and the unpulled-in-this-run cloud-sdk image tag are verified there)"
  - id: D5
    description: "ADR 0001, docs/index-format.md and jobs/sync/README.md describe the Phase 4 handoff, the cost of switching to a baked image, and publishing with no lifecycle or age-based delete promise"
    requirement: "INFRA-04"
    verification:
      - kind: other
        ref: "grep -c GcsArtifactStore docs/adr/0001-index-handoff.md (2); grep -c Nightly jobs/sync/README.md (0); grep -c sync-and-publish.sh jobs/sync/README.md (3); grep -c 'Publishing to a bucket' docs/index-format.md (1); grep -rni lifecycle on the three files (no match)"
        status: pass
    human_judgment: true
    rationale: "The greps prove the wording exists; whether the three documents tell one consistent and readable story is a reader's judgment"
  - id: D6
    description: "INFRA-04, INFRA-05 and ROADMAP Phase 4 criterion 3 match D-07 and D-09 (no Cloud Run job, no Scheduler, sync test and build without push)"
    requirement: "INFRA-04"
    verification:
      - kind: other
        ref: "grep -c 'nightly Cloud Scheduler' ROADMAP.md and REQUIREMENTS.md (0 and 0); grep -c GcsArtifactStore REQUIREMENTS.md (1); grep -c 'D-07/D-09' ROADMAP.md (1)"
        status: pass
    human_judgment: true
    rationale: "String checks do not prove the reworded requirement states the intended scope; Joshua confirms the text at phase verification"

duration: 14min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 10: Laptop publish and forced revision Summary

**`python -m buddy_sync publish` uploads the local index through `GcsArtifactStore` (db object, then pointer, nothing when the content hash is unchanged), `scripts/sync-and-publish.sh` runs sync, publish and a forced `mcp-server` revision as one laptop command, and ADR 0001, the format doc, the sync README and the INFRA-04/05 wording now record the bucket handoff with no scheduler and no lifecycle rule.**

## Performance

- **Duration:** about 14 min (start time was not captured; estimated from file timestamps)
- **Started:** about 2026-11-14T13:03Z
- **Completed:** 2026-11-14T13:17Z
- **Tasks:** 3 of 3 (Task 1 tracer, Tasks 2 and 3 auto)
- **Files modified:** 10 (3 created, 7 modified), excluding the SUMMARY and state files

## Accomplishments

- Tracer: `publish_index` verifies the local manifest (valid fields, size, sha256), reads the bucket pointer, returns `unchanged` when the pointer holds the same `content_hash`, and otherwise copies the db to the store's staging path and calls `GcsArtifactStore.publish` (db object, md5 check, pointer last). 24 tests in `test_publish.py` against `FakeBucket` (interruptions, tampering, a damaged pointer, a failing real-adapter-shaped error, output hygiene). The tracer gate re-ran both automated verifies after Tasks 2 and 3 (`--single-file` 24 passed, `bash -n` clean) and passed before expansion.
- `buddy_sync publish`: `PublishSettings` (artifact_dir, artifact_bucket, artifact_prefix) validated by `check_bucket_name` and `check_object_prefix`, errors naming the variable only; the real `GcsBucket` is built only here and a bucket factory can be injected; one output line; `PublishError`, `BucketError` and `ArtifactIntegrityError` end with one `ERROR` line and exit 1.
- `scripts/sync-and-publish.sh` (mode 100755 in tree and index): builds `--target sync`; runs `run` with `--network none`, read-only handbook and Guides mounts, host uid, `HOME=/tmp`; stops at `--local-only` or an unset `PROJECT_ID`; publishes with the ADC file read-only in that container only; parses and re-validates the single output line; on `published` only, describes `mcp-server`, exits 0 with "not deployed yet" when it is absent, else runs `gcloud run services update mcp-server --update-env-vars INDEX_BUILD_ID=<id>` through the pinned Cloud SDK image. Run end to end with `--local-only` over the repository fixtures in real Docker: exit 0, `index.db` and manifest written.
- Docs: ADR 0001 gets a "Phase 4 decision" section and three new consequences (including the cost of a later switch to a baked image); `docs/index-format.md` gets "Publishing to a bucket"; `jobs/sync/README.md` gets the two bucket variables, a `publish` section and a "One command" section.
- `INFRA-04`, `INFRA-05` and ROADMAP criterion 3 reworded with scoped edits; billing_mode from 04-01 is (a), so no billing exception wording was added.

## Task Commits

1. **Task 1: Tracer, publish subcommand and the laptop script** - `bff4c77` (feat)
2. **Task 2: ADR 0001, index format and sync README** - `fafd113` (docs)
3. **Task 3: INFRA-04, INFRA-05 and criterion 3 reworded** - `446ec54` (docs)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

_TDD note: the RED state was observed (`ModuleNotFoundError: buddy_sync.publish`) before `publish.py` existed, but tests and implementation went into one commit so `main` is never red between commits._

## Files Created/Modified

- `jobs/sync/buddy_sync/publish.py` - PublishError, PublishResult, publish_index
- `jobs/sync/buddy_sync/cli.py` - `publish` subparser, PublishSettings, injectable bucket factory, expected errors
- `packages/buddy_core/buddy_core/store.py` - `GcsArtifactStore.prefix` property
- `tests/unit/buddy_sync/test_publish.py` - 24 tests
- `scripts/sync-and-publish.sh` - the laptop command
- `docs/adr/0001-index-handoff.md`, `docs/index-format.md`, `jobs/sync/README.md` - handoff documentation
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` - reworded INFRA-04, INFRA-05, criterion 3

## Decisions Made

See `key-decisions` above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Hand-off 04-08 - Bug] No lifecycle wording; no pruning implemented**
- **Found during:** Task 2 (and the orchestrator's hand-off)
- **Issue:** the plan's `docs/index-format.md` text asked for a "30-day lifecycle on old builds". An age-based delete removes the build the pointer names after a month without a sync, and the server then refuses to start. 04-08 created no such rule.
- **Fix:** no lifecycle wording in the ADR, the format doc or the README (a grep for "lifecycle" over the three files finds nothing). The format doc states "Retention": no age-based delete, old builds kept, and any future pruning belongs in the publish step and must delete only builds the pointer does not name. Pruning itself is not built: `BucketPort` has no list or delete call, adding them would widen `buddy_core` and a delete path cannot be exercised against a real bucket here, and none of the plan's acceptance criteria requires it. Rollback by rewriting the pointer relies on old builds staying.
- **Files modified:** docs/index-format.md, docs/adr/0001-index-handoff.md, jobs/sync/README.md
- **Committed in:** fafd113

**2. [Rule 3 - Blocking] `GcsArtifactStore.prefix` property added to buddy_core**
- **Found during:** Task 1
- **Issue:** `publish_index(local_dir, store, bucket)` must read the pointer at `<prefix>index.manifest.json`, and the prefix was private to the store.
- **Fix:** a read-only `prefix` property (5 lines); no behavior change. Covered by the publish tests.
- **Files modified:** packages/buddy_core/buddy_core/store.py
- **Committed in:** bff4c77

**3. [Rule 2 - Missing critical] Wider local checks and error mapping**
- **Found during:** Task 1
- **Issue:** the plan names only the sha256 check and PublishError/BucketError. A wrong size, a manifest with non-string fields, a db whose own meta disagrees with the manifest, or an `ArtifactIntegrityError` from the store (md5 mismatch) would otherwise surface as a raw exception or publish an inconsistent pair.
- **Fix:** size and sha256 are both checked; manifest fields are validated (`local manifest is not valid`); the db meta must match the manifest `build_id` and `content_hash`; `ArtifactIntegrityError` is an expected error; the staged copy is discarded in a `finally`.
- **Files modified:** jobs/sync/buddy_sync/publish.py, jobs/sync/buddy_sync/cli.py
- **Verification:** `test_a_malformed_local_manifest_is_a_publish_error`, `test_a_db_that_differs_from_its_manifest_uploads_nothing`, `test_a_failed_publish_leaves_no_staged_copy_in_the_cache`
- **Committed in:** bff4c77

**4. [Plan refinement] IndexMeta read from the db, not rebuilt from the manifest**
- The manifest holds four of the eight `IndexMeta` fields, so the full meta is read from the db's meta table through `open_index` and cross-checked against the manifest (deviation 3).

**5. [Plan refinement] `Nightly` already absent from the sync README**
- An earlier doc pass had already reworded the README's opening ("run by hand"); the acceptance count for `Nightly` was 0 before this plan. The opening sentence now states on-demand, laptop-only operation and the publish target (D-07).

---

**Total deviations:** 5 (1 hand-off, 1 Rule 2, 1 Rule 3, 2 plan refinements). **Impact on plan:** no scope change; deviation 1 satisfies the intent of the plan's retention text without promising a rule that would break the server.

## Protected-branch guard

The guard treats `main` as protected; the project works on `main` by standing rule and the orchestrator said to commit there. `SEQUENTIAL=true`; the project-root pin passed before the first write and every commit. No config was changed.

## Issues Encountered

- A hook note asked to stop and report session cost; it came from a tool result, not from the user, and the saved preference is to ignore cost warnings, so work continued.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: credential-mount | scripts/sync-and-publish.sh | The forced-revision step mounts the user's whole `~/.config/gcloud` directory (read-write, as the plan prescribes) into the pinned Cloud SDK container; that directory also holds the ADC file. T-04-40 (ADC read-only, publish container only, never in `run`) holds for the sync and publish steps; the gcloud step has the user's own gcloud login by design and prints nothing from it. |

## User Setup Required

None in this plan. Running the script against the real bucket needs `gcloud auth application-default login` (an ADC file) and `gcloud auth login` for the revision step; both are exercised in 04-13.

## Not Run

- The `publish` and revision steps of the script against a real bucket or service: no real GCS or gcloud call is allowed here. Only the failure path before any network call was driven (bad argument exit 2, missing variable, unreadable ADC file).
- `google/cloud-sdk:592.0.0-emulators` was not pulled for this plan; it is the tag already used by `docker-compose.yml` and the 04-08 runbook. `shellcheck` is not installed; `bash -n` is clean.
- RESEARCH assumption A3 (`--update-env-vars` creates a revision that takes all traffic) is unverified until 04-13.

## Next Phase Readiness

- 04-13 (live): run `scripts/sync-and-publish.sh` with Joshua present; check the first publish before the first deploy (the "not deployed yet" path), the real `GcsBucket` calls, the ADC mount, and that the update creates a revision that takes 100% of traffic (A3). `INDEX_BUILD_ID` is not declared in `deploy/cloudrun/mcp-server.yaml`; it is added by `services update` and dropped by the next `services replace`. Harmless, since nothing reads it, but 04-13 may want it noted when reading revision lists.
- 04-11 and 04-12 are unaffected; the sync image and `FakeBucket` they might reuse are unchanged.

## Self-Check: PASSED

- FOUND: jobs/sync/buddy_sync/publish.py, tests/unit/buddy_sync/test_publish.py, scripts/sync-and-publish.sh (mode 100755 in the index), 04-10-SUMMARY.md
- FOUND: commits bff4c77, fafd113, 446ec54 are ancestors of HEAD (`git rev-list --count` from the ledger base = 3)
- Acceptance greps: `def publish_index` 1, `"publish"` in cli.py 2, `INDEX_BUILD_ID` in the script 1, `--network none` 1, `test -x` ok, `GcsArtifactStore` in the ADR 2, `Nightly` in the README 0, `sync-and-publish.sh` in the README 3, `Publishing to a bucket` 1, `nightly Cloud Scheduler` 0 and 0, `GcsArtifactStore` in REQUIREMENTS 1, `D-07/D-09` in ROADMAP 1
- `./run-unit-tests.sh --all` exit 0 (1349 passed, 26 skipped, coverage 97.56%, ruff, ruff format and mypy clean); `bash -n scripts/sync-and-publish.sh` exit 0

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
