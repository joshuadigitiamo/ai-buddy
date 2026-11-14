---
phase: "4"
slug: "infrastructure-and-ci-cd"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-14"
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 + pytest-cov 7.1.0, ruff 0.17.3, mypy 2.4.1 strict |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, markers `firestore`, `pubsub`) |
| **Quick run command** | `./run-unit-tests.sh --single-file <file> tests/unit` |
| **Full suite command** | `./run-unit-tests.sh --all` (+ `./run-unit-tests.sh --emulator`, `scripts/validate-infra.sh`) |
| **Estimated runtime** | ~120 seconds (`--all`); smoke scripts several minutes |

`run-unit-tests.sh` runs with `--network none`; Docker/network checks live in `scripts/validate-infra.sh`, `scripts/compose-smoke.sh`, `scripts/kind-smoke.sh` and CI steps.

---

## Sampling Rate

- **After every task commit:** Run the task's `--single-file` command
- **After every plan wave:** Run `./run-unit-tests.sh --all` plus `scripts/validate-infra.sh`
- **Before `/gsd-verify-work`:** `--all`, `--emulator`, `compose-smoke.sh`, `kind-smoke.sh` green; live checkpoint recorded (or recorded as deferred if Joshua defers it; the GCP project `ai-buddy-dev` with billing exists since 2026-11-14)
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

Filled by the planner/executor per task. Requirement → test map from RESEARCH.md:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| INFRA-01 | Dockerfile stages `mcp_server`, `chat_bot`, `sync`; non-root; no secrets/artifacts copied | unit + build | `./run-unit-tests.sh --single-file test_dockerfile_stages.py tests/unit` | ❌ W0 | ⬜ pending |
| INFRA-01 | `ARTIFACT_STORE`, `DEPLOY_ENV`, `MCP_ALLOWED_HOSTS` config | unit | `./run-unit-tests.sh --single-file test_config.py tests/unit/mcp_server` | partial | ⬜ pending |
| INFRA-02 | Hermetic compose round trip with `handbook://` citation | integration | `scripts/compose-smoke.sh` | ❌ W0 | ⬜ pending |
| INFRA-02 | Compose structure | unit | `./run-unit-tests.sh --single-file test_compose.py tests/unit` | migrate | ⬜ pending |
| INFRA-03 | Base + dev overlay pass kubeconform | static | `scripts/validate-infra.sh` | ❌ W0 | ⬜ pending |
| INFRA-03 | Health check + one MCP tool call in kind | live-local | `scripts/kind-smoke.sh` | ❌ W0 | ⬜ pending |
| INFRA-04 | `GcsArtifactStore` pointer-last publish, sha256 check | unit | `./run-unit-tests.sh --single-file test_gcs_store.py tests/unit/buddy_core` | ❌ W0 | ⬜ pending |
| INFRA-04 | Cloud Run YAML structure | unit | `./run-unit-tests.sh --single-file test_cloudrun_yaml.py tests/unit` | ❌ W0 | ⬜ pending |
| INFRA-05 | Path filters vs Dockerfile COPY drift; actionlint | unit + static | `./run-unit-tests.sh --single-file test_workflows.py tests/unit` | ❌ W0 | ⬜ pending |
| INFRA-06 | `deploy` needs `test`; test runs `--all`; script executable | unit | `./run-unit-tests.sh --single-file test_workflows.py tests/unit` | ❌ W0 | ⬜ pending |
| SC5 | Video URLs rewritten; coverage report; md5 skip | unit | `./run-unit-tests.sh --single-file test_video_upload.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |

### Task-level map (from the plan verify commands)

Every new test file is created by the task that first needs it (TDD in the task), so no separate Wave 0 plan exists.

| Task | Requirement | Automated command | Status |
|------|-------------|-------------------|--------|
| 04-01 T1-T2 | INFRA-04 | checkpoint (human legitimacy gate, decisions) | ✅ green |
| 04-01 T3 | INFRA-04 | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit` | ✅ green |
| 04-02 T1 | INFRA-03 | `./run-unit-tests.sh --single-file test_http_transport.py tests/unit/mcp_server` | ✅ green |
| 04-02 T2 | INFRA-01 | `./run-unit-tests.sh --single-file test_config.py tests/unit/mcp_server`; `./run-unit-tests.sh --all` | ✅ green |
| 04-02 T3 | INFRA-01 | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit`; `./run-unit-tests.sh --single-file test_dev_compose.py tests/unit` | ✅ green |
| 04-03 T1 | INFRA-02 | `./run-unit-tests.sh --single-file test_chat_api.py tests/unit/chat_bot` | ⬜ pending |
| 04-03 T2 | INFRA-01 | `./run-unit-tests.sh --single-file test_config.py tests/unit/chat_bot`; `--single-file test_main.py tests/unit/chat_bot` | ⬜ pending |
| 04-03 T3 | INFRA-01 | `./run-unit-tests.sh --single-file test_readme_contract.py tests/unit/chat_bot`; `--all` | ⬜ pending |
| 04-04 T1 | INFRA-04 | `./run-unit-tests.sh --single-file test_gcs_store.py tests/unit/buddy_core` | ⬜ pending |
| 04-04 T2 | INFRA-04 | `--single-file test_gcs_store.py tests/unit/buddy_core`; `--single-file test_snapshot.py tests/unit/mcp_server` | ⬜ pending |
| 04-04 T3 | INFRA-04 | `--single-file test_gcs_bucket.py tests/unit/buddy_core`; `--all` | ⬜ pending |
| 04-05 T1 | INFRA-01 | `scripts/sync-image-smoke.sh` | ⬜ pending |
| 04-05 T2 | INFRA-01 | `./run-unit-tests.sh --single-file test_dockerfile_stages.py tests/unit`; `--all` | ⬜ pending |
| 04-06 T1 | INFRA-02 | `scripts/compose-smoke.sh` | ⬜ pending |
| 04-06 T2 | INFRA-02 | `./run-unit-tests.sh --single-file test_compose.py tests/unit`; `docker compose --profile live config --quiet` | ⬜ pending |
| 04-06 T3 | INFRA-02 | `./run-unit-tests.sh --single-file test_stub_llm.py tests/unit`; `--all` | ⬜ pending |
| 04-07 T1-T2 | INFRA-03 | `scripts/kind-up.sh && scripts/kind-smoke.sh` | ⬜ pending |
| 04-07 T3 | INFRA-03 | `./run-unit-tests.sh --single-file test_k8s_manifests.py tests/unit`; `scripts/validate-infra.sh` | ⬜ pending |
| 04-08 T1-T2 | INFRA-04 | `./run-unit-tests.sh --single-file test_cloudrun_yaml.py tests/unit`; render check | ⬜ pending |
| 04-08 T3 | INFRA-04 | `bash -n deploy/cloudrun/bootstrap.sh`; `--all` | ⬜ pending |
| 04-09 T1-T2 | INFRA-05, INFRA-06 | `./run-unit-tests.sh --single-file test_workflows.py tests/unit`; actionlint via Docker | ⬜ pending |
| 04-09 T3 | INFRA-06 | `--single-file test_workflows.py tests/unit`; `scripts/validate-infra.sh` | ⬜ pending |
| 04-10 T1 | INFRA-04 | `./run-unit-tests.sh --single-file test_publish.py tests/unit/buddy_sync`; `bash -n scripts/sync-and-publish.sh` | ⬜ pending |
| 04-10 T2-T3 | INFRA-04 | grep gates on ADR, README, REQUIREMENTS, ROADMAP | ⬜ pending |
| 04-11 T1-T2 | INFRA-04 / SC5 | `./run-unit-tests.sh --single-file test_video_upload.py tests/unit/buddy_sync`; `--single-file test_video_map.py tests/unit/buddy_sync` | ⬜ pending |
| 04-11 T3 | INFRA-04 | `--single-file test_repo_layout.py tests/unit`; `--all` | ⬜ pending |
| 04-12 T1 | SC5 | `./run-unit-tests.sh --single-file test_video_coverage.py tests/unit/buddy_sync` | ⬜ pending |
| 04-12 T2 | SC5 | `--single-file test_video_map.py tests/unit/buddy_sync`; `--all` | ⬜ pending |
| 04-13 T1 | INFRA-04..06 | `--all`, `--emulator`, `scripts/validate-infra.sh`, `scripts/compose-smoke.sh`, `scripts/kind-up.sh && scripts/kind-smoke.sh` | ⬜ pending |
| 04-13 T2-T3 | INFRA-04, INFRA-05, SC5 | live checkpoint (manual) | ⬜ pending |
| 04-14 T1-T3 | SC5 | `video-coverage --guides-dir` via the sync image; human review and Guides commit | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_dockerfile_stages.py`, `test_compose.py` (migrate from `test_dev_compose.py`), `test_cloudrun_yaml.py`, `test_workflows.py`
- [ ] `tests/unit/buddy_core/test_gcs_store.py`, `tests/unit/buddy_sync/test_video_upload.py`, config tests for new settings and `/healthz`
- [ ] `scripts/validate-infra.sh`, `scripts/compose-smoke.sh`, `scripts/kind-up.sh`, `scripts/kind-smoke.sh`, `scripts/sync-and-publish.sh`
- [ ] Fixtures: smoke stub LLM, expected recorded answer, `deploy/compose/pubsub_init.py`
- [ ] `git update-index --chmod=+x run-unit-tests.sh` (and new scripts)
- [ ] `requirements-dev.txt` gains `-r jobs/sync/requirements.txt`
- [ ] kind binary download with checksum into `.cache/bin/`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| WIF push + deploy, no key file | INFRA-05 | Needs the live run in the existing GCP project `ai-buddy-dev` (billing linked; 04-13) | First push to `main` after bootstrap; check run log and `gcloud run revisions list` |
| Inline video playback + `#t=` seek | SC5 | Needs signed-in browser on private bucket | Chrome signed in as owner; open Guarda link; paste evidence |
| Cloud Run server-side YAML validation | INFRA-04 | Needs auth | `gcloud run services replace <file> --dry-run --region europe-west8` in CI after WIF login |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
