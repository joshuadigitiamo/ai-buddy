# AI Buddy Digitiamo

## What This Is

AI Buddy Digitiamo is a conversational assistant that answers Digitiamo employees' questions about company processes, tools and culture, in Italian, using only official sources: the ClickUp Handbook and the Guides repo. Every answer cites its source page (with revision date, and a video clip when the Guides have one). When no source exists it says so and logs the gap; sensitive topics always go to a person.

Milestone 1 delivers the full chain (content sync, MCP server, Google Chat bot, infra, eval) for **personal development use by Joshua only**, against a separate ClickUp test handbook. No other employee uses it in this milestone.

## Core Value

An employee gets an answer only from official sources with the source cited, or an honest "non lo so, chiedi a ..." with the gap logged. Never an invented policy.

## Milestone 1 Gate (success metric)

Milestone 1 is done when the eval phase reports all three:

- >= 90% correct answers with correct citation on the golden set
- 0 invented policies
- the "empty context" test refuses (no answer produced when the index holds no matching content)

## Requirements

### Validated

- ✓ MCP server: five cited tools over stateless HTTP, Firestore gap log, Google-domain OAuth, Skill `digitiamo-buddy` — Phase 2 (UAT 24/25, connector check deferred to Phase 4)

### Active

Full list with IDs in `.planning/REQUIREMENTS.md`. Summary by area:

- [ ] Foundation: monorepo skeleton (D11), Python 3.12 tooling, Dockerized test runner `run-unit-tests.sh`, Guides best practices applied per phase (D16)
- [ ] Content sync: ClickUp test handbook ([ClickUp doc ID removed], id from env) and Guides repo into `buddy_core` index; redaction filter; incremental sync on `date_edited` + content hash; section -> video mapping
- [ ] Google Chat bot: Pub/Sub events in dev, HTTP + Google JWT on Cloud Run, LangGraph 2-step RAG with citations and confidence gate, pluggable LLM client (`meridian | api`, Vertex configured not enabled), allowlist guard, cards with source link and "Guarda" video button
- [ ] Infra: Dockerfile per service, docker compose, kind manifests (Kustomize), Cloud Run YAMLs (europe-west8), GitHub Actions path-filtered build/test/push/deploy with Workload Identity Federation
- [ ] Eval: golden set (30-50, drafted by Claude, reviewed by Joshua), Recall@5, correctness + citation scoring, MLflow tracing, empty-context refusal test, gate verdict

### Out of Scope

- Phase 0 official handbook cleanup (HR content work, [ClickUp doc ID removed]) — outside Milestone 1 code; the test doc (D14) is used instead; prerequisite before the sync targets the official doc (D8)
- Multi-user rollout, pilot with colleagues, adoption KPIs — Milestone 1 is personal dev use only (D1a)
- Vector DB / embeddings — only if Guides Recall@5 < 0.8 (D5)
- Enabling the Vertex AI production LLM switch — config is prepared, not turned on
- Proactive nudges and 30/60/90 checklist (Phase 2b) — post-Milestone 1
- Open-weight / self-hosted model path (PLAN 3.1 options B/C) — decided later by golden-set A/B
- Multi-agent, Deep Agents, A2A — Q&A needs a 2-step RAG workflow, not an agent
- Per-section ACL — all sources visible to all employees
- Write actions on ClickUp or Factorial — only after a stable later phase
- Thumbs up/down feedback, AI-disclosure notice, worker notice — required before a shared rollout, not for single-user dev
- Python on the host machine, non-Python project code — everything runs in Docker (Meridian, being Node, runs in its own container if used)

## Context

- **Sources:** ClickUp Handbook (official doc [ClickUp doc ID removed], 23 pages, ~4,000 words, ~8k tokens, Italian) is being rewritten by HR and is not touched. Milestone 1 uses the private test copy "AI Buddy - Test Handbook" ([ClickUp doc ID removed], space Wiki), copied from the raw snapshot with the Wi-Fi page redacted. Guides repo at `~/Desktop/WORK/Guides` (~15 technical guides, markdown, plus a video pipeline; videos live as release assets of a private GitHub repo).
- **Retrieval:** handbook fits in one context (no vector DB, D4); Guides use heading-chunked SQLite FTS5/BM25 (D5).
- **Architecture:** `buddy_core` (shared index + models) feeds `mcp_server` (retrieval layer, 5 tools) and `chat_bot` (LangGraph 2-step RAG, calls the MCP server over HTTP as an MCP client, D11). `jobs/sync` builds the index. Local dev on kind; prod on Cloud Run europe-west8.
- **Sensitive content:** the Wi-Fi page of the handbook holds plaintext credentials; redaction excludes it from the index. No credential value is copied into any planning artifact.
- **Privacy posture:** gap log has no user id (Statuto dei Lavoratori art. 4); EU data residency (GDPR); no per-person logging.
- **Guides as standards:** `~/Desktop/WORK/Guides` doubles as the best-practice source for D16 (MCP_SERVERS_GUIDE, RAG_CHATBOT_GUIDE, LANGCHAIN_GUIDE / LANGGRAPH_GUIDE, MLFLOW_GENAI_GUIDE, KUBERNETES_GUIDE, DESIGN_PATTERNS_GUIDE). Section numbers cited in PLAN.md (e.g. MCP_SERVERS_GUIDE 17, 20) were not verified at ingest; phase plans verify them.
- **Research:** `docs/research/01..07` back the decisions (handbook inventory, Meridian and Anthropic terms, onboarding practices, gap analysis, open models, hosting, Cloud Run costs). docs/PLAN.md section 2.1 (03/11/2026) overrides section 2 where they conflict.
- **Conflict report:** `.planning/INGEST-CONFLICTS.md` (0 blockers, 3 warnings acknowledged and resolved: cycle downgrade accepted; Joshua's Max account is his alone so D1a holds; golden set drafted by Claude from the test doc + Guides and reviewed by Joshua).

## Constraints

- **Language/runtime**: Python 3.12 only; no Node/Go/Rust project code — user standard
- **Docker**: every component is a Docker image; code and tests run in containers (cwd mounted `-v "$PWD:/app" -w /app`, secrets via `--env-file .env`); no Python on the host
- **Test runner**: `run-unit-tests.sh` at repo root with `--all`, `--single <file> <test_name> <dir>`, `--single-file <file> <dir>`; builds the test image first, then `docker run --rm`; `set -euo pipefail` and a `log()` helper
- **Python tooling**: pip with `requirements.txt` / `requirements-dev.txt`; ruff (lint + format); pytest `-v --tb=short` with `--cov`; type hints on public functions; `mypy --strict` where feasible
- **Deploy targets**: local development on kind (Kubernetes), production on Cloud Run europe-west8 (region still "da confermare"); CI/CD GitHub Actions with Workload Identity Federation (no keys)
- **MCP**: FastMCP / SDK `mcp`; streamable-http, stateless, JSON responses, no persistent SSE (cost and ephemeral filesystem); fewer than 10 tools; read-only; every output carries source url + revision date
- **Gap log**: Firestore, no user id, short retention
- **LLM access (Milestone 1)**: Meridian + Joshua's Claude Max only for personal dev, single user. Guards: Google Chat app visible to Joshua only, `ALLOWED_USERS` allowlist enforced by the bot, `LLM_BACKEND` switch `meridian | api`. Before anyone else uses the bot, `LLM_BACKEND` must move to an API key (Console or Vertex EU)
- **Test data**: ClickUp doc id from an environment variable, pointing to [ClickUp doc ID removed]; the official [ClickUp doc ID removed] is not used in Milestone 1
- **Redaction**: no credential may reach the index; the Wi-Fi page is excluded before indexing
- **Repo layout (D11)**: `packages/buddy_core`, `services/mcp_server`, `services/chat_bot`, `jobs/sync`, `deploy/k8s`, `deploy/cloudrun`, `.github/workflows`, `tests/`, `run-unit-tests.sh`
- **Guides best practices (D16)**: every phase plan cites the Guides sections applied and justifies exceptions
- **Cost**: Cloud Run request-based, scale-to-zero; ~0 EUR/month claim (D7) is validated for the MCP server only; chat_bot, Pub/Sub, CI and kind are not costed in research 07
- **Secrets**: never committed or echoed; `.env` stays local

## Key Decisions

Locked decisions from docs/PLAN.md sections 2 and 2.1 (section 2.1 overrides section 2). Source: SPEC, precedence 0. Rationale and confidence tags live in `.planning/intel/decisions.md`.

<decisions>

Locked (Milestone 1 approved 03/11/2026):

- **D1** (locked, overridden in part by D1a): Do not use Meridian. Anthropic terms forbid routing requests through Free/Pro/Max credentials on behalf of other users; enforced since 9/1/2026. Still applies to any multi-user use.
- **D1a** (locked, overrides D1 for personal dev): Meridian + Joshua's Claude Max only for personal development; Joshua is the sole user (confirmed 03/11/2026: the Max account is used by him alone). Guards: Google Chat app visibility Joshua only, `ALLOWED_USERS` allowlist in the bot, `LLM_BACKEND` switch `meridian | api`. Before another person uses the bot, `LLM_BACKEND` moves to an API key (Console or Vertex EU). Personal use is a grey area accepted by Joshua. Meridian now declares an MIT license.
- **D2** (locked): One Claude seat per person, ideally moving from Max to Claude Team (licence decision owned by Direzione).
- **D3** (locked, "no custom bot" overridden by D13): Phase 1 = remote MCP server + Skill.
- **D4** (locked): Handbook in full context; no vector DB for the handbook (~8k tokens).
- **D5** (locked): Guides = section index + SQLite FTS5/BM25, chunking by heading, `GUIDES_INDEX.md` maps section -> line; embeddings only if eval requires; hybrid dense+BM25 with RRF when Recall@5 < 0.8.
- **D6** (locked): Shared bot uses commercial Claude API on EU cloud (Vertex AI, Bedrock EU alternative); ~35-70 USD/month for 15 users x 10 questions/day. D1a is the personal-dev exception.
- **D7** (locked platform, region tentative): Hosting on Cloud Run europe-west8 (Milano), "da confermare"; connector reachable from the internet with Google login restricted to `digitiamo.com`; scale-to-zero, request-based billing; billing account required.
- **D7a** (locked): Local Kubernetes (kind) for development, Cloud Run for production.
- **D8** (locked): Fix the official handbook before indexing it (plaintext Wi-Fi credentials, two legal addresses, two conflicting leave processes, L.O.V.E. values only as image). Milestone 1 uses the D14 test doc; official cleanup stays Phase 0 content work.
- **D9** (locked default, alternative proposed): Phase 2 backend is model-independent; default Claude API EU. Open-model alternative (Qwen3.8-27B via EU pay-per-use API or self-hosted vLLM) is a proposal decided by golden-set A/B. One client module, switched by configuration. With any open model, orchestrator checks that each citation points to text the tools actually returned.
- **D10** (locked): MCP server stateless with JSON responses (no held-open SSE); gap log on Firestore (container filesystem is ephemeral).
- **D11** (locked): Monorepo: `packages/buddy_core`, `services/mcp_server`, `services/chat_bot`, `jobs/sync`, `deploy/`; one Docker image per service; the bot calls the MCP server over HTTP as an MCP client.
- **D12** (locked): GitHub Actions: path-filtered build, push to Artifact Registry, deploy, Workload Identity Federation (no keys).
- **D13** (locked, overrides D3 and Phase 2 gating): Milestone 1 = sync, MCP server, Google Chat bot, infra and eval together. Bot receives events via Pub/Sub in dev and via HTTP (Google JWT) on Cloud Run.
- **D14** (locked): Test data = separate ClickUp doc "AI Buddy - Test Handbook" ([ClickUp doc ID removed], private, space Wiki), copied from `docs/research/handbook-raw/` with the Wi-Fi redacted. Official [ClickUp doc ID removed] is not touched. Doc id via environment variable.
- **D15** (locked): Guides videos appear in chat as a "Guarda" button and thumbnail on cards, with the single-scene clip linked to the cited section. Google Chat has no embedded player. The Guides repo is private (release URLs return 404 without login): fine for dev; for other users videos move to Google Drive (domain-shared) before rollout.
- **D16** (locked): Apply Guides best practices to every phase (MCP_SERVERS_GUIDE, RAG_CHATBOT_GUIDE, LANGCHAIN/LANGGRAPH_GUIDE, MLFLOW_GENAI_GUIDE, KUBERNETES_GUIDE, DESIGN_PATTERNS_GUIDE). Each phase plan cites the sections applied and justifies exceptions.

</decisions>

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Meridian + Max for personal dev only (D1a) | Fast dev loop with no API spend; Joshua is sole user; guards enforce it | — Pending (revisit before any second user) |
| Handbook in full context, Guides in FTS5 (D4, D5) | ~8k-token handbook needs no RAG; Guides need section search without vector infra | — Pending (Recall@5 decides) |
| MCP server stateless, JSON, Firestore gap log (D10) | Fits Cloud Run free tier and ephemeral filesystem | — Pending |
| Bot as MCP client over HTTP, monorepo (D11) | No duplicated retrieval logic; future split needs no rewrite | — Pending |
| Milestone 1 includes bot, infra, eval (D13) | Joshua's request; Pub/Sub avoids a public URL to the dev machine | — Pending |
| Test handbook instead of official doc (D14) | Official handbook is being rewritten and has known defects | — Pending |
| Foundation (repo skeleton, `run-unit-tests.sh`, tooling) lands in Phase 1, not Phase 4 | Phases 1-3 cannot be verified in Docker without the test runner | — Pending |
| Golden set drafted by Claude from test doc + Guides, reviewed by Joshua | No HR-sourced set exists for the test doc; HR set replaces it later | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check: still the right priority?
3. Audit Out of Scope: reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-07 after Phase 2*
