---
phase: 04-infrastructure-and-ci-cd
verified: 2026-11-16T22:38:12Z
status: passed
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
  - tests/unit/chat_bot/test_workflow.py
  - tests/unit/test_cloudrun_yaml.py
  - tests/unit/test_deploy_pipeline.py
  - tests/unit/test_workflows.py
covered_digest: "v4:sha256:0d723e7d60904b0526686042f27dbea8875d3e608b32a0cf346106ccbdf9595e"
behavior_unverified: 0
overrides_applied: 0 # the override closes a human-verification item, not a scored truth; all 5 truths are VERIFIED on evidence
overrides:
  - must_have: "Meridian credentials durability on Cloud Run: token refreshes persist across restarts, bucket seeded once (live check 12, decision D-12)"
    reason: "Manual re-seeding of the Meridian credentials bucket is accepted as the recovery when the login drops (deploy/cloudrun/README.md 'Seeding the Meridian credentials bucket'). Signal: chat-bot logs 'reformulate failed: LlmUnavailableError: <SDK error name>' (fix 60aed0a) and Meridian logs 'loggedIn: false'. No phase-4 success criterion or INFRA requirement names credential durability. Backlog: alert on that log line."
    accepted_by: "The owner"
    accepted_at: "2026-11-16T00:00:00Z"
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "Meridian credentials durability human item (D-12): closed by user override, 2026-11-16"
    - "Advisory: silent LlmError in workflow.py reformulate: fixed in 60aed0a, pinned by test_reformulation_failure_is_logged_with_the_error_type_only"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "LLM evaluation gate in CI (CICD_GUIDE section 23)"
    addressed_in: "Phase 5"
    evidence: "Phase 5 goal and success criterion 5: the gate command prints PASS only when correctness-with-citation >= 90%, invented policies 0, empty-context test passes"
advisory:
  - finding: "FIXED (60aed0a): the bot logged nothing when the reformulate LLM call failed (workflow.py caught LlmError and returned the error reply without a log line)"
    category: other
    reason: "workflow.py:102-106 now logs 'reformulate failed: <type>: <msg>' at ERROR on logger buddy_bot. Every LlmError raised in the codebase (llm.py:100, llm.py:112) carries only a schema name or an SDK exception type name, so no question text or response body reaches the log (BOT-11)."
    evidence_status: "fixed; tests/unit/chat_bot/test_workflow.py::test_reformulation_failure_is_logged_with_the_error_type_only passes in the full run; CI tests and chat-bot green on 60aed0a"
  - finding: "Cold start exceeds Chat's ~30 s HTTP limit: 55.7 s measured (04-26), Chat shows 'AI Buddy non risponde' on the first message after idle while the answer still arrives in the thread"
    category: other
    reason: "Accepted by the user on 2026-11-16 (no minScale 1, free-hosting goal). No phase-4 criterion sets a latency bound; SC3 requires scale to zero, which causes this. Backlog: profile the ~25 s between Meridian ready and bot start"
    evidence_status: "live measurement in 04-26 Gaps; user decision recorded there"
---

# Phase 4: Infrastructure and CI/CD Verification Report

**Phase Goal:** The whole system runs from per-service Docker images locally (compose), on kind, and as Cloud Run definitions, built and deployed by path-filtered CI without stored keys.
**Verified:** 2026-11-16T22:38:12Z
**Status:** passed
**Re-verification:** Yes. This pass follows the human_needed report of earlier on 2026-11-16 (plans 04-15 to 04-26). It covers commits 243c6f4, 60aed0a and 2126402 and the user's D-12 override.

All five success criteria and all nine earlier gaps are verified in the code at HEAD. Since the previous report, only three files changed: `services/chat_bot/buddy_bot/workflow.py`, `tests/unit/chat_bot/test_workflow.py` and `04-26-SUMMARY.md`. The workflow change adds one log line in an error branch. I ran the full suite on HEAD in Docker and it passes with one test more than before (1586). The tests and chat-bot workflows on `60aed0a` are green on GitHub Actions. The mcp-server workflow did not run on `60aed0a` because no server file changed; its last run, on `cf7e7c3`, is green.

The one human item from the previous report is closed by the user's decision. On 2026-11-16 the owner chose to accept manual re-seeding of the Meridian credentials bucket when the login drops. This overrides the "seeded once" promise of D-12. The silent-`LlmError` advisory is fixed, and its log line is the signal for a lost login.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` starts mcp_server, chat_bot and the sync job from per-service images with both emulators; a Pub/Sub chat event completes a round trip | VERIFIED | The previous pass ran `scripts/compose-smoke.sh` on the current Dockerfile: exit 0, "round trip ok". In this pass only one line changed in the image inputs, a log call in the reformulate error branch. I did not run the compose smoke again. |
| 2 | Kustomize dev overlay on kind brings services up; health check and one MCP tool call succeed in-cluster; base and overlays pass validation | VERIFIED | `_test.yml` job `validate` runs `scripts/validate-infra.sh`. The tests workflow on `60aed0a` is green. `deploy/k8s/**` is unchanged since the 04-13 in-cluster smoke. |
| 3 | Cloud Run YAMLs target europe-west8, scale to zero, request-based billing; GcsArtifactStore wired; laptop sync forces a new mcp_server revision; no Scheduler or Cloud Run job | VERIFIED | Unchanged since the previous pass. In `mcp-server.yaml` and `chat-bot.yaml`: minScale '0', no cpu-throttling annotation, europe-west8 image and URLs, ARTIFACT_STORE set, images by `@${IMAGE_DIGEST}`, revisions named `<service>-${DEPLOY_ID}`. `sync-and-publish.sh` forces a revision after the publish, behind a traffic-mode guard. Live L9 confirmed the forced revision. |
| 4 | A change under services/mcp_server triggers only that service's workflow; it runs `run-unit-tests.sh --all`, blocks the push on failure; on success pushes to Artifact Registry and deploys via WIF with no key | VERIFIED | Unchanged since the previous pass, and `60aed0a` confirms the behaviour live: a change under `services/chat_bot` triggered only `tests` and `chat-bot`, not `mcp-server`. `deploy: needs: test`. `_deploy.yml` authenticates through `google-github-actions/auth` with `workload_identity_provider`. No key material is stored in `.github` or the repo. |
| 5 | Guide videos play inline from access-controlled hosting and the Guarda button opens at the section's timestamp; coverage above 238/2524 | VERIFIED | `models.py` `video_link` appends `#t=<int seconds>`. `test_guarda_offset_path.py` passes in this pass's full run. Live check 10 (04-16) confirmed inline playback at the offset. Coverage is 708/2524 (04-14). |

**Score:** 5/5 truths verified. Behavior-unverified: 0. Overrides applied to a scored truth: 0.

The live observations were made in the user's browser and project and are recorded in 04-16 and 04-26: SC5 check 10, and the deploy order, re-run and traffic checks L1 to L11. I did not repeat them.

### Override (2026-11-16)

| Item | Status | Evidence |
|------|--------|----------|
| Meridian credentials durability on Cloud Run (live check 12, D-12: "token refreshes ... persist across restarts. Seeded once") | PASSED (override) | Override: manual re-seeding is accepted as the recovery when the login drops. Accepted by the owner on 2026-11-16. |

Consistency check of the override text, done in this pass:
- In `04-CONTEXT.md`, D-12 carries a sub-bullet "Override 2026-11-16 (the owner)". It accepts manual re-seeding, names the `reformulate failed` log line as the signal, and withdraws "seeded once" as a guarantee. This matches the frontmatter override.
- The runbook section it names exists: `deploy/cloudrun/README.md:121` "Seeding the Meridian credentials bucket".
- The signal exists in code. When Meridian rejects a call, the Anthropic SDK raises an `APIError`. `llm.py:110-112` maps that error to `LlmUnavailableError(<SDK exception type name>)`, and `workflow.py:102-106` logs it as `reformulate failed: LlmUnavailableError: <name>`. Reformulate is the first LLM call of every question, so a lost login logs this line on the first question.
- `04-26-SUMMARY.md` Gaps marks the silent-`LlmError` item as fixed in `60aed0a` and names the pinning test. This matches the advisory entry.
- One limit: the same log line also fires for other Meridian failures, such as a timeout or the sidecar being down. Only the SDK error name tells them apart. Live 04-26 showed Meridian logging `loggedIn: false`, but I have not seen which SDK error name the bot gets for a logged-out Meridian. The backlog alert should match on the error name together with Meridian's `loggedIn: false`.

### Change since the previous pass: `workflow.py` reformulate

| Check | Result |
|-------|--------|
| Diff `60aed0a` | `except LlmError:` becomes `except LlmError as exc:` plus `_LOGGER.error("reformulate failed: %s: %s", type(exc).__name__, exc)`. The return value is unchanged: `{"reply": BotReply(kind="error")}`. |
| Logger wiring | `_LOGGER = logging.getLogger("buddy_bot")` (workflow.py:45). The test captures `buddy_bot` at ERROR. |
| No sensitive content in the message (BOT-11) | Every `LlmError` raised in services/ and packages/ comes from two places: `llm.py:100` with the schema name and `llm.py:112` with the SDK exception type name, raised `from None`. The log line therefore holds no question text, prompt or response body. |
| Pinning test | `test_reformulation_failure_is_logged_with_the_error_type_only` asserts the exact message `reformulate failed: LlmUnavailableError: AuthenticationError`. It was committed red in `243c6f4` and passes on HEAD. |
| Existing behaviour | `test_model_unavailable_during_reformulation_gives_the_error_reply` (error reply, no gap record) still passes. |
| Debt markers (TBD, FIXME, XXX) | none in `workflow.py` or `test_workflow.py` |

### Previous gaps (closed in the earlier pass; regression check only)

| Gap | Status now | Evidence in code |
|-----|-----------|------------------|
| 1 Guarda offset (SC5) | CLOSED | See truth 5. |
| 2 bootstrap binds run.developer | CLOSED | `bootstrap.sh` binds `roles/run.admin` for ci-deployer. Pinned by `test_cloudrun_yaml.py`, which passes. |
| 3 same-commit re-run creates no revision | CLOSED | `DEPLOY_ID: r${run_id}-${run_attempt}` in `_deploy.yml`. |
| 4 runbook key format | CLOSED | README names the Fernet format. `config.py` rejects a non-Fernet value. |
| 5 deploy by digest | CLOSED | `image: ...@${IMAGE_DIGEST}`. `render-cloudrun.sh` checks the `sha256:` format. |
| 6 smoke test before traffic | CLOSED | A 0% `candidate` tag and a tagged-URL check run before `--to-latest`. |
| 7 base image by digest | CLOSED | Every `FROM python:3.12-slim@sha256:...` is pinned. Dependabot docker is configured. |
| 8 layer cache | CLOSED | `cache-from/cache-to type=gha`. |
| 9 scan and SBOM | CLOSED | `sbom: true`, `provenance: mode=max`, and a Trivy scan of the pushed digest. |

No file behind gaps 1 to 9 changed in this pass. Their pinning tests pass in the full run.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Dockerfile` | per-service stages on Python 3.12, pinned | VERIFIED | unchanged |
| `docker-compose.yml` | services plus emulators | VERIFIED | unchanged |
| `deploy/k8s/**` | Kustomize base and dev overlay | VERIFIED | CI validate job green on `60aed0a` |
| `deploy/cloudrun/{mcp-server,chat-bot}.yaml`, `scripts/render-cloudrun.sh` | digest, revision name, staged traffic | VERIFIED | unchanged |
| `deploy/cloudrun/bootstrap.sh`, `README.md` | reproducible bootstrap and runbook, including the re-seeding section the override relies on | VERIFIED | README:121 |
| `.github/workflows/*.yml` | path-filtered, test-gated, keyless | VERIFIED | `60aed0a` triggered only tests and chat-bot, both green |
| `scripts/sync-and-publish.sh` | laptop publish, forced revision, traffic guard | VERIFIED | unchanged |
| `services/chat_bot/buddy_bot/workflow.py` | reformulate failure is logged with type only | VERIFIED | pinned by test |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mcp-server.yml` / `chat-bot.yml` test | `_deploy.yml` | `needs: test` | WIRED | red tests stop the push |
| `_deploy.yml` build | Trivy scan and render | `steps.build.outputs.digest` | WIRED | the scanned digest is the deployed digest |
| `_deploy.yml` | `render-cloudrun.sh` | `IMAGE_DIGEST`, `DEPLOY_ID`, `SERVING_REVISION` env | WIRED | the render step validates all three |
| `_deploy.yml` candidate check | traffic switch | step order, `exit 1` on failure | WIRED | a red candidate leaves the old revision serving |
| `models.py` `#t=` | Chat card Guarda button | bot render | WIRED | offline test plus live check 10 |
| `sync-and-publish.sh` | running mcp-server | forced revision after publish | WIRED | live L9 |
| `llm.py` `LlmUnavailableError` | Cloud Run log | `workflow.py` reformulate `_LOGGER.error` | WIRED | the override's lost-login signal |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| mcp-server answers | index.db | private bucket through GcsArtifactStore | Yes (L9) | FLOWING |
| Guarda button | video URL with `#t=` | index video map, `video_link` | Yes (check 10) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite, ruff, ruff format, mypy, coverage on HEAD | `./run-unit-tests.sh --all` (Docker) | ruff "All checks passed!", "164 files already formatted", mypy "no issues found in 151 source files", 1586 passed, 26 skipped (emulator or local-data gated), coverage 97.61%, exit 0 | PASS |
| New log line | `test_reformulation_failure_is_logged_with_the_error_type_only` (in the full run) | PASSED | PASS |
| CI on the fix commit | `gh run list --commit 60aed0a` | tests: success, chat-bot: success | PASS |
| Compose round trip | `scripts/compose-smoke.sh` | not re-run in this pass. Previous pass: "round trip ok", and the only image change since is one log line | SKIP (previous result stands) |

### Probe Execution

No `probe-*.sh` exists and no plan declares one. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-01 | 04-02..04-06, 04-18, 04-21 | One Dockerfile per service on Python 3.12, same image everywhere | SATISFIED | Dockerfile stages, digest pin, lock files |
| INFRA-02 | 04-03, 04-06 | compose with emulators, local round trip | SATISFIED | compose smoke (previous pass) |
| INFRA-03 | 04-02, 04-07 | kind with Kustomize, manifest validation | SATISFIED | CI validate job green |
| INFRA-04 | 04-01, 04-04, 04-08, 04-10, 04-15..04-17, 04-19 | Cloud Run YAMLs, GcsArtifactStore, laptop publish and forced revision | SATISFIED | truths 3 and 5 |
| INFRA-05 | 04-09, 04-20..04-25 | path-filtered build, push, deploy; Meridian from the approved commit; WIF | SATISFIED | truth 4. `60aed0a` path filter observed live |
| INFRA-06 | 04-09 | `run-unit-tests.sh --all` before any image push | SATISFIED | `_test.yml` plus `needs: test` |

Orphaned requirements: none.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | | | | The previous finding, an exception swallowed without a log line at `workflow.py` reformulate, is fixed in `60aed0a`. |

### Human Verification Required

None. The D-12 durability item is closed by the user override above.

### Gaps Summary

There are no gaps. The five success criteria are verified, and the nine earlier gaps stay closed. Since the previous report, the code changed by one log line, pinned by a test that passes. The full suite passes on HEAD in Docker, and CI is green on the fix commit. The last open item, Meridian login durability under D-12, is closed by the owner's decision of 2026-11-16 to accept manual re-seeding, signalled by the new log line. The cold-start advisory stays accepted. The CI evaluation gate is deferred to Phase 5.

---

_Verified: 2026-11-16T22:38:12Z_
_Verifier: Claude (gsd-verifier)_
