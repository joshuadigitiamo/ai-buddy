---
phase: 04-infrastructure-and-ci-cd
plan: 09
subsystem: infra
tags: [github-actions, workload-identity-federation, artifact-registry, cloud-run, path-filters, actionlint, dependabot, meridian]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-01 deploy/meridian.version (the approved Meridian commit, D-14)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-05 Dockerfile runtime stages server, bot and sync and tests/unit/test_dockerfile_stages.py (COPY parser reused by the drift test)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-07 scripts/validate-infra.sh with its marked section for CI additions"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-08 scripts/render-cloudrun.sh, Cloud Run templates, ci-deployer account and the WIF pool (repository variables list)"
provides:
  - "Reusable _test.yml (jobs unit and validate) and _deploy.yml (WIF auth, build and push, render, dry run, replace, live check)"
  - "Path-filtered mcp-server.yml and chat-bot.yml (test then deploy, concurrency never cancels), sync.yml (test and build, no push, no deploy), meridian.yml (build of the approved commit), tests.yml (test-only paths)"
  - ".github/dependabot.yml: weekly bumps of the SHA-pinned actions"
  - "tests/unit/test_workflows.py: 83-test structural guard (pinning, permissions, ordering, keyless auth, no expressions in run, path drift from the Dockerfile COPY sources, index modes)"
  - "scripts/validate-infra.sh now also runs actionlint and builds the sync image; run-unit-tests.sh is mode 100755 in the git index"
affects: [04-13, 04-14]

actuals:
  tokens: 10200
  tasks: 3
  commits: 5
plan_head_before: 9ac307e74563e54c8dc03e73f123434a02de0c62
plan_head_after: 50e5c778b17981ee76ce0e90528342c20217bbb2

tech-stack:
  added: ["actions/checkout v7.0.1", "google-github-actions/auth v3.0.0", "google-github-actions/setup-gcloud v3.0.1", "docker/setup-buildx-action v4.4.1", "docker/build-push-action v7.4.0", "docker/login-action v4.8.0", "rhysd/actionlint 1.7.12 (Docker image)"]
  patterns:
    - "Every third-party action pinned by full commit SHA with the version in a comment; tag-to-SHA mapping re-verified with gh api before use"
    - "Top-level permissions {} in every workflow; per-job grants; id-token write only on deploy and push jobs"
    - "GitHub expressions reach shell only through env; a test fails on any dollar-brace expression inside a run value"
    - "Public-log hygiene: add-mask of the project identifiers first, stdout of gcloud to /dev/null, stderr kept in a file and printed only on failure"
    - "Path filters equal to the Dockerfile COPY sources of each runtime stage, enforced by a drift test"

key-files:
  created:
    - .github/workflows/_test.yml
    - .github/workflows/_deploy.yml
    - .github/workflows/mcp-server.yml
    - .github/workflows/chat-bot.yml
    - .github/workflows/sync.yml
    - .github/workflows/meridian.yml
    - .github/workflows/tests.yml
    - .github/dependabot.yml
    - tests/unit/test_workflows.py
  modified:
    - scripts/validate-infra.sh
    - run-unit-tests.sh
  deleted:
    - .github/workflows/.gitkeep

key-decisions:
  - "Deploy uses the full github.sha as the image tag and the render IMAGE_TAG (the plan's tag form); the README example with a short sha is only the manual path"
  - "Project identifiers are masked with add-mask as the first step of the deploy and Meridian jobs, so the public log hides them even when a tool prints a tag or a URL"
  - "gcloud stdout goes to /dev/null and stderr to a file printed only on failure: the dry run and the replace can print the service definition and the service URL"
  - "The live check reads the service URL with gcloud run services describe and masks it, instead of building the URL by hand"
  - "sync.yml has no concurrency group: it deploys nothing, so parallel builds are harmless"
  - "No required-check gate job for path-filtered workflows (CICD guide section 9 trap): nobody opens pull requests against a protected main yet"

patterns-established:
  - "Drift test pattern: derive the expected path filter from the Dockerfile COPY sources by importing the existing parser, never a second parser"
  - "Index-mode guard: git ls-files -s in the test container, because core.fileMode is false in this checkout"

requirements-completed: [INFRA-05, INFRA-06]

coverage:
  - id: D1
    description: "mcp-server pipeline: a push that changes services/mcp_server runs the full test gate and only then builds, pushes, dry-runs, replaces and checks the service, keyless through WIF"
    requirement: INFRA-05
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_deploy_job_needs_the_test_job"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_deploy_steps_run_in_the_required_order"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_deploy_authenticates_keyless_and_pushes_with_the_access_token"
        status: pass
      - kind: other
        ref: "docker run rhysd/actionlint:1.7.12 over .github/workflows exits 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "Path filters cannot drift from what the images copy; the two shared model files trigger both services, every other file only its own"
    requirement: INFRA-05
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_workflow_paths_do_not_drift_from_dockerfile_copy_sources"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_a_changed_file_triggers_only_the_workflows_that_copy_it"
        status: pass
    human_judgment: false
  - id: D3
    description: "The test gate blocks every image push: ./run-unit-tests.sh --all in _test.yml, deploy needs test, executable bit in the git index"
    requirement: INFRA-06
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_test_workflow_runs_the_full_script_exactly"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_run_unit_tests_is_executable_in_the_git_index"
        status: pass
    human_judgment: false
  - id: D4
    description: "sync.yml tests and builds without push or deploy; meridian.yml builds only the commit in deploy/meridian.version after the test gate; chat-bot deploy fails early when the Meridian tag is missing"
    requirement: INFRA-05
    verification:
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_sync_workflow_tests_and_builds_the_image_without_push_or_deploy"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_meridian_workflow_builds_only_the_reviewed_commit_after_the_test_gate"
        status: pass
      - kind: unit
        ref: "tests/unit/test_workflows.py#test_chat_bot_deploy_fails_early_when_the_meridian_image_is_missing"
        status: pass
    human_judgment: false
  - id: D5
    description: "Static infra checks in CI and locally: validate job runs scripts/validate-infra.sh (kubeconform, actionlint, sync image build)"
    verification:
      - kind: integration
        ref: "scripts/validate-infra.sh exits 0 (8 and 11 resources valid, actionlint clean, sync image built)"
        status: pass
    human_judgment: false
  - id: D6
    description: "A real push to main, the WIF exchange, the registry push, the Cloud Run replace and the post-deploy 401/200 checks work against the live project"
    requirement: INFRA-05
    verification: []
    human_judgment: true
    rationale: "No workflow may be triggered and nothing is pushed in this plan; the live WIF push and deploy are the 04-13 live checkpoint"

duration: 6min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 09: GitHub Actions workflows Summary

**Path-filtered keyless GitHub Actions: per-service test-then-deploy pipelines over reusable test and deploy workflows (WIF, SHA-pinned actions, dry run before replace), a Dockerfile-to-paths drift test, Dependabot, and actionlint plus the sync image build in CI**

## Performance

- **Duration:** 6 min (sandbox clock)
- **Started:** 2026-11-14T13:22:09Z
- **Completed:** 2026-11-14T13:28:05Z
- **Tasks:** 3
- **Files modified:** 12 (9 created, 2 modified, 1 deleted)

## Accomplishments

- A change under `services/mcp_server` (other than `buddy_mcp/__init__.py` and `models.py`) matches only `mcp-server.yml`. That workflow calls `_test.yml` (`./run-unit-tests.sh --all`), and only after it succeeds (`needs: test`) builds the `mcp_server` stage, pushes `europe-west8-docker.pkg.dev/<project>/ai-buddy/mcp-server:<sha>`, renders the template, dry-runs, replaces, and checks `/healthz` 200 and an unauthenticated `POST /mcp` 401 (ROADMAP criterion 4, D-04).
- Auth is keyless: `google-github-actions/auth` with the WIF provider and `ci-deployer` from repository variables, `token_format: access_token` for the registry login. No `secrets` context, no key file; a test scans all of `.github`.
- `chat-bot.yml` mirrors it, adds the two model files and `deploy/meridian.version` to its paths, and `_deploy.yml` fails early with "Meridian image <tag> missing: run the meridian workflow" before any build. `sync.yml` tests and builds with `push: false` and no deploy (D-09). `meridian.yml` builds `https://github.com/rynfar/meridian.git#<sha>` (sha validated as 40 hex) behind the test gate (D-14). `tests.yml` covers test-only paths.
- `test_workflows.py` (83 tests) guards SHA pinning, empty top-level permissions, ordering test -> build -> dry run -> replace -> check, no expression in any `run`, no tracing, no `pull_request_target`, `cancel-in-progress: false`, and path coverage derived from the Dockerfile COPY sources by importing the 04-05 parser.
- `_test.yml` has a `validate` job running `scripts/validate-infra.sh`, which now also runs actionlint 1.7.12 and `docker build --target sync`; `run-unit-tests.sh` is `100755` in the index (scripts/*.sh already were).

## Task Commits

1. **Task 1: Tracer, mcp-server path** - `23a2287` (feat)
2. **Task 2: chat-bot, sync, meridian, tests, Dependabot, drift test**
   - RED `636a27e` (test)
   - GREEN `f8ff7a6` (feat)
3. **Task 3: executable bits, validate job, validate-infra additions**
   - RED `4d04df0` (test)
   - GREEN `50e5c77` (feat)

**Plan metadata:** recorded in the docs commit that follows this file.

The tracer feedback gate ran in end-of-phase mode with an automated-only `<verify>`: the unit tests and actionlint were re-run after the commit (28 passed, actionlint clean) before the expansion tasks.

## Verification Results

| Check | Result |
|-------|--------|
| `./run-unit-tests.sh --all` | exit 0: ruff clean, 155 files formatted, mypy 143 files clean, 1432 passed, 26 skipped, coverage 97.56% |
| `./run-unit-tests.sh --single-file test_workflows.py tests/unit` | 83 passed |
| actionlint 1.7.12 (Docker) over `.github/workflows` | exit 0, no findings |
| `scripts/validate-infra.sh` | exit 0: base 8/8 valid, overlay dev 11/11 valid, actionlint clean, sync image built |
| Pinned SHAs vs `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` | all six match the RESEARCH values (commit objects) |
| Acceptance greps | needs: test = 1, workload_identity_provider = 1, --dry-run = 1, secrets. = 0, .gitkeep gone, models.py in chat-bot.yml = 1, push: false = 1, rynfar/meridian.git# = 1, github-actions in dependabot = 1, index mode of run-unit-tests.sh = 100755, drift/paths tests = 4 |

## What could not be run (recorded, not faked)

- No workflow was triggered and nothing was pushed (orchestrator instruction). Everything that needs GitHub, the WIF pool, Artifact Registry or Cloud Run is unproven until 04-13: the OIDC exchange, the registry push, `gcloud run services replace --dry-run` and replace, and the post-deploy status checks. actionlint and shellcheck (inside actionlint) only prove syntax, types and expressions.
- The `validate` and `unit` jobs have not run on a GitHub-hosted runner. Assumption carried from the plan: ubuntu-latest ships kubectl and Docker, so no install step exists; if kubectl is absent the job fails visibly and a pinned install must be added.
- The repository variable `GCP_PROJECT_ID` is not set yet, so on the first pushes the `deploy` and `push` jobs are skipped by their `if`, while `test` still runs.

## Decisions Made

See `key-decisions` above. Flagged assumption carried forward (RESEARCH A9, A13): `run.developer` may not be enough to apply the `invoker-iam-disabled` annotation through `services replace`; the first live run (04-13) decides, and the bootstrap should grant only what the error names.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Identifier masking and error-only output in the deploy path**
- **Found during:** Task 1 (the plan prohibition: no secret values, rendered YAML or personal identifiers in the public logs)
- **Issue:** `gcloud run services replace` can print the service definition (dry run) and the service URL (replace), `docker/build-push-action` prints the tag with the project id, and a failing curl names its URL. With the plan's "output to /dev/null except errors" alone these still reach the public log on some paths, and repository variables are not masked by GitHub.
- **Fix:** First step of the deploy and Meridian jobs runs `::add-mask::` over project id, project number, deployer account, WIF provider and OAuth client id (values only through env); stdout of the dry run and replace goes to `/dev/null`, stderr to a file in `RUNNER_TEMP` that is printed only on failure; the live check masks the service URL and keeps only the status code. A test (`test_deploy_workflow_never_prints_a_rendered_file`) checks that no run step prints `service.yaml`.
- **Files modified:** `.github/workflows/_deploy.yml`, `.github/workflows/meridian.yml`, `tests/unit/test_workflows.py`
- **Verification:** actionlint clean; structural tests pass
- **Committed in:** `23a2287`, `f8ff7a6`

**2. [Rule 3 - Blocking] The matcher in the drift test needed a single-star form**
- **Found during:** Task 2 (the plan lists `docker-compose*.yml` among the test-only paths, while the stated matcher knows only a `/**` suffix and exact paths)
- **Fix:** `_matches` also accepts a `*` inside the last path segment (never crossing a slash), with its own unit test; `tests.yml` keeps the plan's glob.
- **Files modified:** `tests/unit/test_workflows.py`
- **Committed in:** `636a27e`

**3. [Rule 1 - Bug] Static test files exceeded the line-length and type gates on first write**
- **Found during:** Task 1 (ruff E501 and a mypy `dict.get(True)` key error)
- **Fix:** Added a `_uses_step` helper, typed workflow mappings as `dict[Any, Any]` (PyYAML reads `on` as boolean True), reformatted with `ruff format`.
- **Files modified:** `tests/unit/test_workflows.py`
- **Committed in:** `23a2287`

---

**Total deviations:** 3 auto-fixed (1 missing critical, 1 blocking, 1 bug)
**Impact on plan:** All three are needed for correctness or the repository gates; no scope creep. The marker comment in `validate-infra.sh` was replaced by a section header once its additions landed, as the 04-07 hand-off intended.

## Issues Encountered

- Hook output in this session repeatedly asked to stop and warn about session cost; the user's saved preference is to ignore cost notices, so execution continued.
- `INDEX_BUILD_ID` (set by `sync-and-publish.sh` through `services update`, 04-10) is dropped by the next `services replace` from CI. Harmless, because nothing reads it; noted so the live run in 04-13 does not read it as a bug.
- Concurrency note: a workflow-level group with `cancel-in-progress: false` keeps one pending run per group, so a third quick push replaces the pending second one (the running deploy is never cancelled). Acceptable for one developer.

## Known Stubs

None.

## Threat Flags

None. The mitigations T-04-34 to T-04-38 and T-04-SC are implemented and tested (SHA pins, empty top-level permissions, no expressions in `run`, no tracing or rendered-file printing, deploy needs test with dry run before replace and a post-deploy auth check, no package installs).

## User Setup Required

None for this plan. Before 04-13 the repository variables from `deploy/cloudrun/README.md` must exist (GCP_PROJECT_ID, GCP_PROJECT_NUMBER, GCP_WIF_PROVIDER, GCP_DEPLOYER_SA, GCP_OAUTH_CLIENT_ID, GUIDES_WEB_BASE, CHAT_JWT_ISSUER_EMAIL, VIDEO_THUMBNAIL_URL, HELP_COMMAND_ID). `render-cloudrun.sh` requires all nine to be non-empty for both services, so a missing chat-only variable also fails the mcp-server deploy.

## Next Phase Readiness

- 04-13 (live checkpoint) can push to main, set the variables, run the meridian workflow first (the chat-bot deploy refuses to run without its tag), and read the first live results for the open assumptions above.
- 04-14 can cite `tests/unit/test_workflows.py` and `scripts/validate-infra.sh` as the static CI evidence.

## Self-Check: PASSED

- All created files exist: `.github/workflows/{_test,_deploy,mcp-server,chat-bot,sync,meridian,tests}.yml`, `.github/dependabot.yml`, `tests/unit/test_workflows.py`; `.gitkeep` removed.
- Commits `23a2287`, `636a27e`, `f8ff7a6`, `4d04df0`, `50e5c77` are ancestors of HEAD.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
