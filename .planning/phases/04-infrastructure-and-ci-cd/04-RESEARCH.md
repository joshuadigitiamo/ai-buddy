# Phase 4: Infrastructure and CI/CD - Research

**Researched:** 2026-11-14
**Domain:** Docker/compose, Kustomize on kind, Cloud Run (europe-west8) YAML with sidecar and GCS volume, GitHub Actions + Workload Identity Federation, GCS-based index handoff and video hosting
**Confidence:** MEDIUM (platform docs verified; five live-only behaviours are unverifiable offline and are listed as live-checkpoint items)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Hosting platform**
- **D-01:** Cloud Run free tier stays the production host (D7 kept). No-card hosts (Render, HF Spaces, Oracle Free, self-hosted k3s) are rejected: they would replace Firestore, Pub/Sub, WIF and the `K_SERVICE` auth guards.
- **D-02:** Joshua provides a GCP project with an active billing account during this phase. (Update 2026-11-14: provided; existing project `ai-buddy-dev` under the digitiamo.com organization, billing linked; id in docs/internal/gcp-project.md, gitignored.) Plans include a **live deploy checkpoint** (real Cloud Run, WIF, Chat HTTP JWT, bot-to-MCP ID token, claude.ai connector check, non-digitiamo rejection). Static checks (YAML schema, workflow lint, dry runs) still run in CI.
- **D-03:** Region europe-west8 (Milano). The researcher verifies availability there of Cloud Run (incl. sidecars and GCS volume mounts), Firestore, Artifact Registry and free-tier eligibility. Fallback to europe-west1 only if a blocker is found, and only after asking Joshua. — **Reversibility:** one-way — a Firestore database location cannot be changed after creation; moving it means a new database and data migration.
- **D-04:** CI deploys automatically on push to `main` after `run-unit-tests.sh --all` passes and the image is pushed (no manual approval environment).
- **D-05:** Gap log and thread memory stay on Firestore. Add a native Firestore TTL policy on `expire_at` (03-07 left expiry read-side until Phase 4).

**Index + sync handoff (closes D-12 / ADR 0001)**
- **D-06:** Sync runs on Joshua's laptop (handbook snapshot and Guides checkout mounted read-only, as today) and publishes `index.db` to a private GCS bucket through a new `GcsArtifactStore` adapter. `mcp_server` reads the bucket at cold start. The image stays generic (no handbook content), the same image runs in compose, kind and Cloud Run (INFRA-01). — **Reversibility:** costly — ADR 0001 must be updated to record the choice; switching to a baked image later changes CI, image privacy and INFRA-01.
- **D-07:** The nightly Cloud Scheduler trigger is dropped. Sources change only when Joshua edits them locally, so a nightly run would rebuild identical data. Reword INFRA-04 and ROADMAP Phase 4 criterion 3: sync runs on demand from the laptop.
- **D-08:** After a successful publish, the sync publish step (or a helper script run with it) forces a new `mcp_server` Cloud Run revision so the next request loads the new index. No hot reload; Phase 1 D-11 (cold-start load) stays.
- **D-09:** No Cloud Run Job YAML for sync. Sync keeps its own Dockerfile stage and its own path-filtered CI test path. INFRA-04 is reworded to "Cloud Run YAMLs for `mcp_server` and `chat_bot`".
- **D-10:** Compose and kind use `LocalDirArtifactStore` (shared volume in compose, hostPath / kind extraMount in kind). `GcsArtifactStore` is used only on Cloud Run and is unit-tested with a fake. The store is selected by configuration (the audit found `snapshot.py:77` hard-wires the local store).

**Deployed bot + LLM**
- **D-11:** `chat_bot` runs on Cloud Run with `LLM_BACKEND=meridian`, Meridian as a sidecar container in the same service. D1a guards stay in force: Chat app visible to Joshua only, `ALLOWED_USERS` single entry, startup refusal with more than one user. Joshua accepts that this puts his Max session in the cloud.
- **D-12:** Max credentials live on a private GCS bucket mounted at `/home/claude/.claude` through a Cloud Run GCS FUSE volume, so token refreshes written by Meridian persist across restarts. Seeded once from the local `meridian-claude` volume. Bucket IAM: the Meridian/bot runtime service account only. Never baked into an image, never in the repo, never echoed.
- **D-13:** Cloud Run intake is HTTP + Google JWT (D13, verifier built in 03-10). Pub/Sub intake stays for laptop dev and compose.
- **D-14:** CI builds Meridian from the approved commit `cafdcf780f1b40c8f0dee17481132f47b4cbb353` and pushes it to the private Artifact Registry. A Meridian bump is a reviewed SHA change.
- **D-15:** kind runs the full stack: `mcp_server`, `chat_bot`, Meridian and the Firestore + Pub/Sub emulators. Max credentials reach the cluster without being committed (k8s Secret created from the local volume, or hostPath); exact mechanism is the planner's choice, it must not write credential values into manifests.

**Video hosting (Phase 3 carry-over, ROADMAP criterion 5)**
- **D-16:** Videos are served from a private GCS bucket, uploaded with `Content-Type: video/mp4`. The Guarda link is the authenticated browser URL `https://storage.cloud.google.com/<bucket>/<object>#t=<seconds>`; access by IAM grant to Joshua's account (a domain group later). No expiring signed URLs in chat cards. Researcher verifies inline playback and `#t=` seeking on that URL. [Medium]
- **D-17:** The laptop sync step uploads changed mp4s (by content hash) and writes the GCS URLs into the video map, so one command refreshes index and videos.
- **D-18:** Timestamp coverage target: every Guides section whose guide has a video gets a scene offset (from `sections.yaml` / durations); sections without one fall back to the full video at 0. Coverage is measured and reported against today's 238/2524 scene-mapped rows.

### Claude's Discretion
- Secrets layout (Secret Manager vs plain env per variable), service-account split, IAM role set.
- CI structure: reusable workflow vs per-service files; how shared paths (`packages/buddy_core`, `buddy_mcp/models.py` imported by the bot) trigger dependent services.
- Manifest validation tools (kubeconform / kustomize build checks), workflow lint (actionlint), Cloud Run YAML validation.
- kind credential mechanism for Meridian (within D-15 limits).
- SIGTERM drain handler for Cloud Run (03-11 left the interpreter default).

### Deferred Ideas (OUT OF SCOPE)
- Cloud Run Job + nightly Scheduler for sync: only if sources move to the cloud.
- Videos on Google Drive (domain-shared): before any non-dev user (D15).
- `LLM_BACKEND=api` (Console or Vertex EU) on Cloud Run: before any second user (D1a).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | One Dockerfile per service (`mcp_server`, `chat_bot`, `jobs/sync`) on Python 3.12; same image in compose, kind and Cloud Run | Dockerfile has stages `base`, `test`, `mcp_server`, `chat_bot`; add a `sync` stage (git + buddy_core + jobs/sync + google-cloud-storage). Store/auth selected by env so one image serves all three targets (Standard Stack, Pattern 1, Pitfall 7, 8) |
| INFRA-02 | `docker compose` starts all services plus Firestore and Pub/Sub emulators; a chat event completes a round trip locally | Single `docker-compose.yml` with profiles; hermetic smoke profile needs a recording Chat adapter and an Anthropic-compatible stub (Pattern 4, Pitfall 12) |
| INFRA-03 | kind manifests (Kustomize base + overlays) deploy the services and pass manifest validation (KUBERNETES_GUIDE) | `kubectl kustomize` (v5.8.1 on host) + kubeconform v0.8.0 image + kind v0.33.0; native sidecar for Meridian; `MCP_ALLOWED_HOSTS` fixes the 421 (Pattern 5, Pitfall 8) |
| INFRA-04 | Cloud Run YAMLs for `mcp_server` and `chat_bot` (reworded per D-07/D-09: no sync job, no Scheduler), europe-west8, request-based, scale-to-zero, stateless, `ArtifactStore` bucket read wired in | Service YAML with sidecar and `gcsfuse.run.googleapis.com` volume; `GcsArtifactStore`; forced-revision step (Pattern 2, 3, 6) |
| INFRA-05 | Path-filtered GitHub Actions: build, push to Artifact Registry, deploy, WIF with no key files | Per-service workflows over one reusable workflow; direct/impersonated WIF with numeric repo id (Pattern 7, Security) |
| INFRA-06 | CI runs `run-unit-tests.sh --all` as a required check before any image push | `needs: test` gate; `git update-index --chmod=+x run-unit-tests.sh` (Pitfall 11) |
</phase_requirements>

## Summary

The system already has everything a deployment needs except the glue: Dockerfile stages for the two services, a dev compose, config via env, ID-token auth between the bot and the server, and an HTTP intake. Phase 4 adds (a) a `sync` image stage, (b) a store selector plus `GcsArtifactStore`, (c) compose/kind/Cloud Run definitions, (d) path-filtered CI with keyless auth, and (e) video hosting on a private bucket. The tooling is available and current: `google-github-actions/auth` v3, `docker/*` v4/v7 actions, kind v0.33.0 (default node image Kubernetes 1.37.0), kubeconform v0.8.0, actionlint 1.7.12 (all verified this session). `europe-west8` is listed for Cloud Run (Tier 1), Firestore, Artifact Registry and Cloud Storage, so no D-03 blocker was found.

Five things cannot be proven offline and must be live-checkpoint items with a prepared fallback: (1) a `chat_bot` run longer than the 25 s answer window under request-based billing (CPU is reclaimed after the response, so the background task that patches the placeholder can stall); (2) cold start of a service whose sidecar image is 2.48 GB locally against Chat's ~30 s HTTP deadline; (3) posting replies through the Chat API with the runtime service account and no key file; (4) Meridian refreshing OAuth tokens on a GCS FUSE mount (no file locking, last-writer-wins) while three copies of the same token chain exist (compose volume, kind, Cloud Run); (5) inline playback and `#t=` seeking on `storage.cloud.google.com` URLs. A sixth risk is data, not platform: only 2 of the 15 videos with chunk rows have a `sections.yaml`, and only 7 have `durations.json` locally, so D-18 cannot reach "every section" without Guides-repo work (Pitfall 14).

Four code changes are needed in the Python services and are in scope as Phase 4 tasks: store selector (audit warning 1), explicit deployed/local marker replacing the `K_SERVICE`-only guard (warning 4), an extra allowed Host for pod-to-pod calls (warning 5) and a `/healthz` route on `mcp_server`. All other audit warnings are closed by configuration or CI structure.

**Primary recommendation:** Build in this order: code seams (store selector, `DEPLOY_ENV`, `MCP_ALLOWED_HOSTS`, `/healthz`, recording Chat adapter) -> compose smoke -> Kustomize/kind -> Cloud Run YAML + structural tests -> workflows (static) -> live checkpoint with Joshua's GCP project -> video upload and timestamp work. Keep the instance-based-billing switch (`run.googleapis.com/cpu-throttling: 'false'` on `chat_bot` only) ready as the documented fallback for Pitfall 1, but do not apply it without Joshua's consent because success criterion 3 says request-based.

## Project Constraints (from CLAUDE.md)

No project-level `CLAUDE.md` exists in the repo. Global `~/.claude/CLAUDE.md` directives that apply [VERIFIED: system context]:
- Python only (infra YAML, shell and workflow files are unavoidable; no Node/Go app code). Ubuntu/bash only.
- Everything runs in Docker: tests, lint, sync. New infra checks (kubeconform, actionlint, gcloud dry-run) run from Docker images, not host installs. The host has `kubectl` already (see Environment Availability).
- `run-unit-tests.sh` convention (`--all`, `--single`, `--single-file`, plus the repo's `--emulator`) stays the CI entry point.
- ruff + mypy `--strict` + pytest with coverage (`--cov-fail-under=80`, already in the script).
- Never echo `.env` contents or secrets; pass secrets through env files / Secret Manager.
- No commits or pushes without an explicit ask. Project memory: work on `main`, no branches; repo is public, internal docs only under `docs/internal/`.
- Ignore cost-warning notices (project memory); the free-hosting goal is still a design input (see Cost table).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Index build and video upload | Laptop (Docker `sync` image) | GCS (storage target) | D-06/D-17: sources are local and private; image stays generic |
| Index storage and cold-start load | GCS bucket (europe-west8) | `mcp_server` (reader) | D-06; 6.4 MB file [VERIFIED: `ls -la artifacts`: `6443008` bytes] |
| Retrieval over MCP | `mcp_server` (Cloud Run / kind / compose) | Firestore (gap log, OAuth state) | D10 stateless JSON |
| Chat intake and answer | `chat_bot` (HTTP on Cloud Run; Pub/Sub in compose/kind) | Meridian sidecar, Chat API | D-11, D-13 |
| LLM call | Meridian sidecar (localhost) | none | Same instance, loopback only |
| Gap log and thread memory expiry | Firestore TTL policy | read-side check (`memory.py`) | D-05; TTL deletes lag up to 24 h |
| Max credential persistence | GCS bucket via FUSE volume | none | D-12 |
| Video delivery | GCS (browser, `storage.cloud.google.com`) | Google login cookie | D-16; bypasses the bot entirely |
| Build, test, push, deploy | GitHub Actions | Artifact Registry, Cloud Run | D-04, D-12 (PROJECT.md D12) |
| Auth to GCP from CI | WIF (no keys) | impersonated deployer SA | INFRA-05 |
| Auth enforcement in services | App-level (JWT, OAuth) | Cloud Run invoker IAM disabled | Both services must be reachable by non-Google-IAM callers (claude.ai, Chat) |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `google-github-actions/auth` | v3.0.0 (SHA `7c6bc770dae815cd3e89ee6cdf493a5fab2cc093`, published 2025-08-28) | WIF login | Official; guide CICD §13 prescribes it [VERIFIED: gh api releases, tags] |
| `google-github-actions/setup-gcloud` | v3.0.1 (SHA `aa5489c8933f4cc7a4f7d45035b3b1440c9c10db`) | gcloud for `services replace` | Official [VERIFIED: gh api] |
| `docker/setup-buildx-action` | v4.4.1 (SHA `f87e5991a6d7451dcb8d9637bfbc97413f497069`) | buildx | [VERIFIED: gh api] |
| `docker/build-push-action` | v7.4.0 (SHA `c3c9e263c25d99ce0380d002d59b67737d91b0dc`) | build + push, git-context for Meridian | [VERIFIED: gh api] |
| `docker/login-action` | v4.8.0 (SHA `8aa5831fb8d48d8f76594c7ddde61ae58019f550`) | AR login with access token | [VERIFIED: gh api] |
| `actions/checkout` | v7.0.1 (SHA `3d3c42e5aac5ba805825da76410c181273ba90b1`) | checkout | [VERIFIED: gh api] |
| kind | v0.33.0 (2026-08-26), default node `kindest/node:v1.37.0` | local cluster | [VERIFIED: gh api release body; `docker manifest inspect kindest/node:v1.37.0` OK] |
| `kubectl kustomize` | kubectl v1.36.0 / Kustomize v5.8.1 on host | build overlays | [VERIFIED: `kubectl version --client`] |
| kubeconform | v0.8.0 image `ghcr.io/yannh/kubeconform:v0.8.0` | manifest schema validation | [VERIFIED: `docker manifest inspect` OK; flags from project README] |
| actionlint | image `rhysd/actionlint:1.7.12` | workflow lint | [VERIFIED: `docker manifest inspect` OK; release 2026-03-30] |
| gcloud | `google/cloud-sdk:592.0.0-emulators` (already used by `docker-compose.test.yml`) | `run services replace --dry-run`, Firestore TTL, IAM bootstrap | [VERIFIED: `gcloud version` in that image; `--dry-run` flag in its `--help`] |
| `google-cloud-storage` (Python) | 3.17.1 (2026-10-15), `requires_python >=3.10` | `GcsArtifactStore`, video upload | Official Google library [VERIFIED: pypi json] |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| Dependabot `github-actions` ecosystem | n/a | bump pinned action SHAs weekly | Guide CICD §14 [CITED: CICD_GUIDE.md §14] |
| Cloud Run YAML (`serving.knative.dev/v1` Service) | n/a | service definition, deployed with `gcloud run services replace` | Only way to define sidecars (flags cannot) [CITED: docs.cloud.google.com/run/docs/deploying#sidecars] |
| Secret Manager | n/a | 5 secrets (see Pitfall 16) | `valueFrom.secretKeyRef` in the YAML |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Impersonated deployer SA (recommended) | Pure direct WIF (`principalSet` on every resource) | Direct is the guide's preference, but `docker login` needs an OAuth access token, which the auth action emits only with `service_account` set [CITED: CICD_GUIDE.md §13]; and granting `serviceAccountUser` to a `principalSet` is unverified here. Impersonation still stores no key |
| Native `on.push.paths` per-service workflows (recommended) | `dorny/paths-filter` v4.0.3 | Native needs no third-party action and no extra job. The "required-check trap" [CITED: CICD_GUIDE.md §9] does not apply while nobody opens PRs against protected `main`; add an always-run gate job if that changes |
| `gcloud run services replace` (recommended) | `google-github-actions/deploy-cloudrun@v3` with `metadata:` | The action ignores every other input in YAML mode and its docs do not mention multi-container YAML [CITED: github.com/google-github-actions/deploy-cloudrun] |
| `GcsArtifactStore` (locked D-06) | Mount the artifact bucket read-only through the same FUSE volume and keep `LocalDirArtifactStore` | Zero new code, but contradicts D-06/D-10; mention only as an escape hatch if the adapter causes trouble |

**Installation (Python, one new pin):**
```bash
# services/mcp_server/requirements.txt and a new jobs/sync/requirements.txt
google-cloud-storage==3.17.1
# requirements-dev.txt: add "-r jobs/sync/requirements.txt"
```

**Version verification:** all versions above were read from the GitHub releases API, PyPI JSON and `docker manifest inspect` on 2026-11-14.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| google-cloud-storage | PyPI | latest 3.17.1 published 2026-10-15; project is the long-running official Google library (versions back to 0.20) | not reported by the seam | github.com/googleapis/google-cloud-python (packages/google-cloud-storage) | SUS (`too-new`, `unknown-downloads` on the latest version only) | Flagged. Planner adds a `checkpoint:human-verify` before the pin, as 02-01 and 03-01 did for earlier pins |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `google-cloud-storage` `[WARNING: flagged as suspicious — verify before using.]` The flag comes from the newest release date and missing download data; the package name, repository and release history are the official Google ones. Joshua may prefer 3.16.0 if he wants an older release.

Non-Python tools (kind, kubeconform, actionlint, GitHub Actions) are binaries or actions, not installed packages: provenance is the GitHub release / image manifest checks above. Download the kind binary with its published `.sha256sum` [VERIFIED: release assets `kind-linux-amd64`, `kind-linux-amd64.sha256sum`].

## Architecture Patterns

### System Architecture Diagram

```
LAPTOP (Docker, host uid)                          GITHUB (public repo, push to main)
  Guides checkout (ro) + handbook (ro)               path filter -> per-service workflow
     |                                                  |  test: run-unit-tests.sh --all
     v                                                  |  build image (git SHA tag)
  [sync upload-videos]--mp4 (md5 changed)--+            |  push -> Artifact Registry (WIF)
     |                                     v            |  deploy: gcloud run services replace
  [sync run] (offline) -> index.db         GCS videos   v
     |   (video URLs -> storage.cloud...)  bucket     CLOUD RUN europe-west8
     v                                       ^         +----------------------------------+
  [sync publish]--index-<build>.db+pointer-->GCS index | mcp_server  <--ID token-- chat_bot |
     |                                       bucket    |  (GcsArtifactStore,    +Meridian   |
     v                                         |       |   cold start load)     sidecar     |
  gcloud run services update mcp-server        +-read->|   |   Firestore (gaps,  localhost  |
  (new revision = new index)                           |   |   oauth, memory)    :3456      |
                                                       +---|-----------|--------|----------+
 claude.ai connector --OAuth/Google login--> mcp_server    |           ^        | GCS FUSE
 Google Chat --HTTP + Google JWT-----------> chat_bot -----+           |        v
 Chat API <-- replies (runtime SA) <-------- chat_bot            Chat   .claude bucket (Max creds)

LOCAL: docker compose (profiles: default / meridian / smoke)  and  kind (Kustomize base + dev overlay)
  Pub/Sub emulator -> chat_bot -> mcp_server (LocalDirArtifactStore volume) -> Firestore emulator
  smoke: recorded Chat event -> stub LLM -> recording Chat adapter -> assertion
```

### Recommended Project Structure
```
Dockerfile                       # + `sync` stage
docker-compose.yml               # INFRA-02: emulators, mcp_server, chat_bot, sync; profiles meridian, smoke
deploy/
  meridian.version               # approved SHA, single source for compose, CI and docs (D-14)
  compose/                       # pubsub_init.py, smoke assets (stub LLM, expected answer)
  k8s/base/                      # deployments, services, emulators, kustomization.yaml
  k8s/overlays/dev/              # kind: hostPath artifact dir, secrets generator hooks, DEPLOY_ENV=local
  k8s/kind-config.yaml           # cluster config (extraMounts); NOT a manifest for kubeconform
  cloudrun/mcp-server.yaml       # placeholders: PROJECT_ID, PROJECT_NUMBER, IMAGE_TAG
  cloudrun/chat-bot.yaml
  cloudrun/bootstrap.md|sh       # one-time: project APIs, Firestore db, buckets, WIF, IAM, TTL
.github/workflows/
  _test.yml  _deploy.yml         # reusable (workflow_call)
  mcp-server.yml  chat-bot.yml  sync.yml  meridian.yml
scripts/
  sync-and-publish.sh            # upload-videos -> run -> publish -> new revision (D-08, D-17)
  validate-infra.sh              # kustomize build | kubeconform, actionlint, gcloud dry-run (no network needed except images)
  kind-up.sh  kind-smoke.sh
tests/unit/                      # structural guards (pattern of tests/unit/test_dev_compose.py)
```

### Pattern 1: Store selector and `GcsArtifactStore` (closes audit warning 1, D-10)
**What:** `snapshot.resolve_index_path(artifact_dir)` currently builds `LocalDirArtifactStore` itself. Replace with a factory chosen by settings (`ARTIFACT_STORE=local|gcs`, `ARTIFACT_BUCKET`, `ARTIFACT_PREFIX`; `ARTIFACT_DIR` stays the local path / download cache). `McpSettings.artifact_dir` is a required field today, so make it default to a temp dir when `gcs`.
**In-repo values (read this session):**
- `packages/buddy_core/buddy_core/store.py:12-13`: `INDEX_NAME: Final[str] = "index.db"` and `MANIFEST_NAME: Final[str] = "index.manifest.json"`.
- `store.py:16-25`: `class ArtifactStore(Protocol)` with `def latest_path(self) -> Path | None`, `def staging_path(self) -> Path`, `def publish(self, staged: Path, meta: IndexMeta) -> Path`, `def discard(self, staged: Path) -> None`.
- `services/mcp_server/buddy_mcp/snapshot.py:77`: `path = LocalDirArtifactStore(artifact_dir).latest_path()`.
- `services/mcp_server/buddy_mcp/cli.py:93`: `snapshot = load_snapshot(resolve_index_path(settings.artifact_dir))`.
**Recommended GCS layout:** upload `index-<build_id>.db` first, then overwrite the pointer object `index.manifest.json` (contents already include `build_id`, `sha256`, `size_bytes`). The reader downloads the pointer, then the named object, verifies `sha256`, returns a local path under `/tmp`. A reader can never pair a new pointer with a half-written db, and old builds remain for rollback (add a lifecycle rule deleting objects older than ~30 days). This keeps the four-method port unchanged.
```python
# Source: shape of the existing ArtifactStore Protocol; google-cloud-storage client API [ASSUMED: verify method names against 3.17.1 at implementation]
class GcsArtifactStore:
    def __init__(self, bucket: "BucketPort", prefix: str, cache_dir: Path) -> None: ...
    def latest_path(self) -> Path | None:   # read pointer -> download -> sha256 check -> Path
        ...
    def staging_path(self) -> Path:         # local temp file, like LocalDirArtifactStore
        ...
    def publish(self, staged: Path, meta: IndexMeta) -> Path:  # upload db, then pointer last
        ...
    def discard(self, staged: Path) -> None: ...
```
Unit-test it with a fake `BucketPort` (D-10); do not give the unit tests network access (`run-unit-tests.sh` runs `--network none`). `google.cloud.storage` may need a mypy override if it ships no `py.typed` [ASSUMED]; `pyproject.toml` already has this pattern for pubsub.

### Pattern 2: Cloud Run service YAML with sidecar and GCS volume
**What:** `serving.knative.dev/v1` Service; `chat_bot` is the ingress container (only one container may declare a port, max 10 containers) and Meridian is a sidecar on `localhost:3456`. GCS volume mounts need gen2 and the driver `gcsfuse.run.googleapis.com`; the mount must succeed within 30 s before containers start; no container changes needed.
```yaml
# Source: docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts,
#         docs.cloud.google.com/run/docs/deploying#sidecars, docs.cloud.google.com/run/docs/reference/yaml/v1,
#         docs.cloud.google.com/run/docs/internet-proxy-nginx-sidecar (container-dependencies syntax)
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: chat-bot
  annotations:
    run.googleapis.com/invoker-iam-disabled: 'true'   # app verifies the Chat JWT itself (D-13)
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/execution-environment: gen2        # required for volume mounts
        autoscaling.knative.dev/minScale: '0'                  # scale to zero
        autoscaling.knative.dev/maxScale: '1'                  # one Meridian = one token writer (Pitfall 4)
        run.googleapis.com/startup-cpu-boost: 'true'
        run.googleapis.com/container-dependencies: '{chat-bot: [meridian]}'   # meridian starts first
        # run.googleapis.com/cpu-throttling is absent => request-based billing [CITED: billing-settings]
    spec:
      serviceAccountName: sa-chat-bot@PROJECT_ID.iam.gserviceaccount.com
      containers:
        - name: chat-bot
          image: europe-west8-docker.pkg.dev/PROJECT_ID/ai-buddy/chat-bot:IMAGE_TAG
          ports: [{containerPort: 8080}]
          env: [...]  # INTAKE=http, LLM_BACKEND=meridian, LLM_BASE_URL=http://localhost:3456, MCP_AUTH=google_id_token, ...
        - name: meridian
          image: europe-west8-docker.pkg.dev/PROJECT_ID/ai-buddy/meridian:cafdcf780f1b40c8f0dee17481132f47b4cbb353
          startupProbe: {httpGet: {path: /readyz, port: 3456}}   # /readyz is Meridian's readiness route
          volumeMounts: [{name: claude-creds, mountPath: /home/claude/.claude}]
      volumes:
        - name: claude-creds
          csi:
            driver: gcsfuse.run.googleapis.com
            readOnly: false
            volumeAttributes: {bucketName: BUCKET_NAME_CREDS}
```
The Cloud Run docs page for sidecars says the dependency annotation is not described there but the nginx tutorial uses `"{nginx: [hello]}"`; the tutorial YAML also sets `run.googleapis.com/launch-stage: BETA` "required to use Cloud Run multi-containers (preview feature)". Whether that annotation is still required after the feature left preview is not stated on the page: keep it in the YAML only if `gcloud run services replace --dry-run` rejects the file without it [ASSUMED: sidecars are GA; check at the dry run].

### Pattern 3: Environment contract per target (one image, three hosts)
| Variable | compose | kind dev overlay | Cloud Run |
|----------|---------|------------------|-----------|
| `ARTIFACT_STORE` | local | local | gcs |
| `DEPLOY_ENV` (new) | local | local | production |
| `AUTH_MODE` (mcp) / `MCP_AUTH` (bot) | `off` / `none` | `off` / `none` | `on` / `google_id_token` |
| `INTAKE` | pubsub | pubsub | http |
| `LLM_BACKEND` / `LLM_BASE_URL` | meridian profile or stub | meridian (read-only creds) | meridian / `http://localhost:3456` |
| `MCP_URL` | `http://localhost:8000/mcp` (shared netns) or `http://mcp_server:8000/mcp` with `MCP_ALLOWED_HOSTS` | `http://mcp-server:8000/mcp` | public `https://mcp-server-<PROJECT_NUMBER>.europe-west8.run.app/mcp` |
In-repo names quoted from `.env.example` and config: `ARTIFACT_DIR`, `AUTH_MODE`, `MCP_PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `BOT_SA_EMAILS`, `OAUTH_STORAGE`, `GAP_COLLECTION`, `ALLOWED_USERS`, `LLM_BACKEND`, `LLM_BASE_URL`, `MCP_URL`, `MCP_AUTH`, `MCP_AUDIENCE`, `INTAKE`, `PUBSUB_SUBSCRIPTION`, `CHAT_JWT_AUDIENCE`, `CHAT_JWT_ISSUER_EMAIL`, `VIDEO_THUMBNAIL_URL` (`.env.example` read); secrets named in `config.py` / README: `THREAD_KEY_SECRET`, `MERIDIAN_API_KEY`, `GOOGLE_CLIENT_SECRET`, `OAUTH_JWT_SIGNING_KEY`, `OAUTH_STORAGE_ENCRYPTION_KEY`.
Audience circularity: `MCP_AUDIENCE` (bot) must equal `MCP_PUBLIC_BASE_URL` (server). Cloud Run's deterministic URL `https://[TAG---]SERVICE_NAME-PROJECT_NUMBER.REGION.run.app` is known before the first deploy [CITED: docs.cloud.google.com/run/docs/triggering/https-request], so both values can be placed in the YAML up front. Add a post-deploy smoke step that calls an authenticated tool (audit warning 2).

### Pattern 4: Compose round trip (INFRA-02)
**What:** one `docker-compose.yml` with profiles; migrate `tests/unit/test_dev_compose.py` to it (it currently pins `{"meridian", "firestore", "mcp_server", "chat_bot"}` and "no service publishes a port" for `docker-compose.dev.yml`) and delete the dev file in the same plan.
- Default profile: `firestore`, `pubsub` (`google/cloud-sdk:592.0.0-emulators`, command `gcloud beta emulators pubsub start --host-port=0.0.0.0:8085 --project=demo-ai-buddy` as in `docker-compose.test.yml`), `pubsub-init` (one-shot Python using `google-cloud-pubsub` from the `chat_bot` image to create topic + subscription idempotently), `sync` (one-shot, `buddy_sync run`, writes the shared artifact volume), `mcp_server`, `chat_bot`.
- `meridian` profile: the real LLM and the real Chat API, as `docker-compose.dev.yml` does today (needs the `meridian-claude` volume and a bot SA key).
- `smoke` profile: fixture handbook (`tests/fixtures/handbook`, 4 pages) and fixture Guides repo (`tests/fixtures/guides_repo`), an Anthropic-compatible stub and a recording Chat adapter, so the round trip is hermetic and runnable in CI.
**Why a stub and a recording adapter are needed:** `build_chat_client()` calls `google.auth.default(scopes=[CHAT_BOT_SCOPE])` and talks to the real Chat API; the LLM client goes to `LLM_BASE_URL`. There is no emulator for Chat. Both are behind ports: `ChatApi` (`create_message`, `update_message`) and `LlmClient.structured(...)` [VERIFIED: `services/chat_bot/buddy_bot/ports.py`]. Recommended: a `CHAT_API=google|recording` setting (recording appends JSON lines to a path; refused whenever `DEPLOY_ENV=production` or `K_SERVICE` is set) and an Anthropic-compatible `/v1/messages` stub under `deploy/compose/` that answers by matching the schema title in the system prompt (`Reformulation`, `RetryPlan`, `ContactExtraction`, `AnswerDraft`) and copying a `source_url` out of the user message for `AnswerDraft.citations`. Field shapes quoted from `schemas.py`: `Reformulation(standalone_question, keywords_it, keywords_en, intent: Literal["question","chitchat","off_topic"], sensitive_topic)`, `AnswerDraft(answer: str, citations: list[str], grounded: bool, confidence: float)`.
**Event and user:** reuse `tests/fixtures/chat_events/legacy_dm_message.json`; the test constants are `PROJECT = "demo-ai-buddy"` and `ALLOWED_USER = "users/111111111111111111111"` [VERIFIED: tests/integration/test_bot_process.py]. The smoke script publishes the fixture to the emulator topic, then polls the recording file for the final message (with a timeout), then asserts it contains the handbook citation `handbook://`.
The alternative (an alternate composition root only in tests) is rejected: the smoke would not exercise `cli._run`.

### Pattern 5: Kustomize base + dev overlay on kind (INFRA-03)
- `base/`: Deployments + Services for `mcp-server`, `chat-bot`, `meridian`, `firestore-emulator`, `pubsub-emulator`; a one-shot Job `pubsub-init`; ConfigMaps with non-secret env; labels `app.kubernetes.io/*` (KUBERNETES_GUIDE §28); `requests` and `limits` on every container (§13 rule of thumb: "Always set both requests and limits in production"); non-root `securityContext` (uid 10001 matches the image; §23 Pod Security Standards).
- `meridian` in the same Pod as `chat-bot` as a **native sidecar** (`initContainers` entry with `restartPolicy: Always` and a startup probe) [CITED: KUBERNETES_GUIDE §15 "Native sidecar containers - use this now"]. This gives start-order for free and mirrors Cloud Run. Alternatively a separate Deployment; the sidecar keeps `LLM_BASE_URL=http://localhost:3456` identical to Cloud Run.
- Probes (KUBERNETES_GUIDE §12: liveness must not check dependencies): `mcp-server` readiness/liveness `httpGet /healthz` (new route, see Pitfall 9); `chat-bot` in `INTAKE=pubsub` has no HTTP port, so use no HTTP probe (restart policy only) or an `exec` heartbeat; Meridian `GET /readyz` for readiness and `/livez` for liveness [CITED: Meridian docs/configuration.md at the pinned SHA].
- Dev overlay: `kind-config.yaml` `extraMounts` of the artifact dir, `hostPath` volume at `/artifacts` read-only, `DEPLOY_ENV=local`, `AUTH_MODE=off`, `MCP_AUTH=none`, `MCP_ALLOWED_HOSTS=mcp-server`.
- Images reach kind with `kind load docker-image` (images are not pushed anywhere).
- Meridian credentials in kind: create the Secret imperatively in `scripts/kind-up.sh` (`kubectl create secret generic meridian-credentials --from-file=.credentials.json=<(docker run --rm -v meridian-claude:/s:ro alpine:3 cat /s/.credentials.json)`), mounted through an init copy into an `emptyDir`, and set `MERIDIAN_CREDENTIALS_READONLY=1` so the kind instance never refreshes or writes tokens (Pitfall 5). No credential value enters a manifest or the repo; the secret name appears in manifests, the value does not.
- Validation: `kubectl kustomize deploy/k8s/overlays/dev | docker run -i ghcr.io/yannh/kubeconform:v0.8.0 -strict -summary -kubernetes-version 1.37.0 -` (same for `base`). kubeconform reads stdin; piping kustomize output is an inference from its README, so the plan's first task proves it [CITED: github.com/yannh/kubeconform, ASSUMED for the pipe]. `kustomization.yaml` and the kind cluster config are not Kubernetes resources: validate the built output, not those files.

### Pattern 6: Forced revision after publish (D-08)
After a successful `publish`, run `gcloud run services update mcp-server --region europe-west8 --update-env-vars INDEX_BUILD_ID=<build_id>`. Any change to the revision template creates a new revision, and with the default `--to-latest` traffic it takes 100% [ASSUMED: standard Cloud Run behaviour, verify at the live checkpoint]. A later CI `services replace` also creates a revision and therefore reloads the index; the YAML does not need `INDEX_BUILD_ID`. The helper `scripts/sync-and-publish.sh` runs: `upload-videos` (network) -> `run` (offline, `--network none` as today) -> `publish` (network) -> gcloud update. Joshua's laptop needs ADC: mount a user ADC file read-only into the sync container for the two network steps only; do not bake or copy it.

### Pattern 7: CI structure (INFRA-05, INFRA-06)
```yaml
# .github/workflows/mcp-server.yml  (all third-party actions pinned by full SHA, CICD_GUIDE §14)
name: mcp-server
on:
  push:
    branches: [main]
    paths:                       # derived from the Dockerfile COPY lines, enforced by a drift test
      - "services/mcp_server/**"
      - "packages/buddy_core/**"
      - "requirements.txt"
      - "Dockerfile"
      - "deploy/cloudrun/mcp-server.yaml"
      - ".github/workflows/mcp-server.yml"
      - ".github/workflows/_*.yml"
  workflow_dispatch:
permissions: {}
concurrency: {group: deploy-mcp-server, cancel-in-progress: false}   # CICD §12: deploys never cancel
jobs:
  test:
    uses: ./.github/workflows/_test.yml          # runs ./run-unit-tests.sh --all
    permissions: {contents: read}
  deploy:
    needs: test                                  # INFRA-06: no push if test fails
    uses: ./.github/workflows/_deploy.yml
    with: {service: mcp-server, target: mcp_server}
    permissions: {contents: read, id-token: write}
```
- `chat_bot` paths additionally list exactly the two files its image copies from the server: `services/mcp_server/buddy_mcp/__init__.py` and `services/mcp_server/buddy_mcp/models.py` (`Dockerfile:48-49`: `COPY services/mcp_server/buddy_mcp/__init__.py services/mcp_server/buddy_mcp/__init__.py` and `COPY services/mcp_server/buddy_mcp/models.py services/mcp_server/buddy_mcp/models.py`). Success criterion 4 (a change under `services/mcp_server` triggers only that service) holds for every file except `models.py`/`__init__.py`, which also trigger the bot by design (audit warning 3). Write a unit test that parses the Dockerfile `COPY` sources of each runtime stage and asserts each is covered by that workflow's `paths`.
- `sync.yml`: test + `docker build --target sync` with no push and no deploy (D-09, no Cloud Run job). INFRA-05's "push and deploy" wording should be reworded for sync in the same change as INFRA-04.
- `meridian.yml`: triggers on `deploy/meridian.version`; builds `https://github.com/rynfar/meridian.git#<sha>` with `docker/build-push-action` and tags `meridian:<sha>`; `chat-bot` deploy fails early with a clear message if that tag is not in Artifact Registry.
- Auth step: `google-github-actions/auth` with `workload_identity_provider` and `service_account` (impersonated `ci-deployer`), `token_format: access_token` for `docker/login-action` (`registry: europe-west8-docker.pkg.dev`, `username: oauth2accesstoken`) [CITED: CICD_GUIDE §13]. WIF provider name, project id and service account email live in GitHub **repository variables**, not secrets and not the repo.
- Dry run before deploy: `gcloud run services replace deploy/rendered/<svc>.yaml --region europe-west8 --dry-run` ("only validates the configuration"; flag verified in the 592.0.0 CLI help) then the real replace. Render placeholders (`PROJECT_ID`, `PROJECT_NUMBER`, `IMAGE_TAG`) with `envsubst` into a temp file.
- Test job: `run-unit-tests.sh --all` builds `--target test` and runs ruff, ruff format, mypy, pytest with `--cov-fail-under=80` under `--network none` [VERIFIED: run-unit-tests.sh]; it uses `.env.example` when `.env` is absent, which is the CI case. Optionally add a second job running `./run-unit-tests.sh --emulator`.

### Anti-Patterns to Avoid
- **Service-account key files or `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run:** Cloud Run docs warn never to set it on a service with service identity [CITED: run/docs/securing/service-identity]. The dev compose key file stays dev-only.
- **WIF provider without an attribute condition:** the guide says it is mandatory for GitHub; use numeric ids.
- **Baking the index or credentials into any image** (ADR 0001 consequence, D-12).
- **Relying on `K_SERVICE` alone as the "deployed" marker** (audit warning 4).
- **Declaring a second `containerPort` on a sidecar:** only one container may expose a port [CITED].
- **Hand-written required-check gating around path filters** before PR flow exists.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyless CI auth | Stored JSON key in secrets | WIF via `google-github-actions/auth` | Tokens live 5-10 min; no rotation [CITED: auth README] |
| Mounting a bucket into a container | Download/upload loop for `.claude` | Cloud Run GCS volume (`gcsfuse.run.googleapis.com`) | Managed; no FUSE in the image [CITED] |
| Index download/upload | `requests` + manual auth + resumable upload | `google-cloud-storage` | Large mp4 uploads need resumable uploads and md5/crc handling |
| Video change detection | Own hash database | Compare local md5 with the blob's `md5_hash` metadata before upload [ASSUMED: field available on `Blob` after `reload`] | GCS stores it |
| Row expiry | Cron cleanup job | Firestore TTL policy [CITED: firestore/native/docs/ttl] | Native; deletes lag up to 24 h, keep the read-side check |
| Manifest validation | grep-based YAML checks | kubeconform + `kubectl kustomize` | Schema-aware |
| Workflow validation | Regex lint | actionlint | Knows expressions, runner labels, `needs` |
| Cloud Run YAML validation | Own schema | Structural pytest (repo already does this for compose) plus server-side `--dry-run` | No standalone JSON Schema is published; the YAML maps to the v1 API [CITED: run/docs/reference/yaml/v1] |
| Path filtering | Custom git-diff scripts | `on.push.paths` | Native; documented rules [CITED: CICD_GUIDE §9] |
| Image retention | Manual cleanup | Artifact Registry cleanup policy (keep last N) | Free tier is 0.5 GB |

**Key insight:** every hard part (identity, mounting, expiry, validation) has a managed or standard answer; the Phase 4 code is thin configuration plus the four seams listed in the Summary.

## Runtime State Inventory

Not a rename/refactor phase, but it creates runtime state. State that exists after the phase and must be provisioned outside git (one-time bootstrap, documented in `deploy/cloudrun/bootstrap`):

| Category | Items | Action Required |
|----------|-------|------------------|
| Stored data | Firestore `(default)` database in europe-west8 (one-way, D-03); collections `gaps` and `thread_memory`; OAuth state collection | Create database; add TTL on `expire_at` for `gaps` and `thread_memory` (command in Code Examples); decide whether the OAuth collection needs a TTL (field name not verified) |
| Live service config | Cloud Run services; Chat app configuration (HTTP endpoint URL, audience = that URL); claude.ai connector URL; IAM bindings; Secret Manager entries | Manual/bootstrap steps listed for the live checkpoint |
| OS-registered state | None (D-07 dropped Cloud Scheduler) | None |
| Secrets/env vars | 5 Secret Manager secrets; GitHub repo variables (not secrets) for project id, WIF provider, deployer SA | Create; never echo |
| Build artifacts | Artifact Registry repo `ai-buddy` (cleanup policy); GCS buckets: index, videos, `.claude` credentials (all europe-west8, uniform bucket-level access, public access prevention) | Create; seed credentials bucket once from the local `meridian-claude` volume |

## Common Pitfalls

### Pitfall 1: Background work after the 25 s ack stalls under request-based billing
**What goes wrong:** `HttpIntake` awaits the run for `ACK_SECONDS` (25.0) then returns `{}`; a slower run continues in a task that later patches the placeholder [VERIFIED: `intake/http.py` header docstring and `ACK_SECONDS: Final = 25.0`]. With request-based billing "CPU is allocated only during request processing" [CITED: run/docs/configuring/billing-settings], so after the response the task has no CPU until another request arrives (and the instance may be reclaimed).
**How to avoid:** Keep request-based as specified, measure at the live checkpoint with a deliberately slow question. Prepared fallback: `run.googleapis.com/cpu-throttling: 'false'` on `chat_bot` only. Idle instances never stay beyond 15 minutes after the last request [CITED]; for one user the cost is expected to be small but the free tier for instance-based billing is not documented on the pages fetched [ASSUMED]. Needs Joshua's consent because it changes success criterion 3's wording.
**Warning signs:** placeholder "Sto cercando nelle fonti..." never replaced after slow answers.

### Pitfall 2: Cold start of a heavy sidecar vs Chat's deadline
**What goes wrong:** the local Meridian image is 2.48 GB (`docker images`: `aibuddy-meridian:latest 2.48GB`; compressed registry size unknown). The GCS mount must finish within 30 s before containers start [CITED]. A first message after idle can exceed Chat's ~30 s HTTP deadline (the 25 s ack assumes it).
**How to avoid:** `startup-cpu-boost`, startup probes on both containers (the docs say sidecars get CPU only while a request is handled or the ingress container starts, so configure a startup probe) [CITED: run/docs/deploying#sidecars]. Measure the cold start live; fallback `minScale: '1'` (idle billing, roughly a few euros per month per research 07's estimate [CITED: docs/research/07-costi-hosting-cloud-run.md, Medium]).

### Pitfall 3: Chat API replies from the runtime service account
**What goes wrong:** `build_chat_client` uses `google.auth.default(scopes=[CHAT_BOT_SCOPE])` (`chat_api.py:35-38`). In dev this was verified with a key file. On Cloud Run ADC resolves to the runtime service identity [CITED: run/docs/securing/service-identity], but the docs fetched do not state that the metadata server honours an arbitrary scope, and a community thread reports 403 "insufficient authentication scopes" from Cloud Run [CITED: web search summary, community advice, not official]. Unverified.
**How to avoid:** live-check item. Fallback that stays keyless: the runtime SA impersonates a dedicated Chat-app SA via `google.auth.impersonated_credentials` with `target_scopes=[chat.bot]` (`roles/iam.serviceAccountTokenCreator` on that SA) [ASSUMED]. The Chat app's configured service account and `CHAT_JWT_ISSUER_EMAIL` rules in `services/chat_bot/README.md` stay unchanged.

### Pitfall 4: Meridian credentials on GCS FUSE
**What goes wrong:** FUSE "does not provide concurrency control for multiple writes (file locking)", "the last write wins", is not fully POSIX [CITED]; Meridian writes a transcript per request into `~/.claude/projects/...` with no cleanup by default, plus `.claude.json`, `backups/`, `jobs/`, `sessions/` [CITED: Meridian docs/configuration.md at the pinned SHA].
**How to avoid:** `maxScale: '1'` (single writer); set `MERIDIAN_TRANSCRIPT_RETENTION_DAYS` (e.g. 7) so the bucket does not grow [CITED]; set `MERIDIAN_SESSION_DIR` to a per-instance in-memory volume (the Meridian doc says the container overlay is not a supported SQLite directory and the session store is file-based; keep it local) [ASSUMED: emptyDir `medium: Memory` is the Cloud Run in-memory volume]; set a stable `MERIDIAN_HOST_ID`; `MERIDIAN_SHUTDOWN_GRACE_MS` default 30 s exceeds Cloud Run's SIGTERM window [ASSUMED: 10 s]. The writes that matter (`.credentials.json` refresh) are rare.

### Pitfall 5: Three copies of one OAuth refresh-token chain
**What goes wrong:** "Two instances sharing refresh tokens can invalidate each other" [CITED: Meridian docs]. Compose dev volume, kind Secret and Cloud Run bucket are all seeded from the same login.
**How to avoid:** only the Cloud Run instance refreshes. Run the dev compose and kind Meridian with `MERIDIAN_CREDENTIALS_READONLY=1` after the cloud seed, or re-seed from a fresh `claude` login for the cloud and leave the local login separate. Document in the bootstrap guide. The seed copy happens once, with the file never printed.

### Pitfall 6: Audience and invoker mismatches on the first live deploy
**What goes wrong:** `MCP_AUDIENCE` != `MCP_PUBLIC_BASE_URL`; `BOT_SA_EMAILS` missing the runtime SA; Chat requests rejected because the service requires IAM.
**How to avoid:** deterministic URL in both YAMLs; `invoker-iam-disabled: 'true'` on both services because callers (claude.ai, Chat) are not Google IAM principals and both services verify tokens in-app; this also works when an org policy blocks `allUsers` [CITED: run/docs/authenticating/public]. Cloud Run docs recommend that CI/CD not change unauthenticated-invocation settings [CITED: deploy-cloudrun README]: apply the annotation at bootstrap too, and treat a `services replace` permission error on it as a signal to grant the deployer the needed role rather than widening it [ASSUMED: `run.developer` may not suffice].

### Pitfall 7: One-way and costly decisions to confirm before executing
Firestore location (D-03, one-way). ADR 0001 update (D-06, costly). Writing both into the plan as explicit checkpoints with Joshua before `gcloud firestore databases create` runs.

### Pitfall 8: 421 on pod-to-pod calls
`host_kwargs` (`server.py:68-86`) allows only `localhost`, `127.0.0.1` and the host of `MCP_PUBLIC_BASE_URL`; `MCP_PUBLIC_BASE_URL` validation admits only `https://` or loopback `http://`. A Service DNS name such as `mcp-server` gets 421. Add a `MCP_ALLOWED_HOSTS` setting (csv, hostnames only) appended to `hosts`; tests assert the default list is unchanged. Keep the guard on.

### Pitfall 9: No health endpoints exist
`grep` finds no `/health` route in `services/` and `HttpIntake` registers only `Route("/", receive, methods=["POST"])` (`http.py:215`). Success criterion 2 needs "a health check". Add `@mcp.custom_route("/healthz", methods=["GET"])` to `mcp_server` (signature verified: `FastMCP.custom_route(self, path: str, methods: list[str], name=None, include_in_schema=True)` in fastmcp 4.1.6). For Cloud Run use `tcpSocket` startup probes (the Google tutorial does). Liveness must not touch Firestore or GCS.

### Pitfall 10: Deployed-marker guard fails open off Cloud Run
`config.py:88` (mcp): `if self.auth_mode == "off" and "K_SERVICE" in os.environ:` and `config.py:126` (bot): `if self.mcp_auth == "none" and "K_SERVICE" in os.environ:` [VERIFIED: read]. Replace with an explicit `DEPLOY_ENV: Literal["local","production"]` defaulting to `production` (fail closed): auth off / `MCP_AUTH=none` / `CHAT_API=recording` allowed only for `local`; `K_SERVICE` still forces `production`. Consequences: every test environment that uses `AUTH_MODE=off` and the compose files must set `DEPLOY_ENV=local` (`tests/integration/test_server_process.py`, `test_bot_process.py` build their own env; their `_BOT_VARIABLES` set is derived from `BotSettings.model_fields`, so the new field is cleared automatically).

### Pitfall 11: CI cannot execute the test script
`git ls-files -s run-unit-tests.sh` returns mode `100644` [VERIFIED]. Run `git update-index --chmod=+x run-unit-tests.sh` (a commit is Joshua's call per the global rules) and add a unit test asserting the executable bit via `git ls-files -s`/`os.access`.

### Pitfall 12: The compose round trip silently calls real services
Without the recording adapter and stub LLM, a "round trip" either needs Joshua's Max session and Chat API or fails at the Chat call. Keep the hermetic profile as the CI-able proof and the Meridian profile as the live one.

### Pitfall 13: Video link behaviour is unverified
D-16 flagged this. Official docs say the authenticated browser download is cookie-based and redirects to a `googleusercontent.com/download/storage/v1/b/...` URL, requires `storage.objects.viewer`, and always requires authentication even for public objects [CITED: docs.cloud.google.com/storage/docs/access-control/cookie-based-authentication]. The docs do not state inline-versus-attachment behaviour, multi-account (`/u/N`) handling, or fragment survival. A URL fragment is normally kept across HTTP redirects, but the login hop may drop it [ASSUMED].
**How to avoid:** upload with `Content-Type: video/mp4` and also set `Content-Disposition: inline` and `Cache-Control: private` on the object [ASSUMED]; make "open the Guarda URL in Chrome while signed in as Joshua, verify inline play and seek at `#t=`" a live-checkpoint item with pasted evidence. Fallbacks, in order: (a) a tiny HTML player page that sets `currentTime` from `?t=` (needs hosting and auth: heavier, only if the URL fails); (b) revisit signed URLs minted at click time (contradicts D-16: ask Joshua first). Browsers also depend on HTTP range support for seeking; GCS serves ranges [ASSUMED from general GCS behaviour; an ImageKit post shows 206 responses for a public object, not authoritative].

### Pitfall 14: Timestamp coverage is data-limited (D-18)
Index measured this session (`video_map` joined to `guide_chunks`, 2524 rows over 15 guides): scene-mapped rows 238 = Multi-Agent 176 + MCP Servers 62; all other guides 0. In the Guides checkout only `videos/mcp-servers/sections.yaml` and `videos/multi-agent-design/sections.yaml` exist. `durations.json` exists locally for 7 videos: a2a-protocol, airflow, big-data-frameworks, deep-agents, langsmith, mcp-servers, multi-agent-design. Rows of guides that have durations but no `sections.yaml`: A2A 188, Airflow 143, Big Data 249, Deep Agents 140, LangSmith 178 = 898 rows. Guides with an mp4 but no `durations.json` locally: langgraph (164 rows), etl-vs-elt (110). Guides with neither: mlflow-genai 212, langchain 181, kubernetes 168, bigquery 139, rag-chatbot 126, design-patterns 85 (911 rows). `durations.json` is written by `videos/common/tts.py` (Kokoro-82M TTS from `narration.py`); the videos without it were rendered elsewhere (`RENDER_ON_ANOTHER_PC.txt`).
Consequences for planning: (1) `sections.yaml` is authored in the Guides repo (another repo, private; the sync only indexes committed content per `jobs/sync/README.md`), so those are cross-repo commits; (2) the achievable target without re-rendering is the 5 videos above (+898 rows at most, minus sections no scene covers); (3) the rest needs `durations.json` regenerated by the Guides build (heavy, outside this repo) or stays at the 0-offset fallback; (4) add a `video-coverage` report to the sync CLI (rows by `source`, per guide) so the number is measured, not claimed. Whether sections without a scene should inherit the nearest preceding mapped section's offset is a product decision that D-18 does not settle (D-02 of Phase 1 forbids heuristic text matching; order inheritance is a different heuristic): ask Joshua before implementing.

### Pitfall 15: Firestore TTL
Policy is per collection group, one TTL field per group; the field must be a timestamp (absent/null/other type disables expiry); deletion is "typically within 24 hours"; enabling takes at least ten minutes; emulator support is not documented [CITED: firestore/native/docs/ttl]. Writers store `expire_at` as `datetime` (`gaplog.py:70`, `memory.py:60`) [VERIFIED: grep]. The policy therefore cannot be proved in the emulator: verify with `gcloud firestore fields ttls list` at the live checkpoint; keep the read-side expiry in `memory.py:68-69`.

### Pitfall 16: "Free" is not zero
Cost table (all [CITED: docs.cloud.google.com/free/docs/free-cloud-features unless marked]):
| Service | Free tier | Phase 4 use | Verdict |
|---------|-----------|-------------|---------|
| Cloud Storage | 5 GB-months only in us-east1/us-west1/us-central1 | index (6 MB), videos (~0.57 GB for the 12 local files, ~1 GB total estimated [ASSUMED]), credentials in europe-west8 | Not free, expected cents per month |
| Artifact Registry | 0.5 GB | 3 images; Meridian is 2.48 GB uncompressed locally | Likely over 0.5 GB; add cleanup policy |
| Secret Manager | 6 active versions, 10k accesses | 5 secrets | Within, no spare for rotation without cost |
| Firestore | 1 GiB, 50k reads/20k writes/20k deletes per day per project; page does not say which database | gap log, thread memory, OAuth state | Fine; applicability to a non-default database not stated [ASSUMED default only] |
| Cloud Run request-based | 2M requests, 360,000 GiB-s, 180,000 vCPU-s | both services | Fine; instance-based limits not on that page |
| Pub/Sub | 10 GiB | unused in prod (HTTP) | n/a |
Research 07 costed `mcp_server` only; the sidecar, CI and GCS are new. Record the table in the plan summary for Joshua.

### Pitfall 17: SIGTERM
03-11 left the interpreter default. Cloud Run gives a short window after SIGTERM [ASSUMED 10 s]. uvicorn drains in-flight requests on SIGTERM by default; the Pub/Sub intake and background patch tasks do not. Minimal handler: on SIGTERM stop accepting, await in-flight run tasks up to a few seconds, then exit 0. Optional per discretion; low risk if skipped, because the placeholder-patch race is already covered by Pitfall 1.

## Code Examples

### One-time WIF bootstrap (numeric ids, repo owner is a user account)
```bash
# Source: CICD_GUIDE.md §13 and google-github-actions/auth README (pool + provider + attribute condition)
REPO_ID=1444444230          # [VERIFIED: gh api repos/joshuadigitiamo/ai-buddy --jq .id]
OWNER_ID=141429883          # [VERIFIED: gh api ... --jq .owner.id]; owner is a User, not an Org
gcloud iam workload-identity-pools create github --project="$PROJECT_ID" --location=global
gcloud iam workload-identity-pools providers create-oidc monorepo --project="$PROJECT_ID" \
  --location=global --workload-identity-pool=github \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_id == '${REPO_ID}' && assertion.ref == 'refs/heads/main'"
# let tokens from that repo impersonate the deployer SA (no key is ever created)
gcloud iam service-accounts add-iam-policy-binding ci-deployer@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository_id/${REPO_ID}"
```
The extra `ref == refs/heads/main` condition is a recommendation because the repo is public: fork pull requests cannot obtain `id-token` for this repository, but restricting to `main` also stops any future branch or tag workflow from deploying [ASSUMED fit for D-04]. Pool/provider/IAM changes can take up to 5 minutes to propagate [CITED: auth README].

### Roles (starting point, least privilege)
| Identity | Roles |
|----------|-------|
| `ci-deployer` | `roles/artifactregistry.writer` on the repo; `roles/run.developer` on the two services (project-level at first deploy); `roles/iam.serviceAccountUser` on the two runtime SAs |
| `sa-mcp-server` | `roles/datastore.user`; `roles/storage.objectViewer` on the index bucket; `roles/secretmanager.secretAccessor` on its secrets |
| `sa-chat-bot` | `roles/datastore.user`; `roles/storage.objectUser` on the credentials bucket only; `roles/secretmanager.secretAccessor` on its secrets; listed in `BOT_SA_EMAILS` |
| Joshua | `roles/storage.objectViewer` on the video bucket; `roles/storage.objectAdmin` on index + video buckets for the sync step; Run developer for the forced revision |
FUSE volumes need `roles/storage.objectViewer` for read and `roles/storage.objectUser` for write [CITED: cloud-storage-volume-mounts].

### Firestore TTL (apply once, live checkpoint)
```bash
# Source: docs.cloud.google.com/firestore/native/docs/ttl
gcloud firestore fields ttls update expire_at --collection-group=gaps --enable-ttl --async
gcloud firestore fields ttls update expire_at --collection-group=thread_memory --enable-ttl --async
```
Defaults in code: `gap_collection: str = "gaps"` (`McpSettings`), `memory_collection: str = "thread_memory"` (`BotSettings`).

### Structural guard pattern (offline, in `run-unit-tests.sh --all`)
Follow `tests/unit/test_dev_compose.py` (yaml.safe_load, assertions): for each `deploy/cloudrun/*.yaml` assert `apiVersion: serving.knative.dev/v1`, `kind: Service`, no `minScale` above 0, `cpu-throttling` not `'false'` for `mcp_server`, `execution-environment: gen2` when a `csi` volume is present, exactly one `containerPort`, no literal value for any env name ending `_KEY`/`_SECRET`/`_TOKEN` (must be `valueFrom.secretKeyRef`, the same suffix rule as the compose test), image pinned by tag placeholder not `latest`, region mentioned only through the repo host `europe-west8-docker.pkg.dev`. For workflows assert `permissions: {}` at the top, every `uses:` is a 40-hex SHA or a local `./` path, `deploy` has `needs: test`, and the `paths` drift test of Pattern 7.

### Sync upload step shape (D-17)
`buddy_sync upload-videos --videos-dir <dir>`: for each `https://...releases/download/videos/<name>.mp4` in the README table (parsed by `video_map.parse_readme_videos`), find `<name>.mp4` under the videos dir, upload to `gs://<bucket>/videos/<name>.mp4` with `content_type="video/mp4"` only when the blob's md5 differs. `video_map.resolve_video_links` takes an optional URL-rewrite callable that maps the README URL basename to `https://storage.cloud.google.com/<bucket>/videos/<name>.mp4`. The README stays the source of the part list. Only 12 of the 20 README mp4 links exist locally under `Guides/videos/*/out/`; the rest come from `gh release download videos --repo joshuadigitiamo/Guides --dir <dir>` (Joshua's own login; repo is private) [VERIFIED: counts from `find` and README grep; command from Guides README].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-account JSON keys in CI | WIF with attribute conditions and numeric ids | established | Guide CICD §13 |
| `dorny/paths-filter` for everything | native `on.push.paths` where no required checks exist | n/a | fewer pinned third-party actions |
| Sidecar as a second regular container | native sidecar (`initContainers` + `restartPolicy: Always`) | stable in current Kubernetes (kind default is 1.37.0) | ordering and lifecycle handled by kubelet [CITED: KUBERNETES_GUIDE §15] |
| Cloud Run hash URLs | deterministic `SERVICE-PROJECT_NUMBER.REGION.run.app` | current docs | audience known before first deploy |
| `allUsers` invoker grant | `invoker-iam-disabled` annotation | current docs ("Option 2 (recommended)") | works under domain-restricted sharing |

**Deprecated/outdated:** kind `extraMounts` examples that omit `readOnly`; pinning actions by tag (`@v3`) instead of SHA (the guide cites a 2026 tag-hijack incident).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `google-cloud-storage` 3.17.1 method names/`md5_hash` field and `py.typed` status match the sketches | Pattern 1, Don't Hand-Roll | Small rework of the adapter and a mypy override |
| A2 | Cloud Run sidecars are GA and `launch-stage: BETA` is no longer required | Pattern 2 | `services replace` rejects the YAML; remove or add the annotation per the dry-run |
| A3 | Any template change creates a new revision that takes 100% of traffic | Pattern 6 | D-08 mechanism needs a different flag (e.g. an explicit `--to-latest` or a revision suffix) |
| A4 | Meridian image compressed size and cold-start time are acceptable | Pitfall 2 | Bot first message times out; need `minScale: 1` |
| A5 | Runtime-SA ADC can post to the Chat API with `chat.bot`; impersonation is the keyless fallback | Pitfall 3 | Replies fail live until the fallback is wired |
| A6 | SIGTERM grace on Cloud Run is about 10 s | Pitfall 17 | Drain handler sized wrong |
| A7 | `#t=` fragment survives the storage.cloud.google.com login redirect; `Content-Disposition: inline` is honoured; multiple Google accounts do not break it | Pitfall 13 | Guarda opens a download or the wrong account; fallback (a) or (b) needed and Joshua asked about signed URLs |
| A8 | Instance-based billing free tier covers a single-user bot | Pitfall 1 | Fallback for Pitfall 1 costs more than expected |
| A9 | `run.developer` can set the `invoker-iam-disabled` annotation via `services replace` | Pitfall 6 | CI deploy fails at the first run |
| A10 | Firestore free quota applies to the `(default)` database | Pitfall 16 | Small Firestore charges if another database id is used (plan uses `(default)`) |
| A11 | Total video size is about 1 GB | Pitfall 16 | Slightly different storage cost |
| A12 | kubeconform accepts `kubectl kustomize` output on stdin | Pattern 5 | Use a temp file instead |
| A13 | Restricting the WIF provider to `refs/heads/main` is acceptable for all CI jobs | Code Examples | Pull-request test jobs do not need cloud access, so low risk |
| A14 | Order-inheritance of scene offsets is a product decision, not yet made (Update 2026-11-14: decided at 04-01, coverage_inheritance (a), no inheritance) | Pitfall 14 | D-18 target is read differently by Joshua and the executor |

## Open Questions

(Update 2026-11-14: all six were answered at the 04-01 gate; see 04-01-SUMMARY.md `## Phase decisions (04-01 Task 2)`. 1: (a) request-based. 2: (a) stay at 0. 3: (a) Claude drafts, Joshua reviews and commits. 4: yes, the existing project `ai-buddy-dev` is under the digitiamo.com organization with billing linked; org policies may apply to 04-08 bootstrap and 04-13. 5: (b) a fresh, separate `claude` login seeds the Cloud Run bucket. 6: (a) `gh release download videos --repo <owner>/Guides --dir .cache/videos` with Joshua's login.)

1. **Does Joshua accept request-based billing for `chat_bot` even if slow answers stall?**
   - Known: criterion 3 says request-based; the intake design lets runs outlive the ack window.
   - Unclear: how often real runs exceed 25 s (Meridian spawns a CLI turn per request; `LLM_TIMEOUT_SECONDS` default is 60).
   - Recommendation: ship request-based, measure live, flip to `cpu-throttling: 'false'` only with his consent.
2. **D-18 reading: sections without a scene entry inherit the nearest earlier scene offset, or stay at 0?**
   - Recommendation: stay at 0 (no new heuristic) and report coverage; ask before changing.
3. **Cross-repo work for `sections.yaml`:** who authors the five missing maps and commits them to the Guides repo?
   - Recommendation: generate drafts from scene class names plus narration, Joshua reviews, commit in the Guides repo, then re-run sync.
4. **Org policy / Workspace:** is the GCP project under a Digitiamo organization (domain-restricted sharing, VPC rules)? The plan uses `invoker-iam-disabled`, which avoids the `allUsers` problem, but an org policy on public buckets or service-account creation could still block bootstrap steps.
5. **Meridian token chain:** which of the three seeded copies keeps refreshing (Pitfall 5)? Recommendation in the pitfall; confirm with Joshua at seeding time.
6. **Sync on a machine without the Guides videos locally:** the 8 videos not under `Guides/videos/*/out/` must be fetched with `gh release download`; confirm the download path before the first upload.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | everything | yes | 29.9.1 | none needed |
| Docker Compose | INFRA-02 | yes | v5.6.0 | none needed |
| kubectl (+ built-in kustomize) | INFRA-03 | yes | client v1.36.0, Kustomize v5.8.1 | none needed |
| gh CLI | repo ids, video download | yes | present | none needed |
| kind | INFRA-03 live | no | v0.33.0 downloadable (`kind-linux-amd64` + `.sha256sum`) | pinned download into `.cache/bin/` (gitignored `.cache/`), checksum verified |
| kubeconform | INFRA-03 validation | no (host) | `ghcr.io/yannh/kubeconform:v0.8.0` image exists | run via Docker |
| actionlint | INFRA-05 lint | no (host) | `rhysd/actionlint:1.7.12` image exists | run via Docker |
| gcloud | bootstrap, `--dry-run`, TTL | no (host) | `google/cloud-sdk:592.0.0-emulators` image present locally (gcloud 592.0.0) | run via Docker; needs network and auth for non-emulator commands |
| ffprobe / ffmpeg | video inspection | no | n/a | not required: upload uses file bytes; scene offsets come from `durations.json` |
| GCP project with billing | live checkpoint (criteria 3, 4, 5 live) | not yet (D-02, STATE blocker); (Update 2026-11-14: yes, existing project `ai-buddy-dev` under the digitiamo.com organization, billing linked; id in docs/internal/gcp-project.md, gitignored) | n/a | static checks run now; live checks recorded as pending |
| Joshua's Max login | Meridian live profile, credentials seed | local volume `meridian-claude` exists | n/a | smoke profile uses the stub LLM |

**Missing dependencies with no fallback:** a GCP project with an active billing account blocks only the live checkpoint, not the static work. (Update 2026-11-14: no longer missing; the project `ai-buddy-dev` exists with billing linked.)
**Missing dependencies with fallback:** kind, kubeconform, actionlint, gcloud (all via pinned binary or Docker image).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 + pytest-cov 7.1.0, ruff 0.17.3, mypy 2.4.1 strict (`requirements-dev.txt`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`, markers `firestore`, `pubsub`) |
| Quick run command | `./run-unit-tests.sh --single-file <file> tests/unit` |
| Full suite command | `./run-unit-tests.sh --all` (ruff check, ruff format --check, mypy, pytest, `--cov-fail-under=80`); `./run-unit-tests.sh --emulator` for emulator-marked tests |

`run-unit-tests.sh` runs with `--network none` and cannot call Docker, so checks that need Docker or the network live in a separate `scripts/validate-infra.sh` (and CI steps), while pure-YAML structural guards live in `tests/unit` and run under `--all`.

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Dockerfile has stages `mcp_server`, `chat_bot`, `sync`; non-root `USER 10001` (runtime); no `COPY` of `artifacts/`, `.env`, `docs/`; `sync` stage has git and `jobs/sync`; each stage builds | unit (parse) + build smoke | `./run-unit-tests.sh --single-file test_dockerfile_stages.py tests/unit`; `docker build --target sync .` in `validate-infra.sh` | Wave 0 |
| INFRA-01 | Same image runs with different env: config tests for `ARTIFACT_STORE`, `DEPLOY_ENV`, `MCP_ALLOWED_HOSTS` | unit | `./run-unit-tests.sh --single-file test_config.py tests/unit/mcp_server` | partly (Wave 0 additions) |
| INFRA-02 | Hermetic round trip: fixture event -> Pub/Sub emulator -> bot -> MCP -> stub LLM -> recording adapter -> answer with `handbook://` citation | integration (docker compose smoke) | `scripts/compose-smoke.sh` (compose `--profile smoke`) | Wave 0 |
| INFRA-02 | Compose structure: services, no published ports, secrets only via env/`${}`, Meridian pinned SHA | unit (parse) | `./run-unit-tests.sh --single-file test_compose.py tests/unit` (migrated from `test_dev_compose.py`) | migrate |
| INFRA-03 | Base and dev overlay build and pass schema validation | static | `scripts/validate-infra.sh` (`kubectl kustomize ... | docker run -i ghcr.io/yannh/kubeconform:v0.8.0 -strict -summary`) | Wave 0 |
| INFRA-03 | Health check and one MCP tool call succeed in-cluster | live-local (kind) | `scripts/kind-smoke.sh` | Wave 0 |
| INFRA-04 | `GcsArtifactStore` against a fake bucket: pointer-last publish, sha256 mismatch refused, missing pointer -> `SnapshotError` | unit | `./run-unit-tests.sh --single-file test_gcs_store.py tests/unit/buddy_core` | Wave 0 |
| INFRA-04 | Cloud Run YAML structure (Pattern guard above) | unit | `./run-unit-tests.sh --single-file test_cloudrun_yaml.py tests/unit` | Wave 0 |
| INFRA-04 | Server-side validation of the rendered YAML | static (needs auth) | `gcloud run services replace <file> --dry-run --region europe-west8` in CI after WIF login | CI step |
| INFRA-05 | Workflow structure and path-filter drift vs Dockerfile `COPY` sources; `models.py` triggers the bot, other `services/mcp_server` files do not | unit | `./run-unit-tests.sh --single-file test_workflows.py tests/unit` | Wave 0 |
| INFRA-05 | Workflow lint | static | `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12` | Wave 0 (script) |
| INFRA-05 | WIF push and deploy with no key file | live | first push to `main` after bootstrap; check run log and `gcloud run revisions list` | live checkpoint |
| INFRA-06 | `deploy` job `needs: test`; test job runs `./run-unit-tests.sh --all`; script mode is executable in the git index | unit | `./run-unit-tests.sh --single-file test_workflows.py tests/unit` | Wave 0 |
| SC5 | Video map URLs rewritten to `storage.cloud.google.com`; coverage report counts `source` per guide; upload skips unchanged md5 (fake bucket) | unit | `./run-unit-tests.sh --single-file test_video_upload.py tests/unit/buddy_sync` | Wave 0 |
| SC5 | Inline playback and `#t=` seek on the real URL | manual live | Chrome signed in as Joshua; paste evidence | live checkpoint |

### Sampling Rate
- **Per task commit:** the task's `--single-file` command (seconds).
- **Per wave merge:** `./run-unit-tests.sh --all` plus `scripts/validate-infra.sh`.
- **Phase gate:** `--all`, `--emulator`, `compose-smoke.sh`, `kind-smoke.sh` green, then the live checkpoint recorded (or recorded as pending without billing).

### Wave 0 Gaps
- [ ] `tests/unit/test_dockerfile_stages.py`, `test_compose.py` (migrate from `test_dev_compose.py`), `test_cloudrun_yaml.py`, `test_workflows.py`, `buddy_core/test_gcs_store.py`, `buddy_sync/test_video_upload.py`, config tests for the three new settings and the `/healthz` route.
- [ ] `scripts/validate-infra.sh`, `scripts/compose-smoke.sh`, `scripts/kind-up.sh`, `scripts/kind-smoke.sh`, `scripts/sync-and-publish.sh`.
- [ ] Fixtures: smoke stub LLM, expected recorded answer, `deploy/compose/pubsub_init.py`.
- [ ] `git update-index --chmod=+x run-unit-tests.sh` (and the new scripts).
- [ ] `requirements-dev.txt` gains `-r jobs/sync/requirements.txt`.
- [ ] kind binary download with checksum into `.cache/bin/`.

## Security Domain

`security_enforcement` is absent from `.planning/config.json`, so it is enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing: Google OAuth (digitiamo.com), Chat JWT, bot ID token. Phase 4: deploy with `AUTH_MODE=on`; fail-closed `DEPLOY_ENV`; live rejection of a non-digitiamo account (deferred item) |
| V3 Session Management | no | stateless MCP (D10) |
| V4 Access Control | yes | IAM split per service account; bucket IAM per identity; `invoker-iam-disabled` only because both services verify tokens in-app |
| V5 Input Validation | partial | `MCP_ALLOWED_HOSTS` hostnames-only validator; `ARTIFACT_PREFIX` / object names validated (no `..`); GitHub expression values passed through `env:` never inlined in `run:` [CITED: CICD_GUIDE §14] |
| V6 Cryptography | yes | no hand-rolled crypto; Secret Manager; TLS terminated by Cloud Run; sha256 check of the downloaded index |
| V8/V14 Data and Config | yes | no secrets or handbook in images; `.dockerignore` excludes `artifacts/`, `docs/`, `.env` [VERIFIED: .dockerignore]; public-access-prevention on all buckets; repo variables not secrets for ids |
| V13 API | yes | Host/Origin guard stays on (421); health route unauthenticated and constant |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Fork or foreign repo mints a GCP token via WIF | Elevation | attribute condition on `repository_id` (+ `ref`), numeric ids, impersonated SA with minimal roles |
| Workflow script injection / hijacked action tag | Tampering | `permissions: {}` top-level, grants per job, actions pinned by SHA, Dependabot; no `pull_request_target` |
| Max credentials leak (image, log, repo) | Information disclosure | private bucket, IAM only `sa-chat-bot`, FUSE mount only in the sidecar, never echoed, kind via imperative Secret, `.gitignore` check in a test for `.credentials.json` |
| Meridian takeover on a public Cloud Run URL | Elevation | Meridian binds loopback (`MERIDIAN_HOST=127.0.0.1`) in Cloud Run, `MERIDIAN_API_KEY` from Secret Manager, only the ingress container has a port |
| Public service abuse (no IAM at the edge) | DoS | in-app auth before work, existing rate limit on `mcp_server`, `maxScale` caps, Chat JWT verification before any LLM call |
| Auth-off in a deployed environment | Elevation | `DEPLOY_ENV` fail-closed (replaces K_SERVICE-only) with tests |
| DNS rebinding on `mcp_server` | Spoofing | keep `host_origin_protection`; extra hosts via explicit allow-list only |
| Video bucket exposure | Information disclosure | uniform access, public access prevention, per-user IAM; `storage.cloud.google.com` always requires auth |
| Supply chain: Meridian build | Tampering | SHA-pinned git context in one file, reviewed bump; image in private AR |
| Log leakage of redaction hits | Information disclosure | audit tech-debt: sync logs `source=<file stem>` on stderr; sync runs on the laptop, so it is not hosted; keep it that way |

## Sources

### Primary (HIGH confidence)
- Repo files read this session: `Dockerfile`, `docker-compose.dev.yml`, `docker-compose.test.yml`, `run-unit-tests.sh`, `pyproject.toml`, `packages/buddy_core/buddy_core/store.py`, `services/mcp_server/buddy_mcp/{snapshot,config,server,cli}.py`, `services/chat_bot/buddy_bot/{config,cli,ports,schemas,llm,chat_api}.py`, `intake/{http,pubsub}.py`, `jobs/sync/buddy_sync/{cli,config,video_map}.py`, `tests/integration/test_bot_process.py`, `tests/unit/test_dev_compose.py`, `.env.example`, `.dockerignore`, ADR 0001, `.planning/{STATE,WINDOWS,v1-MILESTONE-AUDIT,REQUIREMENTS}.md`
- GitHub API (`gh api`): action and tool releases, tag SHAs, repo and owner ids
- PyPI JSON for `google-cloud-storage`; `gsd-tools package-legitimacy check`
- Running images: `ai-buddy-test` (fastmcp 4.1.6 `custom_route` signature), `google/cloud-sdk:592.0.0-emulators` (`gcloud run services replace --help`)
- Local data: `artifacts/index.db` `video_map` x `guide_chunks`; Guides checkout (`find`, README)
- `docker manifest inspect` for kindest/node, kubeconform, actionlint images

### Secondary (MEDIUM confidence, official docs fetched)
- docs.cloud.google.com: Cloud Storage volume mounts; deploying sidecars; run YAML v1 reference; nginx sidecar tutorial; run locations (europe-west8 Tier 1); Firestore locations and TTL; Artifact Registry locations; Cloud Storage locations; Cloud Run authenticating public (`invoker-iam-disabled`); billing settings; service identity; request timeout; deterministic URLs; free cloud features; `gcloud run services replace`; cookie-based authentication for browser downloads
- github.com/google-github-actions/auth and deploy-cloudrun READMEs; github.com/yannh/kubeconform README
- Guides: CICD_GUIDE §9, §12, §13, §14; KUBERNETES_GUIDE §12, §13, §15; MCP_SERVERS_GUIDE §11, §19; DESIGN_PATTERNS_GUIDE (Adapter, Hexagonal, Sidecar)
- rynfar/meridian at the pinned SHA: `Dockerfile`, `docs/configuration.md` (first 100,000 of 148,997 characters read)

### Tertiary (LOW confidence)
- Web search summaries on Chat API auth from Cloud Run (community thread) and sidecar annotations; third-party blog posts on sidecar ordering. Not relied on for decisions; listed in Assumptions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for versions and availability (read from registries); MEDIUM for how the pieces combine until the live checkpoint.
- Architecture: MEDIUM: Cloud Run sidecar + FUSE pattern is documented, but Meridian-on-FUSE and request-based background work are untested.
- Pitfalls: MEDIUM-HIGH: repo-derived ones (guards, hard-wired store, no health route, file mode) are verified; platform-behaviour ones carry A-tags.

**Guides applied (D16), for the plan to cite:** KUBERNETES_GUIDE §12 (probes), §13 (requests/limits), §15 (native sidecar), §23 (PSS), §28 (labels); MCP_SERVERS_GUIDE §11 (statelessness checklist), §19.1 (horizontal scaling, serverless without sticky sessions), §12.2 (Streamable HTTP); DESIGN_PATTERNS_GUIDE Adapter, Hexagonal and Sidecar for `GcsArtifactStore`, ports and Meridian; plus CICD_GUIDE §9, §12, §13, §14 which D16 did not list but which prescribes exactly INFRA-05. Exceptions to record: Cloud Run YAML uses the platform's own sidecar mechanism instead of the Kubernetes native one; `pubsub`-mode bot has no HTTP probes.

**Research date:** 2026-11-14
**Valid until:** 2026-12-14 for tool versions (fast-moving actions and images); platform behaviour notes until the live checkpoint replaces them with evidence.
