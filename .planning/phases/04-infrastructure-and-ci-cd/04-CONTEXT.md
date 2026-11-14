# Phase 4: Infrastructure and CI/CD - Context

**Gathered:** 2026-11-14
**Status:** Ready for planning

<domain>
## Phase Boundary

The whole system runs from per-service Docker images: locally with `docker compose` (emulators, Pub/Sub round trip), on a local kind cluster (Kustomize base + dev overlay), and live on Cloud Run europe-west8 (`mcp_server`, `chat_bot` with a Meridian sidecar). GitHub Actions builds, tests, pushes and deploys per service through path filters and Workload Identity Federation. Guides videos play inline from a private Cloud Storage bucket at the section timestamp.

Not in this phase: golden set, Recall@5, MLflow scoring and the milestone gate (Phase 5); multi-user rollout, moving `LLM_BACKEND` to an API key, moving videos to Drive (later, D1a / D15).

</domain>

<decisions>
## Implementation Decisions

### Hosting platform
- **D-01:** Cloud Run free tier stays the production host (D7 kept). No-card hosts (Render, HF Spaces, Oracle Free, self-hosted k3s) are rejected: they would replace Firestore, Pub/Sub, WIF and the `K_SERVICE` auth guards.
- **D-02:** Joshua provides a GCP project with an active billing account during this phase. Plans include a **live deploy checkpoint** (real Cloud Run, WIF, Chat HTTP JWT, bot-to-MCP ID token, claude.ai connector check, non-digitiamo rejection). Static checks (YAML schema, workflow lint, dry runs) still run in CI.
- **D-03:** Region europe-west8 (Milano). The researcher verifies availability there of Cloud Run (incl. sidecars and GCS volume mounts), Firestore, Artifact Registry and free-tier eligibility. Fallback to europe-west1 only if a blocker is found, and only after asking Joshua. — **Reversibility:** one-way — a Firestore database location cannot be changed after creation; moving it means a new database and data migration.
- **D-04:** CI deploys automatically on push to `main` after `run-unit-tests.sh --all` passes and the image is pushed (no manual approval environment).
- **D-05:** Gap log and thread memory stay on Firestore. Add a native Firestore TTL policy on `expire_at` (03-07 left expiry read-side until Phase 4).

### Index + sync handoff (closes D-12 / ADR 0001)
- **D-06:** Sync runs on Joshua's laptop (handbook snapshot and Guides checkout mounted read-only, as today) and publishes `index.db` to a private GCS bucket through a new `GcsArtifactStore` adapter. `mcp_server` reads the bucket at cold start. The image stays generic (no handbook content), the same image runs in compose, kind and Cloud Run (INFRA-01). — **Reversibility:** costly — ADR 0001 must be updated to record the choice; switching to a baked image later changes CI, image privacy and INFRA-01.
- **D-07:** The nightly Cloud Scheduler trigger is dropped. Sources change only when Joshua edits them locally, so a nightly run would rebuild identical data. Reword INFRA-04 and ROADMAP Phase 4 criterion 3: sync runs on demand from the laptop.
- **D-08:** After a successful publish, the sync publish step (or a helper script run with it) forces a new `mcp_server` Cloud Run revision so the next request loads the new index. No hot reload; Phase 1 D-11 (cold-start load) stays.
- **D-09:** No Cloud Run Job YAML for sync. Sync keeps its own Dockerfile stage and its own path-filtered CI test path. INFRA-04 is reworded to "Cloud Run YAMLs for `mcp_server` and `chat_bot`".
- **D-10:** Compose and kind use `LocalDirArtifactStore` (shared volume in compose, hostPath / kind extraMount in kind). `GcsArtifactStore` is used only on Cloud Run and is unit-tested with a fake. The store is selected by configuration (the audit found `snapshot.py:77` hard-wires the local store).

### Deployed bot + LLM
- **D-11:** `chat_bot` runs on Cloud Run with `LLM_BACKEND=meridian`, Meridian as a sidecar container in the same service. D1a guards stay in force: Chat app visible to Joshua only, `ALLOWED_USERS` single entry, startup refusal with more than one user. Joshua accepts that this puts his Max session in the cloud.
- **D-12:** Max credentials live on a private GCS bucket mounted at `/home/claude/.claude` through a Cloud Run GCS FUSE volume, so token refreshes written by Meridian persist across restarts. Seeded once from the local `meridian-claude` volume. Bucket IAM: the Meridian/bot runtime service account only. Never baked into an image, never in the repo, never echoed.
- **D-13:** Cloud Run intake is HTTP + Google JWT (D13, verifier built in 03-10). Pub/Sub intake stays for laptop dev and compose.
- **D-14:** CI builds Meridian from the approved commit `cafdcf780f1b40c8f0dee17481132f47b4cbb353` and pushes it to the private Artifact Registry. A Meridian bump is a reviewed SHA change.
- **D-15:** kind runs the full stack: `mcp_server`, `chat_bot`, Meridian and the Firestore + Pub/Sub emulators. Max credentials reach the cluster without being committed (k8s Secret created from the local volume, or hostPath); exact mechanism is the planner's choice, it must not write credential values into manifests.

### Video hosting (Phase 3 carry-over, ROADMAP criterion 5)
- **D-16:** Videos are served from a private GCS bucket, uploaded with `Content-Type: video/mp4`. The Guarda link is the authenticated browser URL `https://storage.cloud.google.com/<bucket>/<object>#t=<seconds>`; access by IAM grant to Joshua's account (a domain group later). No expiring signed URLs in chat cards. Researcher verifies inline playback and `#t=` seeking on that URL. [Medium]
- **D-17:** The laptop sync step uploads changed mp4s (by content hash) and writes the GCS URLs into the video map, so one command refreshes index and videos.
- **D-18:** Timestamp coverage target: every Guides section whose guide has a video gets a scene offset (from `sections.yaml` / durations); sections without one fall back to the full video at 0. Coverage is measured and reported against today's 238/2524 scene-mapped rows.

### Claude's Discretion
- Secrets layout (Secret Manager vs plain env per variable), service-account split, IAM role set.
- CI structure: reusable workflow vs per-service files; how shared paths (`packages/buddy_core`, `buddy_mcp/models.py` imported by the bot) trigger dependent services.
- Manifest validation tools (kubeconform / kustomize build checks), workflow lint (actionlint), Cloud Run YAML validation.
- kind credential mechanism for Meridian (within D-15 limits).
- SIGTERM drain handler for Cloud Run (03-11 left the interpreter default).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and decisions
- `.planning/ROADMAP.md` — Phase 4 goal and success criteria (criterion 3 to be reworded per D-07/D-09)
- `.planning/REQUIREMENTS.md` — INFRA-01..06; INFRA-04 to be reworded; SYNC-07
- `.planning/PROJECT.md` — D1a, D7, D7a, D10, D11, D12, D13, D15, D16 and constraints
- `.planning/STATE.md` — Phase 4 blockers (GCP billing, connector check, non-digitiamo rejection)
- `.planning/v1-MILESTONE-AUDIT.md` — integration warnings Phase 4 must close: hard-wired `LocalDirArtifactStore`, audience / `BOT_SA_EMAILS` match, bot image needs `buddy_mcp/models.py`, `K_SERVICE` as only deployed marker (fails open on kind), plain-http `MCP_URL` loopback-only (421)
- `.planning/WINDOWS.md` — items deferred to Phase 4 (#1 live JWT and others)

### Index handoff
- `docs/adr/0001-index-handoff.md` — ADR to update with D-06 (bucket read chosen)
- `docs/index-format.md` — artifact format and versioning
- `docs/guides-contract.md` — Guides README / video table contract (video map changes in D-17)

### Prior phase context
- `.planning/phases/01-content-sync/01-CONTEXT.md` — D-11 cold-start load, D-12 host-agnostic store, D-25..27 local sources
- `.planning/phases/02-mcp-server-and-skill/02-CONTEXT.md` — auth (D-12 bot ID token, D-13 `K_SERVICE` guard), gap log
- `.planning/phases/03-google-chat-bot/03-CONTEXT.md` — Meridian credentials (03-01 amendments), intake, thread memory TTL

### Costs
- `docs/research/07-costi-hosting-cloud-run.md` — ~0 EUR claim covers `mcp_server` only; `chat_bot` + sidecar, CI and GCS not costed

### Guides best practices (D16)
- `~/Desktop/WORK/Guides/DevOps-Engineering/KUBERNETES_GUIDE.md` — manifests, Kustomize overlays, probes, resources
- `~/Desktop/WORK/Guides/AI-Engineering/MCP_SERVERS_GUIDE.md` — deployment, stateless transport
- `~/Desktop/WORK/Guides/Foundations/DESIGN_PATTERNS_GUIDE.md` — adapter for `GcsArtifactStore`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Dockerfile`: stages `base`, `test`, `mcp_server`, `chat_bot` (uid 10001). Needs a `sync` stage.
- `docker-compose.dev.yml`: Meridian (pinned SHA, external `meridian-claude` volume), Firestore emulator, `mcp_server`, `chat_bot`; no host ports. Base for the INFRA-02 compose (add Pub/Sub emulator and sync).
- `docker-compose.test.yml`: Firestore + Pub/Sub emulators (`google/cloud-sdk:592.0.0-emulators`) for tests.
- `packages/buddy_core/buddy_core/store.py`: `ArtifactStore` port + `LocalDirArtifactStore`; add `GcsArtifactStore` here.
- `services/mcp_server/buddy_mcp/snapshot.py`: index load at cold start; currently hard-wires the local store.
- `jobs/sync/buddy_sync/video_map.py`, `cli.py`, `config.py`: video URL mapping and sync CLI; video upload (D-17) plugs in here.
- `run-unit-tests.sh`: CI test entry point (INFRA-06). Still mode 100644 in git (needs `chmod +x` in index).
- `.env.example`: full env contract for all services.

### Established Patterns
- Config via pydantic settings per service; `K_SERVICE` presence refuses `AUTH_MODE=off` / `MCP_AUTH=none` (`buddy_mcp/config.py:88`, `buddy_bot/config.py:126`). kind needs its own deployed marker or explicit guard.
- `mcp_server` Host/Origin guard (`host_origin_protection=True`): plain-http non-loopback `MCP_URL` returns 421. Dev compose works by sharing the network namespace; kind pod-to-pod calls need allowed hosts or a sidecar layout.
- Bot-to-MCP auth: Google-signed SA ID token, `aud = MCP_PUBLIC_BASE_URL`, e-mail in `BOT_SA_EMAILS`.
- Secrets only from `.env` / environment; never baked, never echoed.

### Integration Points
- `.github/workflows/` (empty), `deploy/k8s/` (empty), `deploy/cloudrun/` (empty).
- Chat app configuration switches from Pub/Sub (dev) to HTTP endpoint URL on Cloud Run for the live check.
- claude.ai connector points at the hosted `mcp_server` URL (02-UAT test 10).

</code_context>

<specifics>
## Specific Ideas

- Single command on the laptop: sync -> upload changed videos -> publish `index.db` to GCS -> new `mcp_server` revision.
- Guarda opens `storage.cloud.google.com/...#t=<sec>` and plays inline after Google login.

</specifics>

<deferred>
## Deferred Ideas

- Cloud Run Job + nightly Scheduler for sync — only if sources move to the cloud.
- Videos on Google Drive (domain-shared) — before any non-dev user (D15).
- `LLM_BACKEND=api` (Console or Vertex EU) on Cloud Run — before any second user (D1a).

</deferred>

<amendments>
## Amendments (04-01 checkpoint)

- D-17 interpreted by 04-01 checkpoint: video_fetch (a) — Joshua downloads the missing mp4 files with `gh release download videos --repo <owner>/Guides --dir .cache/videos` on the host with his own login; `upload-videos` reads both `Guides/videos/*/out/` and `.cache/videos`
- D-18 interpreted by 04-01 checkpoint: sections_authoring (a) — Claude drafts five `sections.yaml` (a2a-protocol, airflow, big-data-frameworks, deep-agents, langsmith) in the local Guides working tree; Joshua reviews and commits them with the five `durations.json` in the Guides repo; "every section whose guide has a video" is read as "whose guide has scene durations", and the eight guides without `durations.json` stay at the 0-offset fallback and are listed as "no durations" in the coverage report

</amendments>

---

*Phase: 04-infrastructure-and-ci-cd*
*Context gathered: 2026-11-14*
