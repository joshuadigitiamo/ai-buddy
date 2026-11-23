---
phase: 04-infrastructure-and-ci-cd
plan: 18
subsystem: infra
tags: [pip-tools, hashed-locks, require-hashes, docker, supply-chain, wr-04]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: Dockerfile stages (base, test, mcp_server, chat_bot, sync) and the plain requirement files
provides:
  - scripts/lock-requirements.sh regenerating four hashed locks in Docker
  - requirements-dev.lock, services/mcp_server/requirements.lock, services/chat_bot/requirements.lock, jobs/sync/requirements.lock
  - every Dockerfile pip install runs with --require-hashes against a committed lock
  - tests/unit/test_requirements_lock.py (format, input agreement, stage-subset, prohibition tests)
affects: [04-21 base image digest pin (script reads the first FROM line), CI path filters]

actuals:
  tokens: 135000  # chars/4 over the realized diff; about 4500 of it is code and tests, the rest is the four lock files
  tasks: 3
  commits: 4  # MEASURED: git rev-list --count 64df40f..HEAD, task commits only; the metadata commit follows
plan_head_before: 64df40f152ad8dcf45576b35b44ab6d014722d4a
plan_head_after: 5d8e542fbd6fe5bb141d3e37880766f5a7257610

tech-stack:
  added: [pip-tools 7.6.2 (throwaway lock container only, never in an image or requirements-dev.txt)]
  patterns: [compile stage locks with the dev lock as a constraint, hash-checked installs]

key-files:
  created:
    - scripts/lock-requirements.sh
    - requirements-dev.lock
    - services/mcp_server/requirements.lock
    - services/chat_bot/requirements.lock
    - jobs/sync/requirements.lock
    - tests/unit/test_requirements_lock.py
  modified:
    - Dockerfile
    - tests/unit/test_dockerfile_stages.py
    - tests/unit/test_workflows.py
    - .github/workflows/tests.yml

key-decisions:
  - "Stage locks are compiled with the pins of requirements-dev.lock as a constraint, so shipped and tested images resolve the same versions"
  - "Runtime stages drop the plain requirement files and COPY only their own lock; the base stage copies only requirements-dev.lock"
  - "scripts/lock-requirements.sh reads the base image from the Dockerfile's first FROM line so the 04-21 digest pin flows in unedited"

requirements-completed: [INFRA-01, INFRA-06]

coverage:
  - id: D1
    description: "Test image installs a fully hashed requirements-dev.lock with --require-hashes and the full suite passes on it"
    requirement: "INFRA-06"
    verification:
      - kind: unit
        ref: "tests/unit/test_requirements_lock.py#test_test_stage_installs_the_dev_lock_with_require_hashes"
        status: pass
      - kind: unit
        ref: "./run-unit-tests.sh --all (1521 passed, coverage 97.60 percent)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every lock entry is pinned with == and carries sha256 hashes; empty or unhashed locks fail"
    requirement: "INFRA-06"
    verification:
      - kind: unit
        ref: "tests/unit/test_requirements_lock.py#test_lock_is_pinned_and_every_entry_has_a_hash"
        status: pass
      - kind: unit
        ref: "tests/unit/test_requirements_lock.py#test_lock_parser_rejects_empty_unpinned_and_unhashed_locks"
        status: pass
    human_judgment: false
  - id: D3
    description: "Input pins equal lock versions (message names package and regeneration command) and stage locks equal the dev lock versions"
    requirement: "INFRA-06"
    verification:
      - kind: unit
        ref: "tests/unit/test_requirements_lock.py#test_input_pin_drift_names_the_package_and_an_equal_pin_passes"
        status: pass
      - kind: unit
        ref: "tests/unit/test_requirements_lock.py#test_stage_lock_versions_equal_the_dev_lock"
        status: pass
    human_judgment: false
  - id: D4
    description: "mcp_server, chat_bot and sync images install only their own hashed lock; all three build and the compose round trip works"
    requirement: "INFRA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_dockerfile_stages.py#test_runtime_stages_install_only_their_hashed_lock"
        status: pass
      - kind: integration
        ref: "docker build --target mcp_server|chat_bot|sync . && scripts/compose-smoke.sh (round trip ok)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Locks resolve for linux/amd64 CPython 3.12 only; installability on another platform is not tested"
    verification: []
    human_judgment: true
    rationale: "Flagged plan assumption: pip-compile hashes every published file of each pinned version, but no other platform was exercised"

duration: 18min
completed: 2026-11-15
status: complete
---

# Phase 4 Plan 18: Hashed dependency locks Summary

**Four pip-compile locks with sha256 hashes (dev, mcp_server, chat_bot, sync), generated in Docker by one script, installed in every image stage with `pip install --require-hashes`, and tested so the shipped and tested dependency versions cannot drift.**

## pip-tools approval

pip-tools==7.6.2

The owner's reply: "Approve 7.6.2 (2026-11-15)".

Evidence shown at the gate: base image `python:3.12-slim` ships pip 25.0.1; pip-tools 7.6.2 was uploaded 2026-10-07, is not yanked, requires Python >=3.9 and pip >=22.2; source https://github.com/jazzband/pip-tools. No `pip install pip-tools` ran before the reply. pip-tools installs only into a throwaway venv inside the lock-generation container, never into an image or requirements-dev.txt (pinned by `test_pip_tools_stays_out_of_the_images_and_requirement_files`).

## Performance

- **Duration:** about 18 min for this continuation (Task 1 gate was a separate earlier run)
- **Completed:** 2026-11-15T14:40Z
- **Tasks:** 3 (Task 1 gate, Task 2 tracer, Task 3 runtime stages)
- **Files modified:** 10

## Accomplishments

- `scripts/lock-requirements.sh` (mode 100755 in the index): one Docker container from the Dockerfile's first FROM image builds a throwaway venv with pip-tools 7.6.2 and writes the four locks; stage locks use the dev lock pins as a constraint.
- Test image now builds from `requirements-dev.lock` with `--require-hashes`; the full suite (1521 passed, coverage 97.60 percent) runs on it.
- Runtime stages mcp_server, chat_bot and sync each COPY only their own lock and run exactly one `pip install --require-hashes -r <lock>`; all three build and `scripts/compose-smoke.sh` printed "round trip ok".
- `tests/unit/test_requirements_lock.py` (20 tests): lock format and hashes, empty/unhashed rejection, input-pin agreement with a package-naming message, stage-subset equality with the dev lock, script pins the approved version, pip-tools absent from images and requirement files.

## Task Commits

1. **Task 1: Package legitimacy gate for pip-tools** - no commit (read-only evidence; approval recorded above)
2. **Task 2: Tracer, hashed test image** - `1230229` (test, RED), `6059ee0` (feat, GREEN)
3. **Task 3: Runtime images from hashed locks** - `1aa64c4` (test, RED), `5d8e542` (feat, GREEN)

**Plan metadata:** docs(04-18) commit following this file.

## Files Created/Modified

- `scripts/lock-requirements.sh` - regenerates the four locks in Docker
- `requirements-dev.lock`, `services/mcp_server/requirements.lock`, `services/chat_bot/requirements.lock`, `jobs/sync/requirements.lock` - hashed locks
- `Dockerfile` - test and runtime stages install locks with `--require-hashes`; plain requirement COPYs dropped
- `tests/unit/test_requirements_lock.py` - new lock tests
- `tests/unit/test_dockerfile_stages.py` - new per-stage lock test; sync copy sources and test-image test follow the lock layout
- `tests/unit/test_workflows.py`, `.github/workflows/tests.yml` - requirements-dev.lock path trigger

## Decisions Made

- Stage locks compiled against the dev lock pins (constraint file derived in the container) so tested and shipped sets agree.
- Dev lock is compiled in place, so a rerun keeps existing pins unless a requirement file changes; transitive upgrades are a deliberate lock regeneration, not a side effect of a build.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] tests.yml did not trigger on requirements-dev.lock**
- **Found during:** Task 3
- **Issue:** The test image is now built from requirements-dev.lock, but the test-only workflow's path filter listed only requirements-dev.txt, so a lock-only change (for example a Dependabot-style regeneration) would not run the gate.
- **Fix:** added `requirements-dev.lock` to `.github/workflows/tests.yml` paths and to the path list asserted in `test_test_only_workflow_covers_the_files_no_service_image_copies`.
- **Files modified:** .github/workflows/tests.yml, tests/unit/test_workflows.py
- **Commit:** 5d8e542

**2. [Rule 3 - Blocking] git index mode of the new script**
- **Found during:** Task 2
- **Issue:** `core.fileMode=false` in this checkout made `git add` record 100644 despite `chmod +x`.
- **Fix:** `git update-index --chmod=+x scripts/lock-requirements.sh` and amended the unpushed feat commit; index now shows 100755.
- **Commit:** 6059ee0

**3. [Rule 1 - Bug] Own test helper could not parse non-`python:3.12-slim` stages**
- **Found during:** Task 2
- **Issue:** `_dockerfile_stage` in test_repo_layout matches only `FROM python:3.12-slim AS <name>`, so it cannot read the `test` stage (`FROM base AS test`).
- **Fix:** `test_requirements_lock.py` carries its own `_stage_instructions` regex helper; shared helpers untouched.

**Total deviations:** 3 auto-fixed. **Impact:** none on scope; the `core.fileMode=false` local git setting means any future executable script needs `git update-index --chmod=+x`.

### Process notes

- Protected-branch guard: HEAD is `main`, which the guard classes as protected; commits were made on `main` on purpose per the project rule "work on main, no branches" (user memory) and the dispatch instructions, without editing `.planning/config.json`.
- The requirement IDs INFRA-01 and INFRA-06 were reported `blocked` by `requirements.ready-ids` (sibling gap plans still unfinished), so they were not marked complete in REQUIREMENTS.md; they stay open until the last declaring plan finishes.

## Issues Encountered

- Residual, accepted by the plan: pip-tools' own dependencies (build, click, setuptools and so on) are installed unhashed inside the throwaway lock container. They never reach an image or a committed file; the locks themselves are hash-checked at every image build.
- Locks resolve for linux/amd64 CPython 3.12 only (flagged plan assumption).

## Known Stubs

None.

## Threat Flags

None. The new surface (lock container running pip-tools against PyPI) is the one modelled as T-04-58.

## Self-Check: PASSED

- Files exist: scripts/lock-requirements.sh, the four locks, tests/unit/test_requirements_lock.py.
- Commits 1230229, 6059ee0, 1aa64c4, 5d8e542 are ancestors of HEAD.
- `git ls-files -s scripts/lock-requirements.sh` shows 100755; `grep -c require-hashes Dockerfile` prints 4; `grep -c -- --hash=sha256: requirements-dev.lock` prints 2169.
- `./run-unit-tests.sh --all` exit 0 (1521 passed); test_workflows.py and test_dockerfile_stages.py green; three runtime builds and `scripts/compose-smoke.sh` ("round trip ok") pass.
