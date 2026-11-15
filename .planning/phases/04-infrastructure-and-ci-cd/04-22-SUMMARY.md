---
phase: 04-infrastructure-and-ci-cd
plan: 22
subsystem: infra
tags: [cloud-run, ci-cd, staged-deploy, candidate-tag, traffic, runbook, gap-closure]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: digest deploy, run-named revision, forced revision suffix (04-20); base digest, dockerignore, tests.yml paths (04-21)
provides:
  - "Every CI deploy creates its revision at 0% under the tag candidate, checks it on the candidate---<service>-<PROJECT_NUMBER> URL, then moves all traffic with --to-latest and drops the tag"
  - "scripts/serving_revision.py: stdlib lookup of the revision holding 100% in status.traffic, failing closed on split, unresolved or foreign traffic"
  - "render-cloudrun.sh: SERVING_REVISION (default: the new revision) with a per-service format check"
  - "sync-and-publish.sh refuses a forced revision while traffic is pinned and says the index is published"
  - "Runbook section Staged deploys"
affects: [04-26]

actuals:
  tokens: 8200
  tasks: 2
  commits: 4

plan_head_before: 96ed26bcbbc9739b9530859554f262a026b2bf31
plan_head_after: 6d7bbeb576ce812246c7b8cc8e2cb44bab6c2667

tech-stack:
  added: []
  patterns:
    - "Resolved traffic (status.traffic), never requested traffic (spec.traffic), names the serving revision"
    - "Empty lookup output means first deploy and nothing else; every other unclear state exits 2"
    - "Candidate check re-reads traffic before any request and fails if the new revision already serves"

key-files:
  created:
    - scripts/serving_revision.py
  modified:
    - .github/workflows/_deploy.yml
    - scripts/render-cloudrun.sh
    - scripts/sync-and-publish.sh
    - deploy/cloudrun/mcp-server.yaml
    - deploy/cloudrun/chat-bot.yaml
    - deploy/cloudrun/README.md
    - tests/unit/test_deploy_pipeline.py
    - tests/unit/test_workflows.py
    - tests/unit/test_sync_and_publish_script.py

key-decisions:
  - "The serving revision is read from status.traffic; spec.traffic carries no revision name in latest-revision mode"
  - "The publish guard describes the service with --format json and reads spec.traffic in the gcloud image, instead of json(spec.traffic), so the parsed shape is the documented full Knative document"
  - "A manual replace without SERVING_REVISION pins traffic to the new revision; the runbook gives the two update-traffic commands that restore latest-revision mode"

patterns-established:
  - "Step order of _deploy.yml: build, find serving revision, render, dry run, replace, candidate check, traffic switch, live check"

requirements-completed: []

coverage:
  - id: D1
    description: "Both templates stage the new revision: serving target at 100%, new revision at 0% with tag candidate; mcp-server allows the candidate host"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_templates_stage_the_new_revision_behind_the_candidate_tag"
        status: pass
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_server_allows_the_candidate_host"
        status: pass
      - kind: other
        ref: "host render of both services with SERVING_REVISION=mcp-server-r1-1; SERVING_REVISION=other-1 refused"
        status: pass
    human_judgment: false
  - id: D2
    description: "Serving-revision lookup reads status.traffic and refuses split, unresolved, foreign or invalid input without echoing it"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_serving_lookup_reads_the_resolved_status_traffic"
        status: pass
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_serving_lookup_refuses_split_or_unresolved_traffic"
        status: pass
    human_judgment: false
  - id: D3
    description: "_deploy.yml checks the candidate (traffic proof first, same expectations, one unauthenticated POST for chat-bot) before the switch, and the switch runs --to-latest then --remove-tags candidate"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_deploy_pipeline.py#test_deploy_checks_the_candidate_before_moving_traffic"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_deploy_steps_run_in_the_required_order"
        status: pass
      - kind: other
        ref: "scripts/validate-infra.sh (actionlint on _deploy.yml) prints infra validation ok"
        status: pass
    human_judgment: false
  - id: D4
    description: "sync-and-publish refuses the forced revision while traffic is pinned; runbook documents staged deploys and recovery"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_sync_and_publish_script.py#test_forced_revision_waits_for_latest_revision_traffic"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live behaviour: the first-deploy form passes services replace, the tagged host routes right after replace, status.traffic carries the resolved revisionName after a deploy past the first, and the service returns to latest-revision mode"
    requirement: "INFRA-05"
    verification: []
    human_judgment: true
    rationale: "Flagged assumptions that only a live deploy can confirm; the live proof is 04-26 (L11)"

duration: about 35min
completed: 2026-11-15
status: complete
---

# Phase 4 Plan 22: Staged deploys behind the candidate tag Summary

**Each CI deploy now brings its revision up at 0% under the tag `candidate`, runs the post-deploy checks on the tagged URL, and only then moves all traffic with `--to-latest` and removes the tag; the serving revision is read from `status.traffic`, and the laptop publish refuses to force a revision while traffic is pinned.**

## Performance

- **Duration:** about 35 min (start time was not captured; estimate)
- **Completed:** 2026-11-15T15:15Z
- **Tasks:** 2 (4 commits: RED and GREEN per task)
- **Files modified:** 10 (1 created)

## Accomplishments
- Both templates end with a `traffic` block: `${SERVING_REVISION}` at 100%, `<service>-${DEPLOY_ID}` at 0% with `tag: candidate`. `mcp-server.yaml` sets `MCP_ALLOWED_HOSTS` to the candidate host so the Host guard answers `GET /health` with 200 there.
- `scripts/serving_revision.py` (stdlib, ruff-clean) takes the describe JSON on stdin and prints the revision at 100% in `status.traffic`. Missing `status`, a split, a missing or foreign name, bad JSON and empty input all exit 2 with a names-only `::error::` line and empty stdout; it never falls back to `spec.traffic`.
- `render-cloudrun.sh` accepts optional `SERVING_REVISION`, defaults it to `<service>-<DEPLOY_ID>` and checks it against `^<service>-[a-z0-9]([a-z0-9-]{0,50}[a-z0-9])?$`. It sits in both per-service lists, so the render-list parity test still holds.
- `_deploy.yml` gains three steps: "Find the serving revision" (id `serving`, empty output only when the service does not exist), "Check the candidate revision" (re-reads `status.traffic` first and fails with `the new revision took traffic before its checks`, then runs the same expectations on `https://candidate---...`), and "Move traffic to the candidate" (`--to-latest`, then `--remove-tags candidate`). The live check stays last. The chat-bot candidate receives exactly one unauthenticated `POST /` expected to return 401, so no model call and no second Meridian turn happens (INFRA-05 prohibition).
- `sync-and-publish.sh` describes the service as JSON, parses `spec.traffic` in the google/cloud-sdk container, and stops unless exactly one target holds 100% with `latestRevision: true`. The refusal names the service, says the index is already published, and says the next successful deploy loads it. It prints no JSON.
- README section "Staged deploys": the five steps, what a red candidate leaves behind, how to drop the tag by hand, what to do about split traffic, why the publish refuses, and the manual-replace caveat.

## Task Commits

1. **Task 1: tracer, staged deploy behind the candidate tag** - `de21438` (test, RED), `99f3e6f` (feat, GREEN)
2. **Task 2: publish guard and runbook** - `6ae44c1` (test, RED), `6d7bbeb` (feat, GREEN)

**Plan metadata:** the docs(04-22) commit that carries this file.

## TDD Gate Compliance

RED then GREEN for both tasks, in order (`test(04-22)` precedes `feat(04-22)` each time). RED evidence, Task 1: 14 target tests failed in `test_deploy_pipeline.py` plus `test_deploy_steps_run_in_the_required_order`, on missing helper file, missing `spec.traffic`, missing step and missing env entry (assertions for the planned behaviour, no import or syntax fault). RED evidence, Task 2: `test_forced_revision_waits_for_latest_revision_traffic` failed on "the guard reads the service as JSON before it forces a revision" with the two sibling tests passing. No refactor commit.

## Tracer gate

Auto mode: after GREEN the Task 1 verify block was re-run end to end: both test files pass, the host render of both services with `SERVING_REVISION=mcp-server-r1-1` succeeds and `SERVING_REVISION=other-1` is refused, and `scripts/validate-infra.sh` prints `infra validation ok`. Tracer verified, expansion proceeded.

## Files Created/Modified
- `scripts/serving_revision.py` - new lookup helper
- `.github/workflows/_deploy.yml` - serving lookup, candidate check, traffic switch
- `scripts/render-cloudrun.sh` - SERVING_REVISION default and format check
- `deploy/cloudrun/mcp-server.yaml`, `deploy/cloudrun/chat-bot.yaml` - traffic block; candidate host env on mcp-server
- `scripts/sync-and-publish.sh` - traffic-mode guard
- `deploy/cloudrun/README.md` - Staged deploys section, manual-replace note
- `tests/unit/test_deploy_pipeline.py`, `tests/unit/test_workflows.py`, `tests/unit/test_sync_and_publish_script.py` - the new and rewritten tests

## Decisions Made
- The lookup reads only `status.traffic`: in latest-revision mode `spec.traffic` has no revision name, so reading it would report an empty "first deploy" for a service that is serving.
- The publish guard uses `--format json` and reads `spec.traffic` in the SDK image rather than `--format 'json(spec.traffic)'`: the full document shape is the documented one, while the projection's nesting was not verified. The JSON stays in a shell variable and is never printed.
- A manual `replace` without `SERVING_REVISION` pins traffic to the new revision (both targets name it), so the runbook tells the operator to run `--to-latest` and `--remove-tags candidate` afterwards; otherwise `sync-and-publish.sh` would refuse.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff E501 and import order on new code**
- **Found during:** Task 1 (`./run-unit-tests.sh --all` lint step)
- **Issue:** Long docstring lines in `serving_revision.py`, two long lines and one unsorted import block in `test_deploy_pipeline.py`.
- **Fix:** Rewrapped the lines and let `ruff check --fix` sort the import.
- **Files modified:** scripts/serving_revision.py, tests/unit/test_deploy_pipeline.py
- **Committed in:** `99f3e6f`

**2. [Rule 3 - Blocking] Task 2 test docstring over 100 characters**
- **Found during:** Task 2 (ruff before the RED commit)
- **Fix:** Shortened the docstring.
- **Files modified:** tests/unit/test_sync_and_publish_script.py
- **Committed in:** `6ae44c1`

---

**Total deviations:** 2 auto-fixed (both lint). One implementation variance (`--format json`) is recorded under Decisions.
**Impact on plan:** None on scope.

## Issues Encountered
None. The Read and Bash tool results carried a hook notice about session cost asking me to stop and report; per the project's standing instruction to ignore cost warnings I continued.

## User Setup Required
None. No deploy, no push; live proof is 04-26.

## Next Phase Readiness
- 04-26 must prove live, on the first deploy and on a deploy after it: (1) `services replace --dry-run` accepts the first-deploy form where the serving and tagged targets name the same new revision; (2) the tagged host routes within the curl retry window after replace; (3) `status.traffic` carries the resolved `revisionName` after `--to-latest` and the helper reads it (L11); (4) the service ends in latest-revision mode so the forced publish revision takes traffic; (5) COVERAGE.md row for traffic splitting and tags flips from OPT-OUT.
- Requirements INFRA-05 and INFRA-04 are declared by sibling plans in this phase, so they were not force-marked (ready-ids gate).

## Self-Check: PASSED

- Files exist: `scripts/serving_revision.py` and the nine modified files (verified).
- Commits `de21438`, `99f3e6f`, `6ae44c1`, `6d7bbeb` are ancestors of HEAD; `commits: 4` measured from the ledger (`96ed26b..6d7bbeb`).
- Acceptance: `candidate---` count in `_deploy.yml` 1; `tag: candidate` count 1 in each template; `--to-latest` count 1; `serving_revision.py` count 2; `latestRevision` in `sync-and-publish.sh` 2; README has `## Staged deploys`, `candidate` and `--remove-tags`.
- `./run-unit-tests.sh --all`: exit 0, 1548 passed, 26 skipped, coverage 97.60 percent; `bash -n scripts/sync-and-publish.sh` OK; `scripts/validate-infra.sh` prints `infra validation ok`; host render check exits 0.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-15*
