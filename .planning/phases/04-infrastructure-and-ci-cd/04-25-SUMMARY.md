---
phase: 04-infrastructure-and-ci-cd
plan: 25
subsystem: infra
tags: [github-actions, secrets, log-masking, fail-fast, meridian, gap-closure, wr-01, wr-02, wr-09]
status: complete

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: scan step, gha cache, sbom and provenance in _deploy.yml and meridian.yml (04-23); sa-publisher token flow and bootstrap section 10 (04-24)
provides:
  - "_deploy.yml declares GCP_PROJECT_ID, GCP_PROJECT_NUMBER, GCP_DEPLOYER_SA, GCP_WIF_PROVIDER, GCP_OAUTH_CLIENT_ID as required workflow_call secrets; every identifier expression reads secrets, none reads vars"
  - "mcp-server.yml and chat-bot.yml pass the five by name (no secrets: inherit)"
  - "First step 'Check the deploy configuration' in the deploy job and in the Meridian push job: exit 1 with '::error::<NAME> is not set', names only; job-level if on the project variable is gone (WR-09)"
  - "Masking step that printed the ids in its own env header is gone in _deploy.yml and meridian.yml (WR-01)"
  - "Meridian image check polls every 30 s for up to 30 min before the existing 'run the meridian workflow' error; deploy job timeout 75 min (WR-02)"
  - "bootstrap.sh section 10 and the runbook section 'GitHub repository secrets and variables': five secrets, four variables, move with gh variable get | gh secret set, then gh variable delete"
affects: [04-26]

actuals:
  tokens: 9000
  tasks: 3
  commits: 7

plan_head_before: 1d8071cac4fc26d74345004fae17e1907fdfb4b2
plan_head_after: 6a98be8653af678a6ccdbea58be1057444668769

tech-stack:
  added: []
  patterns:
    - "Configuration check steps are executed by the tests with bash and a minimal env, so the names-only error and the exit code are proven, not only the YAML shape"
    - "The Meridian wait is tested against a fake gcloud on PATH with a zero poll interval: retry-then-succeed and give-up-with-the-existing-error"

key-files:
  created: []
  modified:
    - .github/workflows/_deploy.yml
    - .github/workflows/mcp-server.yml
    - .github/workflows/chat-bot.yml
    - .github/workflows/meridian.yml
    - deploy/cloudrun/bootstrap.sh
    - deploy/cloudrun/README.md
    - tests/unit/test_workflows.py
    - tests/unit/test_cloudrun_yaml.py
    - tests/unit/test_deploy_pipeline.py

key-decisions:
  - "The five identifiers are repository secrets only; no vars expression names them anywhere, enforced by test_no_workflow_reads_a_gcp_identifier_from_vars and an allow-list over every file under .github"
  - "The Meridian push job checks four identifiers (project id, number, deployer account, WIF provider), the set its old mask step covered, as the plan states; the OAuth client id is not passed to it"
  - "The Meridian wait uses the bash SECONDS counter and logs one progress line per five minutes with the tag only"

requirements-completed: []  # INFRA-05 is declared by several plans of this phase; the ready-ids gate decides

coverage:
  - id: D1
    description: "Project identifiers reach the workflows only as repository secrets: required workflow_call secrets, explicit caller mapping, no vars expression, allow-list of secret names, no key file"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_secrets_context_holds_only_the_five_gcp_identifiers"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_no_workflow_reads_a_gcp_identifier_from_vars"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_service_callers_pass_the_five_identifiers_by_name"
        status: pass
    human_judgment: false
  - id: D2
    description: "A missing identifier turns the deploy and Meridian runs red with a names-only error instead of skipping"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_deploy_fails_fast_when_the_project_is_not_configured"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_meridian_push_job_fails_fast_when_the_project_is_not_configured"
        status: pass
    human_judgment: false
  - id: D3
    description: "The chat-bot deploy waits up to 30 minutes, every 30 seconds, for the Meridian image before the existing error"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_chat_bot_deploy_waits_a_bounded_time_for_the_meridian_image"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_meridian_check_retries_until_the_image_appears"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_meridian_check_fails_with_the_existing_error_after_the_wait"
        status: pass
    human_judgment: false
  - id: D4
    description: "Bootstrap print-out and runbook split the five identifiers (secrets) from the four other values (variables) and give the move without printing"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_runbook_stores_the_gcp_identifiers_as_secrets"
        status: pass
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_bootstrap_prints_the_identifiers_as_secrets_and_the_rest_as_variables"
        status: pass
    human_judgment: false
  - id: D5
    description: "A live deploy run after the GitHub settings switch shows no project id or project number in its public log"
    requirement: "INFRA-05"
    verification: []
    human_judgment: true
    rationale: "Rests on GitHub's documented masking behaviour and needs a real run after the settings switch (04-26); no unit test can observe a live log"

duration: 40min
completed: 2026-11-15
---

# Phase 4 Plan 25: Identifiers as secrets, fail-fast configuration, bounded Meridian wait Summary

**The five project identifiers move from public `vars` to explicitly passed repository secrets, a missing one fails the run by name instead of skipping the deploy, and the chat-bot deploy now polls 30 minutes for a freshly bumped Meridian image.**

## Performance

- **Duration:** about 40 min
- **Completed:** 2026-11-15T15:45Z
- **Tasks:** 3 (tracer plus two auto), all TDD
- **Files modified:** 9

## Accomplishments

- WR-01: `_deploy.yml` and `meridian.yml` read the identifiers as `secrets.` only. The step that printed them in its own env header is deleted. A test over every file under `.github` allows only the five names and forbids `secrets: inherit`, `secrets[`, `credentials_json` and `GOOGLE_APPLICATION_CREDENTIALS`.
- WR-09: the job `if:` on the project variable is gone from both workflows. Step 2 of each job, "Check the deploy configuration", exits 1 with `::error::<NAME> is not set` for every empty identifier and never prints a value. The tests run the step with bash and check the exit code, the message and that no value leaks.
- WR-02: the Meridian check in `_deploy.yml` loops with `MERIDIAN_WAIT_SECONDS=1800` and `MERIDIAN_POLL_SECONDS=30`, logs the tag once per five minutes, and ends with the existing error. The deploy job timeout is 75 minutes. Tested with a fake `gcloud`.
- `bootstrap.sh` and the runbook tell the operator to store the five as secrets (`gh secret set` reads stdin), the four others as variables, and how to move an existing setup without printing a value.

## Task Commits

1. **Task 1 (tracer): secrets-only identifiers, explicit caller mapping, fail-fast check**
   - RED `771f7d4` (7 failing tests: auth expressions, fail-fast, required secrets, caller mapping, allow-list, no vars)
   - GREEN `7de38aa`
2. **Task 2: Meridian workflow fail-fast and bounded wait**
   - RED `a325f85` (5 failing tests)
   - GREEN `2040d84`
3. **Task 3: bootstrap print-out and runbook**
   - RED `d0c572d` (2 failing tests)
   - Fix `9ba3f2c`, GREEN `6a98be8`

**Plan metadata:** the docs commit that carries this file.

Tracer gate: `<verify>` re-run after the tracer commit, 89 workflow tests and `scripts/validate-infra.sh` green, so expansion went ahead.

## RED evidence

Each RED run was `./run-unit-tests.sh --single-file <file> tests/unit` in Docker. Every target failed on an assertion for the planned behaviour (missing `secrets` key, no `if`-free job, no `MERIDIAN_WAIT_SECONDS`, missing README heading), never on a syntax, import or collection error. The pre-existing tests of the same files stayed green (82, 88 and 42 passed). `gsd_run check tdd-red-evidence` was not run: the Python `pytest` report format is not one of its adapters, so the semantic assessment above is the evidence.

## Decisions Made

- The Meridian push job checks four identifiers, as the plan words it. It needs three (project id, deployer account, WIF provider); the project number is checked because the old mask step covered it. The OAuth client id is not passed to that job.
- The Meridian wait uses bash `SECONDS`, so the loop needs no `date` arithmetic and the tests can shrink it with a zero poll interval.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale expression pinned in a test outside the plan's file list**
- **Found during:** Task 3 (`./run-unit-tests.sh --all`)
- **Issue:** `tests/unit/test_deploy_pipeline.py::test_the_pushed_digest_is_scanned_before_render` compared the scan `image-ref` to a string holding `vars.GCP_PROJECT_ID`; Task 1 changed the workflow to `secrets.GCP_PROJECT_ID`.
- **Fix:** one-token change in the expected string.
- **Files modified:** tests/unit/test_deploy_pipeline.py
- **Verification:** `./run-unit-tests.sh --all` exits 0, 1580 passed, 26 skipped, coverage 97.61%
- **Committed in:** 9ba3f2c

**2. [Rule 3 - Blocking] ruff line-length and format failures in the new test code**
- **Found during:** Task 3 (`--all` runs `ruff check` and `ruff format --check`)
- **Fix:** `ruff format` on the two test files inside the test image; included in the Task 3 GREEN commit (the RED commits carried the unformatted text, as those runs do not lint).
- **Files modified:** tests/unit/test_workflows.py, tests/unit/test_cloudrun_yaml.py
- **Committed in:** 6a98be8

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** none on scope.

## Issues Encountered

- A PostToolUse hook printed session cost notices and asked to stop. The project memory says to ignore cost warnings, so the run continued.
- `scripts/render-cloudrun.sh` line 6 still says "GitHub repository variables" in a comment. It is outside this plan's file list and the comment is not load-bearing; left as is.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path or trust boundary: the change narrows what reaches public logs.

## Threat model

- T-04-78 (identifiers in public logs): mitigated, secrets plus allow-list and no-vars tests.
- T-04-79 (silent skip): mitigated, no `if`, fail-fast step executed by tests.
- T-04-80 (Meridian race): mitigated, bounded wait tested with a fake `gcloud`.
- T-04-SC: no installs.

## User Setup Required

None for this plan. **04-26 must switch the settings before the next deploy run goes green:** until the five repository secrets exist, every deploy and Meridian run fails at "Check the deploy configuration" by design. The move is in the runbook section "GitHub repository secrets and variables". Not done here (project rule: no changes to GitHub variables or secrets).

## Next Phase Readiness

Ready for 04-26: set the five secrets from the current variables, push, check that the run log holds no project id or number (flagged assumption, [Medium]), then delete the five variables.

## Self-Check: PASSED

- All nine modified files exist and are in `git diff 1d8071c..HEAD`.
- Commits 771f7d4, 7de38aa, a325f85, 2040d84, d0c572d, 9ba3f2c, 6a98be8 are ancestors of HEAD; `git rev-list --count` from the ledger base gives 7.
- Acceptance criteria re-run: identifier `vars.` count 0 in `_deploy.yml`, `mcp-server.yml`, `chat-bot.yml`; `add-mask` in `_deploy.yml` 3 to 2; `secrets: inherit` 0 in every workflow; `GCP_PROJECT_ID != ''` 0 in `_deploy.yml` and `meridian.yml`; `vars.GCP_` 0 in `meridian.yml`; `MERIDIAN_WAIT_SECONDS` present; README holds `gh secret set` and `gh variable delete`.
- Plan verification: `./run-unit-tests.sh --all` exit 0 (1580 passed, 26 skipped, coverage 97.61%); `scripts/validate-infra.sh` prints "infra validation ok"; `bash -n deploy/cloudrun/bootstrap.sh` clean.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-15*
