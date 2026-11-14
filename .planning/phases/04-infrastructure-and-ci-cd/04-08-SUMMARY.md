---
phase: 04-infrastructure-and-ci-cd
plan: 08
subsystem: infra
tags: [cloud-run, knative, gcs-fuse, meridian-sidecar, workload-identity-federation, firestore-ttl, envsubst, bootstrap]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-01 billing_mode (a), token_chain (b), org_policy yes, deploy/meridian.version"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-02 DEPLOY_ENV fail-closed marker, MCP_ALLOWED_HOSTS, /healthz"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-03 bot DEPLOY_ENV and CHAT_API guards (YAML half of T-04-10)"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-04 ARTIFACT_STORE=gcs, ARTIFACT_BUCKET, ARTIFACT_PREFIX"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-07 Meridian probe findings (loopback bind, /health versus /readyz)"
provides:
  - "deploy/cloudrun/mcp-server.yaml and chat-bot.yaml: serving.knative.dev/v1 templates for europe-west8, scale 0..1, request-based billing"
  - "scripts/render-cloudrun.sh: envsubst with a fixed variable list; refuses empty or unsafe values and leftover placeholders"
  - "deploy/cloudrun/bootstrap.sh: one-time project setup (never creates a project), typed confirmation for the one-way Firestore step"
  - "deploy/cloudrun/README.md: runbook with seeding, deploy, Chat and claude.ai wiring, org-policy notes, cost table, prepared fallbacks"
  - "tests/unit/test_cloudrun_yaml.py: 33-test offline structural guard over both templates and both scripts"
affects: [04-09, 04-10, 04-11, 04-12, 04-13, 04-14]

actuals:
  tokens: 15822
  tasks: 3
  commits: 4
plan_head_before: 1e7c2ecf0cc436859547be14d2426438aef1fdc4
plan_head_after: 93a8ebba75435f874d6d8624a00628210f8dee55

tech-stack:
  added: []
  patterns:
    - "Public-repo templates: dollar-brace placeholders rendered from env by a script that names missing variables and never prints values"
    - "Structural guard over deploy YAML with cross-file assertions (audience, service account, secret suffix rule)"
    - "Idempotent describe-then-create bootstrap, IAM output suppressed so member emails never reach the terminal"

key-files:
  created:
    - deploy/cloudrun/mcp-server.yaml
    - deploy/cloudrun/chat-bot.yaml
    - deploy/cloudrun/bootstrap.sh
    - deploy/cloudrun/README.md
    - scripts/render-cloudrun.sh
    - tests/unit/test_cloudrun_yaml.py
  modified: []

key-decisions:
  - "Meridian start-up probe on Cloud Run is httpGet /health (not /readyz): the seeded single credentials file gives /readyz 503 'no profiles configured', exactly as measured on kind in 04-07; Cloud Run has no exec probe"
  - "GCS FUSE volume carries mountOptions uid=1000,gid=1000 so the Meridian image user (uid 1000) can write the refreshed OAuth login"
  - "No age-based lifecycle rule on the index bucket: it would delete the build the pointer names after a month without a sync"
  - "chat-bot leaves DEPLOY_ENV unset (04-03 hand-off) while mcp-server sets DEPLOY_ENV production explicitly (plan); both are fail-closed production"
  - "container-dependencies is written as JSON {\"chat-bot\":[\"meridian\"]}, not YAML flow style"

patterns-established:
  - "Templates keep comments free of placeholder markers, so any leftover marker after rendering is a bug"
  - "Runbook states every prepared fallback as 'only with Joshua's consent'"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "mcp-server.yaml is a europe-west8 knative Service, scale 0..1, stateless, request-based billing, reads its index from the private bucket through the gcs store, secrets only through secretKeyRef, and renders from env with no placeholder left"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "./run-unit-tests.sh --single-file test_cloudrun_yaml.py tests/unit (33 passed; mcp-server tests plus render-script test)"
        status: pass
      - kind: other
        ref: "scripts/render-cloudrun.sh mcp-server <file> with sample values, then ! grep -q '${' <file> (exit 0, yaml.safe_load of the output succeeds)"
        status: pass
    human_judgment: false
  - id: D2
    description: "chat-bot.yaml carries the loopback Meridian sidecar started first, the read-write GCS FUSE credentials volume in Meridian only, an in-memory session volume, HTTP intake, maxScale 1, single-user guards, no-log-leak settings, and agrees with mcp-server.yaml on audience, MCP URL and bot service account"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_chat_bot_sidecar_starts_first_on_gen2_and_scales_to_zero, #test_meridian_credentials_fuse_volume_is_mounted_read_write_in_meridian_only, #test_chat_bot_single_user_guards_hold_while_the_llm_is_meridian, #test_chat_bot_audience_calls_equal_the_server_public_url_and_its_mcp_endpoint, #test_chat_bot_logs_no_question_text_with_a_user_identity"
        status: pass
      - kind: other
        ref: "scripts/render-cloudrun.sh chat-bot <file> with sample values, then ! grep -q '${' <file> (exit 0, yaml.safe_load succeeds)"
        status: pass
    human_judgment: false
  - id: D3
    description: "bootstrap.sh holds the one-time setup (APIs, Firestore behind a typed region confirmation, two TTL policies, registry with cleanup policy, three private buckets, three service accounts and roles, six empty secrets, WIF limited to repository id and main) and prints names only"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_bootstrap_never_creates_a_project_and_takes_ids_only_from_the_environment and 3 sibling bootstrap tests"
        status: pass
      - kind: other
        ref: "bash -n deploy/cloudrun/bootstrap.sh (exit 0)"
        status: pass
    human_judgment: true
    rationale: "No gcloud command was run against any project (this plan is static; the live run is 04-13). Whether each flag and role is accepted by the real API and the organization policies is provable only live."
  - id: D4
    description: "Runbook covers prerequisites, bootstrap in Docker, secret handling, the fresh-login seeding of the credentials bucket, GitHub variables, render and deploy, Chat and claude.ai wiring, org-policy notes, cost table and the prepared fallbacks"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_cloudrun_yaml.py#test_runbook_covers_the_bootstrap_seeding_fallbacks_and_org_policy_notes (11 headings)"
        status: pass
    human_judgment: true
    rationale: "A test proves the runbook mentions each topic; whether the steps are clear and complete enough to follow with the owner present is a reader's judgment, confirmed in 04-13."
  - id: D5
    description: "Cloud Run runtime behaviour the docs do not state: a start-up probe reaching the loopback-bound Meridian port, the FUSE uid option giving Meridian write access, the in-memory volume being writable by uid 1000, Meridian cold start inside Chat's deadline"
    requirement: "INFRA-04"
    verification: []
    human_judgment: true
    rationale: "Provable only on a live revision; flagged as assumptions with prepared fallbacks in the README and checked in 04-13."

duration: 12min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 08: Cloud Run templates, render script and bootstrap Summary

**Two europe-west8 Cloud Run templates (MCP server on the GCS-backed index, chat bot with a loopback Meridian sidecar and a GCS FUSE credentials volume), an envsubst render script that never prints values, and a one-time bootstrap that never creates a project, all guarded by a 33-test offline suite.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-11-14T12:55:57Z
- **Completed:** 2026-11-14T13:07:12Z
- **Tasks:** 3 (1 tracer, 1 TDD, 1 auto)
- **Files modified:** 7 (6 created, 1 deleted: `deploy/cloudrun/.gitkeep`)

## Accomplishments

- `mcp-server.yaml`: `serving.knative.dev/v1` Service, minScale 0 and maxScale 1, no volume, no `PORT`, no cpu-throttling annotation (04-01 `billing_mode` (a)), `DEPLOY_ENV production`, `AUTH_MODE on`, `ARTIFACT_STORE gcs` over `<PROJECT_ID>-ai-buddy-index` with prefix `index/`, three secrets through `secretKeyRef`, deterministic public URL, `BOT_SA_EMAILS` naming the bot's runtime account.
- `chat-bot.yaml`: ingress container `chat-bot` (port 8080, `INTAKE=http`, Google JWT, `LLM_BACKEND=meridian`, `ALLOWED_USERS` from a secret) plus the `meridian` sidecar (no port, `MERIDIAN_HOST 127.0.0.1`, `MERIDIAN_SILENT 1`, 7-day transcript retention, session dir on a 64Mi in-memory volume), gen2, container-dependencies, and the credentials bucket mounted read-write in Meridian only. `MCP_AUDIENCE` equals the server's `MCP_PUBLIC_BASE_URL`, `MCP_URL` is that plus `/mcp`, both asserted across the two files.
- `scripts/render-cloudrun.sh`: nine-variable fixed list, `MERIDIAN_TAG` defaulting to `deploy/meridian.version`, names (never values) of missing variables, refuses a value with a quote, backslash, `$` or newline, fails on any leftover `${`, never prints the rendered file. Executable bit set in the index.
- `deploy/cloudrun/bootstrap.sh`: verifies the project exists and its number matches, enables nine APIs, creates the Firestore `(default)` database only after the region is typed at a terminal, enables TTL on `expire_at` for `gaps` and `thread_memory`, creates the `ai-buddy` registry (keep 3 versions), three private buckets (uniform access, public access prevention), three service accounts with the RESEARCH roles, six empty secrets, and the WIF pool and provider restricted to the numeric repository id and `refs/heads/main`.
- `deploy/cloudrun/README.md` (11 sections) with the fresh-login seeding procedure (`claude auth login` in the Meridian image into a temp dir), cost table, org-policy handling and seven prepared fallbacks, each marked "only with Joshua's consent".

## Task Commits

1. **Task 1: Tracer, mcp-server.yaml renders and passes the guard** - `e0a3288` (feat). Tracer gate: `<verify>` re-run end to end after Task 2 and Task 3 (12 tests at first, 33 at the end, render check for both services); passed, expansion continued.
2. **Task 2 (TDD): chat-bot.yaml** - `468e08f` (test, RED: 14 tests failing on the missing file), `523759f` (feat, GREEN)
3. **Task 3: bootstrap.sh, README, gitkeep removal, bootstrap guard tests** - `93a8ebb` (feat)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md and ROADMAP.md.

## Files Created/Modified

- `deploy/cloudrun/mcp-server.yaml`, `deploy/cloudrun/chat-bot.yaml` - the two service templates
- `deploy/cloudrun/bootstrap.sh` - one-time project setup (mode 100755)
- `deploy/cloudrun/README.md` - runbook
- `scripts/render-cloudrun.sh` - placeholder rendering (mode 100755)
- `tests/unit/test_cloudrun_yaml.py` - 33 offline tests
- `deploy/cloudrun/.gitkeep` - deleted (intentional)

## Decisions Made

See `key-decisions` above. The first four deviate from or refine the plan text and are explained below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Meridian start-up probe path `/readyz` replaced by `/health`**
- **Found during:** Task 2 (hand-off from 04-07)
- **Issue:** the plan asked for httpGet `/readyz`. 04-07 measured that `/readyz` answers 503 "no profiles configured" for the single credentials file this deployment seeds, while `/health` answers 200 once the login is read. Cloud Run seeds the same single file (`token_chain` (b)), so `/readyz` would never pass and `container-dependencies` would block the bot forever. The loopback half of the 04-07 finding (kubelet probes the pod IP) does not carry over as a certainty: Cloud Run offers no exec probe, and its docs do not say whether a start-up probe reaches a loopback-bound port (checked the health-check page on 2026-11-14, silent).
- **Fix:** httpGet `/health` on port 3456, `MERIDIAN_HOST 127.0.0.1` kept as the plan and T-04-28 require. The loopback uncertainty is documented in the YAML comment and the README with ordered fallbacks (tcpSocket probe, then `MERIDIAN_HOST 0.0.0.0`, which stays unreachable from outside because only the ingress container takes traffic).
- **Files modified:** `deploy/cloudrun/chat-bot.yaml`, `deploy/cloudrun/README.md`
- **Verification:** `test_meridian_sidecar_startup_probe_is_a_supported_http_probe_on_the_health_route`
- **Committed in:** `523759f`, `93a8ebb`

**2. [Rule 2 - Missing critical] GCS FUSE `mountOptions: uid=1000,gid=1000`**
- **Found during:** Task 2
- **Issue:** without ownership options the mounted objects belong to root and the Meridian image user (uid 1000, confirmed with `id` in the pinned image) cannot write the refreshed OAuth login back, which would break the token chain after the first expiry.
- **Fix:** `mountOptions: uid=1000,gid=1000` on the volume; the YAML form (comma separated) was confirmed on the Cloud Run Cloud Storage volume page.
- **Files modified:** `deploy/cloudrun/chat-bot.yaml`; asserted in `test_meridian_credentials_fuse_volume_is_mounted_read_write_in_meridian_only`
- **Committed in:** `523759f`

**3. [Rule 1 - Bug] 30-day delete rule on the index bucket not applied**
- **Found during:** Task 3
- **Issue:** the plan asked for a 30-day delete rule on `index/index-` objects. A lifecycle rule by age also removes the build that `index.manifest.json` names once a month passes without a new sync; the server would then refuse to start at the next cold start (the pointer names a missing object). `docs` written by 04-10 mention "30-day lifecycle on old builds".
- **Fix:** bootstrap creates no lifecycle rule; a comment in the script and a README design note explain why. Old builds are a few MB each.
- **Follow-up for the orchestrator:** 04-10 (`docs/index-format.md` "Publishing to a bucket") should not promise a bucket lifecycle rule; pruning belongs in the sync step (delete builds the pointer does not name and that are older than N days) or a customTime-based rule.
- **Files modified:** `deploy/cloudrun/bootstrap.sh`, `deploy/cloudrun/README.md`
- **Committed in:** `93a8ebb`

**4. [Rule 2 - Missing critical] Render script rejects unsafe characters in values**
- **Found during:** Task 1
- **Issue:** values are inserted into double-quoted YAML scalars; a quote, backslash, `$` or newline in a repository variable could end the scalar or smuggle in a field.
- **Fix:** the script refuses such values (naming only the variable) before `envsubst`.
- **Files modified:** `scripts/render-cloudrun.sh`
- **Committed in:** `e0a3288`

**5. [Hand-off] `DEPLOY_ENV` unset on chat-bot, explicit on mcp-server**
- The plan's Task 2 behaviour line says `DEPLOY_ENV production` for the bot; the 04-03 hand-off and the orchestrator say to leave it unset. Both mean production (fail closed). Followed the hand-off for the bot, asserted `DEPLOY_ENV` absent and `CHAT_API` absent or `google` (the YAML half of T-04-10); `mcp-server.yaml` sets `DEPLOY_ENV production` explicitly as the plan's truth requires.

**6. [Rule 1 - Bug] `container-dependencies` as JSON, project id kept out of the README**
- The RESEARCH sketch wrote `{chat-bot: [meridian]}`, which is not the JSON the annotation takes; the file uses `'{"chat-bot":["meridian"]}'` and a test parses it. The plan told the README to name the GCP project by id; the repository is public and the orchestrator forbade project ids in tracked files, so the README says "the existing GCP project" and points to `docs/internal/gcp-project.md`. A test asserts the id literal appears in none of the new files.

**7. [Rule 3 - Blocking] Tracer render check failed on comments**
- The first render left `${` in the output because the template's own header comment quoted the marker syntax. Comments were reworded ("dollar-brace placeholders") and the rule is now a pattern: a template comment never holds a marker. Same wording used in `chat-bot.yaml`.

Plan-text refinements, not fixes: `ci-deployer` and the owner get `run.developer` on the project because the services do not exist before the first deploy; secrets use automatic replication; 5 extra tests cover `bootstrap.sh` and the runbook (33 total, plan minimum was 8 plus 3).

---

**Total deviations:** 7 (3 Rule 1, 2 Rule 2, 1 Rule 3, 1 hand-off interpretation)
**Impact on plan:** All necessary for correctness (a probe that can pass, a volume that is writable, an index that is not deleted under the server, YAML that cannot be injected). No scope creep; the lifecycle omission needs a one-line follow-up in 04-10's documentation.

## Authentication Gates

None. No gcloud command was run against any project.

## Issues Encountered

- `ctx7` is not installed and no Context7 tool was available to this agent; the Cloud Run health-check and Cloud Storage volume pages were fetched directly with `curl` (public documentation, nothing private sent) to confirm the probe types and the `mountOptions` YAML form.
- The Meridian variable names in the plan (`MERIDIAN_HOST`, `MERIDIAN_PORT`, `MERIDIAN_HOST_ID`, `MERIDIAN_SILENT`, `MERIDIAN_SESSION_DIR`, `MERIDIAN_TRANSCRIPT_RETENTION_DAYS`) were checked against the built pinned image (`dist` of the commit in `deploy/meridian.version`): all are read there (the retention variable through Meridian's prefixed `env()` helper, default `0`). `MERIDIAN_DEBUG` exists, so a test forbids any variable containing DEBUG. No name differed from the plan.

## Known Stubs

None. Every placeholder in the templates is rendered by `scripts/render-cloudrun.sh`; the README's `...` values are shell examples.

## Threat Flags

None beyond the plan's threat model (T-04-27 to T-04-33 covered: production and auth env asserted, loopback sidecar without a port, private credentials bucket mounted in Meridian only, secretKeyRef for six values, render script that never prints, WIF condition on repository id and `main`, `maxScale '1'`, typed Firestore confirmation).

## User Setup Required

None in this plan. 04-13 (live, with Joshua present) runs `bootstrap.sh`, adds the six secret values, seeds the credentials bucket with a fresh `claude auth login`, and sets the GitHub repository variables, all described in `deploy/cloudrun/README.md`.

## Not Run (static plan)

- `bootstrap.sh` and every `gcloud` command: not executed; only `bash -n` was run. `shellcheck` was not available locally.
- `gcloud run services replace --dry-run`: runs in CI (04-09) and live in 04-13.
- Rendered files were produced only with sample values (`demo-ai-buddy`, a fake project number) into the scratchpad.

## Next Phase Readiness

- 04-09 can render both templates in CI with the nine variables and validate them with `gcloud run services replace --dry-run` after WIF login; the variable names are listed in `scripts/render-cloudrun.sh` and the README.
- 04-10 should drop the "30-day lifecycle on old builds" wording (deviation 3) and may add pruning to the sync step.
- 04-13 must check: the Meridian start-up probe reaches the loopback port (fallbacks in README), the FUSE `uid=1000` write, the in-memory volume permission, Meridian cold start inside Chat's deadline, the slow-answer placeholder replacement (Pitfall 1), Firestore TTL listing, and the authenticated bot-to-server call.

## Self-Check: PASSED

- FOUND: `deploy/cloudrun/mcp-server.yaml`, `deploy/cloudrun/chat-bot.yaml`, `deploy/cloudrun/bootstrap.sh`, `deploy/cloudrun/README.md`, `scripts/render-cloudrun.sh`, `tests/unit/test_cloudrun_yaml.py`; `deploy/cloudrun/.gitkeep` absent
- FOUND: commits `e0a3288`, `468e08f`, `523759f`, `93a8ebb` on main (`git rev-list --count` from the ledger base = 4)
- Acceptance: `serving.knative.dev/v1` 1, `ARTIFACT_STORE` in mcp-server.yaml 1, `envsubst` in the script 2, `gcsfuse.run.googleapis.com` 1, `container-dependencies` 1, `secretKeyRef` in chat-bot.yaml 4, matching test names 8, `refs/heads/main` 1, `ttls update expire_at` 2, `public-access-prevention` 2, `set -x` 0, README `## ` headings 11, `.gitkeep` gone, scripts executable (100755)
- Verification: `./run-unit-tests.sh --all` exit 0 (1325 passed, 26 skipped, ruff, ruff format and mypy clean); `bash -n` on both scripts; render of both services leaves no `${`

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
