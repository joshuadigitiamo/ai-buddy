## Conflict Detection Report

### BLOCKERS (0)

(none)

### WARNINGS (3)

[WARNING] Cross-reference cycles between PLAN.md and research docs (cycle-detection rule deviation)
  Found: docs/PLAN.md cross_refs -> docs/research/02-meridian-e-backend-ai.md, 05-modelli-open-self-hosted.md, 06-hosting-modello-self-hosted.md, and each of those three lists docs/PLAN.md in its own cross_refs. Three 2-node cycles: PLAN <-> 02, PLAN <-> 05, PLAN <-> 06.
  Impact: The synthesizer rule says cycles are recorded as BLOCKERs and the cyclic set is not synthesized. Here the references are supporting-doc / defers-to-plan back-references, not a dependency loop: precedence is acyclic (SPEC precedence 0 over DOC; 02 states "docs/PLAN.md ... ha la precedenza"), and no content was derived by traversing cross_refs. The synthesizer therefore reported it as WARNING and DID synthesize all docs. This is a deliberate deviation from the letter of the rule, made so a benign back-reference does not block the whole ingest.
  → Confirm the downgrade is acceptable. If strict handling is wanted, reclassify as BLOCKER and re-run with these back-references removed via --manifest.

[WARNING] D1a premise: Max account used with Meridian must be single-user
  Found: docs/PLAN.md D1a assumes Joshua is the only user of the Max account Meridian runs on.
  Impact: If the account had other users, the D1a guard would not hold at account level.
  → RESOLVED 2026-11-03: Joshua confirmed the account is used by him alone.

[WARNING] Golden set required for Milestone 1 eval but not yet produced; source is HR, outside the code work
  Found: docs/PLAN.md section 4 Phase 0 item 7: golden set of 30-50 real questions collected from HR and colleagues, "diventa il test di accettazione". Milestone 1 includes a golden-set eval phase (D13, orchestrator phase 5). D14 says Milestone 1 uses a separate test handbook copied from the raw snapshot, not the official handbook being rewritten. docs/PLAN.md section 5 lists HR as owner of page owners; no source states who writes the golden set against the test doc.
  Impact: Phase 5 eval and the >= 90% gate have no input data, and expected-answer pages must point at the test doc (xkwgt-39975), not the official handbook (xkwgt-22915). Questions collected from HR may refer to content that differs between the two.
  → Decide who authors the golden set for Milestone 1 (Joshua from the snapshot, or HR) and that expected source pages reference the test doc; record it in the eval phase plan.

### INFO (10)

[INFO] Auto-resolved: PLAN section 2.1 D1a over section 2 D1, PLAN risk row, and research 02 verdict
  Note: docs/PLAN.md D1 ("Non usare Meridian"), the section 7 risk row (mitigation "D1, D2: niente Meridian") and docs/research/02-meridian-e-backend-ai.md (verdict: reject Meridian, options (a) and (b) prohibited) are overridden for personal development by docs/PLAN.md section 2.1 D1a (03/11/2026): Meridian + Joshua's Max allowed ONLY in personal dev, single user, guards ALLOWED_USERS and Google Chat visibility limited to Joshua, LLM_BACKEND switches to API key before any other user. D1 and 02 remain valid for any multi-user use. D6's "credenziali commerciali, non abbonamenti" for the shared bot is likewise subject to this exception. Research 02 point that Meridian has no LICENSE file is superseded by D1a "Meridian ora dichiara licenza MIT". Winner: PLAN section 2.1 (later date, SPEC over DOC, orchestrator instruction). Not a LOCKED-vs-LOCKED case: D1 and D1a are in the same document with explicit supersession.

[INFO] Auto-resolved: PLAN section 2.1 D13 over D3, section 1 Phase 2 and section 4 gating
  Note: docs/PLAN.md D3 ("Fase 1 ... nessun bot custom"), section 1 ("Fase 2: assistente dedicato ... la scelta si fa al gate di fine Fase 1") and section 4 Phase 2 ("solo se il gate lo giustifica") put the Google Chat bot after the Phase 1 gate. D13 brings the Google Chat bot into Milestone 1 together with sync, MCP server, infra and eval. D13 wins. Consequently PLAN open question 1 (Google Chat vs ClickUp Chat) is answered for Milestone 1 by D13 (Google Chat, single dev user), but remains open for the rollout. The 2-step RAG / LangGraph design from section 3 Phase 2 is retained as the bot design.

[INFO] Refinement, no conflict: D7a over D7 for development environment
  Note: docs/PLAN.md D7 (Cloud Run, europe-west8, "da confermare") is refined by D7a: kind for local development, Cloud Run for production. Region europe-west8 is still not formally confirmed in the source.

[INFO] Auto-resolved: D11 monorepo over PLAN section 7 mitigation "un servizio, SQLite"
  Note: docs/PLAN.md section 7 (bus factor mitigation: "Stack minimo (un servizio, SQLite)") predates D11, which defines three services (mcp_server, chat_bot, jobs/sync) plus a shared package, one image per service. D11 wins; the bus-factor mitigation now relies on README and ADR, and on the shared buddy_core package.

[INFO] Auto-resolved: PLAN over research 02 on cost, tool names and framework
  Note: docs/research/02-meridian-e-backend-ai.md states cost 40-420 $/month based on 20-50 users and an 80k-token handbook, tools named search_handbook / get_section / search_guides, and a FastMCP example. docs/PLAN.md D6 (~35-70 $/month, 15 users, ~8k token handbook), the five handbook_* / guides_* / buddy_report_gap tools, and the `mcp` SDK take precedence (SPEC over DOC). Research 02 itself notes the PLAN has precedence.

[INFO] Auto-resolved: PLAN over research 03 on accuracy target
  Note: docs/research/03-onboarding-best-practices.md suggests answer accuracy >= 95% on compliance topics (tagged [Low: soglia di progetto]). docs/PLAN.md section 6 sets >= 90% at the Phase 1 gate and >= 95% at regime, citing that research. PLAN wins; no variants kept because PLAN already reconciles both.

[INFO] Naming difference to reconcile at planning: pluggable LLM client implementations
  Note: Milestone 1 intent (orchestrator) is a client with `meridian | api` backends selected by LLM_BACKEND (D1a). docs/PLAN.md D9 and section 3.1 describe a client module with two implementations, Anthropic SDK and an OpenAI-compatible endpoint. Meridian exposes an Anthropic Messages-compatible API (docs/research/02), so it can sit behind the Anthropic-SDK implementation with a different base_url. Not contradictory; the phase plan should define the interface once.

[INFO] D14 test handbook vs Phase 0 and D8 handbook cleanup
  Note: docs/PLAN.md D14 uses a separate test doc (xkwgt-39975, Wi-Fi redacted) and leaves the official handbook xkwgt-22915 untouched (being rewritten). This does not cancel D8 / Phase 0 (fix the official handbook before indexing it); that work stays outside Milestone 1 code and is a prerequisite for pointing the sync at the official doc. Sensitive page xkwgt-28055 (credentials in clear) is excluded by redaction; no credential values were copied into intel files.

[INFO] Scope gap: research 07 costs the MCP server only
  Note: docs/research/07-costi-hosting-cloud-run.md estimates ~0 EUR/month for one MCP server plus Scheduler, Artifact Registry, Firestore, Secret Manager and Cloud Build. Milestone 1 (D11, D12, D13) adds a second Cloud Run service (chat_bot), Pub/Sub, GitHub Actions with Workload Identity Federation, and a kind-based dev cluster; these are not covered by the cost research. The ~0 EUR/month claim (D7) should be treated as valid for the MCP server only until checked.

[INFO] D16 references material outside the ingest set
  Note: docs/PLAN.md D16 and several sections cite Guides (~/Desktop/WORK/Guides: MCP_SERVERS_GUIDE, RAG_CHATBOT_GUIDE, LANGCHAIN_GUIDE, MLFLOW_GENAI_GUIDE, KUBERNETES_GUIDE, DESIGN_PATTERNS_GUIDE, section numbers such as MCP_SERVERS_GUIDE section 17 and 20). These were not part of the ingest and their section numbers were not verified. docs/research/handbook-raw/ (referenced by PLAN, 01 and D14) is a directory snapshot and was not classified as a document.
