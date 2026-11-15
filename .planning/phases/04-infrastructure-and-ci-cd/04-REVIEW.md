---
phase: 04-infrastructure-and-ci-cd
reviewed: 2026-11-15T14:00:00Z
depth: standard
files_reviewed: 84
files_reviewed_list:
  - .env.example
  - .github/dependabot.yml
  - .github/workflows/_deploy.yml
  - .github/workflows/_test.yml
  - .github/workflows/chat-bot.yml
  - .github/workflows/mcp-server.yml
  - .github/workflows/meridian.yml
  - .github/workflows/sync.yml
  - .github/workflows/tests.yml
  - Dockerfile
  - deploy/cloudrun/bootstrap.sh
  - deploy/cloudrun/chat-bot.yaml
  - deploy/cloudrun/mcp-server.yaml
  - deploy/compose/stub_llm.py
  - deploy/k8s/base/chat-bot.yaml
  - deploy/k8s/base/emulators.yaml
  - deploy/k8s/base/kustomization.yaml
  - deploy/k8s/base/mcp-server.yaml
  - deploy/k8s/base/pubsub-init.yaml
  - deploy/k8s/kind-config.yaml
  - deploy/k8s/overlays/dev/artifacts-hostpath.yaml
  - deploy/k8s/overlays/dev/kustomization.yaml
  - deploy/k8s/overlays/dev/local-env.yaml
  - deploy/k8s/overlays/dev/namespace.yaml
  - deploy/meridian.version
  - docker-compose.yml
  - jobs/sync/buddy_sync/cli.py
  - jobs/sync/buddy_sync/config.py
  - jobs/sync/buddy_sync/coverage.py
  - jobs/sync/buddy_sync/pipeline.py
  - jobs/sync/buddy_sync/publish.py
  - jobs/sync/buddy_sync/video_map.py
  - jobs/sync/buddy_sync/video_upload.py
  - jobs/sync/requirements.txt
  - packages/buddy_core/buddy_core/gcs_bucket.py
  - packages/buddy_core/buddy_core/store.py
  - pyproject.toml
  - requirements-dev.txt
  - run-unit-tests.sh
  - scripts/compose-smoke.sh
  - scripts/kind-smoke.sh
  - scripts/kind-up.sh
  - scripts/render-cloudrun.sh
  - scripts/sync-and-publish.sh
  - scripts/sync-image-smoke.sh
  - scripts/validate-infra.sh
  - services/chat_bot/buddy_bot/chat_api.py
  - services/chat_bot/buddy_bot/cli.py
  - services/chat_bot/buddy_bot/config.py
  - services/mcp_server/buddy_mcp/cli.py
  - services/mcp_server/buddy_mcp/config.py
  - services/mcp_server/buddy_mcp/server.py
  - services/mcp_server/buddy_mcp/snapshot.py
  - services/mcp_server/requirements.txt
  - tests/integration/test_bot_process.py
  - tests/integration/test_server_process.py
  - tests/unit/buddy_core/conftest.py
  - tests/unit/buddy_core/test_gcs_bucket.py
  - tests/unit/buddy_core/test_gcs_store.py
  - tests/unit/buddy_sync/test_config.py
  - tests/unit/buddy_sync/test_publish.py
  - tests/unit/buddy_sync/test_video_coverage.py
  - tests/unit/buddy_sync/test_video_map.py
  - tests/unit/buddy_sync/test_video_upload.py
  - tests/unit/chat_bot/conftest.py
  - tests/unit/chat_bot/test_chat_api.py
  - tests/unit/chat_bot/test_config.py
  - tests/unit/chat_bot/test_llm_client.py
  - tests/unit/chat_bot/test_main.py
  - tests/unit/chat_bot/test_readme_contract.py
  - tests/unit/mcp_server/conftest.py
  - tests/unit/mcp_server/test_auth_mode.py
  - tests/unit/mcp_server/test_config.py
  - tests/unit/mcp_server/test_gap_tool.py
  - tests/unit/mcp_server/test_http_transport.py
  - tests/unit/mcp_server/test_main.py
  - tests/unit/mcp_server/test_snapshot.py
  - tests/unit/test_cloudrun_yaml.py
  - tests/unit/test_compose.py
  - tests/unit/test_dockerfile_stages.py
  - tests/unit/test_k8s_manifests.py
  - tests/unit/test_repo_layout.py
  - tests/unit/test_stub_llm.py
  - tests/unit/test_workflows.py
findings:
  critical: 0
  warning: 9
  info: 9
  total: 18
  necessity: 1
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-11-15T14:00:00Z
**Depth:** standard
**Files Reviewed:** 84
**Status:** issues_found

## Summary

All 84 files in scope were read, with the product source, infra and scripts read in full. The 29 test files were read selectively: workflow, Cloud Run, bootstrap and store fixtures, plus a scan of skip markers. The necessity rubric was read and applied.

The Phase 4 foundations are sound.
- The GCS artifact store validates the pointer, the object name, the size and the sha256, and uploads the pointer last.
- The render script refuses unsafe substitution values.
- Workflows pin every action by commit, drop default token permissions, use no `secrets` context, and bind WIF to a repository id plus `refs/heads/main`.
- Repo scan: no project id, project number or key material is tracked outside `.planning`.

I found no Critical issues. The nine warnings are mostly about CI/CD behaviour, supply-chain exposure and the owner's credentials:
- the Mask step prints the very identifiers it masks;
- the Meridian build races the chat-bot deploy;
- the owner's full ADC is mounted into containers built from unpinned dependency trees;
- one phantom guard is now live-wrong.

Findings that duplicate known gaps in `04-VERIFICATION.md` are not repeated:
- bootstrap `run.developer` (gap 7)
- same-commit re-run creates no revision (gap 6)
- the README Fernet key row (gap 8)
- the missing `#t=` fragment (gap 9)
- no digest, `--no-traffic` stage, base-image pin, cache or scan (gaps 1 to 5)

Where a new finding touches one of those, the gap number is cited. The gaps' own suggested fixes are not repeated here.

Not verified: I could not fetch the Actions logs (`gh run view --log` returned nothing), so WR-01 rests on documented GitHub Actions log behaviour, not on observing a live log. Confidence is Medium.

## Warnings

### WR-01: The "mask the identifiers" step prints them in the public log before it masks

**File:** `.github/workflows/_deploy.yml:50-62` (same pattern at `.github/workflows/meridian.yml:106-117`)
**Issue:** The step receives `GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_DEPLOYER_SA`, `GCP_WIF_PROVIDER` and `GCP_OAUTH_CLIENT_ID` through `env:`. GitHub prints a `run` step's expanded `env:` block in the step header before the script runs. Repository variables (`vars.*`) are not registered secrets, so nothing masks them at that moment. The `::add-mask::` calls only affect output produced after they run. The header comment of `_deploy.yml` states that masking happens "before the first step that could print them", but the masking step is itself the first step that prints them. The repository is public (CLAUDE project rule: no ids in public). Any other way to read `vars.*` into a step has the same problem, and `tests/unit/test_workflows.py::test_no_github_secrets_context_and_no_key_file_anywhere` forbids the one mechanism (`secrets.*`) that is masked at registration.
**Fix:** Either accept that ids appear in logs and drop the false claim, or store the five values as repository secrets (auto-masked) and relax the test to allow `secrets.GCP_*` only. If you keep `vars`, make the masking step load the values without placing them in its own header. For example, pass the whole set as one secret, `GCP_IDS_JSON`, and `::add-mask::` each field with `jq`. Then check one live log for the project-number pattern. Count only, do not print.

### WR-02: A Meridian version bump deploys chat-bot before its image is guaranteed to exist

**File:** `.github/workflows/chat-bot.yml:21`, `.github/workflows/meridian.yml:61-64`, `.github/workflows/_deploy.yml:75-87`
**Issue:** `deploy/meridian.version` is in the path filter of both `chat-bot.yml` and `meridian.yml`. Both workflows start on the same push, with different concurrency groups (`deploy-chat-bot`, `deploy-meridian`) and no ordering between them. The chat-bot deploy fails fast if the `meridian:<sha>` image is missing. The Meridian build waits for the `unit` and `validate` test jobs and then builds a full Node image. The chat-bot deploy waits for the same test jobs and then reaches the existence check. On a version bump the check will often win the race and fail with "run the meridian workflow". That is the one change this repo makes to the Max-login sidecar, and it needs a manual rerun each time.
**Fix:** Make the chat-bot workflow wait for Meridian when the version file changed. Options:
- chain it with `workflow_run` on `meridian`;
- make the meridian job a `needs:` of the chat-bot deploy;
- have the check step poll for the image for a few minutes before it fails.

### WR-03: The owner's full ADC is mounted into containers whose dependency tree is unpinned

**File:** `scripts/sync-and-publish.sh:115-122`, `161-170`, `189`; `Dockerfile:73`
**Issue:** `upload-videos` and `publish` run in the `sync` image with `-v "${ADC_FILE}:/adc.json:ro"`, and the revision step mounts the whole `~/.config/gcloud` directory read-write into `google/cloud-sdk`. The ADC file holds the owner's long-lived refresh token with the default cloud-platform scope. The owner holds project-level IAM (bootstrap gives `run.developer`, bucket admin and more, and the live deployer is `run.admin`). The `sync` image installs `pip install -r requirements.txt -r jobs/sync/requirements.txt`, which pins only the top-level packages (see WR-04). A compromised or malicious transitive release would run with network access and exfiltrate a refresh token that can act as the project owner. The comment "mounted into this container only" describes the blast radius within the host, not its reach.
**Fix:** Give these containers a short-lived, narrow token instead of the refresh token, for example:
- `gcloud auth print-access-token --impersonate-service-account=<publisher-sa>` on the host, passed as `GOOGLE_OAUTH_ACCESS_TOKEN` (or `CLOUDSDK_AUTH_ACCESS_TOKEN` for the gcloud container);
- a dedicated `sa-publisher` account with only `objectAdmin` on the index and videos buckets.
Do not mount `~/.config/gcloud` for the revision step; pass the token and a throwaway `CLOUDSDK_CONFIG`.

### WR-04: Runtime images install unpinned transitive dependencies

**File:** `Dockerfile:16`, `28`, `47`, `73`; `requirements.txt`, `services/*/requirements.txt`, `jobs/sync/requirements.txt`
**Issue:** The requirement files pin top-level packages with `==`, but no constraint or lock file pins what they pull in (grpcio, protobuf, starlette, uvicorn, httpx, cryptography and others). Two builds of the same commit can ship different dependency versions. A CI "green" test image and the deployed image can differ. The deploy image is built separately from the test image, so the tested code and the shipped code do not share one dependency set. The pin test `test_sync_requirements_are_pinned_and_agree_with_the_other_files` only checks the pinned top level. This is not gap 3 (base image digest); that gap covers the `FROM` line only.
**Fix:** Generate a fully pinned lock with hashes (`pip-compile --generate-hashes` or `uv pip compile`) per stage, install with `--require-hashes`, and have the test stage install the same lock plus the dev tools.

### WR-05: CI path filters leave tested files outside every workflow

**File:** `.github/workflows/tests.yml:199-209` (and the service workflows' path lists)
**Issue:** Files that tests read and assert on trigger no workflow when changed alone:
- `deploy/cloudrun/bootstrap.sh`
- `deploy/cloudrun/README.md`
- `.env.example` (`run-unit-tests.sh` loads it as the test env file when `.env` is absent)
- `.dockerignore` (pinned by `test_dockerignore_keeps_private_paths_out_of_the_build_context`)
- `.github/dependabot.yml`

`tests.yml` lists `tests/**`, `scripts/**` and `deploy/k8s/**` but not `deploy/cloudrun/**` outside the two service YAMLs. A commit that fixes gap 7 by editing only `bootstrap.sh` and its pin test would still run the tests, because `tests/**` changes. A commit that edits only `bootstrap.sh` or the README, such as the gap 8 runbook fix, runs nothing and breaks the pinned test silently.
**Fix:** Add `deploy/cloudrun/**`, `.env.example`, `.dockerignore` and `.github/dependabot.yml` to `tests.yml` paths, and extend `test_test_only_workflow_covers_the_files_no_service_image_copies` with those paths.

### WR-06: The README tells the operator to deploy an image tag CI never pushes

**File:** `deploy/cloudrun/README.md:144`
**Issue:** The "Render and deploy" block exports `IMAGE_TAG="$(git rev-parse --short HEAD)"  # the tag CI pushed`. `_deploy.yml:105,112` tags and renders the full 40-character `github.sha`. A manual render and `replace` with the short tag points the service at an image that does not exist, and the revision fails to start. This is the documented manual-recovery path used after the failed `mcp-server-00001` revision (gap 6), so it is likely to be run.
**Fix:** Use `export IMAGE_TAG="$(git rev-parse HEAD)"`, and add a README contract test that compares this line with the tag expression in `_deploy.yml`.

### WR-07: `publish` reports "unchanged" without checking that the db object still exists

**File:** `jobs/sync/buddy_sync/publish.py:304-308`
**Issue:** If the bucket pointer's `content_hash` equals the local manifest's, `publish_index` returns `unchanged` and uploads nothing. It reads only the pointer, never the `index-<build_id>.db` object it names. If that object is deleted or corrupted (a manual cleanup, or the "prune old builds" step the README mentions), the pointer stays and the server refuses to start with "index object named by the pointer is missing". `sync-and-publish.sh:179-183` then exits 0 and forces no revision. A fix cannot be made by re-running the command; the operator must change content to force a re-upload.
**Fix:** Before returning `unchanged`, verify the object: `bucket.md5_base64(store.prefix + object_name) == local md5`. If it is missing or different, fall through and re-upload the db object, then rewrite the pointer.

### WR-08: A local-only run keeps video links that point at the private bucket

**File:** `jobs/sync/buddy_sync/pipeline.py:106-118`
**Issue:** When the Guides commit is unchanged, `videos = previous.video_links()`. `rewrite_links` runs only when `url_for` is set. The comment says VIDEO_BUCKET may have changed, but only the "bucket set, set to another" case is handled. After a published run, `--local-only` (or a run with no `PROJECT_ID`) leaves `VIDEO_BUCKET=""`, so `url_for` is `None` and the previous bucket URLs are copied forward unchanged. `sync-and-publish.sh:95-96` and the T-04-44 note say no local index link may point at the video bucket when no upload ran. The reverse direction (README, then bucket) does rewrite correctly.
**Fix:** When `url_for is None` and the previous links are not README URLs, re-resolve them from the README instead of keeping them. The simplest correct change is to set `rebuilt=True` for the video step whenever the previous index's video host differs from the requested one, or to run `resolve_video_links(..., url_for=None)` whenever `settings.video_bucket` is unset.

### WR-09: Phantom requirement, the `GCP_PROJECT_ID != ''` job guard now hides failures

**File:** `.github/workflows/_deploy.yml:38` (also `.github/workflows/meridian.yml:81`)
**Category:** necessity
**Issue:** The guard exists so a push made "before the bootstrap in 04-13" runs the tests and stops without an auth error (`_deploy.yml:14-15`). That requirement has lapsed: 04-13 is complete, and `04-VERIFICATION.md` records every live deploy as WIF-authenticated with the variables set. The guard now has the opposite effect. If the variable is deleted, renamed or unset (for example when the variables are re-keyed after WR-01), the deploy job is skipped, the workflow stays green, and no deploy happens. Nobody is told that the pipeline stopped deploying.
**Fix:** Remove the `if:` from both jobs. Optionally add a first step that fails with `::error::GCP_PROJECT_ID is not set` when the variable is empty.

## Info

### IN-01: `.dockerignore` is narrower than `.gitignore`

**File:** `.dockerignore:1-9`
**Issue:** `.env`, `.cache/` and `artifacts/` are anchored to the build-context root, and `*.db` is not listed at all. `.gitignore` uses unanchored `.env` and `*.db`. Runtime stages `COPY` whole directories (`services/mcp_server`, `packages/buddy_core`, `jobs/sync`), so a stray `services/mcp_server/.env` or an `index.db` under `jobs/sync` would be baked into a laptop-built image. CI builds from a clean checkout, so the exposure is local builds only.
**Fix:** Add `**/.env`, `**/*.db`, `**/.cache`, `.planning/`, `tests/` and `.github/`, and extend the pinned test.

### IN-02: Rendering `mcp-server` requires variables only `chat-bot` uses

**File:** `scripts/render-cloudrun.sh:315-325`
**Issue:** The fixed `VARIABLES` list is required for every service. `CHAT_JWT_ISSUER_EMAIL`, `VIDEO_THUMBNAIL_URL`, `HELP_COMMAND_ID` and `MERIDIAN_TAG` are unused by `mcp-server.yaml`, so deploying the server fails when a chat-only variable is unset. `IMAGE_TAG` is also never checked for a valid tag form.
**Fix:** Keep a per-service variable list. Check `IMAGE_TAG` against `^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$`.

### IN-03: IAM breadth in `bootstrap.sh`, and a pin test that matches substrings

**File:** `deploy/cloudrun/bootstrap.sh:166,172,173,178-179`; `tests/unit/test_cloudrun_yaml.py:388-435`
**Issue:**
- Both runtime accounts get project-wide `roles/datastore.user`. The MCP server can read and write `thread_memory` and the bot can write `oauth_state`, although each needs only its own collections.
- `sa-chat-bot` has `objectUser` on the Max-login bucket. The README and YAML say it is mounted "in the Meridian container only", but a Cloud Run service account belongs to the whole instance, so the chat-bot container can read the same bucket through the metadata server.
- The owner gets `objectViewer` and `objectAdmin` on the videos bucket; the first is implied by the second.
- The bootstrap tests assert text with `in script`. A change that comments a line out, or binds a role in the wrong function, still passes.

**Fix:** Scope Firestore with an IAM condition on the collection, or accept and document it. Reword the isolation claim to "separate mount", not "separate access". Drop the redundant viewer binding. Pin roles by asserting the exact `bind_*` calls with a regex.

### IN-04: `assert` as a runtime guard, and recording names reset on restart

**File:** `services/chat_bot/buddy_bot/cli.py:112`; `services/chat_bot/buddy_bot/chat_api.py:103,114-115`
**Issue:** `_build_chat_api` relies on `assert settings.chat_record_path is not None`. Under `python -O` the assert is stripped and `RecordingChatApi(None)` fails later with an `AttributeError` at the first message. `BotSettings` enforces the rule already, so this is a type-narrowing aid only; a plain `if ... is None: raise` is safer. `RecordingChatApi._created` restarts at 0 with each process, so two runs append duplicate `rec-1` names to the same JSON-lines file. Local use only.
**Fix:** Use an explicit raise. Seed the counter from the existing line count, or add a short random run id to the name.

### IN-05: `kind-up.sh` edge cases

**File:** `scripts/kind-up.sh:51,69-72,77`
**Issue:**
- An existing cluster is reused without checking that its node mount equals the requested `ARTIFACTS_DIR`, so changing the variable has no effect and no warning.
- The download is hard-wired to `kind-linux-amd64`.
- `${template//__ARTIFACTS_DIR__/${ARTIFACTS_DIR}}` treats `&` in the replacement as the matched text under bash 5.2 (`patsub_replacement`), so a path containing `&` renders a wrong mount.

**Fix:** Warn or fail when the cluster exists and the mounts differ. Use `uname -m` to select the asset. Replace with `sed` using an escaped value, or `shopt -u patsub_replacement`.

### IN-06: Compose `meridian` can start without an API key; the infra validator mounts the repo read-write

**File:** `docker-compose.yml:198`; `scripts/validate-infra.sh:366`
**Issue:**
- `MERIDIAN_API_KEY: ${MERIDIAN_API_KEY:-}` lets the `meridian` service start with an empty key. It then serves the Max login unauthenticated on the compose network, while `chat-bot-live` is the one that refuses to start. The compose comment explains why `:?` cannot be used here.
- `validate-infra.sh` mounts the repository `-v "${ROOT_DIR}:/repo"` read-write into the actionlint image.

**Fix:** Start Meridian through a `command` wrapper that exits when the key is empty. Mount the repo `:ro` for actionlint.

### IN-07: The Fernet key is not validated at config time

**File:** `services/mcp_server/buddy_mcp/config.py:76,172`
**Issue:** `oauth_storage_encryption_key` is only checked for presence. A non-Fernet value (the exact failure behind gap 8) fails later inside `build_oauth_storage` as a generic expected error, after the index has been downloaded. The validation error that names the variable never fires.
**Fix:** Add a validator that builds `Fernet(value)` and raises `ValueError("OAUTH_STORAGE_ENCRYPTION_KEY must be a Fernet key")` without echoing the value, in the same validator that checks the signing key length.

### IN-08: Dependabot watches only GitHub Actions

**File:** `.github/dependabot.yml:1-8`
**Issue:** Python pins (`pip`) and base images (`docker`) have no update PRs, so the pins in `requirements*.txt` and the `FROM python:3.12-slim` line age silently. Gap 3's suggested fix mentions a docker ecosystem entry; the `pip` ecosystem is not mentioned anywhere.
**Fix:** Add `pip` (directories `/`, `/services/mcp_server`, `/services/chat_bot`, `/jobs/sync`) and `docker` entries, and extend `test_dependabot_bumps_the_pinned_actions_weekly`.

### IN-09: The chat-bot pod has no probe in kind

**File:** `deploy/k8s/base/chat-bot.yaml:133-178`
**Issue:** Only the Meridian sidecar has start-up, readiness and liveness probes. The `chat-bot` container, which runs the Pub/Sub intake, has none, so a hung bot is reported Ready and is never restarted. The in-cluster smoke checks the pod Ready condition and so never exercises it.
**Fix:** Add an exec liveness probe, for example a short Python check of the process or a file heartbeat, or note in the manifest comment that kind deliberately omits it.

---

_Reviewed: 2026-11-15T14:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
