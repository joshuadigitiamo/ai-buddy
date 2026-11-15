---
phase: 04-infrastructure-and-ci-cd
plan: 26
subsystem: infra
tags: [live-proof, gap-closure, cloud-run, github-actions, iam, offline-gate]
status: in-progress

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: 04-17..04-25 gap fixes (role fix, locks, publish fixes, digest and revision names, base pin, staged traffic, cache/scan/SBOM, sa-publisher, identifiers as secrets)
provides:
  - "Task 1 only: offline gate result and live-readiness list; Tasks 2 and 3 (live setup, live checks, COVERAGE.md) are pending"
affects: [04-26 continuation]

plan_head_before: 65ce1b0c5a2a82655f27eb4bb279dd83f8856535

requirements-completed: []

duration: in progress
completed: pending
---

# Phase 4 Plan 26: Live proof of the gap-closure hardening Summary (partial: Task 1 done)

**Task 1 is done: every check that needs no cloud is green, and the live steps are listed by name. Tasks 2 (live setup) and 3 (live checks L1..L11, COVERAGE.md) are not run yet; this file is finished by the continuation.**

## Offline gate

Run on 2026-11-15 from the primary checkout (`main`, not a worktree), HEAD `65ce1b0`.

| Command | Exit | Result |
|---------|------|--------|
| `./run-unit-tests.sh --all` | 0 | 1584 passed, 26 skipped (all local-only: no Guides or live-artifact checkout) |
| `./run-unit-tests.sh --emulator` | 0 | 12 passed (Firestore and Pub/Sub emulators) |
| `scripts/validate-infra.sh` | 0 | prints "infra validation ok" |
| `scripts/compose-smoke.sh` | 0 | prints "round trip ok" |
| `bash -n` on `scripts/compose-smoke.sh`, `kind-smoke.sh`, `kind-up.sh`, `lock-requirements.sh`, `render-cloudrun.sh`, `sync-and-publish.sh`, `sync-image-smoke.sh`, `validate-infra.sh` | 0 each | clean |
| `bash -n deploy/cloudrun/bootstrap.sh` | 0 | clean |
| `scripts/render-cloudrun.sh mcp-server` with `SERVING_REVISION` set (previous revision at 100%, new revision at 0% behind tag `candidate`) | 0 | no `${` left |
| `scripts/render-cloudrun.sh mcp-server` with `SERVING_REVISION` unset (first-deploy form, new revision holds 100%) | 0 | no `${` left |
| `scripts/render-cloudrun.sh chat-bot`, `SERVING_REVISION` set | 0 | no `${` left |
| `scripts/render-cloudrun.sh chat-bot`, `SERVING_REVISION` unset | 0 | no `${` left |

The renders used made-up sample values and a temporary directory outside the repository; nothing was written under the repo (`git status --short` empty after the run).

### Base image scan flag of 04-23: resolved by a package pin, not a digest bump

04-23 flagged that the pinned `python:3.12-slim` digest ships two fixed HIGH findings in `zlib1g`, so the first deploy would fail the Trivy gate. Since 04-25 the orchestrator added two commits on `main`:

- `cbad9f5` test: failing test for the pinned `zlib1g` security fix in every stage (RED).
- `65ce1b0` fix: the Dockerfile installs the fixed `zlib1g` from `trixie-security` in every stage (4 pinned installs in `Dockerfile`), because the pinned digest is already the newest upstream image and still ships the vulnerable package.

Local Trivy 0.76.2 with `ignore-unfixed` reports 0 HIGH or CRITICAL on `mcp_server` and `chat_bot`. The digest is therefore not bumped, and the first deploy is expected to pass the scan gate under the `fixable` policy. L5 confirms this live.

### Live-readiness list (names only, no values)

Everything below needs Joshua's identity (gcloud config, gh login) and is run in Tasks 2 and 3, not here.

1. **Bootstrap re-run** on the existing project (README "Bootstrap", `deploy/cloudrun/bootstrap.sh`): creates `sa-publisher`, its `roles/storage.objectAdmin` on the index and videos buckets, and the owner's `roles/iam.serviceAccountTokenCreator` on it; binds `ci-deployer` to `roles/run.admin` (L8 checks that `roles/run.developer` is not held by it). The Firestore `describe` pre-check must be allowed to finish (a killed describe would fall into the create prompt). Fallback if it cannot finish: only `gcloud iam service-accounts create sa-publisher` and the three bindings.
2. **Optional, Joshua decides:** remove the owner's two `roles/storage.objectAdmin` bucket bindings (index and videos) so live IAM equals the repository.
3. **Five repository secrets** from the existing variables, without printing: `GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_DEPLOYER_SA`, `GCP_WIF_PROVIDER`, `GCP_OAUTH_CLIENT_ID` (`gh variable get <NAME> | gh secret set <NAME>`). The variables stay until the first green deploy on secrets. The four other variables (`GUIDES_WEB_BASE`, `CHAT_JWT_ISSUER_EMAIL`, `VIDEO_THUMBNAIL_URL`, `HELP_COMMAND_ID`) stay variables.
4. **The push** of `main` (64 local commits ahead of origin at HEAD `65ce1b0`); only when Joshua asks.
5. **After L1..L11 pass and Joshua agrees:** delete the five old variables (`gh variable delete <NAME>`).
6. **Optional, destructive, Joshua's choice (T-04-82):** delete older public run logs that still show identifiers. Nothing is deleted without his explicit request.

### Flagged assumptions this plan resolves live

04-20: Cloud Run accepts the image-index digest, and `--revision-suffix` works on a pipeline-named template. 04-22: first-deploy traffic form, tag host routing, `status.traffic` resolving the serving revision after the first deploy (L11). 04-23: Trivy registry auth, gha cache permissions, attested index accepted. 04-24: impersonated token minting. 04-25: zero identifiers in logs. Any that fails becomes a gap.

## Live setup

Pending (Task 2).

## Live checks

Pending (Task 3: L1..L11).

## Deferred review items

Not in this gap set; each goes to the backlog with its review id.

- IN-03 (04-REVIEW.md): Firestore IAM condition per collection. Outside this gap set because the gap asks for the five hardening items and the live proof, not for per-collection IAM conditions. backlog
- IN-04 (04-REVIEW.md): assert in the bot CLI instead of an explicit raise, and chat recording names that reset on restart. Outside this gap set because no gap item touches the bot CLI or the recording names. backlog
- IN-05 (04-REVIEW.md): `kind-up.sh` edge cases (reused cluster mount check, amd64-only download, `&` in the path). Outside this gap set because kind is a local smoke tool, not part of the deploy path proved here. backlog
- IN-06 (04-REVIEW.md): compose Meridian can start with an empty API key, and `validate-infra.sh` mounts the repo read-write. Outside this gap set because both are local-only and carry no live-deploy effect. backlog
- IN-09 (04-REVIEW.md): the chat-bot container has no probe on kind. Outside this gap set because it concerns the kind manifest only, not Cloud Run. backlog
- Meridian sidecar image by digest and its scan (gap statement): the gap names the two service images only; the sidecar is built by `meridian.yml` and deserves its own pinning and scan. backlog
- Cosign signature and `actions/attest` (CICD_GUIDE section 16): not requested by the gap; SBOM and provenance from BuildKit are what was asked. backlog
- CI on Dependabot pull requests (plan 04-26 deferred list): workflows run on push to main only, so Dependabot PRs get no CI today; a trigger change is a separate decision. backlog
