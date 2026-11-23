---
gsd_state_version: "1.0"
current_phase: 5
status: completed
stopped_at: Phase 5 complete — all phases complete
last_updated: "2026-11-23T11:15:37.364Z"
last_activity: 2026-11-23
last_activity_desc: Phase 5 complete
state_head: 6af3b94ca905cfe38ce3ceed041cb9ab01f39c1f
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 73
  completed_plans: 73
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-22)

**Core value:** An employee gets an answer only from official sources with the source cited, or an honest "non lo so, chiedi a ..." with the gap logged. Never an invented policy.
**Current focus:** Phase 05 — Evaluation and Milestone Gate

## Current Position

Phase: 5
Plan: Not started
Status: All phases complete
Last activity: 2026-11-23 - Completed quick task 261123-fpj: Restructure internal deep dive and story deck into three parts, with terminology, fact and clear-writing fixes

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 73
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 11 | - | - |
| 02 | 7 | - | - |
| 03 | 12 | - | - |
| 4 | 26 | - | - |
| 5 | 17 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 25 min | 3 tasks | 17 files |
| Phase 01 P02 | 5 min | 3 tasks | 13 files |
| Phase 01 P03 | 5 min | 3 tasks | 5 files |
| Phase 01 P04 | 4 min | 3 tasks | 6 files |
| Phase 01 P05 | 6 min | 3 tasks | 11 files |
| Phase 01 P06 | 4 min | 3 tasks | 9 files |
| Phase 01 P07 | 25 min | 2 tasks | 6 files |
| Phase 1 P09 | 45 min | 3 tasks | 18 files |
| Phase 1 P10 | 2 min | 3 tasks | 10 files |
| Phase 02 P01 | 8min | 3 tasks | 17 files |
| Phase 02 P02 | 10 min | 2 tasks | 9 files |
| Phase 02 P03 | 25 min | 3 tasks | 10 files |
| Phase 02 P04 | 8 min | 3 tasks | 11 files |
| Phase 02 P05 | 8 min | 3 tasks | 10 files |
| Phase 02 P06 | 15 min | 3 tasks | 3 files |
| Phase 02 P07 | n/a | 3 tasks | 9 files |
| Phase 03 P02 | 6 min | 2 tasks | 3 files |
| Phase 03 P01 | 2 min | 3 tasks | 8 files |
| Phase 03 P03 | 5 min | 2 tasks | 12 files |
| Phase 03 P04 | 10 min | 2 tasks | 13 files |
| Phase 03 P05 | 25 min | 3 tasks | 9 files |
| Phase 03 P06 | 7 min | 3 tasks | 4 files |
| Phase 03 P07 | 4 min | 2 tasks | 3 files |
| Phase 03 P08 | 12 min | 2 tasks | 2 files |
| Phase 03 P09 | 8 min | 2 tasks | 6 files |
| Phase 03 P10 | 12 min | 3 tasks | 11 files |
| Phase 03 P11 | 25 min | 3 tasks | 10 files |
| Phase 03 P12 | n/a | 3 tasks | 11 files |
| Phase 04 P02 | 15 min | 3 tasks | 15 files |
| Phase 04 P01 | 25 min | 3 tasks | 3 files |
| Phase 04 P03 | 5 min | 3 tasks | 12 files |
| Phase 04 P04 | 14 min | 3 tasks | 14 files |
| Phase 04 P05 | 4 min | 2 tasks | 5 files |
| Phase 04 P06 | 25 min | 3 tasks | 12 files |
| Phase 04 P07 | 17 min | 3 tasks | 16 files |
| Phase 04 P08 | 12 min | 3 tasks | 7 files |
| Phase 04 P10 | 14 min | 3 tasks | 10 files |
| Phase 04 P09 | 6 min | 3 tasks | 12 files |
| Phase 04 P11 | 7 min | 3 tasks | 13 files |
| Phase 04 P12 | 13 min | 2 tasks | 5 files |
| Phase 04 P17 | 4 min | 2 tasks | 6 files |
| Phase 04 P19 | 14 min | 2 tasks | 4 files |
| Phase 04 P18 | 18 min | 3 tasks | 10 files |
| Phase 04 P15 | 60min | 3 tasks | 1 files |
| Phase 04 P20 | 12 min | 2 tasks | 9 files |
| Phase 04 P21 | 20 min | 2 tasks | 7 files |
| Phase 04 P22 | 35 min | 2 tasks | 10 files |
| Phase 04 P24 | 35 min | 2 tasks | 9 files |
| Phase 04 P23 | 40min | 3 tasks | 4 files |
| Phase 04 P25 | 40 min | 3 tasks | 9 files |

## Accumulated Context

### Decisions

Full log in PROJECT.md Key Decisions (`<decisions>` block, D1-D16 locked).
Recent decisions affecting current work:

- [Init]: D1a — Meridian + Joshua's Max only for personal dev; guards: Chat app visible to Joshua, `ALLOWED_USERS`, `LLM_BACKEND` meridian|api
- [Init]: D14 — Test handbook [ClickUp doc ID removed] (id via env); official [ClickUp doc ID removed] not used in Milestone 1
- [Init]: D16 — every phase plan cites applied Guides sections and justifies exceptions
- [Init]: Foundation (repo skeleton, `run-unit-tests.sh`, tooling) moved from Phase 4 to Phase 1 so Phases 1-3 can be verified in Docker
- [Init]: Golden set drafted by Claude from test doc + Guides (incl. no-answer and sensitive cases), reviewed by Joshua
- [Phase 01]: Dependency pins: user chose latest versions; verified latest on PyPI 2026-11-03 (ten direct packages, pinned with ==)
- [Phase 01]: ruff extend-exclude .planning and docs: ruff 0.17 formats Python code blocks in Markdown
- [Phase 01]: 01-02: search queries built only via to_match_query (quoted tokens, NUL as separator, bound MATCH parameter); chunk_key is heading-based (changing it needs a schema major bump plus re-sync)
- [Phase 01]: 01-02: only the latest artifact is kept in ARTIFACT_DIR; versioned = schema_version + build_id + manifest. ArtifactStore port with LocalDirArtifactStore; bucket vs baked image deferred to Phase 4 (D-12, ADR 0001)
- [Phase 01]: 01-03: IBAN rule retries shorter heads when an uppercase word is swallowed; signed_url_query keeps fragment; entropy rule skips URLs via one alternation
- [Phase 01]: 01-03: non-company e-mails masked by default; allow-listing calendar/reply-to domains deferred to plan 08
- [Phase 01]: Plan 01-04: a page is processed when new, versions_match is False, date_edited differs, or the redacted-text hash differs; unchanged pages keep the previous row with current position, depth and parent
- [Phase 01]: Plan 01-04: ClickUp response is streamed and capped at MAX_RESPONSE_BYTES; transport errors are not retried and report the exception type only
- [Phase 01]: 01-05: chunk keys always derive from redacted headings via public assign_chunk_keys; GUIDES_INDEX.md table format is the costly cross-repo contract (File | Level | Section | Line)
- [Phase 01]: 01-05: GitGuidesSource attaches the token only as an http.extraHeader in GIT_CONFIG env for https urls; destructive git requires the .buddy-sync-checkout marker
- [Phase 01]: resolve_video_links fails on a duplicate README row or a guide mapped by two sections.yaml files, and needs the chunks of every mapped guide — Silent override is the drift D-02 forbids; guide must be an indexed file (T-01-26)
- [Phase 01]: Only a dash in the README video cell means no video; an empty or malformed cell raises VideoMapError — Format drift guard for the cross-repo README table contract
- [Phase 01]: 01-07: run_sync closes the previous artifact before building; only IndexVersionError counts it as absent (WARNING, full rebuild)
- [Phase 01]: 01-07: CLI maps OSError/sqlite3.Error/IndexFormatError to one ERROR line and exit 1; ValidationError names variables only, never values
- [Phase 01]: 01-07: guides_index_drift is checked only when Guides are rebuilt; list-pages prints denylisted pages with [denied] and redacted title
- [Phase 1]: Handbook citation is handbook://<page_id>, page_id = file stem (costly; no consumer yet)
- [Phase 1]: REDACT_PAGE_FILES holds bare file names and every entry must name an existing page file (fail closed)
- [Phase 1]: Handbook pages flat (parent_id null, depth 0) in file-name order; index.db schema stays 1.0.0
- [Phase 1]: Executor commits went to branch gsd/phase-01-content-sync because main is guard-protected; needs merge to main
- [Phase 1]: 01-10: revision_date_iso documented as full ISO-8601 UTC datetime (matches code); handbook format change recorded as 1.0.0 amendment (DDL unchanged, no artifact published)
- [Phase 02]: 02-01: fastmcp 4.1.6, snowballstemmer 3.1.1, google-cloud-firestore 2.34.1 pins approved by Joshua at the legitimacy gate
- [Phase 02]: 02-01: revision_kind keeps its default but is forced into the advertised output schema required list (json_schema_extra)
- [Phase 02]: 02-01: Guides revision_date is the index build date labelled indexed_on; source_url is a GitHub permalink pinned to the indexed commit with #L<n> for single-line sections
- [Phase 02]: handbook_get and handbook://{pagina} use exact page_id lookup only (case-sensitive, no fuzzy match); resources/list stays empty, only the template is advertised
- [Phase 02]: Handbook FTS is a separate in-memory sqlite3 db of Snowball stems built in load_snapshot; no prefix matching until Phase 5 Recall@5
- [Phase 02]: 02-03: FirestoreStore built directly (gRPC channel is lazy, no loop bound at construction); Fernet imported directly from fastmcp transitive; raise_on_decryption_error=False so a rotated key re-registers clients
- [Phase 02]: 02-03: MCP-05/MCP-07 left Pending - 02-03 provides storage only; tool (02-04) and auth (02-05) complete them
- [Phase 02]: buddy_report_gap never reads token or request context and logs only the exception type on backend failure; no caller identity (D-10)
- [Phase 02]: Log hygiene test attaches its handler to the non-propagating fastmcp logger; handbook_get TOC text carries a Fonte line per entry so every source_url appears in text
- [Phase 02]: 02-05: bot-to-MCP auth is a Google-signed service-account ID token (aud = MCP_PUBLIC_BASE_URL, e-mail in BOT_SA_EMAILS) verified through MultiAuth beside the OAuth proxy (D-12 defined and tested)
- [Phase 02]: 02-05: email_verified accepts only boolean true or string 'true' (Google tokeninfo returns strings); user and bot verifiers require audience and bot tokens require exp
- [Phase 02]: 02-05: Host/Origin guard uses fastmcp host_origin_protection=True via host_kwargs(settings); K_SERVICE presence refuses AUTH_MODE=off in McpSettings
- [Phase 02]: 02-06: D-17 escalation list (8 rows, roles HR and responsabile diretto) approved by Joshua as drafted; Skill holds roles only
- [Phase 02]: 02-06: Skill description must avoid ': ' (breaks unquoted YAML front matter); guarded by safe_load test
- [Phase 02]: 02-07: python -m buddy_mcp composition root proven as a real process on the Firestore emulator; mcp_server image runs as uid 10001 and does not bake the index
- [Phase 02]: 02-07: Google OAuth verified live through a fastmcp OAuth client (DCR, Google login, token, five tools, cited search); MCP-07 marked complete by user decision 2026-11-06 with claude.ai connector and non-digitiamo rejection checks carried to Phase 4
- [Phase 03]: 03-02: escalation table ids fixed (stipendio, malattia, molestie, disciplinare, contratto, privacy, ferie_personali, rimborsi); ruolo is the role the bot names, referente keeps Skill wording for the drift check
- [Phase 03]: 03-01: chat-bot pins approved by Joshua (langgraph 1.2.20, anthropic 2.6.0, google-cloud-pubsub 2.43.0, google-apps-chat 0.10.9, requests 2.34.2 pin-only); Meridian source commit cafdcf780f1b40c8f0dee17481132f47b4cbb353
- [Phase 03]: 03-01: D-16, D-11, D-09 overridden (Meridian credentials in a named volume; DM memory key HMAC(space); HTTP run awaited up to 25 s); BOT-09, D-10, D-07 interpreted; recorded in 03-CONTEXT.md Amendments (03-01 checkpoint)
- [Phase 03]: 03-01: VIDEO_THUMBNAIL_URL is a required HTTPS setting; the image is supplied by Joshua via .env at the 03-12 live checkpoint (not yet provided)
- [Phase 03]: All chat-bot I/O ports are async; RunContext and State are public workflow names for 03-05
- [Phase 03]: render strips URL tokens from model prose so only bot-built Fonte lines carry links (T-03-01)
- [Phase 03]: normalize_event takes object and returns None for malformed shapes (mistyped slashCommand, messagePayload without message, bool or missing command id) instead of degrading the event
- [Phase 03]: Mention fallback removes one leading @word token when argumentText is absent; a two-word display name leaves a residue; argumentText is the primary path and 03-12 confirms RESEARCH A13
- [Phase 03]: 03-05: only LlmOutputError skips the retry plan; LlmUnavailableError propagates (error text, no gap); LlmError at reformulate gives the error reply
- [Phase 03]: 03-05: a non-null sensitive_topic (even empty or unknown id) is sensitive; role from shared table, HR fallback; final failure is kind referral plus gap
- [Phase 03]: 03-05: referente contact kept only as verbatim substring of a handbook page returned in the run; gap logs the standalone question plus tried queries of both attempts
- [Phase 03]: 03-06: anthropic 2.6.0 sends the API key as Authorization: Bearer (no x-api-key); Meridian gate header compatibility to confirm at the 03-12 live check
- [Phase 03]: 03-06: 'more than one user' under LLM_BACKEND=meridian counts distinct normalized ALLOWED_USERS entries; list exactly one form of the identifier
- [Phase 03]: 03-07: ThreadMemory adapters hash a caller-supplied key source (DM space name or room thread name, memory_key 3b) with HMAC-SHA256; document shape fixed to turns/updated_at/expire_at; read-side 24h expiry (expire_at <= now reads empty) until Phase 4 Firestore TTL
- [Phase 03]: 03-08: card sections only for cited Guides sources with an http(s) video_url; non-web schemes get no section or button
- [Phase 03]: 03-08: sensitive answer order is prose, Fonte lines, contact provenance line, then the fixed referral sentence last; final 4,000-char clamp for any kind
- [Phase 03]: 03-09: memory_key_source follows 03-01 option b (DM space name, room thread name); no thread means no memory
- [Phase 03]: 03-09: message-name TTL dedupe (600 s, 1024 entries) marks a name seen on first handling, also when that attempt fails; per process only
- [Phase 03]: 03-09: run deadline covers history read, workflow and rendering; placeholder creation sits outside it
- [Phase 03]: 03-10: ChatTokenVerifier refuses an empty audience (google-auth skips the audience check when None); http_ack (b) implemented as ACK_SECONDS=25.0, 0 gives option (a)
- [Phase 03]: 03-10: Chat API errors re-raised as ChatApiError(type name) with from None; GoogleChatApi factory typed to a two-method ChatClient protocol
- [Phase 03]: 03-11: fastmcp and anthropic loggers floored at INFO in buddy_bot.cli.main so FASTMCP_LOG_LEVEL=DEBUG or ANTHROPIC_LOG=debug cannot log question text or prompts (BOT-11)
- [Phase 03]: 03-11: SIGTERM left at the interpreter default in python -m buddy_bot; Phase 4 may add a drain handler for Cloud Run
- [Phase 03]: 03-12: add-on Chat apps publish to Pub/Sub as the gsuiteaddons service agent (not chat-api-push); bot shares the MCP server network namespace for the loopback Host guard; live check approved 2026-11-07
- [Phase 04]: DEPLOY_ENV (default production) is the explicit marker for auth-off guards; AUTH_MODE=off only with DEPLOY_ENV=local, and local is refused whenever K_SERVICE is set — K_SERVICE-only guard failed open on kind and any non-Cloud-Run host (audit warning 4, WR-01)
- [Phase 04]: MCP_ALLOWED_HOSTS widens the Host guard by exact-match bare hostnames only; /healthz is a FastMCP custom route outside the auth provider, Host-guarded — Pod-to-pod Service names got 421; guard must stay on (INFRA-03); AUTH_MODE=on test proved route is unauthenticated
- [Phase 04]: billing_mode (a): request-based on both services; 04-13 measures a slow question and re-asks Joshua on a stall (keeps INFRA-04)
- [Phase 04]: coverage_inheritance (a): literal D-18 fallback, no-entry sections start at 0 (keeps D-18)
- [Phase 04]: sections_authoring (a): Claude drafts five sections.yaml; Joshua commits them with five durations.json; eight guides stay at 0 offset (interprets D-18)
- [Phase 04]: video_fetch (a): Joshua downloads release videos to .cache/videos; upload-videos reads both directories (interprets D-17)
- [Phase 04]: token_chain (b): fresh separate claude login seeds the Cloud Run bucket; local volume keeps its own chain (keeps D-12)
- [Phase 04]: org_policy (yes): project `ai-buddy-dev` (IDs in docs/internal/gcp-project.md, gitignored) under the digitiamo.com organization, billing linked; org policies may apply to 04-08 and 04-13 (information)
- [Phase 04]: 04-03: bot mirrors the server DEPLOY_ENV rule; MCP_AUTH=none and CHAT_API=recording need explicit DEPLOY_ENV=local, local refused under K_SERVICE — RecordingChatApi is a config-selected second adapter of the ChatApi port so compose and kind can prove a chat round trip with no Google Chat API (Chat has no emulator); CHAT_API and CHAT_RECORD_PATH stay out of .env.example
- [Phase 04]: 04-04: artifact store chosen only by ARTIFACT_STORE in artifact_store_from_settings; the bucket pointer is trusted only after build_id, object name, sha256 and size validation
- [Phase 04]: 04-04: GcsArtifactStore.publish uploads the db object, checks the bucket md5, then overwrites the pointer last; BucketError carries the exception type name only
- [Phase 04]: 04-05: sync image stage marks /guides-src and /guides-src/.git safe.directory (git names the .git path for a non-root clone of a host-owned mount); INFRA-01 met by one multi-stage Dockerfile with a runtime target per service, guarded by tests/unit/test_dockerfile_stages.py
- [Phase 04]: Compose live-profile inputs are not compose-required; chat-bot-live fails fast on a missing key (compose interpolates inactive profiles, so :? broke the default stack) — Found by the plan-level re-run of the smoke script after the live profile was added.
- [Phase 04]: Sync source mounts use long bind syntax so a relative HANDBOOK_SRC_DIR is a path, not a named volume — Found by the plan-level re-run of the smoke script after the live profile was added.
- [Phase 04]: chat-bot depends on sync directly as well as through mcp-server; the Pub/Sub emulator REST surface works for topic, subscription and publish — Found by the plan-level re-run of the smoke script after the live profile was added.
- [Phase 04]: 04-07: Meridian in kind is probed with exec probes (node fetch inside the container) on /health and /livez, staying bound to 127.0.0.1; /readyz needs a Meridian profile and answers 503 for the single seeded credentials file
- [Phase 04]: 04-07: kind-up uses a per-cluster kubeconfig under .cache and creates Secrets imperatively from streams (meridian-credentials re-applied each run via server-side apply, bot-secrets created once); no Secret object or value in git
- [Phase 04]: 04-08: Meridian Cloud Run start-up probe is httpGet /health, not /readyz (single seeded credentials file gives /readyz 503; Cloud Run has no exec probe; loopback reachability unverified, checked in 04-13)
- [Phase 04]: 04-08: GCS FUSE credentials volume uses mountOptions uid=1000,gid=1000 so the Meridian image user can write the refreshed login
- [Phase 04]: 04-08: no age-based lifecycle rule on the index bucket (it would delete the build the pointer names after a month without a sync); 04-10 docs must not promise one
- [Phase 04]: 04-08: chat-bot leaves DEPLOY_ENV unset (04-03 hand-off), mcp-server sets DEPLOY_ENV production; both fail closed
- [Phase 04]: 04-10: publish reports unchanged from the bucket pointer content_hash before any upload; old builds are never pruned and no age-based delete exists (it would remove the build the pointer names), so rollback means rewriting the pointer
- [Phase 04]: 04-09: deploy and Meridian jobs mask project identifiers with add-mask first; gcloud stdout to /dev/null, stderr printed only on failure (public Actions logs)
- [Phase 04]: 04-09: path filters equal the Dockerfile COPY sources per runtime stage, enforced by a drift test importing the 04-05 COPY parser; no required-check gate job until pull requests exist
- [Phase 04]: 04-11: links kept from the previous artifact are re-pointed with rewrite_links when VIDEO_BUCKET is set, so adding the variable takes effect without a Guides commit
- [Phase 04]: 04-11: sync-and-publish.sh passes VIDEO_BUCKET to run only after upload-videos ran (T-04-44); project id and ADC are validated before the first bucket step
- [Phase 04]: 04-11: upload-videos skips by md5 only (BucketPort has no header metadata); live header and playback check is 04-13
- [Phase 04]: 04-12: D-18 fallback kept (04-01 coverage_inheritance (a)); video-coverage reports scene/fallback only, no inherited source, no schema change
- [Phase 04]: D-18 coverage 708/2524 scene-mapped rows after the Guides maps (baseline 238/2524); 8 guides with video still at fallback (8 without durations)
- [Phase 04]: 04-17: ci-deployer keeps roles/run.admin in bootstrap.sh (run.services.setIamPolicy for invoker-iam-disabled); every IAM bind call pinned by an exact test
- [Phase 04]: 04-17: OAUTH_STORAGE_ENCRYPTION_KEY validated as a Fernet key at McpSettings config time, error names the variable only
- [Phase 04]: 04-19: publish trusts a pointer only after its db object is confirmed via BucketPort.md5_base64; local-only runs re-resolve video links from the README
- [Phase 04]: 04-18: stage locks compiled with requirements-dev.lock pins as constraint; every image installs hashed locks with --require-hashes (pip-tools 7.6.2 approved, throwaway container only)
- [Phase 04]: 04-15: Guarda offset diagnosis decision no-fix; every live hop keeps #t=, the 04-13 click was a fallback row
- [Phase 04]: 04-20: image digest is the deploy identity; IMAGE_TAG leaves the render contract, revision names are chosen by the pipeline (r<run>-<attempt>, p<build>-<epoch>, manual-<epoch>)
- [Phase 04]: 04-21: python:3.12-slim pinned by digest sha256:5e2bdb1b...fa5b (2026-11-15) in all four FROM lines; Dependabot (docker + 4 pip dirs) opens PRs only, pip PRs need scripts/lock-requirements.sh before merge
- [Phase 04]: 04-22: serving revision read from status.traffic (resolved list); spec.traffic carries no revisionName in latest-revision mode
- [Phase 04]: 04-22: manual replace without SERVING_REVISION pins traffic to the new revision; runbook gives --to-latest and --remove-tags candidate to restore latest-revision mode
- [Phase 04]: 04-24: sync image gets only a one-hour sa-publisher token (GCS_ACCESS_TOKEN_FILE); owner gcloud login mounted only into digest-pinned gcloud minting containers; owner loses bucket objectAdmin in bootstrap (live removal deferred to 04-26)
- [Phase 04]: 04-23: scan-policy fixable (ignore-unfixed true), Trivy v0.76.2, trivy-action pinned to v0.36.0 commit; first deploy needs the zlib1g base-digest bump
- [Phase 04]: 04-25: the five GCP identifiers are repository secrets only (no vars expression); a missing one fails the deploy and Meridian runs by name instead of skipping
- [Phase 04]: 04-25: chat-bot deploy polls up to 30 min (30 s interval) for the Meridian image before the existing error; deploy job timeout 75 min
- [Phase 05]: 05-GAP-DECISION approved changes (all four): Guides search also uses the standalone question with k 4 -> 8 (05-14); case-scope answer-prompt rule (05-14); CR-01, WR-01..03 fixes (05-15, 05-16); golden edits gd-02, sr-02, gd-05 (05-15); then one live gate re-run (05-17)
- [Phase 05]: 05-17: live gate re-run printed GATE: PASS — correctness-with-citation 38/40 = 95.0%, invented 0, empty-context 28/28; Recall@5 handbook 15/15 = 1.00, Guides 11/13 = 0.85 (no D5 hybrid trigger)
- [Phase 05]: 05-GAP-DECISION UAT follow-up: Joshua accepted 05-17 GATE: PASS 38/40 as the Milestone 1 outcome; gd-05 and sr-03 recorded as known compound-fact items; no golden, judge, threshold or bot change, no re-run

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] RESOLVED: how synced data reaches the MCP container (SYNC-07) decided in 01-02 / ADR 0001 (ArtifactStore port); bucket store implemented in Phase 4 (04-04)
- [Phase 1] Per-scene video clips: source is the Guides README (full-video URLs); scene-clip URLs may not exist yet, fall back to full video
- [Phase 1] RESOLVED: no ClickUp token needed. ClickUp is shut down (D-25); the handbook comes from the local gitignored snapshot and the Guides from a local checkout, with no tokens
- [Phase 2] RESOLVED: Bot-to-MCP authentication mechanism defined by D-12 and tested in 02-05 (Google-signed service-account ID token, BOT_SA_EMAILS allowlist). 02-07 verified the user OAuth flow live; a live bot ID-token call was not run (covered by offline tests, revisit with the Phase 3 bot)
- [Phase 4] Live Cloud Run deploy done 2026-11-15 (04-13): europe-west8, WIF keyless CI, both services green; 9 gaps recorded in 04-13-SUMMARY for /gsd-plan-phase 04 --gaps
- [Phase 4] Cost of chat_bot service, Pub/Sub, CI and kind is not covered by research 07; ~0 EUR/month holds for the MCP server only
- [Phase 4] chat_bot cost observation for OPS-01: request-based billing; cold start about 17 s (bot + Meridian) plus about 8 s (mcp-server) on the first message
- [Later] Videos must move to Google Drive before any non-dev user (D15); `LLM_BACKEND` must move to API key before any second user (D1a)
- [Later] Re-check the thread-memory privacy posture (D-11: HMAC key, N turns, 24 h TTL) before any second user, together with the LLM_BACKEND switch (D1a)
- [Later] Open: real team chat channel, Team license budget, CCNL, official handbook owner, which Guides go company-wide, formal data-sovereignty constraint

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 261123-fpj | Restructure internal deep dive and story deck into three parts, with terminology, fact and clear-writing fixes | 2026-11-23 | 6af3b94 | [261123-fpj-restructure-deep-dive-and-story-deck-aft](./quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/) |

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-11-22
Stopped at: Phase 5 complete — all phases complete
Next step: run the verifier (05-VERIFICATION.md), then the Phase 5 transition (marks Phase 5 and EVAL-01..06 complete)
Resume file: .planning/phases/05-evaluation-and-milestone-gate/05-GAP-DECISION.md
