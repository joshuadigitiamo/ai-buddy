# API Coverage — Phase 4

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 4 integrates Google Cloud Storage (Python client), the Cloud Run Admin API, Artifact Registry, Secret Manager, Firestore administration, IAM with Workload Identity Federation (all through gcloud or YAML), and GitHub Actions. The Google Chat API surface is unchanged from Phase 3 (see 03 COVERAGE.md); only the intake moves to the HTTP endpoint.

## Google Cloud Storage, Python client google-cloud-storage (plans 04-04, 04-10, 04-11)

| capability | decision | reason |
|---|---|---|
| read object bytes (pointer `index.manifest.json`) | INTEGRATE | |
| download object to file (index db) | INTEGRATE | |
| upload from file with content_type, content_disposition, cache_control (index db, mp4) | INTEGRATE | |
| upload from bytes (pointer, written last) | INTEGRATE | |
| object metadata reload (md5_hash for change detection) | INTEGRATE | |
| resumable upload of large files | INTEGRATE | used implicitly by the client for the mp4 files |
| list objects | OPT-OUT | not needed: the pointer names the current build, videos are addressed by README names |
| delete objects | OPT-OUT | not needed: a 30-day bucket lifecycle rule removes old builds (04-08 bootstrap) |
| signed URLs | OPT-OUT | explicitly out of scope: D-16 forbids expiring signed URLs in chat cards |
| generation preconditions (if_generation_match) | OPT-OUT | not needed: single writer by design (ADR 0001); readers are protected by pointer-last publish and sha256 check |
| per-object ACLs | OPT-OUT | explicitly out of scope: uniform bucket-level access with public access prevention |
| bucket creation and configuration from Python | OPT-OUT | not needed: done once by deploy/cloudrun/bootstrap.sh with gcloud |
| composite objects, notifications, CMEK, requester pays | OPT-OUT | not needed for a 6 MB index and about 1 GB of videos |

## Cloud Run Admin API via gcloud and service YAML (plans 04-08, 04-09, 04-10, 04-13)

| capability | decision | reason |
|---|---|---|
| services replace (YAML deploy, sidecar, GCS FUSE volume) | INTEGRATE | |
| services replace --dry-run (server-side validation) | INTEGRATE | |
| services update --update-env-vars (forced revision after publish, D-08) | INTEGRATE | |
| services describe / list, revisions list | INTEGRATE | |
| invoker-iam-disabled annotation | INTEGRATE | |
| traffic splitting and revision tags | OPT-OUT | not needed: every new revision takes 100% of traffic |
| Cloud Run jobs | OPT-OUT | explicitly out of scope: D-09 (no sync job on Cloud Run) |
| Cloud Scheduler triggers | OPT-OUT | explicitly out of scope: D-07 |
| domain mappings | OPT-OUT | not needed: deterministic run.app URLs are the audiences |
| invoker IAM bindings | OPT-OUT | not needed: callers (claude.ai, Chat) are not IAM principals; tokens are verified in-app |

## Artifact Registry (plans 04-08, 04-09)

| capability | decision | reason |
|---|---|---|
| docker push with an OAuth access token | INTEGRATE | |
| images describe (Meridian tag present before chat-bot deploy) | INTEGRATE | |
| repository creation with cleanup policy (keep 3) | INTEGRATE | |
| vulnerability scanning | OPT-OUT | not needed yet: single private user; revisit before rollout |

## Secret Manager (plans 04-08, 04-13)

| capability | decision | reason |
|---|---|---|
| secretKeyRef injection into Cloud Run env | INTEGRATE | |
| create secrets, add versions from stdin | INTEGRATE | |
| client-library access at runtime | OPT-OUT | not needed: Cloud Run injects values as env |
| rotation and multiple active versions | OPT-OUT | not needed yet: six secrets equal the free active-version quota |

## Firestore administration (plans 04-08, 04-13)

| capability | decision | reason |
|---|---|---|
| create (default) database in europe-west8 | INTEGRATE | |
| TTL policy on expire_at (gaps, thread_memory) | INTEGRATE | |
| composite indexes, backups, point-in-time recovery | OPT-OUT | not needed yet: gap log and thread memory are short-lived |

## IAM, Workload Identity Federation, STS (plans 04-08, 04-09)

| capability | decision | reason |
|---|---|---|
| workload identity pool and OIDC provider with attribute condition | INTEGRATE | |
| workloadIdentityUser on the deployer service account (impersonation) | INTEGRATE | |
| service accounts and role bindings per service | INTEGRATE | |
| service-account keys | OPT-OUT | explicitly out of scope: INFRA-05 forbids key files |
| impersonated Chat credentials for the bot | OPT-OUT | not needed yet: prepared fallback for RESEARCH Pitfall 3, applied only if the 04-13 live check fails and Joshua agrees |

## GitHub Actions (plan 04-09)

| capability | decision | reason |
|---|---|---|
| push-triggered workflows with path filters | INTEGRATE | |
| reusable workflows (workflow_call) | INTEGRATE | |
| OIDC id-token for WIF | INTEGRATE | |
| repository variables | INTEGRATE | |
| concurrency groups | INTEGRATE | |
| Dependabot for action SHAs | INTEGRATE | |
| environments with manual approval | OPT-OUT | explicitly out of scope: D-04 deploys automatically after tests |
| required status checks and branch protection gate job | OPT-OUT | not needed yet: no pull-request flow against protected main |
| GitHub secrets for GCP | OPT-OUT | explicitly out of scope: keyless WIF; ids are repository variables |
