---
phase: 04-infrastructure-and-ci-cd
plan: 21
subsystem: infra
tags: [docker, base-image-digest, dependabot, dockerignore, github-actions, path-filters, supply-chain]
status: complete

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: hashed locks and scripts/lock-requirements.sh reading the Dockerfile's first FROM line (04-18)
provides:
  - python:3.12-slim pinned by digest in all four external FROM lines
  - dependabot entries for github-actions, docker (/) and pip (/, /services/mcp_server, /services/chat_bot, /jobs/sync)
  - narrower .dockerignore (nested .env, *.db, .cache, .planning/, tests/, .github/)
  - tests.yml push paths for deploy/cloudrun, .env.example, .dockerignore, .github/dependabot.yml
affects: [Dependabot PR handling (pip PRs need regenerated locks), CI path filters]

actuals:
  tokens: 3000  # chars/4 over the realized diff (6 text files, small hand-written changes)
  tasks: 2
  commits: 4  # MEASURED: git rev-list --count c452b12..HEAD, task commits only; the metadata commit follows
plan_head_before: c452b12a76dfe1a5aed26ec3cff60d042dee6b8d
plan_head_after: ae4b7401801830b1212d3f76b3b502c2dc20c953

tech-stack:
  added: []
  patterns: [tag@digest FROM lines written literally so Dependabot can move each one, dependabot opens PRs and a person merges]

key-files:
  created: []
  modified:
    - Dockerfile
    - .dockerignore
    - .github/dependabot.yml
    - .github/workflows/tests.yml
    - tests/unit/test_dockerfile_stages.py
    - tests/unit/test_workflows.py
    - tests/unit/test_repo_layout.py

key-decisions:
  - "Base image digest sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b (multi-arch index of python:3.12-slim, resolved 2026-11-15) in every FROM line, written literally with no ARG"
  - "Dependabot only opens PRs; pip PRs must be updated with scripts/lock-requirements.sh before merging, otherwise the lock test fails on main"
  - "tests.yml gained deploy/cloudrun/**, .env.example, .dockerignore and .github/dependabot.yml (requirements-dev.lock was already listed by 04-18)"

requirements-completed: [INFRA-01, INFRA-06]

coverage:
  - id: D1
    description: "All four FROM lines are python:3.12-slim@sha256:<64 hex> with one shared digest, and every stage still builds"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_dockerfile_stages.py#test_every_stage_uses_the_same_digest_pinned_base"
        status: pass
      - kind: other
        ref: "for t in test mcp_server chat_bot sync; do docker build -q --target $t .; done"
        status: pass
    human_judgment: false
  - id: D2
    description: "Dependabot watches github-actions, docker and four pip directories weekly"
    requirement: "INFRA-06"
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_dependabot_watches_actions_docker_and_pip"
        status: pass
    human_judgment: false
  - id: D3
    description: ".dockerignore keeps nested env files, databases, caches, planning notes, tests and CI files out of the build context"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_dockerfile_stages.py#test_dockerignore_keeps_private_paths_out_of_the_build_context"
        status: pass
      - kind: other
        ref: "scripts/validate-infra.sh (infra validation ok) and scripts/compose-smoke.sh (round trip ok)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The test-only workflow runs on cloudrun runbook and bootstrap, .env.example, .dockerignore, dependabot.yml and requirements-dev.lock changes"
    requirement: "INFRA-06"
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_test_only_workflow_covers_the_files_no_service_image_copies"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-11-15
---

# Phase 04 Plan 21: Base image digest pin, Dependabot, build context and test gate Summary

**python:3.12-slim pinned by digest in all four FROM lines, Dependabot widened to docker and four pip directories, .dockerignore narrowed, and tests.yml triggered by every file tests read but no image copies.**

## Base image digest

- Image: `python:3.12-slim` (multi-arch index digest, top-level `Digest:` line of `docker buildx imagetools inspect`)
- Digest: `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`
- Resolved: 2026-11-15
- `scripts/lock-requirements.sh` takes `awk '/^FROM /{print $2; exit}'` from the Dockerfile, which now yields `python:3.12-slim@sha256:...`, so the lock container uses the pinned base unedited.

## Accomplishments

- RED/GREEN for Task 1 (tracer): `test_every_stage_uses_the_same_digest_pinned_base` plus the dependabot test failed on the plain `FROM python:3.12-slim AS ...` lines and on the single-entry file; the digest and the docker ecosystem entry turned them green. All four targets (`test`, `mcp_server`, `chat_bot`, `sync`) build.
- Task 2: four `pip` Dependabot entries with a comment that a pip PR needs `scripts/lock-requirements.sh` before merge; six `.dockerignore` lines; five `tests.yml` path additions (the sixth, `requirements-dev.lock`, already existed from 04-18 and is now also covered by the test list).
- Verified: `./run-unit-tests.sh --all` (1533 passed, 26 skipped, coverage 97.60 percent, ruff and mypy clean), `scripts/validate-infra.sh` ("infra validation ok") and `scripts/compose-smoke.sh` ("round trip ok"). Tracer gate re-ran green before Task 2 started.

## RED evidence (TDD)

- Task 1 RED (`b460e66`): `test_every_stage_uses_the_same_digest_pinned_base` failed on the assertion that every FROM line is digest-pinned, the three `test_runtime_stage_is_slim_and_ends_non_root[...]` cases failed on the pinned-FROM match, and `test_dependabot_watches_actions_docker_and_pip` failed on the missing docker pair. Semantic assessment: assertion failures for the planned behaviour, not load or fixture errors.
- Task 2 RED (`47bf7b5`): `test_dependabot_watches_actions_docker_and_pip` (missing pip pairs), `test_test_only_workflow_covers_the_files_no_service_image_copies` (cloudrun, .env.example, .dockerignore, dependabot paths) and `test_dockerignore_keeps_private_paths_out_of_the_build_context` (six entries) failed on their planned assertions.
- The RED evidence was inspected from pytest output, not run through `gsd_run check tdd-red-evidence` (pytest text is not one of the classifier's supported report formats).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_dockerfile_stage` helper only matched the unpinned FROM text**
- **Found during:** Task 1 (GREEN, after pinning the Dockerfile)
- **Issue:** `tests/unit/test_repo_layout.py::_dockerfile_stage` located a stage with `text.find("FROM python:3.12-slim AS <name>")`, so 13 unrelated stage tests failed once the digest was in the FROM line. That file is not in the plan's `files_modified`.
- **Fix:** The helper now finds the stage with a regex that accepts the optional `@sha256:<64 hex>`; added `import re`.
- **Files modified:** tests/unit/test_repo_layout.py
- **Commit:** b65846f

**2. [Rule 3 - Blocking] Line length in the new dockerignore test comment**
- **Found during:** Task 2
- **Issue:** a 102-character comment line would fail `ruff check` (limit 100).
- **Fix:** Shortened the comment before the GREEN commit.
- **Files modified:** tests/unit/test_dockerfile_stages.py
- **Commit:** ae4b740

**Total deviations:** 2 auto-fixed (both Rule 3). **Impact:** none on scope; one extra test-helper file touched.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None. T-04-65, T-04-66 and T-04-67 are mitigated as planned; no new packages were installed (T-04-SC).

## Flagged assumptions

- kind smoke was not re-run (needs a cluster); compose round trip and infra validation cover the rebuilt images.
- Dependabot behaviour (PR creation, digest rewriting in the four FROM lines) cannot be exercised locally; it is verified only by the configuration test.
- INFRA-01 and INFRA-06 are shared requirement IDs: left to the ready-ids gate (see STATE update), not force-marked.

## TDD Gate Compliance

RED (`test(04-21)`) commits `b460e66`, `47bf7b5` precede GREEN (`feat(04-21)`) commits `b65846f`, `ae4b740`. No refactor commit.

## Commits

- b460e66: test(04-21): add failing tests for digest-pinned base and docker dependabot entry
- b65846f: feat(04-21): pin the base image by digest in every stage and add docker dependabot
- 47bf7b5: test(04-21): add failing tests for pip dependabot, narrower dockerignore and tests.yml paths
- ae4b740: feat(04-21): dependabot for pip pins, narrower build context, wider test gate

## Next

Ready for the next plan in the phase.

## Self-Check: PASSED

- Modified files exist: Dockerfile, .dockerignore, .github/dependabot.yml, .github/workflows/tests.yml, tests/unit/test_dockerfile_stages.py, tests/unit/test_workflows.py, tests/unit/test_repo_layout.py
- Commits b460e66, b65846f, 47bf7b5, ae4b740 are ancestors of HEAD
- Acceptance criteria re-run: FROM pinned count 4, package-ecosystem count 6, pip count 4, `**/` dockerignore count 4, deploy/cloudrun in tests.yml 1, `--all` exit 0
