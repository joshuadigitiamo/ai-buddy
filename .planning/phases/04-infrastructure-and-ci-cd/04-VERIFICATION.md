---
phase: 04-infrastructure-and-ci-cd
verified: 2026-11-15T13:00:00Z
status: gaps_found
score: 4/5 must-haves verified
covered_files:
  - .github/workflows/_deploy.yml
  - .github/workflows/mcp-server.yml
  - .planning/phases/04-infrastructure-and-ci-cd/04-01-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-01-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-02-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-02-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-03-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-03-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-04-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-04-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-05-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-05-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-06-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-06-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-07-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-07-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-08-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-08-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-09-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-09-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-10-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-10-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-11-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-11-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-12-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-12-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-13-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-13-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-14-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-14-SUMMARY.md
  - Dockerfile
  - deploy/cloudrun/README.md
  - deploy/cloudrun/bootstrap.sh
  - deploy/cloudrun/chat-bot.yaml
  - deploy/cloudrun/mcp-server.yaml
  - docker-compose.yml
  - packages/buddy_core/buddy_core/models.py
covered_digest: "v4:sha256:6ec624867f687c31106bed0b021bb40518b036b953a113e70080acf8b3711784"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Guide videos play inline from access-controlled hosting and the Guarda button opens at the section's timestamp (ROADMAP SC5)"
    status: partial
    reason: "Live check 10: the video plays inline from the private bucket, but from 0:00. The opened URL carries no #t= fragment, although buddy_core builds one. The fragment is lost in the Chat button or in the storage.cloud.google.com redirect. Coverage part of SC5 is met (708/2524 scene-mapped, baseline 238)."
    artifacts:
      - path: "packages/buddy_core/buddy_core/models.py"
        issue: "line 91 appends #t=<seconds>; the live click path drops it"
      - path: "services/chat_bot/buddy_bot"
        issue: "chat card Guarda button URL; confirm the fragment survives into the button"
    missing:
      - "Find where the fragment is lost (card button vs. storage.cloud.google.com redirect)"
      - "Apply the RESEARCH Pitfall 13 fallback (for example a small HTML player page, or a query-parameter offset) so the Guarda button opens at the section offset"
      - "Re-run live check 10 and record the result"
  - truth: "Cloud Run deploy definition and bootstrap are reproducible from the repository (INFRA-04, INFRA-05)"
    status: failed
    reason: "deploy/cloudrun/bootstrap.sh line 162 still grants the ci-deployer role run.developer. Both committed YAMLs set the invoker-iam-disabled annotation, and a run.developer deployer cannot set it (error: run.services.setIamPolicy required). Live was fixed by hand to run.admin, so repo and live have drifted: a fresh bootstrap yields a deployer that cannot deploy the committed YAML. The README (line 221) documents the failure but the script is unchanged."
    artifacts:
      - path: "deploy/cloudrun/bootstrap.sh"
        issue: "line 162: bind_project ci-deployer roles/run.developer"
    missing:
      - "Bind a role that can set invoker-iam-disabled (run.admin, or a narrower custom role with run.services.setIamPolicy) in bootstrap.sh"
      - "Update README line 221 and add a test that pins the role"
  - truth: "A pipeline re-run recovers a failed deploy (INFRA-05 deploy reliability)"
    status: failed
    reason: "_deploy.yml tags and renders the image as github.sha. A re-run on the same commit renders an identical service spec, so gcloud run services replace creates no new revision; the failed revision mcp-server-00001 kept the old secret and was recovered by hand with --revision-suffix."
    artifacts:
      - path: ".github/workflows/_deploy.yml"
        issue: "no per-run revision identity (suffix or run id) in the rendered spec"
    missing:
      - "Make each run produce a new revision (for example a revision suffix from github.run_id and run_attempt, or deploy by image digest)"
  - truth: "Runbook secrets table is correct for the server (INFRA-04 runbook)"
    status: failed
    reason: "deploy/cloudrun/README.md line 81 says oauth-storage-encryption-key is 'random, never reused'. The server needs a Fernet key; a plain random value made mcp-server exit(1) on start (OAUTH_STORAGE_ENCRYPTION_KEY is not a valid Fernet key)."
    artifacts:
      - path: "deploy/cloudrun/README.md"
        issue: "line 81 wrong key format"
    missing:
      - "State Fernet key format and the generation command in the secrets table"
  - truth: "Deploy by image digest, not by the github.sha tag (CICD_GUIDE section 21) - 04-13 gap 1"
    status: partial
    reason: "OUTSIDE THE WRITTEN REQUIREMENTS. INFRA-05 asks for build, push, deploy and WIF; it does not name digest pinning, and CICD_GUIDE is not in the phase's Guides-applied list. Kept as hardening for the gap plan. _deploy.yml deploys ...:${github.sha}."
    artifacts:
      - path: ".github/workflows/_deploy.yml"
        issue: "tag, not digest"
    missing:
      - "Capture the digest from build-push-action output and render the image as name@digest (can be combined with gap on re-run revisions)"
  - truth: "Smoke test before traffic: deploy --no-traffic, check, then switch (CICD_GUIDE sections 20, 28) - 04-13 gap 2"
    status: partial
    reason: "OUTSIDE THE WRITTEN REQUIREMENTS (hardening). The post-deploy check in _deploy.yml runs after the new revision already holds 100% of traffic; a bad revision is live before it is checked."
    artifacts:
      - path: ".github/workflows/_deploy.yml"
        issue: "check after full traffic, no --no-traffic stage"
    missing:
      - "Deploy with --no-traffic and a revision tag, run the checks against the tagged URL, then move traffic (note: COVERAGE.md currently records traffic splitting and tags as OPT-OUT; update it if adopted)"
  - truth: "Base image pinned by digest (CICD_GUIDE section 28) - 04-13 gap 3"
    status: partial
    reason: "OUTSIDE THE WRITTEN REQUIREMENTS (hardening). Dockerfile lines 1, 20, 38 and 61 use FROM python:3.12-slim, a moving tag. INFRA-01 requires Python 3.12 only."
    artifacts:
      - path: "Dockerfile"
        issue: "four FROM lines on a moving tag"
    missing:
      - "Pin python:3.12-slim by digest and let dependabot (docker ecosystem) bump it"
  - truth: "Docker layer cache in CI (CICD_GUIDE section 8) - 04-13 gap 4"
    status: partial
    reason: "OUTSIDE THE WRITTEN REQUIREMENTS (performance). build-push-action in _deploy.yml and meridian.yml has no cache-from/cache-to; every build is cold."
    artifacts:
      - path: ".github/workflows/_deploy.yml"
        issue: "no cache-from/cache-to"
      - path: ".github/workflows/meridian.yml"
        issue: "no cache-from/cache-to"
    missing:
      - "Add a buildx cache (type=gha or registry) to both build steps"
  - truth: "Image scan and SBOM (CICD_GUIDE section 16) - 04-13 gap 5"
    status: partial
    reason: "OUTSIDE THE WRITTEN REQUIREMENTS (hardening). No scan or SBOM step exists in any workflow (grep for trivy, sbom, provenance finds nothing in .github/workflows)."
    artifacts:
      - path: ".github/workflows/_deploy.yml"
        issue: "no scan or SBOM step"
    missing:
      - "Add an image scan (fail on high/critical) and SBOM attestation before the deploy step"
deferred:
  - truth: "LLM evaluation gate in CI (CICD_GUIDE section 23)"
    addressed_in: "Phase 5"
    evidence: "Phase 5 goal and success criterion 5: the gate command prints PASS only when correctness-with-citation >= 90%, invented policies 0, empty-context test passes"
behavior_unverified_items: []
human_verification:
  - test: "Cold start after about 20 minutes idle (live check 6)"
    expected: "First Chat message after idle gets its placeholder, and the final answer, within the ~30 s window or as an asynchronous follow-up, with both services at zero instances"
    why_human: "Needs the live Cloud Run services at zero instances; only one post-deploy measurement exists (about 17 s bot + about 8 s mcp-server, both cold)"
  - test: "Meridian token across a refresh (live check 12)"
    expected: "After Meridian refreshes its own login, answers still work on the next revision without reseeding the claude bucket"
    why_human: "Needs a real token expiry; only three consecutive revisions seeded once were seen"
---

# Phase 4: Infrastructure and CI/CD Verification Report

**Phase Goal:** The whole system runs from per-service Docker images locally (compose), on kind, and as Cloud Run definitions, built and deployed by path-filtered CI without stored keys.
**Verified:** 2026-11-15
**Status:** gaps_found
**Re-verification:** No, initial verification

The goal itself is largely achieved: the system runs from compose, on kind, and live on Cloud Run through keyless CI. Four things block a clean pass: the Guarda timestamp (a stated success criterion), the repo-versus-live drift in the deployer role, the same-commit re-run that creates no revision, and a wrong runbook key format. Five more items from the 04-13 gap table are CI hardening that is outside the written requirements.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` starts mcp_server, chat_bot and the sync job from per-service images with both emulators; a Pub/Sub chat event completes a round trip | VERIFIED | `docker-compose.yml` defines firestore, pubsub, pubsub-init, sync, mcp-server, chat-bot with depends_on health conditions. I ran `scripts/compose-smoke.sh` myself: exit 0, "round trip ok" (legacy DM fixture published to the Pub/Sub emulator, final answer received). |
| 2 | Kustomize dev overlay on kind brings services up; health check and one MCP tool call succeed in-cluster; base and overlays pass validation | VERIFIED | `deploy/k8s/base`, `overlays/dev`, `kind-up.sh`, `kind-smoke.sh` exist. I ran `scripts/validate-infra.sh` (kustomize, kubeconform, actionlint, sync image build): exit 0, "infra validation ok". In-cluster smoke ("kind smoke ok", SMOKE_PROBE_OK) is from the 04-13 offline gate; I did not re-run kind (needs a cluster). |
| 3 | Cloud Run YAMLs for mcp_server and chat_bot target europe-west8, scale to zero, request-based billing; GcsArtifactStore wired; sync runs from laptop and forces a new revision; no Scheduler or Cloud Run job | VERIFIED | `deploy/cloudrun/mcp-server.yaml`: minScale 0, ARTIFACT_STORE gcs, ARTIFACT_BUCKET, no cpu-throttling annotation (request-based), europe-west8 image and URL. `chat-bot.yaml`: minScale 0 and GCS FUSE volume for the Meridian credentials. `scripts/sync-and-publish.sh`: sync, publish (pointer last), then forced revision. Live check 11 passed (forced revision `mcp-server-00005`, answer cited the new revision date). Check 9: TTL ACTIVE on `gaps` and `thread_memory`. No Scheduler or Cloud Run job file exists. |
| 4 | Change under `services/mcp_server` triggers only that service's workflow; it runs `run-unit-tests.sh --all`, blocks image push on failure; on success pushes to Artifact Registry and deploys through WIF with no key in repo or secrets | VERIFIED | `mcp-server.yml` path filter (service, buddy_core, requirements, Dockerfile, its YAML, render script, workflow files); `test` job calls `_test.yml` (`./run-unit-tests.sh --all`); `deploy` has `needs: test`. `_deploy.yml` authenticates with `google-github-actions/auth` via `workload_identity_provider` and `service_account`; `grep` for credentials_json, GOOGLE_APPLICATION_CREDENTIALS, private_key and `secrets.` in `.github` finds nothing; no key file is tracked. `sync.yml` builds without push; `meridian.yml` builds only from `deploy/meridian.version`. Live check 1: every deploy authenticated through WIF. `tests/unit/test_workflows.py` guards path drift. |
| 5 | Guide videos play inline from access-controlled hosting and the Guarda button opens at the section's timestamp; coverage improved beyond 238/2524 | FAILED (partial) | Inline playback from the private bucket: live check 10, passed. Coverage: 708/2524 scene-mapped, published index equals projection (04-14), above 238. Timestamp: not met. The video opens from 0:00 and the URL has no `#t=` fragment. `models.py:91` builds `#t=<seconds>`, so the loss happens after the URL is built (button or redirect). See gap 1. |

**Score:** 4/5 truths verified. Behavior-unverified: 0 (the two live items below are runtime observations needing a human, not code-presence checks).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Dockerfile` | stages `mcp_server`, `chat_bot`, `sync` on Python 3.12, non-root | VERIFIED | `USER 10001`, one runtime stage per service; `tests/unit/test_dockerfile_stages.py` guards COPY sources |
| `docker-compose.yml` | all services plus emulators | VERIFIED | round trip run by me |
| `deploy/k8s/**` | Kustomize base and dev overlay | VERIFIED | validated by `validate-infra.sh` |
| `deploy/cloudrun/*.yaml`, `scripts/render-cloudrun.sh` | templates, render with no placeholder left | VERIFIED | live deploy used them; 04-13 rendered both with no `${` left |
| `deploy/cloudrun/bootstrap.sh` | reproducible project bootstrap | STUB-LEVEL DRIFT | runs, but binds `run.developer` (gap 2) |
| `.github/workflows/{_test,_deploy,mcp-server,chat-bot,sync,meridian,tests}.yml` | path-filtered, test-gated, keyless | VERIFIED | read in full for `_test`, `_deploy`, `mcp-server`, `sync`; `meridian` top half |
| `packages/buddy_core/buddy_core/gcs_bucket.py`, `store.py` | GcsArtifactStore | VERIFIED | live service reads the index from the bucket (check 3, 11) |
| `scripts/sync-and-publish.sh` | laptop publish and forced revision | VERIFIED | live check 11 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mcp-server.yml` test job | `_deploy.yml` deploy job | `needs: test` | WIRED | push cannot start on a red test job |
| `_deploy.yml` | Artifact Registry and Cloud Run | WIF token, `docker/login-action`, `gcloud run services replace` | WIRED | live runs green |
| `_deploy.yml` | `scripts/render-cloudrun.sh` | env vars from repository variables | WIRED | live runs green |
| `sync-and-publish.sh` | running `mcp-server` | `services update` forced revision after publish | WIRED | live check 11 |
| `models.py` video link (`#t=`) | Chat card Guarda button | button URL | NOT_WIRED end to end | live: fragment absent in the opened URL (gap 1) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| mcp-server answers | index.db | GCS bucket via `GcsArtifactStore` (pointer then db, sha256 check) | Yes (live: handbook page cited with revision date after publish) | FLOWING |
| Guarda button | video URL with `#t=` | `models.py` plus video map | URL built, offset lost at click | HOLLOW at the last hop (gap 1) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite, ruff, ruff format, mypy, coverage | `./run-unit-tests.sh --all` | 1475 passed, 26 skipped, exit 0 (the skips are local-only live-artifact tests) | PASS |
| Static infra validation | `scripts/validate-infra.sh` | "infra validation ok", exit 0 | PASS |
| Compose round trip | `scripts/compose-smoke.sh` | "round trip ok", exit 0 | PASS |
| Image scan, SBOM, cache, digest, no-traffic in workflows | grep `.github/workflows` | none found | ABSENT (gaps 5 to 9 below) |

### Probe Execution

Step 7c: no `probe-*.sh` files exist and the plans declare none. SKIPPED. `compose-smoke.sh` and `validate-infra.sh` were run as the phase's own runnable checks (above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-01 | 04-02, 04-03, 04-04, 04-05, 04-06 | One Dockerfile per service on Python 3.12, same image in compose, kind, Cloud Run | SATISFIED | Dockerfile stages; compose, kind and Cloud Run all build from them |
| INFRA-02 | 04-03, 04-06 | compose with emulators and local round trip | SATISFIED | compose-smoke run by me |
| INFRA-03 | 04-02, 04-07 | kind manifests with Kustomize and validation | SATISFIED | validate-infra run by me; kind smoke from 04-13 |
| INFRA-04 | 04-01, 04-04, 04-08, 04-10 | Cloud Run YAMLs, GcsArtifactStore, laptop publish and forced revision | PARTIAL | Deployed and working live. Bootstrap role drift (gap 2), wrong secrets table (gap 4); the SC5 video part belongs to 04-11, 04-12, 04-14 (INFRA-04 coverage entries). |
| INFRA-05 | 04-09 | path-filtered build, push, deploy; Meridian from approved commit; WIF | PARTIAL | Everything stated is met and live. Re-run does not recover a failed deploy (gap 3). Gaps 5 to 9 are hardening outside the requirement text. |
| INFRA-06 | 04-09 | CI runs `run-unit-tests.sh --all` before any image push | SATISFIED | `_test.yml` runs the script; every deploy job has `needs: test`. Note: no branch-protection setting was verified, so "required check" rests on `needs`, which is what blocks the push. |

Orphaned requirements: none. REQUIREMENTS.md maps exactly INFRA-01 to INFRA-06 to Phase 4 and every ID appears in at least one plan's `requirements` field. SYNC-07 is closed by 04-04 (not a Phase 4 ID).

Bookkeeping: REQUIREMENTS.md still shows INFRA-04, INFRA-05 and INFRA-06 as Pending and unchecked; ROADMAP.md header says "12/14 plans executed" while both plan lists show 14 checked. Update after the gap plans close.

### Disposition of the 9 gaps from 04-13

| # | Gap | In phase requirements? | Where recorded |
|---|-----|------------------------|----------------|
| 1 | Deploy by digest | No: outside INFRA-05 text; hardening (CICD_GUIDE not a Phase 4 Guides-applied) | gaps (partial) |
| 2 | Smoke test before traffic | No: hardening | gaps (partial) |
| 3 | Base image digest pin | No: hardening (INFRA-01 asks Python 3.12 only) | gaps (partial) |
| 4 | Docker layer cache | No: performance | gaps (partial) |
| 5 | Image scan and SBOM | No: hardening | gaps (partial) |
| 6 | Re-run creates no revision | Yes, INFRA-05 deploy reliability | gaps (failed) |
| 7 | bootstrap grants run.developer | Yes, INFRA-04 and INFRA-05 reproducibility | gaps (failed) |
| 8 | README key format | Yes, INFRA-04 runbook | gaps (failed) |
| 9 | Guarda loses `#t=` | Yes, ROADMAP SC5 | gaps (partial) |

The status is `gaps_found` because gaps 6 to 9 are inside the phase. Gaps 1 to 5 alone would not block, and are listed so the gap plan can take them or the maintainer can defer them. Live checks 7 (claude.ai connector, blocked by org ownership) and 8 (non-digitiamo rejection) were removed by the user's decision and are recorded here, not counted as gaps. Their offline coverage stays in the unit tests (`tests/unit/mcp_server/test_auth.py`). Consequence to note: the MCP OAuth login on Cloud Run has no live evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `deploy/cloudrun/bootstrap.sh` | 162 | role too weak for the committed YAML | Blocker (gap 2) | fresh bootstrap cannot deploy |
| `deploy/cloudrun/README.md` | 81 | wrong secret format | Warning (gap 4) | first deploy exits on start |
| `.github/workflows/_deploy.yml` | image tag and replace | same-commit re-run is a no-op | Warning (gap 3) | manual recovery |

Debt-marker scan (TBD, FIXME, XXX) was not run over every modified file. I did not detect any in the files read. Confidence: Medium.

### Human Verification Required

1. **Cold start after idle (live check 6).** Test: leave both services idle about 20 minutes, send one Chat message. Expected: placeholder and answer within the window. Why human: needs live services at zero instances.
2. **Meridian token across a refresh (live check 12).** Test: after Meridian refreshes its login, send a message on a later revision. Expected: still answers without reseeding the bucket. Why human: needs a real token expiry.

These do not change the status (gaps_found takes precedence); they are recorded for the end-of-phase UAT.

### Gaps Summary

The infrastructure works: 1475 tests pass, static validation passes, the compose round trip passes when run by me, and the 04-13 record shows both services live from europe-west8 through keyless CI with a cited answer in Chat. What is not achieved: (1) the Guarda button still opens at 0:00, so SC5 is only partly met; (2) bootstrap.sh would recreate a deployer that cannot deploy the committed YAML (live was hand-patched); (3) a re-run on the same commit does not create a new revision; (4) the runbook gives the wrong key format. Group 2 and 4 are bootstrap and runbook fixes with a pinning test. Group 3 and the digest and no-traffic items share a root cause (revision identity in `_deploy.yml`) and fit one plan. Items 5 to 9 of the guide-hardening list are optional for this phase's requirements.

Suggested plans for `/gsd-plan-phase 4 --gaps`: (a) Guarda offset (investigate then fix, re-run live check 10); (b) bootstrap role plus README key format plus tests; (c) `_deploy.yml` revision identity and optional digest and no-traffic staging; (d) optional hardening: base image digest, layer cache, scan and SBOM.

---

_Verified: 2026-11-15_
_Verifier: Claude (gsd-verifier)_
