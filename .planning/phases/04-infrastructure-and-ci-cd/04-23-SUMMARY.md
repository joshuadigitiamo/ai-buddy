---
phase: 04-infrastructure-and-ci-cd
plan: 23
subsystem: infra
tags: [github-actions, buildkit, gha-cache, sbom, provenance, trivy, supply-chain, gap-closure]
status: complete

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: _deploy.yml with auth, build-push by digest, serving lookup, render, replace (04-22); pin-by-commit test (04-21)
provides:
  - "build-push in _deploy.yml and meridian.yml reads and writes a type=gha BuildKit cache, mode=max, one scope per image"
  - "service images carry an SBOM (sbom: true) and max provenance (provenance: mode=max)"
  - "step 'Scan the pushed image': trivy-action pinned to the verified v0.36.0 commit, Trivy v0.76.2, CRITICAL,HIGH, exit-code 1, ignore-unfixed true, scans <repo>/<service>@<steps.build.outputs.digest> right after the push"
  - "order test pins test job -> build -> scan -> serving lookup -> render -> dry run -> replace -> candidate check -> switch -> live check"
affects: [04-26]

actuals:
  tokens: 9000
  tasks: 3
  commits: 6

plan_head_before: 22dc05e83b6cd75b544de7cb2040ca9bef7337ce
plan_head_after: c28d47afbb71f15451dcd623f8ce62f14265d9b2

tech-stack:
  added: ["aquasecurity/trivy-action v0.36.0 (commit-pinned)", "Trivy binary v0.76.2"]
  patterns:
    - "Push then scan the digest: the scanned digest is the rendered digest (same steps.build.outputs.digest)"
    - "Scan policy recorded in the SUMMARY and enforced by a test that reads it"

key-files:
  created: []
  modified:
    - .github/workflows/_deploy.yml
    - .github/workflows/meridian.yml
    - tests/unit/test_deploy_pipeline.py
    - tests/unit/test_workflows.py

key-decisions:
  - "scan-policy fixable: ignore-unfixed true; no .trivyignore.yaml (the owner, 2026-11-15, on measured local counts)"
  - "Trivy binary v0.76.2, outside GHSA-69fq-xp46-6x23, set explicitly in with.version; test rejects 0.69.4, 0.69.5, 0.69.6"

requirements-completed: []

coverage:
  - id: D1
    description: "gha layer cache per image in _deploy.yml and meridian.yml"
    requirement: INFRA-05
    verification:
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_builds_use_a_per_image_gha_cache"
        status: pass
    human_judgment: false
  - id: D2
    description: "SBOM and provenance attached to service images"
    requirement: INFRA-05
    verification:
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_service_images_carry_sbom_and_provenance"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pushed digest scanned before the serving lookup and render, with the recorded policy"
    requirement: INFRA-06
    verification:
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_the_pushed_digest_is_scanned_before_render"
        status: pass
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_scan_policy_matches_the_recorded_decision"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_deploy_steps_run_in_the_required_order"
        status: pass
    human_judgment: false
  - id: D4
    description: "Live proof: cache hit, attestations present, scan ran, Cloud Run accepts the image index, Trivy reads Artifact Registry"
    verification: []
    human_judgment: true
    rationale: "Needs a real deploy run on GitHub and GCP; planned for 04-26"

duration: 40min
completed: 2026-11-15
---

# Phase 04 Plan 23: Cache, SBOM, provenance and scan Summary

**CI builds read and write a per-image gha layer cache, service images carry SBOM and max provenance, and a commit-pinned Trivy scan of the pushed digest fails the deploy on fixable HIGH or CRITICAL findings before any revision exists.**

## Performance

- **Duration:** about 40 min across the initial run and the continuation after the policy decision
- **Completed:** 2026-11-15
- **Tasks:** 3 (Task 1 tracer, Task 2 decision, Task 3 policy)
- **Files modified:** 4 source and test files, plus this summary

## Accomplishments

- `type=gha` cache with `mode=max` and scopes `mcp-server`, `chat-bot` (from `inputs.service`) and `meridian`.
- `sbom: true` and `provenance: mode=max` on the service image build.
- "Scan the pushed image" step directly after the build, on `<repo>/<service>@<digest>`, authenticating with the job's short-lived WIF access token (`TRIVY_USERNAME: oauth2accesstoken`, `TRIVY_PASSWORD` from `steps.auth.outputs.access_token`). No key file, no long-lived token, action pinned by commit.
- Tests: per-image cache, attestations, scan placement and inputs, order test extended, `test_scan_policy_matches_the_recorded_decision` (reads the `scan-policy:` line below and checks `ignore-unfixed` and the absence of `.trivyignore.yaml`).

## Task Commits

1. **Task 1 (tracer), RED:** `e1219f9` (test)
2. **Task 1 (tracer), GREEN:** `231b400` (feat)
3. **Task 2 (decision record):** `675ea46` (docs)
4. **Task 3, RED:** `01ef313` (test)
5. **Task 3, GREEN:** `f051746` (feat)
6. **Task 3, lint fix of the new test comment:** `c28d47a` (style)

**Plan metadata:** the docs commit that carries this file, STATE.md and ROADMAP.md.

## Pin verification

- trivy-action tag `v0.36.0` -> annotated tag object `a9c7b0f06e461e9d4b4d1711f154ee024b8d7ab8` -> commit `ed142fd0673e97e23eac54620cfb913e5ce36c25` (the pinned SHA; tag created 2026-04-22).
- GHSA-69fq-xp46-6x23 affected: trivy binary 0.69.4, trivy-action < 0.35.0, setup-trivy < 0.2.6; DockerHub trivy images v0.69.5 and v0.69.6 are named compromised.
- trivy-action v0.36.0 pins setup-trivy `3fb12ec12f41e471780db15c232d5dd185dcb514` (v0.2.6).
- Chosen Trivy binary: `v0.76.2` (released 2026-11-05), set in `with.version`. A test rejects 0.69.4, 0.69.5 and 0.69.6.

## Local scan counts

Scanner: `aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb` (0.76.2). Images built with `--target mcp_server` and `--target chat_bot` (Debian 13.7 on the pinned `python:3.12-slim`); Python dependencies: 0 findings. Counts are per package hit.

| Image | CRITICAL fixed | CRITICAL unfixed | HIGH fixed | HIGH unfixed |
|-------|----------------|------------------|------------|--------------|
| mcp-server | 0 | 0 | 2 | 47 |
| chat-bot | 0 | 0 | 2 | 47 |

Fixed (2 CVEs, zlib1g, fix `1:1.3.dfsg+really1.3.1-1+deb13u1`, not in the pinned base digest): CVE-2026-76844, CVE-2026-85091.

Unfixed (11 CVEs, all HIGH, Debian OS packages):
- util-linux family (36 of the 47 hits): CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410
- ncurses: CVE-2025-69720
- libsqlite3-0: CVE-2026-119373, CVE-2026-119374, CVE-2026-119379
- libsystemd0, libudev1: CVE-2026-16742
- libacl1: CVE-2026-54369
- perl-base: CVE-2026-9538

## Scan policy

Decision by the owner (via the orchestrator, 2026-11-15): fail only on findings that have a fixed version (`ignore-unfixed: true`, as CICD_GUIDE section 16). Dependabot (04-21) moves the base image as fixes land; unfixed findings ship without a per-CVE record. The choice is reversible (one input).

scan-policy: fixable

## Decisions Made

- Policy `fixable` (above). No `.trivyignore.yaml` is created, as the plan specifies for this option.
- The policy test reads the `scan-policy:` line from this file under `.planning/`, so changing the policy means editing this record and the workflow together.

## Deviations from Plan

**1. [Rule 1 - Bug] Test comment exceeded the ruff line limit**
- **Found during:** Task 3 full run (`./run-unit-tests.sh --all` stops at `ruff check`)
- **Fix:** shortened the comment, no logic change
- **Committed in:** `c28d47a`

Otherwise none; the plan ran as written, with the Task 2 decision taken by the user.

## Issues Encountered

None open. `./run-unit-tests.sh --all`: 1567 passed, 26 skipped (all local-only live-artifact tests). `scripts/validate-infra.sh`: "infra validation ok".

## Flags for 04-26 (live proof)

1. **First deploy will fail the scan gate.** The pinned `python:3.12-slim` digest carries the 2 fixed HIGH CVEs in zlib1g (CVE-2026-76844, CVE-2026-85091). Until the base digest is bumped (Dependabot PR, or a manual bump plus `scripts/lock-requirements.sh` re-run), both services fail the gate under `fixable`. Bump the digest before the first deploy.
2. Cloud Run must accept the image index that now carries SBOM and provenance manifests [Medium assumption, unverified].
3. Trivy must authenticate to Artifact Registry with `TRIVY_USERNAME=oauth2accesstoken` and the WIF access token [Medium assumption, unverified].
4. The gha cache must work with the job permissions (`contents: read`, `id-token: write`) [Medium assumption, unverified]; confirm a cache hit on the second run.

## Known Stubs

None.

## Threat Flags

None. The scan step adds no endpoint or credential beyond the existing short-lived access token (T-04-71, T-04-72, T-04-73 mitigated as planned).

## Requirements

INFRA-05 and INFRA-06 are shared with other plans and the live proof is 04-26, so they are not force-marked complete here.

## Self-Check: PASSED

Commits `e1219f9`, `231b400`, `675ea46`, `01ef313`, `f051746`, `c28d47a` are ancestors of HEAD; the four modified files exist; `.trivyignore.yaml` is absent as the policy requires.
