# Phase 4: Infrastructure and CI/CD - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-14
**Phase:** 4-Infrastructure and CI/CD
**Areas discussed:** Hosting platform, Index + sync handoff, Deployed bot + LLM, Video hosting

---

## Hosting platform

| Option | Description | Selected |
|--------|-------------|----------|
| Cloud Run free tier | Keeps D7; billing account; ~0 EUR; existing code fits | ✓ |
| No-card host | Render EU / HF Spaces / Oracle Free; replace Firestore/Pub/Sub/WIF | |
| Self-hosted k3s | Reuse kind manifests + tunnel | |

| GCP access | | |
|---|---|---|
| Yes, live deploy | Live deploy checkpoint in plans | ✓ |
| Not yet, static only | | |
| Unsure, plan both | | |

(Update 2026-11-14: GCP access now exists: project `ai-buddy-dev` under the digitiamo.com organization, billing linked; id in docs/internal/gcp-project.md, gitignored.)

| Deploy gate | | |
|---|---|---|
| Auto on push to main | | ✓ |
| Manual approval | | |
| Push only, deploy by hand | | |

| Datastore | | |
|---|---|---|
| Keep Firestore | + native TTL on expire_at | ✓ |
| Switch to Postgres | | |

| Region | | |
|---|---|---|
| europe-west8, researcher verifies | fallback europe-west1 only after asking | ✓ |
| europe-west1 | | |

## Index + sync handoff

| Option | Description | Selected |
|--------|-------------|----------|
| Laptop, upload to GCS | GcsArtifactStore; generic image | ✓ |
| Cloud Run Job from bucket sources | | |
| Baked private image | | |

| Scheduler | | |
|---|---|---|
| Drop, reword criterion | | ✓ |
| Keep as reload trigger | | |
| Keep full nightly sync | | |

| Reload | | |
|---|---|---|
| Publish forces new revision | | ✓ |
| Wait for scale-to-zero | | |
| Hot reload on bucket generation | | |

| Sync job YAML | | |
|---|---|---|
| No Cloud Run Job | | ✓ |
| Keep Job YAML anyway | | |

| Local store | | |
|---|---|---|
| Local dir everywhere local | | ✓ |
| GCS emulator locally | | |

## Deployed bot + LLM

| Option | Description | Selected |
|--------|-------------|----------|
| Meridian sidecar on Cloud Run | Max creds in cloud; D1a guards | ✓ |
| Bot local, mcp_server hosted | (recommended by Claude) | |
| Bot on Cloud Run with API key | | |

| Max creds | | |
|---|---|---|
| GCS FUSE volume | refresh writes persist | ✓ |
| Secret Manager, read-only | | |
| Researcher decides | | |

| Intake | | |
|---|---|---|
| HTTP + Google JWT | | ✓ |
| Pub/Sub pull on Cloud Run | | |

| Meridian image | | |
|---|---|---|
| Build pinned commit in CI | | ✓ |
| Build locally, push by hand | | |

| kind scope | | |
|---|---|---|
| mcp_server only in kind | (recommended by Claude) | |
| Full stack in kind | | ✓ |

**Notes:** Joshua chose Meridian on Cloud Run and full-stack kind over Claude's recommendations, accepting Max credentials in the cloud and in the cluster.

## Video hosting

| Option | Description | Selected |
|--------|-------------|----------|
| GCS authenticated URL | storage.cloud.google.com + #t=, IAM | ✓ |
| GCS signed URLs | 7-day expiry | |
| Google Drive domain-shared | | |

| Upload | | |
|---|---|---|
| Sync step does it | | ✓ |
| Separate script | | |

| Coverage | | |
|---|---|---|
| Every video-backed section | | ✓ |
| Fixed % target | | |
| Researcher proposes | | |

## Claude's Discretion

Secrets layout, SA/IAM split, CI workflow structure and shared-path triggers, validation tools, kind credential mechanism, SIGTERM drain.

## Deferred Ideas

Cloud Run Job + nightly Scheduler (if sources move to cloud); videos on Drive (D15); LLM_BACKEND=api (D1a).
