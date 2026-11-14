# Context (synthesized intel from DOC sources)

All entries are from docs/research/*.md (DOC, lowest precedence). Where they conflict with docs/PLAN.md, PLAN.md wins (see INGEST-CONFLICTS.md). No credentials from any source are reproduced here.

## Topic: Handbook inventory and quality problems
- source: docs/research/01-handbook-inventory.md
- Handbook = ClickUp Doc [ClickUp doc ID removed], 23 pages, ~4.000 words, ~8k tokens: "L'intero handbook entra comodamente in un singolo contesto LLM". Italian, 16/23 pages unchanged since June 2025.
- Quality problems listed: contradictory legal address across two pages; contradictory leave process (Factorial vs ClickUp form); Team page empty; L.O.V.E. values only as image/video; "Luoghi utili" titles only; incomplete root index; stale "Posizioni Aperte"; stale company closures; no owner or review date on policy pages; no IT channel (IT support = HR).
- Chat tool: handbook mentions no chat tool; ClickUp Chat active with 40 channels (hypothesis: main internal channel); Google Chat unconfirmed.
- Roles: HR is contact for nearly everything; no named persons in text; de facto owner to be confirmed.
- Gaps: org chart/who-does-what, communication channels, working hours, tools/access list, IT/security policy, expense process, offboarding, glossary, FAQ.

## Topic: Sensitive content to exclude
- source: docs/research/01-handbook-inventory.md (section 7)
- Wi-Fi page ([ClickUp doc ID removed]) contains plaintext network credentials: exclude from index or redact; bot answers "chiedi a HR / vedi pagina ClickUp". (Credential values deliberately NOT copied.)
- Door-key page links a Google Sheet of bookings (keep text only). Company billing data (VAT/tax IDs) is public company data: ok. No individual salaries or personal employee data found [High].

## Topic: ClickUp API ingestion notes
- source: docs/research/01-handbook-inventory.md (section 9)
- `clickup_list_document_pages(document_id, max_page_depth=-1)` returns the full tree in one call, no pagination; `clickup_get_document_pages(..., content_format="text/md")` accepts batches of ids. Markdown output; images as ClickUp attachment URLs; some blocks (e.g. Team) not exported; internal links `app.clickup.com/.../{page_id}` usable as citation deep-links.
- Metadata for incremental sync: `date_created`, `date_updated`, `date_edited`, `edited_by`, etc. `date_updated` can change without content change: use `date_edited` or a content hash.
- Attachments via `clickup_list_document_page_attachments` (limit max 100) and download call; needed for OCR/transcription of values image/video.
- REST rate limit ~100 req/min on base plans [Medium]; irrelevant at 23 pages. Production needs a ClickUp token; API v3 Docs endpoint `/api/v3/workspaces/{id}/docs/{doc_id}/pages` is what the MCP exposes. ~8k tokens total: chunking by page or H2-H3 is sufficient.

## Topic: Meridian, Anthropic terms and backend options (SUPERSEDED IN PART by PLAN D1a)
- source: docs/research/02-meridian-e-backend-ai.md
- Meridian = local API bridge (TypeScript, Node 22+/Bun; Dockerfile and compose available; not Python) exposing Anthropic Messages / OpenAI Chat Completions / partial Responses API on 127.0.0.1:3456, using the subscription login through `@anthropic-ai/claude-agent-sdk`. Single main maintainer, very high release cadence with frequent regressions. README says MIT but at research time (24/09/2026) no LICENSE file in root (PLAN D1a states Meridian now declares MIT license).
- Anthropic terms quoted by research: third parties may not "route requests through Free, Pro, or Max plan credentials on behalf of their users"; Consumer Terms forbid sharing account login or making the account available to anyone else, and automated access except via API key; Max "assume ordinary, individual usage". Enforcement: server-side blocks from 9/01/2026, clarifications 19-20/02/2026.
- Research verdict (DOC): reject Meridian for AI Buddy; use Claude Team or API (Bedrock/Vertex EU). Overridden for personal dev by PLAN D1a.
- Phase 1 feasibility: remote MCP custom connectors work on Free/Pro/Max/Team/Enterprise; server must be reachable from Anthropic IPs; Claude Code imports claude.ai connectors; Skills/Projects shared org-wide only on Team/Enterprise.
- Cost table (stale assumptions, 20-50 users, 80k-token handbook): Haiku 4.5 ~42-105 $/month, Sonnet 5 ~84-210 $/month, Opus 5.5 ~167-420 $/month; EU routing +10%. Research itself states PLAN D6 (~35-70 $/month) takes precedence.

## Topic: Onboarding best practices and evidence
- source: docs/research/03-onboarding-best-practices.md
- Bauer 4 C framework (Compliance, Clarification, Culture, Connection); Gallup ~12 months to full potential; BambooHR 2023: 65% of new hires do not know whom to ask.
- Key cautions: organization answers for what the bot says (Air Canada 2024, NYC MyCity 2024); commercial RAG hallucinates 17-33% in legal domains. Trust = citations + "non lo so" + escalation; AI Buddy bridges Connection, does not replace people.
- Italian compliance: L. 132/2025 art. 11 and D.Lgs 152/1997 art. 1-bis (AI information notice), AI Act art. 50 transparency (from 2 Aug 2026), Statuto dei Lavoratori art. 4 (logging limits), D.Lgs 81/08, L. 81/2017 art. 22. Applicability of art. 1-bis to an informational chatbot needs legal check.
- Escalation triggers: no source above threshold; sensitive topic (health, harassment, manager conflict, pay, resignation); explicit user request; repeated negative feedback.
- Chatbot KPIs: accuracy >= 95% on compliance topics [Low: project threshold], citation coverage 100% on policies, "non lo so" rate must be > 0, content freshness >= 90%, unanswered-log fix time <= 2 weeks [Low].
- MVP feature set: cited Q&A, escalation, "who handles X" directory, 30/60/90 checklist, per-answer feedback and unanswered log, document governance metadata, bot compliance. Phase 2 items: proactive nudges (day 1/7/30/60/90), buddy reminders, KPI dashboard, preboarding. Later: transactional actions, CI golden set. Do not: answer pay/sanctions/contracts/health without a human source; keep individual question profiles; present the bot as the human buddy.
- KCS method: "flag it or fix it", reuse is review.

## Topic: Handbook gap analysis and RAG-friendly writing
- source: docs/research/04-handbook-gap-analysis.md
- Reference handbooks compared: GitLab, Basecamp, Valve. Taxonomy of 13 section families; new pages proposed P0 (legal/operational block), P1 (onboarding/operations), P2 (growth). Compares current handbook row by row (section 6) and lists quality problems to fix before ingestion (section 6.3).
- Chatbot escalation rules (section 4): no substantive answer on individual situation (payslip, leave balance, pay, evaluation, health, personal smart-working deal), disciplinary/litigation/resignation, reports (harassment, whistleblowing, incident, data breach, injury; bot should not retain content beyond necessity), legal/CCNL interpretation on a concrete case, confidential client data. Always cite source page with last-review date and flag when source is older than declared validity.
- RAG-friendly page rules (section 5): one topic per page, explicit hierarchical titles phrased as user questions, frontmatter (`id`, `titolo`, `owner`, `ultima_revisione`, `valida_fino_a`, `sensibilita'`, `tags`), Q&A section per page, explicit dates, no information only in images/PDF, central glossary, stable URLs/IDs, single source of truth, tables for numbers, self-contained chunks, per-page changelog, marked sensitive content, feedback loop from "not found" queries.

## Topic: Open-weight self-hosted models (Phase 2 alternative; outside Milestone 1)
- source: docs/research/05-modelli-open-self-hosted.md
- Requirements: ~32k useful context, Italian generation quality, mandatory citations + refusal, tool calling, ~3.300 questions/month with 1-3 concurrent users, no EU license block.
- Shortlist: small Qwen3.6-35B-A3B (alt Gemma 4 26B-A4B); medium (recommended) Qwen3.8-27B FP8 (A/B Gemma 4 31B), single 48 GB GPU; large Mistral Small 4 (119B-A6.5B, 80-96 GB). Excluded: Llama 4 (EU license limit), TGI (archived 21/03/2026), Italian-native models (weaker tool calling/context).
- Serving: vLLM (production, `vllm/vllm-openai`, prefix caching), Ollama or llama.cpp for local dev, SGLang valid alternative; MCP tools need an MCP-to-OpenAI-tools adapter (vLLM has no native MCP); scale-to-zero cold start in minutes.
- Honest gap vs Claude: largest gap is refusing when source is missing; needs external gate (every citation must map to a retrieved chunk + retrieval threshold). Self-hosting not justified on cost at this volume. Embeddings if leaving FTS5: bge-m3 (hybrid) or Qwen3-Embedding-0.6B, both CPU-capable.
- Recommendation: default stays Claude API (D6); self-host only with formal data-sovereignty need; mandatory citation guardrail for any open model.

## Topic: Hosting an open-weight LLM (Phase 2 alternative; outside Milestone 1)
- source: docs/research/06-hosting-modello-self-hosted.md
- Load: 3.300 questions/month, ~10k input and ~500 output tokens each, ~14 GPU-hours actually used vs 220-730 billed, utilization ~2-6%.
- Options: Cloud Run GPU (not available in europe-west8; L4 in europe-west1, L4/RTX PRO 6000 in europe-west4; ~230-313 $/month office hours with L4, ~700 $ for RTX PRO 6000); Seeweb (Milano/Frosinone) L4 0,38 EUR/h ~84 EUR/month office hours; EU pay-per-token APIs (Regolo.ai, OVH, Scaleway, Mistral) 3-40 EUR/month; on-prem Varese (DGX Spark ~5.000 EUR) only as test bench; Mac Studio excluded by the Docker constraint (GPU not visible in container).
- Cold start: 15-21 s for 8B (Ollama), 1,5-5 min for 32B (vLLM); Google Chat expects a reply within ~30 s, so a warm-up or async reply is needed.
- Docker constraint: managed APIs keep parity (same image, only env changes); self-host options coherent with Docker are Cloud Run GPU and VMs with NVIDIA Container Toolkit.
- Recommendation: no self-hosting in Phase 2; keep Claude default; backend OpenAI-compatible or adapter with Regolo.ai as sovereign alternative; to verify: Seeweb billing of stopped servers/DPA, Regolo data-center per model, Vertex MaaS open models in EU region, G2/L4 on Compute Engine in europe-west8, DPO opinion ("UE + DPA" vs "Italia + fornitore UE").

## Topic: Cloud Run hosting cost for the MCP server
- source: docs/research/07-costi-hosting-cloud-run.md
- Free tier (request-based): 180,000 vCPU-s, 360,000 GiB-s, 2 million requests per month, aggregated by billing account; europe-west8 (Milano) is Tier 1 so fully covered. Billed only while at least one request is processed (100 ms rounding). Jobs: 240,000 vCPU-s and 450,000 GiB-s free.
- Side services free tier: Cloud Scheduler 3 jobs; Artifact Registry 0,5 GB; Firestore 1 GiB, 50k reads/20k writes per day; Secret Manager 6 active versions, 10k accesses/month; Cloud Build 2.500 build-minutes. Cloud Storage free tier only in us-east1/us-west1/us-central1. A billing account is required.
- Estimate: 20k requests x ~0,5 s x 1 vCPU ~10k vCPU-s (~6% of free tier) [inference, not measured]. Risk: long SSE streams (~792k s over office hours -> ~15 $/month) mitigated by stateless JSON; min-instances=1 ~6-10 $/month always-on or ~2-3 $ office hours only.
- Gaps: cold start numbers for small Python container unverified [Low]; claude.ai client SSE behavior unverified.
