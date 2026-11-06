# Roadmap: AI Buddy Digitiamo

## Overview

Milestone 1 builds the full AI Buddy chain for Joshua's personal development use, against the local handbook snapshot (D-25) and the Guides repo. It starts with the content the assistant may speak from (sync, redaction, index), puts it behind five cited MCP tools plus the `digitiamo-buddy` Skill, adds the Google Chat bot that reasons over those tools with a 2-step RAG workflow, packages everything for kind and Cloud Run with CI/CD, and closes with an eval phase that decides the milestone gate: >= 90% correct answers with citation on the golden set, 0 invented policies, and the empty-context test refusing. Every phase applies the Guides best practices (D16) and its plan cites the sections used.

Execution environment for every phase: Python 3.12, all code and tests run in Docker, no Python on the host.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Content Sync** - Repo foundation plus the local handbook snapshot and Guides synced into a redacted, incremental, citable index with video mapping (completed 2026-11-03)
- [ ] **Phase 2: MCP Server and Skill** - Five cited MCP tools over stateless HTTP with Firestore gap log, Google-domain auth, and the `digitiamo-buddy` Skill
- [ ] **Phase 3: Google Chat Bot** - Guarded Google Chat bot with LangGraph 2-step RAG, citation and confidence gates, pluggable LLM client, and video cards
- [ ] **Phase 4: Infrastructure and CI/CD** - Service images, docker compose, kind manifests, Cloud Run YAMLs and path-filtered GitHub Actions with Workload Identity Federation
- [ ] **Phase 5: Evaluation and Milestone Gate** - Golden set, Recall@5, correctness and citation scoring, MLflow tracing, empty-context test and the gate verdict

## Phase Details

### Phase 1: Content Sync
**Goal**: The developer can build a clean, citable knowledge index from the local handbook snapshot and the Guides repo, and run all tests in Docker from day one.
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, GUIDE-01, SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06, SYNC-07
**Guides applied (D16)**: RAG_CHATBOT_GUIDE (chunking by heading, retrieval basics), DESIGN_PATTERNS_GUIDE (source adapters, shared `buddy_core`); plan lists exact sections and exceptions.
**Success Criteria** (what must be TRUE):
  1. `./run-unit-tests.sh --all` builds the test image and runs the suite in Docker, `--single <file> <test_name> <dir>` and `--single-file <file> <dir>` run only the targeted tests, and ruff, mypy and pytest coverage all execute without Python installed on the host.
  2. Running the sync job on the local handbook folder (path from the environment, mounted read-only, no token, no network) produces a handbook snapshot where every page has its `handbook://` citation URI, title and revision date, and the Wi-Fi page and any credential-like text are absent from every produced artifact.
  3. Re-running sync with no handbook edits processes 0 pages; editing one page re-processes only that page; a change of file modification time alone (no content or revision-date change) is not re-indexed.
  4. A keyword query against the Guides index returns the matching heading chunk with its file and line reference, together with the scene-clip URL (or the full-video URL from the Guides README) when that section has a video, and nothing when it does not.
  5. The index artifact has a documented, versioned format, and a recorded decision states how it reaches the MCP container (image rebuild vs bucket read).
**Plans**: 11/11 plans complete

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Foundation: pinned deps (legitimacy gate), Dockerfile, run-unit-tests.sh, D11 layout, GUIDE-01 convention

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — index.db contract in buddy_core: schema, writer, reader/search, ArtifactStore, format doc, handoff ADR
- [x] 01-03-PLAN.md — SyncSettings and the shared redaction filter (D-14..D-18), local corpus check

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-04-PLAN.md — ClickUp v3 source, denylist, incremental handbook sync (SYNC-01/02/03/05)
- [x] 01-05-PLAN.md — Guides git source, heading chunker, GUIDES_INDEX.md generation and drift check (SYNC-04)
- [x] 01-06-PLAN.md — Video map: README URLs, sections.yaml, durations offsets, fallbacks, contract doc (SYNC-06)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 01-07-PLAN.md — Sync CLI and pipeline end to end on fixtures (run, list-pages, guides-index, search)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 01-08-PLAN.md — Real Guides maps + GUIDES_INDEX.md (Joshua commits); its live ClickUp run was removed by D-25 and moved to 01-11
- [x] 01-09-PLAN.md — Gap: local handbook folder replaces ClickUp in the sync (handbook:// citation, file denylist, no token)

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 01-10-PLAN.md — Gap: delete the ClickUp adapter and httpx; README, index format, SYNC-01/02/05 and Phase 1 criteria reworded

**Wave 7** *(blocked on Wave 6 completion)*
- [x] 01-11-PLAN.md — Gap: live run on read-only local handbook + Guides mounts, live-artifact checks (supersedes 01-08 Task 3)

### Phase 2: MCP Server and Skill
**Goal**: Any MCP client can ask the synced handbook and Guides for answers through five cited tools over stateless HTTP, and Claude knows how to use them via the Skill.
**Depends on**: Phase 1
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, MCP-06, MCP-07, MCP-08
**Guides applied (D16)**: MCP_SERVERS_GUIDE (tool surface, namespacing, transport, authorization), RAG_CHATBOT_GUIDE (source-carrying retrieval output), DESIGN_PATTERNS_GUIDE; plan lists exact sections and exceptions.
**Success Criteria** (what must be TRUE):
  1. An MCP client connecting over streamable-http (stateless, JSON responses, no held-open stream) lists exactly five tools (`handbook_get`, `handbook_search`, `guides_search`, `guides_get_section`, `buddy_report_gap`) and the `handbook://{pagina}` resource.
  2. Every tool result on the test handbook and the Guides carries a source URL and revision date, plus `video_url` for Guides sections with a mapped video; a test fails if any output lacks a source.
  3. A query with no matching content returns an explicit "no results" result, and `buddy_report_gap` writes a Firestore document with question, timestamp and the "nessuna fonte trovata" marker and no user id (checked on the Firestore emulator).
  4. With auth enabled, a request without a valid Google identity from `@digitiamo.com` is rejected, tools are read-only, and requests beyond the rate limit are refused.
  5. The `digitiamo-buddy` Skill states when to use each tool, the answer format (answer, source, owner, revision date), the escalation topics with referral contacts, and ships with a one-page install guide.
**Plans**: 6/7 plans executed

Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Legitimacy gate for the new pins; tracer: guides_search over stateless JSON HTTP; full D-06 output contract; Guides slice and cold-start failures

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — Handbook slice: Italian stemmed in-memory FTS search, handbook_get (TOC/page), handbook://{pagina} resource
- [x] 02-03-PLAN.md — GapLog port + Firestore adapter, Fernet-encrypted Firestore OAuth store, `--emulator` test mode

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-04-PLAN.md — buddy_report_gap tool; five-tool surface, read-only, source-field and no-results contract tests

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 02-05-PLAN.md — Auth: Google OAuth proxy restricted to @digitiamo.com, bot service-account ID tokens (D-12), AUTH_MODE/K_SERVICE guard, per-identity rate limit
- [x] 02-06-PLAN.md — digitiamo-buddy Skill (escalation list approved by Joshua) and one-page install guide

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 02-07-PLAN.md — `python -m buddy_mcp` composition root, real-process emulator test, runtime image stage, env contract + README, live Google login checkpoint (may defer to Phase 4)

### Phase 3: Google Chat Bot
**Goal**: Joshua can ask the bot a question in Google Chat and get a cited, grounded answer (or an honest refusal or escalation) with a video card when one exists.
**Depends on**: Phase 2
**Requirements**: BOT-01, BOT-02, BOT-03, BOT-04, BOT-05, BOT-06, BOT-07, BOT-08, BOT-09, BOT-10, BOT-11
**Guides applied (D16)**: LANGCHAIN_GUIDE and LANGGRAPH_GUIDE (2-step RAG workflow, citations seen by the model), MCP_SERVERS_GUIDE (client side), RAG_CHATBOT_GUIDE (confidence gate, refusal), DESIGN_PATTERNS_GUIDE (pluggable LLM client, transport interface); plan lists exact sections and exceptions.
**Success Criteria** (what must be TRUE):
  1. A DM or @mention from an allowlisted user, delivered through Pub/Sub in development, gets an answer in chat within the ~30 s window (or an asynchronous follow-up); the HTTP endpoint accepts requests with a valid Google JWT and rejects missing or invalid ones.
  2. A sender not on `ALLOWED_USERS` gets no answer content and triggers no MCP or LLM call; the bot refuses to start with `LLM_BACKEND=meridian` when the allowlist holds more than one user; switching `LLM_BACKEND` between `meridian` and `api` needs configuration changes only.
  3. Answerable questions return text whose every citation maps to content the MCP tools returned in that run; a question with no source, an unsupported citation, or low confidence returns "non lo so, chiedi a ..." and logs a gap, with no user id stored next to the question.
  4. Questions on sensitive topics (illness, disputes, pay, health, conflicts) receive at most the general written rule plus a referral to a person.
  5. An answer sourced from a Guides section with a mapped video shows a card with the source link, a thumbnail and a "Guarda" button that opens the scene clip (or the full video); handbook answers show the source link.
**Plans**: TBD

### Phase 4: Infrastructure and CI/CD
**Goal**: The whole system runs from per-service Docker images locally (compose), on kind, and as Cloud Run definitions, built and deployed by path-filtered CI without stored keys.
**Depends on**: Phase 3
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06
**Guides applied (D16)**: KUBERNETES_GUIDE (manifests, Kustomize overlays, probes, resources), MCP_SERVERS_GUIDE (deployment, stateless transport), DESIGN_PATTERNS_GUIDE; plan lists exact sections and exceptions.
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts `mcp_server`, `chat_bot` and the sync job from per-service images, with Firestore and Pub/Sub emulators, and a Pub/Sub chat event completes a round trip to an answer.
  2. Applying the Kustomize dev overlay to a local kind cluster brings the services up, and a health check plus one MCP tool call succeed in-cluster; base and overlays pass manifest validation.
  3. Cloud Run YAMLs for `mcp_server`, `chat_bot` and the sync job target europe-west8 with scale-to-zero and request-based billing, a nightly Cloud Scheduler trigger exists for sync, and the SYNC-07 handoff mechanism is wired in.
  4. A change under `services/mcp_server` triggers only that service's workflow, which runs `run-unit-tests.sh --all` (ruff, mypy, pytest with coverage) and blocks the image push on failure; on success it pushes to Artifact Registry and deploys, authenticating through Workload Identity Federation with no key file in the repo or secrets.
**Plans**: TBD
**Note**: Live deploy needs a GCP project with an active billing account (Admin Google). Without it, criteria 3 and 4 are verified statically (YAML schema validation, workflow lint, dry runs) and the live deploy check is recorded as pending.

### Phase 5: Evaluation and Milestone Gate
**Goal**: The developer can run one command and know whether Milestone 1 passes its gate, with every judged answer inspectable.
**Depends on**: Phase 3, Phase 4
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
**Guides applied (D16)**: RAG_CHATBOT_GUIDE (evaluation, Recall@k), MLFLOW_GENAI_GUIDE (tracing, scorers, LLM judges), LANGGRAPH_GUIDE (tracing the workflow), DESIGN_PATTERNS_GUIDE; plan lists exact sections and exceptions.
**Success Criteria** (what must be TRUE):
  1. A golden set of 30-50 Q&A pairs exists in the repo, drafted from the test doc `xkwgt-39975` and the Guides, with expected answer and expected source per item, covering answerable, no-answer and sensitive-escalation cases, each item showing Joshua's review status, and none pointing at the official handbook.
  2. One command prints Recall@5 for handbook search and Guides search over the golden set, and flags Guides Recall@5 < 0.8 as the hybrid-upgrade trigger.
  3. One command runs the golden set through the bot workflow with the configured `LLM_BACKEND` and prints the correctness-with-citation percentage and the count of invented policies; each judged answer has an MLflow trace (retrieval, generation, gate) viewable in a containerized MLflow UI.
  4. The empty-context test passes: with an index holding no matching content, every question gets a refusal and a logged gap, and the test fails if any answer is produced.
  5. The gate command prints PASS only when correctness-with-citation is >= 90%, invented policies are 0 and the empty-context test passes; otherwise it prints FAIL with the failing metric.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Content Sync | 11/11 | Complete    | 2026-11-03 |
| 2. MCP Server and Skill | 6/7 | In Progress | - |
| 3. Google Chat Bot | 0/0 | Not started | - |
| 4. Infrastructure and CI/CD | 0/0 | Not started | - |
| 5. Evaluation and Milestone Gate | 0/0 | Not started | - |
