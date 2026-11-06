# Requirements: AI Buddy Digitiamo

**Defined:** 2026-11-03
**Core Value:** An employee gets an answer only from official sources with the source cited, or an honest "non lo so, chiedi a ..." with the gap logged. Never an invented policy.

Source: docs/PLAN.md (SPEC, sections 1-4 and 2.1) via `.planning/intel/requirements.md`. No PRD exists; IDs are derived from explicit PLAN.md statements. Milestone 1 scope: personal dev use only (Joshua), handbook = the local Markdown snapshot kept in a gitignored folder of this repo (D-25: ClickUp is being shut down).

## v1 Requirements (Milestone 1)

### Foundation

- [x] **FND-01**: Repo follows the D11 layout (`packages/buddy_core`, `services/mcp_server`, `services/chat_bot`, `jobs/sync`, `deploy/k8s`, `deploy/cloudrun`, `.github/workflows`, `tests/`) on Python 3.12 with pip `requirements.txt` / `requirements-dev.txt`, and ruff, pytest (`-v --tb=short`, `--cov`) and `mypy --strict` (where feasible) configured; public functions carry type hints.
- [x] **FND-02**: `run-unit-tests.sh` at repo root supports `--all`, `--single <file> <test_name> <dir>` and `--single-file <file> <dir>`; it builds the test image first, then runs `docker run --rm` with `--env-file .env` (fallback `.env.example`) and the cwd mounted; uses `set -euo pipefail` and a `log()` helper. No Python runs on the host.
- [x] **GUIDE-01**: Every phase plan cites the Guides sections it applies (MCP_SERVERS_GUIDE, RAG_CHATBOT_GUIDE, LANGCHAIN/LANGGRAPH_GUIDE, MLFLOW_GENAI_GUIDE, KUBERNETES_GUIDE, DESIGN_PATTERNS_GUIDE as relevant) and justifies any exception (D16). Owned by Phase 1 (convention set there), enforced at every phase plan check.

### Content Sync

- [x] **SYNC-01**: Sync job reads the handbook from a local folder of Markdown pages whose path comes from an environment variable (`HANDBOOK_DIR`, mounted read-only; Milestone 1 content: the 23-page snapshot in the gitignored `docs/research/handbook-raw/`). One file per page with YAML front matter (`title`, `last_updated`, optional `date_created`). The folder is never committed (public repo). No external API and no token are used (D-25, D-26).
- [x] **SYNC-02**: Sync is incremental: a page is re-processed only when its revision date (front matter `last_updated`, or its `date_edited` part for pages exported with both dates) or the hash of its redacted content changed; a change in file modification time alone does not trigger re-indexing.
- [x] **SYNC-03**: A redaction filter runs before indexing: the Wi-Fi page is excluded and no credential-like content reaches any index artifact (covered by a fixture test with synthetic secrets).
- [x] **SYNC-04**: Guides repo content (git pull of the repo path/URL from env) is split by heading into a SQLite FTS5 index; each chunk keeps file, heading and line reference (`GUIDES_INDEX` section -> line mapping, D5).
- [x] **SYNC-05**: The handbook is stored as an in-memory-loadable snapshot of full pages; each page records its citation URI `handbook://<page-id>` (page id = file name without `.md`, the URI the Phase 2 resource `handbook://{pagina}` serves), its title and its revision date.
- [x] **SYNC-06**: Video mapping links each Guides section to its scene clip URL when one exists, otherwise to the full-video URL taken from the Guides README; sections without a video map to none.
- [x] **SYNC-07**: The sync output is a versioned index artifact (handbook snapshot + Guides SQLite + video map) with a documented format, and the handoff decision is recorded: an `ArtifactStore` interface with a local-directory implementation in Phase 1, with bucket read vs image rebuild (baked) chosen together with the hosting platform in Phase 4 (D-12).

### MCP Server and Skill

- [x] **MCP-01**: MCP server (Python, FastMCP / SDK `mcp`) serves streamable-http in stateless mode with JSON responses and no persistent SSE streams; it keeps no state on the container filesystem.
- [x] **MCP-02**: Server exposes exactly five namespaced tools (fewer than 10): `handbook_get(section?)`, `handbook_search(query)`, `guides_search(query)`, `guides_get_section(id)`, `buddy_report_gap(question)`, with the contract from PLAN section 3.
- [x] **MCP-03**: Every tool output includes the source URL and revision date, plus `video_url` when the Guides section has a mapped video.
- [x] **MCP-04**: A search that finds nothing returns an explicit "no results" result (never filler text), so callers can refuse.
- [ ] **MCP-05**: `buddy_report_gap(question)` writes a Firestore document with question, timestamp and a "nessuna fonte trovata" marker, and stores no user id (verified against the Firestore emulator).
- [x] **MCP-06**: Resource `handbook://{pagina}` lets a client attach a whole handbook page.
- [ ] **MCP-07**: Server auth is OAuth 2.1 with Google restricted to `@digitiamo.com`, read-only, with rate limiting; auth can be switched off for local/kind development only. The bot-to-server authentication mechanism is defined in the phase plan.
- [x] **MCP-08**: Skill `digitiamo-buddy` (SKILL.md) states when to use the tools, the answer format (answer, source, owner, revision date), the escalation topic list with referral contacts, and includes a one-page install guide for colleagues.

### Google Chat Bot

- [ ] **BOT-01**: In development the bot receives Google Chat events (DM and @mention) through a Pub/Sub subscription and replies in chat.
- [ ] **BOT-02**: The same bot exposes an HTTP endpoint that verifies the Google JWT on every request (reject missing or invalid tokens) for Cloud Run; event intake sits behind one interface so the workflow is identical for both transports.
- [ ] **BOT-03**: An allowlist guard (`ALLOWED_USERS`) rejects any sender not on the list before any MCP or LLM call; the Chat app is visible to Joshua only (documented manual setting).
- [ ] **BOT-04**: Answers come from a LangGraph 2-step RAG workflow (query reformulation, retrieval via the MCP server's tools over HTTP as an MCP client, answer with citations, confidence gate); the bot holds no duplicate retrieval logic.
- [ ] **BOT-05**: Every citation in an answer must point to text the MCP tools returned in that run; an answer with an unsupported citation, or below the confidence gate, is replaced by "non lo so, chiedi a ..." and the question is reported via `buddy_report_gap`.
- [ ] **BOT-06**: Sensitive topics (illness, disputes, pay, health, conflicts) get at most the general written rule plus referral to a person; no substantive answer on an individual situation.
- [ ] **BOT-07**: One LLM client module, selected by `LLM_BACKEND` (`meridian | api`; Vertex configuration present but not enabled); Meridian sits behind the Anthropic Messages implementation via `base_url`; switching backend changes configuration only.
- [ ] **BOT-08**: The bot refuses to start with `LLM_BACKEND=meridian` when `ALLOWED_USERS` holds more than one user (enforces D1a single-user guard).
- [ ] **BOT-09**: Answers sourced from a Guides section with a mapped video render as a card with the source link, a thumbnail and a "Guarda" button opening the scene clip (or full video); handbook answers show the source link.
- [ ] **BOT-10**: The bot answers within Google Chat's event window (~30 s) or sends the answer as an asynchronous follow-up message.
- [ ] **BOT-11**: Logs and traces do not persist user identifiers alongside question text (Statuto dei Lavoratori art. 4 posture).

### Infrastructure and CI/CD

- [ ] **INFRA-01**: One Dockerfile per service (`mcp_server`, `chat_bot`, `jobs/sync`) on Python 3.12; the same image is used in compose, kind and Cloud Run.
- [ ] **INFRA-02**: `docker compose` starts all services plus Firestore and Pub/Sub emulators with separate services, and a chat event completes a round trip locally.
- [ ] **INFRA-03**: kind manifests (Kustomize base + overlays) deploy the services to a local kind cluster, and pass manifest validation (KUBERNETES_GUIDE).
- [ ] **INFRA-04**: Cloud Run service/job YAMLs for `mcp_server`, `chat_bot` and the sync job (europe-west8, request-based, scale-to-zero, stateless), with a nightly Cloud Scheduler trigger for sync and the `ArtifactStore` implementation chosen in Phase 4 per D-12 (bucket read or baked image) wired in.
- [ ] **INFRA-05**: GitHub Actions workflows are path-filtered per service: build, push to Artifact Registry, deploy, authenticating with Workload Identity Federation (no key files or long-lived credentials).
- [ ] **INFRA-06**: CI runs `run-unit-tests.sh --all` (ruff, mypy, pytest with coverage) as a required check before any image push.

### Evaluation and Gate

- [ ] **EVAL-01**: Golden set of 30-50 Q&A pairs drafted by Claude from the test doc `xkwgt-39975` and the Guides, with expected answer and expected source page, covering answerable, no-answer and sensitive-escalation cases; each item records Joshua's review status; no item points at the official `xkwgt-22915`.
- [ ] **EVAL-02**: One command measures Recall@5 of retrieval (handbook search and Guides search) over the golden set and reports it; a Guides Recall@5 < 0.8 is flagged as the D5 hybrid-upgrade trigger.
- [ ] **EVAL-03**: One command scores the golden set end to end against Claude (via the bot workflow and the configured `LLM_BACKEND`) for correctness and correct citation, and counts invented policies (an answer asserting a rule absent from its cited source).
- [ ] **EVAL-04**: "Empty context" test: with an index that holds no matching content, every answer is a refusal and a gap is logged; the test fails if any answer is produced.
- [ ] **EVAL-05**: MLflow tracing (self-hosted, containerized) records eval runs and bot workflow steps (retrieval, generation, gate) so each judged answer can be inspected (MLFLOW_GENAI_GUIDE).
- [ ] **EVAL-06**: A gate command reports PASS/FAIL against: correctness-with-citation >= 90%, invented policies = 0, empty-context test passes.

## v2 Requirements

Deferred beyond Milestone 1. Tracked, not in the current roadmap.

### Rollout

- **ROLL-01**: Switch `LLM_BACKEND` to API key (Console or Vertex EU) and enable Vertex before any second user; open the allowlist and Chat app visibility.
- **ROLL-02**: Move Guides videos to Google Drive (domain-shared) so non-developer users can play them (D15).
- **ROLL-03**: AI disclosure ("stai parlando con un'AI", AI Act art. 50) and worker notice (L. 132/2025) before a shared rollout.
- **ROLL-04**: Feedback thumbs up/down and "segnala errore"; pilot with 3-4 colleagues for 2 weeks; adoption and thumbs-up KPIs.
- **ROLL-05**: Confirm the real team chat (Google Chat vs ClickUp Chat) and the europe-west8 region.

### Content and quality

- **CONT-01**: Phase 0 official handbook cleanup (HR): remove plaintext Wi-Fi, single legal address, single leave process, L.O.V.E. text, Team page, per-page metadata (owner, revision date, validity), new P0 pages; then point the sync at the official doc.
- **CONT-02**: HR-collected golden set (30-50 real questions) replaces the drafted set; target >= 95% at regime.
- **CONT-03**: Monthly gap-log review and alerts on pages with review older than 6 months (governance).

### Capability

- **RET-01**: Hybrid dense + BM25 retrieval with RRF for Guides when Recall@5 < 0.8 (D5).
- **LLM-01**: Open-model A/B (Qwen3.8-27B via EU API or vLLM) decided by golden set, with orchestrator citation check (D9).
- **NUDGE-01**: Proactive nudges at day 1/7/30/60/90 and an interrogable 30/60/90 checklist (Phase 2b).
- **OPS-01**: Monitor `container/billable_instance_time` and cost the chat_bot service, Pub/Sub, CI and kind during the pilot.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Official handbook `xkwgt-22915` as sync target | Being rewritten; fix before indexing (D8, D14) |
| Meridian for any user other than Joshua | Anthropic terms (D1); D1a covers personal dev only |
| Vector DB / embeddings | Only if Guides Recall@5 < 0.8 (D5) |
| Multi-agent, Deep Agents, A2A | 2-step RAG is enough for Q&A |
| Per-section ACL | All sources visible to all employees |
| Write actions on ClickUp or Factorial | Only after a stable later phase |
| Self-hosted open-weight model | Not justified at ~3,300 questions/month; decided by golden set later |
| Non-Python project code, Python on the host | User standard; everything runs in Docker |

## Traceability

Each requirement maps to exactly one phase. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| GUIDE-01 | Phase 1 | Complete |
| SYNC-01 | Phase 1 | Complete |
| SYNC-02 | Phase 1 | Complete |
| SYNC-03 | Phase 1 | Complete |
| SYNC-04 | Phase 1 | Complete |
| SYNC-05 | Phase 1 | Complete |
| SYNC-06 | Phase 1 | Complete |
| SYNC-07 | Phase 1 | Complete |
| MCP-01 | Phase 2 | Complete |
| MCP-02 | Phase 2 | Complete |
| MCP-03 | Phase 2 | Complete |
| MCP-04 | Phase 2 | Complete |
| MCP-05 | Phase 2 | Pending |
| MCP-06 | Phase 2 | Complete |
| MCP-07 | Phase 2 | Pending |
| MCP-08 | Phase 2 | Complete |
| BOT-01 | Phase 3 | Pending |
| BOT-02 | Phase 3 | Pending |
| BOT-03 | Phase 3 | Pending |
| BOT-04 | Phase 3 | Pending |
| BOT-05 | Phase 3 | Pending |
| BOT-06 | Phase 3 | Pending |
| BOT-07 | Phase 3 | Pending |
| BOT-08 | Phase 3 | Pending |
| BOT-09 | Phase 3 | Pending |
| BOT-10 | Phase 3 | Pending |
| BOT-11 | Phase 3 | Pending |
| INFRA-01 | Phase 4 | Pending |
| INFRA-02 | Phase 4 | Pending |
| INFRA-03 | Phase 4 | Pending |
| INFRA-04 | Phase 4 | Pending |
| INFRA-05 | Phase 4 | Pending |
| INFRA-06 | Phase 4 | Pending |
| EVAL-01 | Phase 5 | Pending |
| EVAL-02 | Phase 5 | Pending |
| EVAL-03 | Phase 5 | Pending |
| EVAL-04 | Phase 5 | Pending |
| EVAL-05 | Phase 5 | Pending |
| EVAL-06 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 41 total
- Mapped to phases: 41
- Unmapped: 0

Note on GUIDE-01: it is a project-wide constraint (D16). It is mapped to Phase 1, where the convention is established, and re-checked in every later phase through the "Guides applied" line of each phase and the plan check.

---
*Requirements defined: 2026-11-03*
*Last updated: 2026-11-03 after the D-25..D-27 scope change (SYNC-01, SYNC-02, SYNC-05 reworded)*
