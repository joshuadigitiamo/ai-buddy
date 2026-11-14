---
phase: 04-infrastructure-and-ci-cd
plan: 07
subsystem: infra
tags: [kubernetes, kind, kustomize, kubeconform, meridian, native-sidecar, pubsub-emulator, firestore-emulator]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-01 deploy/meridian.version and the token_chain (b) decision (kind mounts a read-only copy)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-02 MCP_ALLOWED_HOSTS, DEPLOY_ENV and GET /healthz on the MCP server"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-03 recording Chat adapter (CHAT_API, CHAT_RECORD_PATH) and the bot DEPLOY_ENV guards"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-05 images running as uid 10001"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-06 compose as the working reference for env vars and the emulator commands"
provides:
  - "deploy/k8s Kustomize base (mcp-server, chat-bot with Meridian native sidecar, Firestore and Pub/Sub emulators, pubsub-init Job) and overlays/dev (namespace, ConfigMaps, hostPath artifacts, image tags)"
  - "scripts/kind-up.sh: pinned and checksum-verified kind v0.33.0, cluster ai-buddy on kindest/node v1.37.0, images built and loaded, Secrets created imperatively without printing, overlay applied"
  - "scripts/kind-smoke.sh: in-cluster /healthz plus one cited guides_search call, Job and sidecar checks"
  - "scripts/validate-infra.sh: kubectl kustomize plus kubeconform v0.8.0 strict for base and every overlay (04-09 appends its checks)"
  - "tests/unit/test_k8s_manifests.py: 19-test offline structural guard"
affects: [04-08, 04-09, 04-14]

actuals:
  tokens: 13356
  tasks: 3
  commits: 4
plan_head_before: 4114fc1a06c2a65195093a0e97828aa1a358b9d0
plan_head_after: e127a5d02388fb8025eede2b5dea6087cb8a69f5

tech-stack:
  added: [kind v0.33.0 (downloaded to .cache/bin), kubeconform v0.8.0 (Docker image), kindest/node v1.37.0]
  patterns:
    - "Fail-closed base, local knobs only in the dev overlay ConfigMaps"
    - "Secrets created imperatively from a stream (never printed, never on disk, never in git); manifests carry only Secret names"
    - "Meridian as a loopback-only native sidecar probed with exec probes, because kubelet httpGet targets the pod IP"
    - "One kubeconfig per kind cluster under .cache, so ~/.kube/config is never touched"

key-files:
  created:
    - deploy/k8s/kind-config.yaml
    - deploy/k8s/base/kustomization.yaml
    - deploy/k8s/base/mcp-server.yaml
    - deploy/k8s/base/chat-bot.yaml
    - deploy/k8s/base/emulators.yaml
    - deploy/k8s/base/pubsub-init.yaml
    - deploy/k8s/overlays/dev/kustomization.yaml
    - deploy/k8s/overlays/dev/namespace.yaml
    - deploy/k8s/overlays/dev/local-env.yaml
    - deploy/k8s/overlays/dev/artifacts-hostpath.yaml
    - deploy/k8s/README.md
    - scripts/kind-up.sh
    - scripts/kind-smoke.sh
    - scripts/validate-infra.sh
    - tests/unit/test_k8s_manifests.py
  modified: []

key-decisions:
  - "Meridian probes in kind are exec probes (node fetch inside the container) on /health for start-up and readiness and /livez for liveness; Meridian stays bound to 127.0.0.1"
  - "Meridian credentials-read-only variable is MERIDIAN_CREDENTIALS_READONLY=1 (confirmed in docs/configuration.md at the pinned commit cafdcf78)"
  - "kind-up uses a per-cluster kubeconfig at .cache/kubeconfig-<cluster> instead of the user's default kubeconfig"
  - "bot-secrets is created once and kept across kind-up re-runs; meridian-credentials is re-applied from the volume on every run with server-side apply (no last-applied copy of the value in the cluster)"
  - "The dev Namespace lives in overlays/dev/namespace.yaml, applied before the Secrets and again as part of the overlay"

patterns-established:
  - "Secret-free manifests enforced by test: no Secret kind, no secretGenerator, secret-named env only through secretKeyRef"
  - "Overlay image tags pinned and cross-checked against deploy/meridian.version"

requirements-completed: [INFRA-03]

coverage:
  - id: D1
    description: "kind runs the full stack from the local images (mcp-server, chat-bot with Meridian native sidecar, both emulators, pubsub-init Job); an in-cluster request reaches the MCP server by Service name and gets a cited guides_search answer"
    requirement: INFRA-03
    verification:
      - kind: integration
        ref: "scripts/kind-up.sh && scripts/kind-smoke.sh (exit 0, last line 'kind smoke ok', 5 cited results; run on a live kind cluster)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Max credentials reach the cluster only as an imperatively created Secret from the local meridian-claude volume, never printed or written to git; Meridian in kind runs read-only"
    requirement: INFRA-03
    verification:
      - kind: unit
        ref: "tests/unit/test_k8s_manifests.py#test_no_secret_object_and_no_literal_secret_value_anywhere_under_deploy_k8s"
        status: pass
      - kind: unit
        ref: "tests/unit/test_k8s_manifests.py#test_chat_bot_runs_meridian_as_a_loopback_native_sidecar"
        status: pass
      - kind: unit
        ref: "tests/unit/test_k8s_manifests.py#test_kind_up_verifies_the_download_and_creates_secrets_without_printing_them"
        status: pass
    human_judgment: false
  - id: D3
    description: "kubectl kustomize of base and overlays/dev passes kubeconform strict against Kubernetes 1.37.0 (8 and 11 resources valid); an injected unknown field is rejected"
    requirement: INFRA-03
    verification:
      - kind: integration
        ref: "scripts/validate-infra.sh (exit 0; Valid 8/8 and 11/11, Invalid 0, Errors 0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Resource, securityContext, label, probe, image-pin, fail-closed-base and read-only-mount rules are guarded offline"
    requirement: INFRA-03
    verification:
      - kind: unit
        ref: "./run-unit-tests.sh --single-file test_k8s_manifests.py tests/unit (19 passed); ./run-unit-tests.sh --all (1292 passed, coverage 97.60%, ruff and mypy clean)"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 07: Kustomize Base and kind Dev Overlay Summary

**The whole system, Meridian included, runs on a local kind cluster from a fail-closed Kustomize base and a dev overlay; an in-cluster smoke gets a cited MCP answer, credentials arrive only as imperatively created Secrets, and base and overlay pass kubeconform strict.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-11-14T12:35:40Z
- **Completed:** 2026-11-14T12:52:12Z
- **Tasks:** 3
- **Files modified:** 16 (15 created, 1 deleted: deploy/k8s/.gitkeep)

## Accomplishments

- `scripts/kind-up.sh` downloads kind v0.33.0, verifies the published sha256 before the file becomes executable, creates cluster `ai-buddy` on `kindest/node:v1.37.0` with the artifact directory mounted read-only, builds and loads the three images (mcp-server, chat-bot, Meridian from the pinned commit) and applies `deploy/k8s/overlays/dev`. Re-running it on an existing cluster works (apply unchanged, Job recreated).
- `scripts/kind-smoke.sh` requires the `pubsub-init` Job complete and the chat-bot pod Ready with the Meridian sidecar started, then runs a restricted one-off pod from the already loaded image that GETs `http://mcp-server:8000/healthz` (200, `{"status": "ok"}`) and POSTs `tools/call guides_search` (200, `isError` false, 5 results each with `source_url`). Last line: `kind smoke ok`.
- Chat bot Deployment with Meridian as a native sidecar (init container, `restartPolicy: Always`, startup probe), `LLM_BASE_URL http://localhost:3456` as on Cloud Run, Pub/Sub intake, recording Chat API. The bot started cleanly (`intake pubsub, llm backend meridian, chat api recording`) with 0 restarts.
- `scripts/validate-infra.sh`: base 8 resources and overlay 11 resources valid under `kubeconform -strict -kubernetes-version 1.37.0` (stdin input works, RESEARCH A12 confirmed); a deliberately injected unknown field is rejected with a non-zero exit.
- 19-test offline guard `tests/unit/test_k8s_manifests.py`; `./run-unit-tests.sh --all`: 1292 passed, 26 skipped, coverage 97.60%, ruff and mypy clean.

## Task Commits

1. **Task 1: Tracer, mcp-server on kind answers /healthz and one tools/call in-cluster** - `671d039` (feat). Tracer gate: `<verify>` re-run end to end after the commit and again after Task 2; passed, expansion continued.
2. **Task 2: Full stack on kind** - `7ba2485` (feat)
3. **Task 3 (TDD): structural guard, validate-infra, README, gitkeep removal** - `f4878b5` (test, RED), `e127a5d` (feat, GREEN)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md and ROADMAP.md (hash recorded by the orchestrator).

## Files Created/Modified

- `deploy/k8s/kind-config.yaml` - cluster template with the read-only `/artifacts` extraMount placeholder
- `deploy/k8s/base/` - `mcp-server.yaml`, `chat-bot.yaml`, `emulators.yaml`, `pubsub-init.yaml`, `kustomization.yaml`
- `deploy/k8s/overlays/dev/` - `kustomization.yaml` (namespace, images, ConfigMap generators, patches), `namespace.yaml`, `local-env.yaml`, `artifacts-hostpath.yaml`
- `deploy/k8s/README.md` - run guide, env contract per target, credentials handling, probes, Pod Security exception
- `scripts/kind-up.sh`, `scripts/kind-smoke.sh`, `scripts/validate-infra.sh` - executable in tree and index (mode 100755)
- `tests/unit/test_k8s_manifests.py` - offline structural guard
- `deploy/k8s/.gitkeep` - deleted (intentional)

## Decisions Made

- Meridian runs in kind with `MERIDIAN_CREDENTIALS_READONLY=1`. The variable name was confirmed in Meridian's `docs/configuration.md` at the pinned commit (the plan asked for confirmation).
- Per-cluster kubeconfig `.cache/kubeconfig-<cluster>` rather than the user's default one: the scripts cannot affect or be confused by other contexts.
- `bot-secrets` is generated once and kept; `meridian-credentials` is refreshed from the volume on every run with server-side apply so no copy of the value lands in a last-applied annotation.
- The emulator pods and the hostPath keep the namespace at `warn`/`audit` restricted without `enforce` (the plan's recorded exception, T-04-26 accepted).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Meridian probes cannot be httpGet against a loopback-bound sidecar, and /readyz never passes here**
- **Found during:** Task 2 (first full `kind-up.sh` run; the chat-bot pod sat in `Init:1/2`, Meridian killed on a failed startup probe)
- **Issue:** the plan asked for httpGet `/readyz` and `/livez` probes together with `MERIDIAN_HOST 127.0.0.1`. kubelet httpGet probes connect to the pod IP, never to the pod's loopback, so they cannot reach a loopback-bound server. Separately, `/readyz` returned `503 [-]profiles failed: no profiles configured` because this deployment seeds a single credentials file, not a Meridian profile, while `/health` returned 200 with `loggedIn: true`.
- **Fix:** exec probes that run `node -e fetch('http://127.0.0.1:3456/...')` inside the container (the same method as Meridian's own Docker HEALTHCHECK): `/health` for startup and readiness, `/livez` for liveness. Meridian stays bound to 127.0.0.1, which keeps it unreachable from every other pod. Reasoning recorded in the comment header of `chat-bot.yaml` and in the README.
- **Files modified:** `deploy/k8s/base/chat-bot.yaml`, `deploy/k8s/README.md`
- **Verification:** full `kind-up.sh && kind-smoke.sh` passes, chat-bot pod 2/2 Running with 0 restarts; structural test asserts the startup probe, loopback host and read-only mode.
- **Committed in:** `7ba2485`

**2. [Rule 3 - Blocking] Dev Namespace needed its own file**
- **Found during:** Task 1
- **Issue:** the plan's file list has no home for the Namespace resource it requires (labelled warn/audit restricted), and `kind-up.sh` must create the namespace before the Secrets.
- **Fix:** added `deploy/k8s/overlays/dev/namespace.yaml`, listed in the overlay resources and applied first by `kind-up.sh`.
- **Files modified:** `deploy/k8s/overlays/dev/namespace.yaml`, `deploy/k8s/overlays/dev/kustomization.yaml`
- **Verification:** `kubectl kustomize`, kubeconform and a live apply (`namespace/ai-buddy unchanged` on the second apply)
- **Committed in:** `671d039`

**3. [Rule 3 - Blocking] kubectl 1.36 replaces the whole container list for `kubectl run --overrides`**
- **Found during:** Task 1 (adding a restricted securityContext to the smoke probe pod)
- **Issue:** an overrides patch naming only the container's securityContext produced `spec.containers[0].image: Required value`.
- **Fix:** the overrides carry the full container (image, command `python -`, env, securityContext); the probe script is passed on stdin. `SMOKE_QUERY` is refused when it contains a double quote or backslash, since it is embedded in the JSON.
- **Files modified:** `scripts/kind-smoke.sh`
- **Verification:** smoke passes with no Pod Security warning for the probe pod.
- **Committed in:** `671d039`

**4. [Process note - TDD] RED was only partly red**
- Task 3 is marked `tdd="true"` but the manifests it guards already existed from Tasks 1-2, so 17 of the 19 tests passed at the RED commit; the two that failed covered the Task 3 deliverables (validate-infra script, README, gitkeep removal). The RED commit is `f4878b5`.

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking) plus 1 process note
**Impact on plan:** The probe change keeps the plan's intent (Meridian unreachable from other pods, native sidecar start-order). No scope creep beyond one extra overlay file.

## Authentication Gates

None. The `meridian-claude` volume already existed and `kind-up.sh` read it without any login prompt.

## Issues Encountered

- A background wait on the first (failing) `kind-up.sh` run had to be killed after the Meridian probe diagnosis; the script was re-run after the fix and passed.
- `/tmp/x.yaml` was written briefly outside the scratchpad during a kustomize check and removed immediately.

## Environment and Tools Actually Run

- kind v0.33.0 was not installed; `kind-up.sh` downloaded it into `.cache/bin` and verified the sha256 (published checksum file). A mismatch path (`rm` plus abort) is in the script but was not exercised with a tampered file.
- The cluster `ai-buddy` is left running on the host (Docker container `ai-buddy-control-plane`). Tear down with `.cache/bin/kind delete cluster --name ai-buddy`.
- The real Max login (volume `meridian-claude`) was copied into a local kind Secret, as the plan specifies. It never left the machine and nothing was printed or committed (grep for token markers across the diff: none).
- kubeconform ran from `ghcr.io/yannh/kubeconform:v0.8.0` via Docker; kubectl is the host v1.36.0 (kustomize v5.8.1), server v1.37.0.
- Not exercised: a full Pub/Sub chat round trip on kind (it would spend real Max quota through Meridian); the smoke checks the Job, the Ready bot and the sidecar instead, as the plan requires.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-04-23 to T-04-26 covered: imperative Secret, read-only Meridian, pinned and checksummed kind, accepted hostPath exception).

## User Setup Required

None - no external service configuration required. Prerequisites that already hold on this host: Docker volume `meridian-claude`, `artifacts/index.db`.

## Next Phase Readiness

- 04-09 appends actionlint and the sync image build below the marked line in `scripts/validate-infra.sh`, and can wire `validate-infra.sh` into CI (needs kubectl and Docker on the runner).
- The Meridian token in the volume ages: if kind's read-only Meridian reports an expired login, refresh it with the Compose live profile and re-run `kind-up.sh` (README).
- Cloud Run YAML (04-08) can reuse the env contract table in `deploy/k8s/README.md`.

## Self-Check: PASSED

- Files: all 15 created files exist; `deploy/k8s/.gitkeep` absent.
- Commits: `671d039`, `7ba2485`, `f4878b5`, `e127a5d` present in `git log`.
- Acceptance: `grep -c '/healthz'` base 3 (>=2); `MCP_ALLOWED_HOSTS` in overlay 1; `sha256sum` in kind-up 3 (>=1); `kind smoke ok` in smoke 1; `restartPolicy: Always` 1; `secretKeyRef` 3; `kubectl create secret generic` 2; kubeconform image 1; 19 test functions; `.gitkeep` gone.
- Verification: `scripts/kind-up.sh && scripts/kind-smoke.sh` exit 0; `scripts/validate-infra.sh` exit 0; `./run-unit-tests.sh --all` exit 0.
