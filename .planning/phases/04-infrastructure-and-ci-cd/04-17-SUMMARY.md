---
phase: 04-infrastructure-and-ci-cd
plan: 17
subsystem: infra
tags: [cloud-run, iam, bootstrap, fernet, pydantic-settings, runbook]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: bootstrap.sh, runbook README, McpSettings, oauth_storage (plans 04-06 to 04-13)
provides:
  - "bootstrap.sh binds ci-deployer to roles/run.admin, the role the live project has held since 04-13"
  - "Exact bind-call pin test over every IAM binding in bootstrap.sh (commented-out lines ignored)"
  - "Runbook: Fernet key row and stdin-piped generation command for oauth-storage-encryption-key"
  - "McpSettings refuses a non-Fernet OAUTH_STORAGE_ENCRYPTION_KEY at config time, naming the variable only"
affects: [04-24, 04-26]

actuals:
  tokens: 2650
  tasks: 2
  commits: 4

plan_head_before: f17153a2869989b0dc0a8147f332cc8dd2347391
plan_head_after: e7300477cfa890ca14fc35ea05d23d63e69c9967

tech-stack:
  added: []
  patterns:
    - "Parser-based IAM pin: join shell continuation lines, drop comments, compare the sorted bind-call set exactly"
    - "Secret validators raise a names-only message from None so the value never reaches the error chain"

key-files:
  created: []
  modified:
    - deploy/cloudrun/bootstrap.sh
    - deploy/cloudrun/README.md
    - services/mcp_server/buddy_mcp/config.py
    - tests/unit/test_cloudrun_yaml.py
    - tests/unit/mcp_server/test_config.py
    - tests/unit/mcp_server/test_main.py

key-decisions:
  - "ci-deployer keeps roles/run.admin in the repo (the owner's 04-13 choice); a narrower custom role stays a one-line change recorded in the README (T-04-54 accepted)"
  - "Owner bindings untouched here; 04-24 reworks them, the exact-set test will then change in a reviewed commit"
  - "The CLI error line names OAUTH_STORAGE_ENCRYPTION_KEY only (existing cli behaviour); the full 'must be a Fernet key' text is asserted at McpSettings level"

patterns-established:
  - "Every IAM binding of bootstrap.sh is pinned by an exact test, so repo and live differ only through a reviewed commit"

requirements-completed: [INFRA-04, INFRA-05]

coverage:
  - id: D1
    description: "bootstrap.sh binds ci-deployer to roles/run.admin with the invoker-iam-disabled reason in a comment"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_bootstrap_binds_exactly_these_roles"
        status: pass
      - kind: other
        ref: "bash -n deploy/cloudrun/bootstrap.sh && grep -v '^\\s*#' deploy/cloudrun/bootstrap.sh | grep -c roles/run.admin (prints 1)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Exact bind-call pin that rejects a commented-out or moved binding"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_bind_call_parser_ignores_a_commented_binding"
        status: pass
    human_judgment: false
  - id: D3
    description: "Runbook Roles paragraph names roles/run.admin and run.services.setIamPolicy; fallback bullet removed; Meridian bucket wording says not separate access"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_runbook_names_the_deployer_role_and_the_meridian_bucket_scope"
        status: pass
    human_judgment: false
  - id: D4
    description: "Runbook says the storage key is a Fernet key and gives a docker-generated command piped into gcloud secrets versions add without showing the key"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_runbook_documents_the_fernet_key_format"
        status: pass
    human_judgment: false
  - id: D5
    description: "McpSettings refuses a set non-Fernet OAUTH_STORAGE_ENCRYPTION_KEY with a names-only error; whitespace and trailing newline accepted; unset key unchanged"
    requirement: "INFRA-05"
    verification:
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_a_value_that_is_not_a_fernet_key_names_the_variable_only"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_config.py#test_a_fernet_key_with_surrounding_whitespace_is_accepted"
        status: pass
      - kind: unit
        ref: "tests/unit/mcp_server/test_main.py#test_a_non_fernet_encryption_key_exits_one_without_echoing_it"
        status: pass
    human_judgment: false
  - id: D6
    description: "Live ci-deployer holds roles/run.admin and not roles/run.developer"
    requirement: "INFRA-04"
    verification: []
    human_judgment: true
    rationale: "A fresh bootstrap cannot be re-run against a new project in this gap set; the live proof is 04-26"

duration: 4min
completed: 2026-11-15
status: complete
---

# Phase 4 Plan 17: Deployer role and Fernet key format Summary

**bootstrap.sh now grants ci-deployer roles/run.admin (the role the committed YAML's invoker-iam-disabled needs), every IAM binding is pinned by an exact parser-based test, and the OAuth storage key is a Fernet key in both the runbook and McpSettings.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-11-15T14:14:14Z
- **Completed:** 2026-11-15T14:18:04Z
- **Tasks:** 2 (4 commits: RED and GREEN per task)
- **Files modified:** 6

## Accomplishments
- Gap 2 (INFRA-04): `bind_project "serviceAccount:${SA_CI_EMAIL}" roles/run.admin` with the reason in a comment (`run.services.setIamPolicy`, live since 04-13). README Roles paragraph names the role and reason; the pending "run.developer cannot set invoker-iam-disabled" fallback bullet is replaced by a sentence saying the role is applied.
- IN-03: `test_bootstrap_binds_exactly_these_roles` compares the sorted set of 15 uncommented bind calls (including the multi-line WIF `bind_sa` and the Artifact Registry call) to an explicit expected set; a helper test proves a commented binding drops out. README Meridian bucket sentence now says "a separate mount, not separate access".
- Gap 4 / IN-07 (INFRA-05): runbook row says Fernet key (32 random bytes, URL-safe base64, 44 characters) and adds a `docker run --rm python:3.12-slim python -c ... | gcloud secrets versions add oauth-storage-encryption-key --data-file=-` command with no trailing newline and no echo. `McpSettings` validates with `Fernet(value.strip().encode())` and raises `OAUTH_STORAGE_ENCRYPTION_KEY must be a Fernet key` from None.

## Task Commits

1. **Task 1: tracer, bootstrap role and exact bind-call pin** - `b6b3b70` (test, RED), `f804b2c` (feat, GREEN)
2. **Task 2: Fernet key format in runbook and config** - `0dc2084` (test, RED), `e730047` (feat, GREEN)

**Plan metadata:** the docs(04-17) commit that carries this file.

## Files Created/Modified
- `deploy/cloudrun/bootstrap.sh` - ci-deployer project role `roles/run.admin`, comment rewritten
- `deploy/cloudrun/README.md` - Roles paragraph, Fernet row and command, Meridian bucket sentence, fallback list
- `services/mcp_server/buddy_mcp/config.py` - field validator for `oauth_storage_encryption_key`
- `tests/unit/test_cloudrun_yaml.py` - `_bind_calls` helper, exact-set, helper and runbook tests
- `tests/unit/mcp_server/test_config.py` - Fernet validator tests; sample keys now generated Fernet keys
- `tests/unit/mcp_server/test_main.py` - non-Fernet key exits 1 without echoing the value

## Decisions Made
- Kept `roles/run.admin` (the owner's 04-13 choice, T-04-54 accepted); owner bindings left for 04-24.
- The CLI prints only the variable name on a config error (existing behaviour), so the main-level test asserts the name and the absence of the value; the full message is asserted in test_config.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff E501 / format on the new tests**
- **Found during:** Task 2 (`./run-unit-tests.sh --all` lint step)
- **Issue:** Long lines in the new test code failed `ruff check` and `ruff format --check`
- **Fix:** Rebuilt the expected set from member/role constants, shortened a docstring and a comment, ran `ruff format`
- **Files modified:** tests/unit/test_cloudrun_yaml.py, tests/unit/mcp_server/test_config.py
- **Verification:** `./run-unit-tests.sh --all` exits 0
- **Committed in:** `e730047`

**2. [Rule 1 - Test expectation] test_main asserts the variable name, not the full message**
- **Found during:** Task 2 (GREEN run)
- **Issue:** The test expected the full validator text in the CLI error line; the CLI logs field names only by design
- **Fix:** Assert `OAUTH_STORAGE_ENCRYPTION_KEY` in the error line and that the bad value is absent from stderr
- **Files modified:** tests/unit/mcp_server/test_main.py
- **Committed in:** `e730047`

---

**Total deviations:** 2 auto-fixed (1 blocking lint, 1 test expectation)
**Impact on plan:** None on scope; both are test-side.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. The live ci-deployer role is unchanged (already `roles/run.admin`); 04-26 verifies it.

## Next Phase Readiness
- 04-24 reworks owner bindings: update `_EXPECTED_BIND_CALLS` in the same commit.
- 04-26 live proof: the live ci-deployer holds `roles/run.admin`, not `roles/run.developer`; the live `oauth-storage-encryption-key` secret version must be a valid Fernet key.

## Self-Check: PASSED

- Files exist: bootstrap.sh, README.md, config.py, the three test files (verified).
- Commits `b6b3b70`, `f804b2c`, `0dc2084`, `e730047` are ancestors of HEAD.
- `./run-unit-tests.sh --all`: 1491 passed, 26 skipped (emulator and local-only), coverage 97.61 percent; `bash -n deploy/cloudrun/bootstrap.sh` OK; non-comment `roles/run.admin` count 1.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-15*
