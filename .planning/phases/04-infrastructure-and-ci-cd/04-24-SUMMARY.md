---
phase: 04-infrastructure-and-ci-cd
plan: 24
subsystem: infra
tags: [credentials, gcloud, service-account, impersonation, access-token, bootstrap, gap-closure, wr-03]
status: complete

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: pinned dependency tree (04-18); exact IAM binding set and bootstrap (04-17); traffic guard in sync-and-publish.sh (04-22)
provides:
  - "buddy_core.gcs_bucket.token_file_client_factory(token_file, project): storage client from a token file, read at first use, names-only errors"
  - "publish and upload-videos select the token-file client when GCS_ACCESS_TOKEN_FILE is set; unset keeps ADC; an injected factory still wins"
  - "sync-and-publish.sh: no ADC mount; a one-hour sa-publisher token minted before upload-videos and again before publish, mounted read-only as /run/gcs-token"
  - "Revision step on a one-hour owner token (--access-token-file, throwaway CLOUDSDK_CONFIG); ~/.config/gcloud mounted only into the two token-minting containers of the digest-pinned gcloud image"
  - "bootstrap.sh: sa-publisher with objectAdmin on the index and videos buckets only; owner gets serviceAccountTokenCreator on it and loses both bucket objectAdmin bindings"
  - "Runbook: credentials of the laptop publish, one-time bootstrap re-run"
affects: [04-26]

actuals:
  tokens: 9000
  tasks: 2
  commits: 6

plan_head_before: e8eea2a090c54dc1bd0f70b1eb8f8cd064f89ed8
plan_head_after: b8e8fbbb5f035656cf79ca322454b0a32d62bd00

tech-stack:
  added: []
  patterns:
    - "The credential choice stays inside the GcsBucket client factory (Adapter); publish and upload code is unchanged"
    - "Tokens minted per step in a mode-700 temp dir, removed by an EXIT trap, mounted read-only, never printed"

key-files:
  created: []
  modified:
    - packages/buddy_core/buddy_core/gcs_bucket.py
    - jobs/sync/buddy_sync/cli.py
    - scripts/sync-and-publish.sh
    - deploy/cloudrun/bootstrap.sh
    - deploy/cloudrun/README.md
    - tests/unit/buddy_core/test_gcs_bucket.py
    - tests/unit/buddy_sync/test_cli.py
    - tests/unit/test_cloudrun_yaml.py
    - tests/unit/test_sync_and_publish_script.py

key-decisions:
  - "An injected bucket factory wins over the token file, which wins over plain GcsBucket (ADC): tests and laptop-less runs are unchanged"
  - "The gcloud image is pinned to sha256:808708b26bdf6705e2b42ed48ab53ad4abe0ce171ec8e78074669d28f5cb8dcc (docker buildx imagetools inspect google/cloud-sdk:592.0.0-emulators, 2026-11-15)"
  - "Owner bucket objectAdmin bindings are removed from bootstrap.sh only; removing them on the live project is left to 04-26 with the owner's go-ahead"
  - "google.oauth2.credentials.Credentials is untyped under mypy strict: a single inline type-ignore on that call instead of a module-wide override (an override on the defining module does not affect the caller)"

patterns-established:
  - "Static script tests join docker run continuation lines and check every container's mounts"

requirements-completed: []

coverage:
  - id: D1
    description: "Token-file storage client: token read at first use, whitespace stripped, missing or empty file is a names-only BucketError"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/buddy_core/test_gcs_bucket.py#test_token_file_factory_reads_the_token_at_first_use"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_core/test_gcs_bucket.py#test_missing_or_empty_token_file_is_a_names_only_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "publish and upload-videos build their bucket from GCS_ACCESS_TOKEN_FILE when set; unset and injected factories keep prior behaviour"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_publish_uses_the_token_file_when_set"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_cli.py#test_upload_videos_uses_the_token_file_when_set"
        status: pass
    human_judgment: false
  - id: D3
    description: "Script: only the two minting containers mount the gcloud login; sync image gets a read-only publisher token; revision step uses an owner token file; image pinned by digest; token dir private and removed on exit"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_sync_and_publish_script.py#test_sync_image_never_receives_the_gcloud_config"
        status: pass
      - kind: unit
        ref: "tests/unit/test_sync_and_publish_script.py#test_revision_step_runs_with_an_access_token_file"
        status: pass
    human_judgment: false
  - id: D4
    description: "bootstrap.sh creates sa-publisher with objectAdmin on the two buckets and grants the owner Token Creator; exact binding set pinned"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_bootstrap_binds_exactly_these_roles"
        status: pass
    human_judgment: false
  - id: D5
    description: "Impersonated token minting works from the mounted owner config inside the cloud-sdk image, and an upload fits the one-hour token life"
    requirement: "INFRA-04"
    verification: []
    human_judgment: true
    rationale: "Needs the live project and a bootstrap re-run; planned for 04-26 (flagged assumption [Medium])"
---

# Phase 4 Plan 24: Short-lived publisher tokens instead of the owner's ADC Summary

**The sync image receives only a one-hour access token of a bucket-only service account (`sa-publisher`); the owner's refresh token stays in the digest-pinned gcloud image, and the forced revision runs on a one-hour owner token without the gcloud config.**

## Performance

- **Tasks:** 2 (1 tracer, 1 auto, both TDD)
- **Files modified:** 9
- **Commits:** 6 (measured from `plan_head_before`)

## Accomplishments

- `token_file_client_factory` builds `storage.Client(project, credentials=Credentials(token))` from a file read at call time; a missing, unreadable or empty file raises `BucketError` naming `GCS_ACCESS_TOKEN_FILE` only.
- `PublishSettings` and `VideoUploadSettings` gain `gcs_access_token_file` and `google_cloud_project`; `_select_bucket_factory` picks injected, then token file, then ADC.
- `sync-and-publish.sh` drops `ADC_FILE` and `GOOGLE_APPLICATION_CREDENTIALS`; `mint_publisher_token` runs before upload-videos and before publish; `mint_owner_token` runs before the describe step; `GCLOUD` uses `--access-token-file=/run/owner-token` and `CLOUDSDK_CONFIG=/tmp/gcloud`.
- `bootstrap.sh`: `SA_PUB`/`SA_PUB_EMAIL`, in the creation loop; objectAdmin for it on both buckets; owner has `roles/iam.serviceAccountTokenCreator` on it and keeps videos `objectViewer` and project `run.developer`; the owner's two `objectAdmin` lines are gone. `_EXPECTED_BIND_CALLS` updated in the same commit.
- Runbook: resource table, Roles paragraph, "Credentials of the laptop publish" with the one-time bootstrap re-run.

## Task Commits

1. Task 1 (tracer) RED: `3dfda56` test(04-24): failing tests for the token-file storage client
2. Task 1 GREEN: `8a3ba22` feat(04-24): storage client from a token file; `7feca28` feat(04-24): per-step sa-publisher token in the script
3. Task 2 RED: `562dccd` test(04-24): failing tests for the config-free revision step
4. Task 2 GREEN: `9f9e79b` feat(04-24): revision step on an owner access token, image pinned by digest; `b8e8fbb` feat(04-24): sa-publisher and owner off bucket admin

Tracer gate: `./run-unit-tests.sh --all` passed after Task 1 before expansion.

## TDD Gate Compliance

- RED (`3dfda56`): a stub `token_file_client_factory` raising `NotImplementedError` was committed with the tests so the target tests fail on their assertions, not on an import error. Observed: 5 failures in `test_gcs_bucket.py` (the token-file tests) and 2 in `test_cli.py` (publish and upload-videos use the token file). Semantic assessment: the failures are the planned behaviour assertions. `gsd_run check tdd-red-evidence` was not run: pytest console output is not one of its supported report formats.
- RED (`562dccd`): `test_sync_image_never_receives_the_gcloud_config` and `test_revision_step_runs_with_an_access_token_file` failed on the assertions for the old `GCLOUD` array.
- Bootstrap part: per the orchestrator note, `_EXPECTED_BIND_CALLS` and the new bootstrap tests were changed in the same commit as `bootstrap.sh` (`b8e8fbb`). Run locally before the script change, `test_bootstrap_binds_exactly_these_roles` and `test_bootstrap_creates_sa_publisher_and_keeps_the_owner_off_bucket_admin` failed; no separate RED commit exists for that part.

## Decisions Made

See `key-decisions` above. The image digest recorded for the SUMMARY (plan requirement): `google/cloud-sdk:592.0.0-emulators@sha256:808708b26bdf6705e2b42ed48ab53ad4abe0ce171ec8e78074669d28f5cb8dcc`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy strict rejected `Credentials(token=...)` as an untyped call**
- **Found during:** Task 1 (`./run-unit-tests.sh --all`)
- **Fix:** an inline `# type: ignore[no-untyped-call]` on that one call. A `pyproject.toml` override for `google.oauth2.credentials` was tried first and did not help (the flag applies to the calling module), so it was reverted; `pyproject.toml` is unchanged.
- **Files modified:** packages/buddy_core/buddy_core/gcs_bucket.py
- **Commit:** 8a3ba22

**2. [Rule 3 - Blocking] A RED test line exceeded the ruff line limit**
- **Found during:** Task 1 verification (the RED commit hook does not run ruff)
- **Fix:** split the line in `test_gcs_bucket.py`; the same fix was committed with the GREEN commit.
- **Commit:** 8a3ba22

**Total deviations:** 2 auto-fixed (both Rule 3). **Impact:** none on behaviour.

## Issues Encountered

None beyond the deviations.

## Known Stubs

None. The RED-commit stub in `gcs_bucket.py` was replaced in `8a3ba22`.

## Threat Flags

None. T-04-75 to T-04-77 are mitigated as planned: the sync image gets only a one-hour sa-publisher token; token files sit in a mode-700 directory with mode-600 files, an EXIT trap and read-only mounts, covered by `test_token_files_live_in_a_private_directory_removed_on_exit_and_are_never_printed`; sa-publisher has objectAdmin on two buckets and no project role (`test_bootstrap_creates_sa_publisher_and_keeps_the_owner_off_bucket_admin`).

## Authentication Gates

None. Nothing was run against the live project: no bootstrap run, no IAM change, no deploy, no push.

## Next Phase Readiness

04-26 must, on the live project: re-run `bootstrap.sh` once (creates `sa-publisher` and its bindings), confirm `gcloud auth print-access-token --impersonate-service-account` works from the mounted owner config in the pinned image, run one real publish on the new token, and, with the owner's go-ahead, remove the owner's old bucket `objectAdmin` bindings.

## Verification

- `./run-unit-tests.sh --all`: 1563 passed, 26 skipped (local-only), coverage 97.61%; ruff and mypy strict clean.
- `bash -n` on `scripts/sync-and-publish.sh` and `deploy/cloudrun/bootstrap.sh`: pass.
- Acceptance: non-comment `ADC_FILE` count 0; `GCS_ACCESS_TOKEN_FILE` in the script 3 (at least 2); `token_file_client_factory` defined; `sa-publisher` in bootstrap 4; `access-token-file` in the script 1; README names `sa-publisher` and `serviceAccountTokenCreator`.

## Self-Check: PASSED

All six commit hashes are ancestors of HEAD; the modified files exist; `commits: 6` measured from the ledger.
