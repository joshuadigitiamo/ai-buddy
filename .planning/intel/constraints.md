# Constraints (synthesized intel)

Source: docs/PLAN.md (SPEC, precedence 0) unless marked "orchestrator/user global config" (not an ingested doc; supplied in the synthesis prompt, listed for roadmapper convenience).

## MCP tool contract (five tools)
- source: docs/PLAN.md (section 3 Phase 1)
- type: api-contract
- content: |
    handbook_get(section?)     -> markdown + url + data revisione
    handbook_search(query)     -> sezioni pertinenti
    guides_search(query)       -> sezioni Guides (FTS5)
    guides_get_section(id)     -> testo sezione + riferimento
    buddy_report_gap(question) -> log domande senza risposta
  Fewer than 10 tools, namespaced names (MCP_SERVERS_GUIDE section 20). Every output includes the source. Resource `handbook://{pagina}` for attaching whole pages.

## MCP transport and statelessness
- source: docs/PLAN.md (D10, section 4 Phase 1 item 1); docs/research/07-costi-hosting-cloud-run.md (DOC, supporting)
- type: protocol
- content: Python SDK `mcp`, streamable-http in modalita' stateless con risposte JSON, no persistent SSE streams (request-based billing keeps an instance billed while a request is open; long SSE streams would exit the free tier at ~15 $/month). Ephemeral container filesystem: no persistent state in the container.

## MCP authentication
- source: docs/PLAN.md (section 3, section 4 Phase 1 item 3, section 7)
- type: protocol
- content: OAuth 2.1 with Google, restricted to the `digitiamo.com` domain (MCP_SERVERS_GUIDE section 17). Read-only, no sensitive data, rate limit. Connector must be reachable from the internet (called by Anthropic servers).

## Google Chat bot event transport
- source: docs/PLAN.md (D13, D1a)
- type: protocol
- content: Events via Pub/Sub in development (no public URL to the local machine); via HTTP with Google JWT verification on Cloud Run in production. Dev guards: app visibility limited to Joshua, `ALLOWED_USERS` allowlist. Google Chat expects a reply within ~30 s (docs/research/06 section 7.1, DOC) else asynchronous reply.

## Bot to MCP server interface
- source: docs/PLAN.md (D11)
- type: api-contract
- content: The bot calls the MCP server over HTTP as an MCP client. No duplicated retrieval logic in the bot.

## LLM backend selection
- source: docs/PLAN.md (D1a, D6, D9, section 3.1)
- type: api-contract
- content: Single model-client module, switched by configuration (`LLM_BACKEND`). Milestone 1: Meridian + Joshua's Max allowed ONLY for personal dev, single user, with guards. Before any other user: API key (Console or Vertex EU). Shared/production bot uses commercial credentials with EU residency (Vertex AI, Bedrock EU fallback). Open-model path (OpenAI-compatible `base_url`) requires orchestrator citation check. Meridian exposes Anthropic Messages API on 127.0.0.1:3456 (docs/research/02, DOC).

## Gap log schema
- source: docs/PLAN.md (section 3, D10, section 7)
- type: schema
- content: Firestore collection. Fields: question, timestamp, "nessuna fonte trovata" marker. NO user id (Statuto dei Lavoratori art. 4; Garante 2024). Short retention, aggregate analytics only, DPO opinion pending.

## ClickUp sync metadata and redaction
- source: docs/PLAN.md (section 3); mechanics from docs/research/01-handbook-inventory.md section 9 (DOC)
- type: schema
- content: Incremental sync keyed on `date_edited` plus content hash (NOT `date_updated`, which can change without content change). ClickUp doc ID from environment variable. Redaction filter before indexing (Wi-Fi page excluded; page id [ClickUp doc ID removed] per research 01 contains plaintext credentials, values intentionally not reproduced anywhere in intel).
- update 2026-11-14: ClickUp parts superseded by Phase 1 D-25/D-26 (ClickUp is being shut down): the handbook is read from a local gitignored snapshot via `HANDBOOK_DIR`, no ClickUp API, no token; incremental key is the front-matter revision date + content hash; the Wi-Fi denylist is keyed by page file. Redaction rule unchanged.

## Retrieval strategy
- source: docs/PLAN.md (D4, D5, section 8)
- type: nfr
- content: Handbook (~8k tokens) fully in context, no vector DB. Guides (~15 files, ~100 KB each) via section index + SQLite FTS5/BM25. Vector DB/embeddings out of scope until Recall@5 < 0,8.

## Quality gate and KPIs
- source: docs/PLAN.md (section 4 Phase 1 exit, section 6)
- type: nfr
- content: Correct-with-citation >= 90% at Phase 1 gate (>= 95% at regime); invented policies = 0; pages with review < 6 months >= 90%; adoption >= 70% of employees/month; thumbs-up >= 80% (Phase 2); new hires "so a chi chiedere" >= 4/5 at day 30; unanswered questions/week trending down.

## Cost and hosting envelope
- source: docs/PLAN.md (D6, D7); docs/research/07-costi-hosting-cloud-run.md (DOC)
- type: nfr
- content: Cloud Run europe-west8 request-based, scale-to-zero, ~0 EUR/month for the MCP server at <15 people (~20k requests/month ~6% of free tier). Claude API EU ~35-70 $/month for 15 users x 10 questions/day. Billing account required (update 2026-11-14: satisfied — the existing GCP project `ai-buddy-dev`, ID in docs/internal/gcp-project.md, gitignored, has billing linked; region europe-west8 still "da confermare"). Cloud Storage not usable for free gap log outside three US regions. Note: research 07 costs the MCP server only (see INFO in conflicts report).

## Privacy, compliance and security
- source: docs/PLAN.md (section 1, section 7)
- type: nfr
- content: EU data residency (GDPR); no per-person logging (Statuto art. 4); AI disclosure "stai parlando con un'AI" (AI Act art. 50) and worker notice (Phase 2); read-only access; no credentials in index; Workload Identity Federation instead of keys; all sources visible to all employees (no per-section ACL).

## Out of scope (for now)
- source: docs/PLAN.md (section 8)
- type: nfr
- content: Vector DB/embeddings; multi-agent/Deep Agents/A2A; per-section ACL; write actions on ClickUp or Factorial.

## Everything runs in Docker; test runner convention
- source: docs/PLAN.md (section 1); orchestrator/user global config
- type: nfr
- content: Every running component is a Docker image; local via `docker compose` with separate services; deploys use the same image; never Python on the host. Each Python project ships `run-unit-tests.sh` at repo root with modes `--all`, `--single <file> <test_name> <dir>`, `--single-file <file> <dir>`; builds the test image first, then `docker run --rm` with `--env-file .env` and cwd mount; `set -euo pipefail` and a `log()` helper.

## Python tooling
- source: orchestrator/user global config (not an ingested doc)
- type: nfr
- content: Python only (no Node/Go/Rust unless asked); pip with requirements.txt / requirements-dev.txt; ruff for lint and format; pytest with `-v --tb=short`, coverage via `pytest --cov`; type hints on public functions, mypy --strict where feasible. Note: Meridian itself is TypeScript/Node (docs/research/02, DOC); if run, it runs in its own container, outside the Python-only project code.

## Repository layout
- source: docs/PLAN.md (D11)
- type: nfr
- content: `packages/buddy_core`, `services/mcp_server`, `services/chat_bot`, `jobs/sync`, `deploy/`; one Docker image per service.

## Guides best-practice mapping
- source: docs/PLAN.md (D16)
- type: nfr
- content: Each phase plan must cite the applied Guides sections (MCP_SERVERS_GUIDE, RAG_CHATBOT_GUIDE, LANGCHAIN/LANGGRAPH_GUIDE, MLFLOW_GENAI_GUIDE, KUBERNETES_GUIDE, DESIGN_PATTERNS_GUIDE) and justify exceptions. Guides live at `~/Desktop/WORK/Guides`, outside this repo and outside the ingest set (not verified).

## Plan-level dependencies and open questions (unresolved in source)
- source: docs/PLAN.md (sections 5 and 10, section 3)
- type: nfr
- content: Dependencies: license decision Max -> Team (Direzione); ClickUp read-only API token (Admin ClickUp); GCP project + billing (Admin Google); page owners (HR, to be confirmed); consent to make Guides company-wide (Joshua); legal/DPO opinion. Open questions: real team chat (Google Chat vs ClickUp Chat; Milestone 1 proceeds with Google Chat per D13); Team budget; applicable CCNL; official handbook owner; which Guides become company-wide; formal data-sovereignty constraint (decides option A vs B/C in PLAN 3.1); how sync data reaches the container (image rebuild vs bucket).
- update 2026-11-14: ClickUp read-only API token no longer needed (Phase 1 D-25, ClickUp is being shut down). GCP project + billing done: the existing GCP project `ai-buddy-dev` (ID in docs/internal/gcp-project.md, gitignored), under the digitiamo.com organization, billing linked; org policies may apply to deploys. Sync-to-container decided in Phase 4 (04-CONTEXT D-06: private GCS bucket read at cold start).
