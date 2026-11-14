# Decisions (synthesized intel)

Source set: docs/PLAN.md only (SPEC, precedence 0). No ADR documents exist in the ingest set.
Lock note: classifier marked `locked: false` (no ADR status). Per orchestrator, decisions in PLAN.md sections 2 and 2.1 are treated as locked (Milestone 1 approved 03/11/2026). Where a decision is explicitly tentative in the source ("da confermare", "Proposta"), that is stated in the status line.
Precedence inside PLAN.md: section 2.1 (03/11/2026) overrides section 2 wherever they conflict.

## D1: Do not use Meridian (SUPERSEDED IN PART by D1a)
- source: docs/PLAN.md (section 2, D1)
- status: locked (overridden by D1a for personal-dev use only; D1 still applies to any multi-user use)
- decision: Non usare Meridian. I termini Anthropic vietano di instradare richieste tramite credenziali Free/Pro/Max per conto di altri utenti, Agent SDK incluso; il divieto e' applicato (blocchi lato server dal 9/1/2026, ban di account). Il repo non ha un file LICENSE e ha un solo maintainer. Confidenza [High].
- scope: backend AI, Meridian, Claude Max credentials, multi-user usage

## D1a: Meridian + Joshua's Claude Max only for personal development
- source: docs/PLAN.md (section 2.1, D1a, 03/11/2026)
- status: locked
- decision: Meridian + Claude Max di Joshua solo in sviluppo personale. Joshua e' l'unico utente. Prima che un'altra persona usi il bot, `LLM_BACKEND` passa ad API key (Console o Vertex UE). Guardie: visibilita' dell'app Google Chat limitata a Joshua; allowlist `ALLOWED_USERS` nel bot. Uso personale = zona grigia accettata da Joshua (verificato il 03/11/2026 su code.claude.com/docs/en/legal-and-compliance e Consumer Terms sez. 2). Correzione: Meridian ora dichiara licenza MIT. Confidenza [High] divieto, [Medium] uso personale.
- scope: LLM backend in Milestone 1, Google Chat bot access control

## D2: One Claude seat per person, ideally move from Max to Claude Team
- source: docs/PLAN.md (section 2, D2)
- status: locked
- decision: Un seat Claude per persona, idealmente con il passaggio da Max a Claude Team. Due seat Team Standard costano meno di un Max 5x; Team porta Commercial Terms, nessun training sui dati, connettori e Project condivisi. Confidenza [High]. (Licence decision itself is a dependency owned by Direzione, see PLAN section 5.)
- scope: licensing, Claude seats

## D3: Phase 1 = remote MCP server + Skill, no custom bot
- source: docs/PLAN.md (section 2, D3)
- status: locked (the "no custom bot" part is overridden by D13 for Milestone 1)
- decision: Fase 1 = server MCP remoto + Skill, nessun bot custom. I custom connector (MCP remoti) funzionano su Pro/Max/Team. Costo LLM aggiuntivo zero. Confidenza [High].
- scope: Phase 1 delivery channel

## D4: Handbook in full context, no vector DB for the handbook
- source: docs/PLAN.md (section 2, D4)
- status: locked
- decision: Handbook in contesto completo, niente vector DB per l'handbook (~8k token, sta in un solo contesto; RAG su 23 pagine e' complessita' senza beneficio). Confidenza [High].
- scope: handbook retrieval

## D5: Guides = section index + full-text search (SQLite FTS5/BM25)
- source: docs/PLAN.md (section 2, D5)
- status: locked
- decision: Guides: indice per sezioni + ricerca full-text (SQLite FTS5/BM25); embeddings solo se l'eval lo richiede. Upgrade ibrido dense+BM25 con RRF quando Recall@5 < 0,8. `GUIDES_INDEX.md` mappa sezione -> riga (chunking per heading). Confidenza [Medium].
- scope: Guides retrieval

## D6: Phase 2 via Claude API on EU cloud
- source: docs/PLAN.md (section 2, D6)
- status: locked
- decision: Fase 2 via Claude API su cloud EU: Vertex AI se si ospita su GCP, Bedrock EU in alternativa. Il bot condiviso deve usare credenziali commerciali, non abbonamenti (see D1a for the personal-dev exception). Residenza UE (GDPR). Stima ~35-70 $/mese per 15 utenti x 10 domande/giorno, incl. +10% routing UE. Confidenza [Medium] costi.
- scope: shared-bot LLM backend, data residency, cost

## D7: Hosting on Cloud Run europe-west8 (Milano)
- source: docs/PLAN.md (section 2, D7; refined by D7a)
- status: locked (platform Cloud Run confirmed by D7a/D12; region europe-west8 still marked "da confermare" in source)
- decision: Hosting Cloud Run europe-west8 (Milano), da confermare. Connettore MCP raggiungibile da internet; login Google ristretto al dominio `digitiamo.com`. Scale-to-zero + billing request-based = ~0 EUR/mese (~20k richieste/mese ~6% del free tier). Serve un billing account attivo. Confidenza [High] prezzi, [Medium] traffico.
- update 2026-11-14: billing account presente — progetto GCP esistente `ai-buddy-dev` (ID in docs/internal/gcp-project.md, gitignored), nell'organizzazione digitiamo.com, billing collegato. Regione europe-west8 ancora "da confermare".
- scope: production hosting, cost

## D7a: Local Kubernetes (kind) for development, Cloud Run for production
- source: docs/PLAN.md (section 2.1, D7a)
- status: locked
- decision: Kubernetes locale (kind) per lo sviluppo, Cloud Run per la produzione. K8s locale per validare i manifest senza costi di cluster. Cloud Run resta a ~0 EUR/mese (D7). Confidenza [Medium].
- scope: dev environment, deploy targets

## D8: Fix the handbook before indexing it
- source: docs/PLAN.md (section 2, D8)
- status: locked
- decision: Correggere l'handbook prima di indicizzarlo (credenziali Wi-Fi in chiaro, due indirizzi legali, due processi ferie in conflitto, valori L.O.V.E. solo come immagine). Confidenza [High]. (Milestone 1 uses a separate test doc per D14; the official handbook cleanup remains Phase 0 content work.)
- scope: handbook content quality, redaction

## D9: Phase 2 backend model-independent; default Claude API EU
- source: docs/PLAN.md (section 2, D9; section 3.1)
- status: locked (default: Claude API EU); proposed (alternative: open model Qwen3.8-27B via EU pay-per-use API or self-hosted vLLM in Docker)
- decision: Backend Fase 2 indipendente dal modello. Default Claude API UE. Proposta alternativa: modello open (Qwen3.8-27B) via API UE a consumo oppure self-hosted con vLLM in Docker. A ~3.300 domande/mese una GPU e' inattiva il 94-98% del tempo (self-hosted costa 4-30x l'API). Un solo punto di contatto con il modello: modulo client con due implementazioni (Anthropic SDK e endpoint OpenAI-compatibile), cambio via configurazione. Il golden set decide l'A/B tra opzioni A e B/C. Confidenza [Medium].
- scope: LLM client abstraction, model choice (options A/B/C in PLAN 3.1)

## D10: MCP server stateless, gap log on Firestore
- source: docs/PLAN.md (section 2, D10)
- status: locked
- decision: Server MCP stateless con risposte JSON (evita stream SSE tenuti aperti che escono dal free tier, ~15 $/mese). Filesystem Cloud Run effimero, quindi il gap log non puo' stare in SQLite nel container: Firestore (free tier anche in UE; Cloud Storage free tier solo per tre regioni USA). Confidenza [High].
- scope: MCP transport mode, gap log storage

## D11: Monorepo
- source: docs/PLAN.md (section 2.1, D11)
- status: locked
- decision: Monorepo (questo repo): `packages/buddy_core`, `services/mcp_server`, `services/chat_bot`, `jobs/sync`, `deploy/`. Un'immagine Docker per servizio. Il bot chiama il server MCP via HTTP come client MCP, cosi' una separazione futura non richiede riscritture. Confidenza [Medium-High].
- scope: repo layout, service boundaries

## D12: CI/CD with GitHub Actions
- source: docs/PLAN.md (section 2.1, D12)
- status: locked
- decision: GitHub Actions: build con filtri per path, push su Artifact Registry, deploy, autenticazione Workload Identity Federation (niente chiavi). Confidenza [High].
- scope: CI/CD, deploy auth

## D13: Milestone 1 = sync, MCP server, Google Chat bot, infra and eval together
- source: docs/PLAN.md (section 2.1, D13)
- status: locked
- decision: Milestone 1 = sync, server MCP, bot Google Chat, infra ed eval insieme. Il bot riceve gli eventi via Pub/Sub in sviluppo e via HTTP (JWT Google) su Cloud Run. Richiesta di Joshua; Pub/Sub non richiede un URL pubblico verso la macchina locale. Confidenza [Medium].
- scope: Milestone 1 scope, bot event transport

## D14: Test data = separate ClickUp doc "AI Buddy - Test Handbook"
- source: docs/PLAN.md (section 2.1, D14)
- status: locked
- decision: Doc ClickUp separato "AI Buddy - Test Handbook" ([ClickUp doc ID removed], privato, space Wiki), copiato dallo snapshot `docs/research/handbook-raw/` con redazione del Wi-Fi. L'handbook ufficiale [ClickUp doc ID removed] non si tocca (e' in riscrittura). ID del doc via variabile d'ambiente. Confidenza [High].
- scope: test data, ClickUp sync target
- update 2026-11-14: superseded by Phase 1 D-25..D-27 (ClickUp in dismissione): handbook dallo snapshot locale gitignored via `HANDBOOK_DIR`, Guides dal checkout locale; nessuna API ClickUp, nessun token.

## D15: Guides videos in chat as "Guarda" button and thumbnail on cards
- source: docs/PLAN.md (section 2.1, D15)
- status: locked
- decision: Video delle Guides nella chat come pulsante "Guarda" e miniatura nelle card, con il clip della singola scena collegato alla sezione citata. Google Chat non incorpora un player video. Repo Guides privato, URL delle release danno 404 senza login: ok in sviluppo; per altri utenti i video vanno spostati su Google Drive (condivisione al dominio) prima del rollout. Confidenza [Medium].
- scope: Google Chat cards, video hosting

## D16: Apply Guides best practices to every phase
- source: docs/PLAN.md (section 2.1, D16)
- status: locked
- decision: Applicare le best practice delle Guides (`~/Desktop/WORK/Guides`) a ogni fase: MCP_SERVERS_GUIDE (server MCP, tool, transport, auth), RAG_CHATBOT_GUIDE (retrieval, chunking, eval), LANGCHAIN/LANGGRAPH_GUIDE (bot), MLFLOW_GENAI_GUIDE (tracing, eval), KUBERNETES_GUIDE (manifest, deploy), DESIGN_PATTERNS_GUIDE (architettura). Ogni piano di fase cita le sezioni applicate e motiva le eccezioni. Confidenza [High].
- scope: all phases, planning process
