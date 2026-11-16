---
phase: 04-infrastructure-and-ci-cd
verified: 2026-11-16T23:30:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .dockerignore
  - .github/dependabot.yml
  - .github/workflows/_deploy.yml
  - .github/workflows/_test.yml
  - .github/workflows/chat-bot.yml
  - .github/workflows/mcp-server.yml
  - .github/workflows/meridian.yml
  - .github/workflows/sync.yml
  - .github/workflows/tests.yml
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
  - .planning/phases/04-infrastructure-and-ci-cd/04-15-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-15-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-16-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-16-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-17-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-17-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-18-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-18-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-19-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-19-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-20-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-20-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-21-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-21-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-22-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-22-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-23-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-23-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-24-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-24-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-25-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-25-SUMMARY.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-26-PLAN.md
  - .planning/phases/04-infrastructure-and-ci-cd/04-26-SUMMARY.md
  - Dockerfile
  - deploy/cloudrun/README.md
  - deploy/cloudrun/bootstrap.sh
  - deploy/cloudrun/chat-bot.yaml
  - deploy/cloudrun/mcp-server.yaml
  - docker-compose.yml
  - jobs/sync/buddy_sync/publish.py
  - packages/buddy_core/buddy_core/gcs_bucket.py
  - packages/buddy_core/buddy_core/models.py
  - scripts/render-cloudrun.sh
  - scripts/serving_revision.py
  - scripts/sync-and-publish.sh
  - services/chat_bot/buddy_bot/workflow.py
  - services/mcp_server/buddy_mcp/config.py
  - tests/unit/chat_bot/test_guarda_offset_path.py
  - tests/unit/test_cloudrun_yaml.py
  - tests/unit/test_deploy_pipeline.py
  - tests/unit/test_workflows.py
covered_digest: "v4:sha256:cc10e0937733ca8fdf13dcc8d4fccd8732bc27036868826d5b8523cd4251bc22"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Guarda button opens at the section's timestamp (ROADMAP SC5)"
    - "Cloud Run deploy definition and bootstrap are reproducible from the repository (bootstrap binds run.admin)"
    - "A pipeline re-run recovers a failed deploy (per-run revision name)"
    - "Runbook secrets table is correct for the server (Fernet key)"
    - "Deploy by image digest"
    - "Smoke test before traffic (0% candidate tag, checks, then traffic switch)"
    - "Base image pinned by digest"
    - "Docker layer cache in CI"
    - "Image scan and SBOM"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "LLM evaluation gate in CI (CICD_GUIDE section 23)"
    addressed_in: "Phase 5"
    evidence: "Phase 5 goal and success criterion 5: the gate command prints PASS only when correctness-with-citation >= 90%, invented policies 0, empty-context test passes"
advisory:
  - finding: "The bot logs nothing when the reformulate LLM call fails: services/chat_bot/buddy_bot/workflow.py lines 102-104 catch LlmError and return the error reply without a log line, so the Meridian logout in 04-26 left no error in Cloud Run logs"
    category: other
    reason: "Observability debt in Phase 3 code. The file was not changed since the previous verification and no phase-4 criterion or INFRA requirement covers bot error logging. Resolved by logging the error type (no question text, BOT-11) at that catch"
    evidence_status: "none provided (no failing test; behaviour read in code)"
  - finding: "Cold start exceeds Chat's ~30 s HTTP limit: 55.7 s measured (04-26), Chat shows 'AI Buddy non risponde' on the first message after idle while the answer still arrives in the thread"
    category: other
    reason: "Accepted by the user on 2026-11-16 (no minScale 1, free-hosting goal). No phase-4 criterion sets a latency bound; SC3 requires scale to zero, which causes this. Backlog: profile the ~25 s between Meridian ready and bot start"
    evidence_status: "live measurement in 04-26 Gaps; user decision recorded there"
human_verification:
  - test: "Meridian credentials durability on Cloud Run (live check 12, decision D-12). After the 2026-11-16 re-seed, leave the chat-bot running across at least one Claude token expiry (and one new chat-bot revision), then ask one question in Chat."
    expected: "The answer arrives without re-seeding the credentials bucket; the Meridian container logs no 'loggedIn: false'. If this fails again, decide between accepting manual re-seeding (record an override on D-12 and add a health signal) or opening a fix plan for the refresh chain."
    why_human: "Needs a real token expiry on the live service. The only live observation so far is negative: 04-26 found the login lost on new instances and fixed it by re-seeding; the cause is not proven. The committed volume is read-write and owned by uid 1000 (chat-bot.yaml), so the code shows no defect that explains it."
---

# Phase 4: Infrastructure and CI/CD Verification Report

**Phase Goal:** The whole system runs from per-service Docker images locally (compose), on kind, and as Cloud Run definitions, built and deployed by path-filtered CI without stored keys.
**Verified:** 2026-11-16
**Status:** human_needed
**Re-verification:** Yes, after gap closure (plans 04-15 to 04-26)

All five success criteria and all nine previous gaps are verified in the code at HEAD. Every non-planning file at HEAD is identical to commit `cf7e7c3`, and the tests, mcp-server and chat-bot workflows on that commit are green on GitHub Actions (`gh run list`). One item stays open for a human: the Meridian login on Cloud Run was lost once (04-26) and was restored by hand. No success criterion names credential durability, so this item does not block a criterion. It does contradict locked decision D-12 ("token refreshes ... persist across restarts. Seeded once"). The status is therefore human_needed, not passed.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` starts mcp_server, chat_bot and the sync job from per-service images with both emulators; a Pub/Sub chat event completes a round trip | VERIFIED | Regression check: I ran `scripts/compose-smoke.sh` on HEAD. Exit 0, "round trip ok". The Dockerfile changed in the gap round (lock files, base digest, zlib1g pin); the smoke run used the changed Dockerfile. |
| 2 | Kustomize dev overlay on kind brings services up; health check and one MCP tool call succeed in-cluster; base and overlays pass validation | VERIFIED | `_test.yml` job `validate` runs `scripts/validate-infra.sh` (kustomize, kubeconform, actionlint, sync image build), and the tests workflow on `cf7e7c3` is green. 04-26 offline gate: validate-infra exit 0. The in-cluster kind smoke dates from 04-13; `deploy/k8s/**` did not change in the gap round. |
| 3 | Cloud Run YAMLs target europe-west8, scale to zero, request-based billing; GcsArtifactStore wired; laptop sync forces a new mcp_server revision; no Scheduler or Cloud Run job | VERIFIED | `mcp-server.yaml` and `chat-bot.yaml`: minScale '0', no cpu-throttling annotation, europe-west8 image and URLs, ARTIFACT_STORE set. Images are now `@${IMAGE_DIGEST}` and revisions are named `<service>-${DEPLOY_ID}`. `sync-and-publish.sh` line 291 runs `services update --revision-suffix` after the publish; a traffic-mode guard (lines 267-277) refuses a forced revision while traffic is pinned. Live L9: the forced revision served 100% and Chat cited the new revision date. |
| 4 | A change under services/mcp_server triggers only that service's workflow; it runs `run-unit-tests.sh --all`, blocks the push on failure; on success pushes to Artifact Registry and deploys via WIF with no key | VERIFIED | `mcp-server.yml` path filter; `deploy: needs: test`; `_test.yml` runs `./run-unit-tests.sh --all`. `_deploy.yml` authenticates with `google-github-actions/auth` using `workload_identity_provider` and `service_account`. A grep for credentials_json, GOOGLE_APPLICATION_CREDENTIALS and private_key in `.github` finds nothing, and the repo tracks no key file. The repository secrets now hold identifiers only, which GitHub masks in logs; they are not credentials. Only two server files (`buddy_mcp/__init__.py`, `models.py`) also trigger chat-bot.yml, because the chat_bot stage copies them (Dockerfile lines 58-59). `tests/unit/test_workflows.py` guards path drift. |
| 5 | Guide videos play inline from access-controlled hosting and the Guarda button opens at the section's timestamp; coverage above 238/2524 | VERIFIED | Code path: `models.py` `video_link` appends `#t=<int seconds>`. `tests/unit/chat_bot/test_guarda_offset_path.py` drives a scene offset through the real MCP guides_search, the bot workflow and the Chat card, and asserts the button URL ends in `#t=125`; it passes in the full run. Live check 10 on 2026-11-16 (04-16): the video played inline from the private bucket at about 211 s for the 202 s offset. The 04-13 failure is explained in 04-15 as a click on a fallback row that had no offset. Coverage is 708/2524 (04-14). WINDOWS entry 7 is closed. |

**Score:** 5/5 truths verified. Behavior-unverified: 0.

The live observations for SC5 (check 10) and for the deploy order, re-run and traffic (L1 to L11) were made in the user's browser and project. I did not repeat them; they are recorded in 04-16 and 04-26. The code each one depends on is present and matches what was observed.

### Previous gaps, re-verified

| Gap | Status now | Evidence in code |
|-----|-----------|------------------|
| 1 Guarda offset (SC5) | CLOSED | See truth 5. The decision was no-fix, backed by the offline test and live check 10. |
| 2 bootstrap binds run.developer | CLOSED | `bootstrap.sh:168` `bind_project ... roles/run.admin` for ci-deployer. `run.developer` remains only for the owner (line 193), which is intended. Pinned by `tests/unit/test_cloudrun_yaml.py:478` and `:621`. Live L8 confirms. |
| 3 same-commit re-run creates no revision | CLOSED | `_deploy.yml` `DEPLOY_ID: r${run_id}-${run_attempt}`, rendered into `metadata.name`. Live L4: the re-run created `-2`, which serves. |
| 4 runbook key format | CLOSED | README line 101 names the Fernet format and line 111 gives the generation command. `config.py:95-97` rejects a non-Fernet value with a clear message. |
| 5 deploy by digest | CLOSED | `image: ...@${IMAGE_DIGEST}`; `render-cloudrun.sh:102` checks the `sha256:` format. Live L2 confirms. |
| 6 smoke test before traffic | CLOSED | The traffic block puts the candidate at 0% under the tag `candidate`. `_deploy.yml` checks the tagged URL, then runs `--to-latest` and `--remove-tags`. Live L3 and L11 confirm. |
| 7 base image by digest | CLOSED | All four `FROM python:3.12-slim@sha256:...` lines; Dependabot docker ecosystem configured. |
| 8 layer cache | CLOSED | `cache-from/cache-to type=gha` in `_deploy.yml` (and meridian per `test_deploy_pipeline.py:241`). Live L6 confirms. |
| 9 scan and SBOM | CLOSED | `sbom: true`, `provenance: mode=max`, and a Trivy scan of the pushed digest before any revision is created. Live L5 confirms. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Dockerfile` | per-service stages on Python 3.12, pinned | VERIFIED | digest-pinned base, hashed lock files, zlib1g security pin in every stage |
| `docker-compose.yml` | services plus emulators | VERIFIED | round trip run by me |
| `deploy/k8s/**` | Kustomize base and dev overlay | VERIFIED | validated in CI `_test.yml` validate job |
| `deploy/cloudrun/{mcp-server,chat-bot}.yaml`, `scripts/render-cloudrun.sh` | digest, revision name, staged traffic | VERIFIED | live deploys from `cf7e7c3` green |
| `deploy/cloudrun/bootstrap.sh`, `README.md` | reproducible bootstrap and runbook | VERIFIED | run.admin, sa-publisher, Fernet format |
| `.github/workflows/*.yml` | path-filtered, test-gated, keyless | VERIFIED | read `_deploy`, `_test`, `mcp-server`, `chat-bot`, `tests`, `sync` (header) |
| `scripts/sync-and-publish.sh` | laptop publish, forced revision, traffic guard | VERIFIED | live L9 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mcp-server.yml` / `chat-bot.yml` test | `_deploy.yml` | `needs: test` | WIRED | red tests stop the push |
| `_deploy.yml` build | Trivy scan and render | `steps.build.outputs.digest` | WIRED | the scanned digest is the deployed digest |
| `_deploy.yml` | `render-cloudrun.sh` | `IMAGE_DIGEST`, `DEPLOY_ID`, `SERVING_REVISION` env | WIRED | render validates all three |
| `_deploy.yml` candidate check | traffic switch | step order, `exit 1` on failure | WIRED | a red candidate leaves the old revision serving |
| `models.py` `#t=` | Chat card Guarda button | bot render | WIRED | offline test plus live check 10 |
| `sync-and-publish.sh` | running mcp-server | forced revision after publish | WIRED | live L9 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| mcp-server answers | index.db | private bucket through GcsArtifactStore | Yes (L9: cited the new revision date) | FLOWING |
| Guarda button | video URL with `#t=` | index video map, `video_link` | Yes (check 10: playback at the offset) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite, ruff, ruff format, mypy, coverage | `./run-unit-tests.sh --all` | 1585 passed, 26 skipped (environment-gated: emulator and local-only data), coverage 97.61%, ruff and mypy clean, exit 0 | PASS |
| Compose round trip | `scripts/compose-smoke.sh` | "round trip ok", exit 0 | PASS |
| CI on the code at HEAD | `gh run list` | tests, mcp-server, chat-bot on `cf7e7c3`: success | PASS |
| Decision coverage gate | `check.decision-coverage-verify` | 18/18 honored (substring heuristic; see D-12 note) | PASS (warning-only gate) |

### Probe Execution

No `probe-*.sh` exists and no plan declares one. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-01 | 04-02..04-06, 04-18, 04-21 | One Dockerfile per service on Python 3.12, same image everywhere | SATISFIED | Dockerfile stages, digest pin, lock files |
| INFRA-02 | 04-03, 04-06 | compose with emulators, local round trip | SATISFIED | compose smoke run by me |
| INFRA-03 | 04-02, 04-07 | kind with Kustomize, manifest validation | SATISFIED | CI validate job green |
| INFRA-04 | 04-01, 04-04, 04-08, 04-10, 04-15..04-17, 04-19 | Cloud Run YAMLs, GcsArtifactStore, laptop publish and forced revision | SATISFIED | truths 3 and 5; bootstrap and runbook fixed |
| INFRA-05 | 04-09, 04-20..04-25 | path-filtered build, push, deploy; Meridian from the approved commit; WIF | SATISFIED | truth 4; per-run revision, digest deploy, staged traffic |
| INFRA-06 | 04-09 | `run-unit-tests.sh --all` before any image push | SATISFIED | `_test.yml` plus `needs: test`. Branch protection was not checked; `needs` is what blocks the push |

Orphaned requirements: none.

Bookkeeping, not gaps: REQUIREMENTS.md still marks INFRA-04, INFRA-05 and INFRA-06 as Pending and unchecked. ROADMAP.md still shows 04-16 and 04-26 unchecked and "24/26 plans executed", although both have SUMMARY files with status complete. Update these when the phase closes.

### Judgment on the three 04-26 gaps

| 04-26 gap | Blocks a phase-4 criterion? | Reasoning |
|-----------|-----------------------------|-----------|
| Meridian login lost on Cloud Run, fixed by re-seeding | No criterion. Contradicts D-12, so it is the human item | SC1 to SC5 and INFRA-01..06 do not mention credential durability. D-12 (04-CONTEXT) promises that refreshes persist and that the bucket is seeded once. The committed config matches D-12: the FUSE volume is read-write and owned by uid 1000. The cause of the lost login is not proven, and the only live observation contradicts D-12. This is the open live check 12. |
| Silent `LlmError` in `workflow.py` reformulate | No | This is observability in Phase 3 code. The file is unchanged since the previous verification, and no Phase 4 criterion covers bot logging. Recorded as advisory. Confirmed in code at lines 102-104. |
| Cold start over Chat's ~30 s limit | No | SC3 requires scale to zero, which causes this delay. No criterion sets a latency bound. The previous human item expected the answer "within the window or as an asynchronous follow-up", and the answer does arrive in the thread. The user accepted the delay on 2026-11-16. Recorded as advisory. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `services/chat_bot/buddy_bot/workflow.py` | 102-104 | exception swallowed without a log line | Advisory (new scope, file unmodified since the previous pass) | failures are invisible in Cloud Run logs |

Debt-marker scan (TBD, FIXME, XXX) over every non-test file changed since the previous verification: none found. No skipped test covers a phase-4 requirement; the 26 skips are emulator or local-data gated.

### Human Verification Required

1. **Meridian credentials durability (live check 12, D-12).**
   **Test:** After the 2026-11-16 re-seed, leave the chat-bot running across at least one Claude token expiry and one new chat-bot revision. Then ask one question in Chat.
   **Expected:** The answer arrives with no re-seed, and the Meridian container logs no "loggedIn: false".
   **Why human:** This needs a real token expiry on the live service. The one live observation so far is negative and its cause is unknown.
   **Decision if it fails again:** either accept manual re-seeding with an override on D-12 plus a health signal (already in the backlog), or open a fix plan for the refresh chain.

The cold-start item from the previous verification is resolved: it was measured, the answer arrives asynchronously, and the user accepted the delay.

### Gaps Summary

There are no gaps. The nine previous gaps are closed in code and backed by passing pinning tests. Where a gap needed live proof (L1 to L11 and check 10), that proof is recorded in 04-16 and 04-26. The suite (1585 passed) and the compose round trip pass on HEAD, and CI is green on the same code. The phase goal is achieved. One runtime promise from decision D-12 (Meridian credentials seeded once) has a negative live observation and needs a human decision or a follow-up observation before the phase is marked passed.

---

_Verified: 2026-11-16_
_Verifier: Claude (gsd-verifier)_
