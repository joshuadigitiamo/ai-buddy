# Requirements (synthesized intel)

Note: the ingest set contains no PRD documents. Entries below are taken from explicit requirement statements in docs/PLAN.md (SPEC, precedence 0): section 1 "Requisiti riformulati", section 3 (architecture), section 4 (phases and gate), section 2.1 (Milestone 1). Source section is cited per entry. Milestone 1 phase mapping (user intent from orchestrator): 1 sync+redaction, 2 MCP server, 3 Google Chat bot, 4 infra, 5 golden-set eval. No competing acceptance variants were found.

## REQ-grounded-cited-answers
- source: docs/PLAN.md (section 1)
- description: Un dipendente fa una domanda in linguaggio naturale (italiano). AI Buddy risponde solo in base alle fonti ufficiali e cita sempre la pagina di origine. Ogni output dei tool include la fonte (section 3). Format della risposta: risposta, fonte, owner, data di revisione (Skill, section 3).
- acceptance: Correctness-with-citation >= 90% on golden set at Phase 1 gate; 0 invented policies (section 4 Phase 1 exit gate, section 6 KPI).
- scope: answer quality, citations

## REQ-no-source-refusal-and-gap-log
- source: docs/PLAN.md (section 1, section 3 gap log, D10)
- description: Se la fonte non esiste, AI Buddy lo dice ("non lo so, chiedi a ...") e registra la domanda come gap dell'handbook. Gap log = collezione Firestore con domanda, timestamp e "nessuna fonte trovata", senza user id (Statuto dei Lavoratori art. 4). Tool: `buddy_report_gap(question)`.
- acceptance: "Test contesto vuoto": the assistant must refuse (section 4 Phase 1 item 6).
- scope: refusal behavior, gap log, privacy

## REQ-sensitive-topic-escalation
- source: docs/PLAN.md (section 1); detail in docs/research/04-handbook-gap-analysis.md (section 4, DOC)
- description: I temi sensibili (malattia, contestazioni, retribuzione, salute, conflitti) vanno sempre a una persona. AI Buddy fornisce al massimo la regola generale scritta. Skill carries the list of escalation topics and referral contacts.
- acceptance: absent (not stated numerically in source; covered by golden set / "0 policy inventate")
- scope: escalation, HR topics

## REQ-mcp-server-five-tools
- source: docs/PLAN.md (section 3 Phase 1 architecture, section 4 Phase 1 item 1)
- description: Server MCP Python (SDK `mcp`, streamable-http in modalita' stateless con risposte JSON, D10) con 5 tool namespaced: `handbook_get(section?)`, `handbook_search(query)`, `guides_search(query)`, `guides_get_section(id)`, `buddy_report_gap(question)`. Resource `handbook://{pagina}`. Handbook in memoria, Guides in SQLite FTS5, gap log su Firestore. Meno di 10 tool.
- acceptance: Recall@5 of retrieval measured on golden set (section 4 Phase 1 item 6); Guides upgrade to hybrid when Recall@5 < 0,8 (D5).
- scope: MCP server, tools

## REQ-mcp-auth-google-domain
- source: docs/PLAN.md (section 3, section 4 Phase 1 item 3, section 7)
- description: Auth OAuth 2.1 con Google, dominio ristretto a `@digitiamo.com` (MCP_SERVERS_GUIDE section 17); sola lettura; rate limit.
- acceptance: absent
- scope: MCP server security

## REQ-sync-clickup-guides
- source: docs/PLAN.md (section 3 sync, section 4 Phase 1 item 2, D14)
- description: Job di sync ClickUp + Guides con redazione e hash. ClickUp: `list_document_pages` per l'albero, `get_document_pages` (text/md); sync incrementale con `date_edited` e hash del contenuto (non `date_updated`). Guides: git pull del repo. Target ClickUp doc ID via variabile d'ambiente (test doc [ClickUp doc ID removed], never the official [ClickUp doc ID removed]). Open design point in source: how synced data reaches the container (image rebuild vs bucket read at startup).
- acceptance: absent
- scope: sync job, ClickUp API, Guides repo

## REQ-sync-redaction
- source: docs/PLAN.md (section 3, section 7, D14)
- description: Prima dell'indicizzazione si applica un filtro di redazione (pagina Wi-Fi esclusa). Nessuna credenziale deve finire nell'indice.
- acceptance: absent
- scope: redaction, security

## REQ-skill-digitiamo-buddy
- source: docs/PLAN.md (section 3, section 4 Phase 1 item 5)
- description: Skill `digitiamo-buddy` (SKILL.md): quando usare i tool, formato della risposta (risposta, fonte, owner, data di revisione), lista temi da escalare, rimando ai referenti; guida di installazione di una pagina per i colleghi.
- acceptance: absent
- scope: Skill

## REQ-google-chat-bot
- source: docs/PLAN.md (D13, D1a, section 3 Phase 2, section 4 Phase 2)
- description: Bot Google Chat in Milestone 1 (DM / @menzione). Riceve eventi via Pub/Sub in sviluppo e via HTTP (JWT Google) su Cloud Run. Chiama il server MCP via HTTP come client MCP (D11). Workflow, non agente: 2-step RAG (riformulazione query, retrieval via tool MCP, risposta con citazioni, gate di confidenza). Guardie in sviluppo: app visibile solo a Joshua, allowlist `ALLOWED_USERS`. Google Chat risponde a un evento entro ~30 s, altrimenti risposta asincrona (docs/research/06 section 7.1, DOC).
- acceptance: absent for Milestone 1; Phase 2 feedback KPI thumbs-up >= 80% (section 6)
- scope: Google Chat bot

## REQ-pluggable-llm-client
- source: docs/PLAN.md (D1a, D9, section 3.1)
- description: Un solo modulo client verso il modello, configurabile via `LLM_BACKEND` (Milestone 1 intent: meridian | api). Prima che un'altra persona usi il bot, `LLM_BACKEND` passa ad API key (Console o Vertex UE). PLAN 3.1 describes the same module as two implementations (Anthropic SDK and OpenAI-compatible endpoint). With any open model, citation check in the orchestrator (each citation must point to text the tools actually returned).
- acceptance: absent
- scope: LLM client

## REQ-chat-video-cards
- source: docs/PLAN.md (D15)
- description: Video delle Guides nelle card Google Chat: pulsante "Guarda" e miniatura, clip della singola scena collegato alla sezione citata.
- acceptance: absent
- scope: Google Chat cards

## REQ-dockerized-everything
- source: docs/PLAN.md (section 1)
- description: Ogni componente che gira e' un'immagine Docker (server MCP, job di sync, backend bot, eventuale modello self-hosted). Locale con `docker compose` a servizi separati; i deploy usano la stessa immagine. Test tramite `run-unit-tests.sh` (build dell'immagine di test, poi `docker run --rm` con `--env-file .env`). Mai Python sull'host.
- acceptance: absent
- scope: containerization, test runner

## REQ-infra-ci-cd
- source: docs/PLAN.md (D7, D7a, D11, D12, section 4 Phase 1 item 4)
- description: Un'immagine Docker per servizio; kind per sviluppo locale; deploy su Cloud Run EU; GitHub Actions con filtri per path, push su Artifact Registry, auth via Workload Identity Federation. Durante il pilota controllare `container/billable_instance_time` per restare nel free tier.
- acceptance: absent
- scope: infra, CI/CD

## REQ-golden-set-eval
- source: docs/PLAN.md (section 4 Phase 0 item 7, Phase 1 item 6 and exit gate, section 6)
- description: Golden set di 30-50 domande reali con risposta attesa e pagina fonte (raccolte da HR e colleghi) come test di accettazione. Eval: golden set contro i tool (Recall@5) e contro Claude con la Skill (correttezza e citazione corretta); test "contesto vuoto" deve rifiutare. Phase 2: scorer MLflow `RetrievalGroundedness` e `Correctness` in CI (MLFLOW_GENAI_GUIDE sections 11, 29).
- acceptance: >= 90% correct answers with citation, 0 invented policies (Phase 1 gate); >= 95% at regime.
- scope: evaluation

## REQ-apply-guides-best-practices
- source: docs/PLAN.md (D16)
- description: Ogni piano di fase cita le sezioni delle Guides applicate e motiva le eccezioni.
- acceptance: each phase plan lists applied Guides sections and justified exceptions
- scope: planning process

## REQ-handbook-content-cleanup
- source: docs/PLAN.md (section 4 Phase 0, no code); problems detailed in docs/research/01 (section 5) and 04 (section 6.3), DOC
- description: Pulizia contenuti dell'handbook ufficiale: rimuovere password Wi-Fi in chiaro, indirizzo legale unico, processo ferie unico, testo dei valori L.O.V.E., pagina Team, metadati per pagina (owner, data di revisione, validita'), nuove pagine P0. Not Milestone 1 code work; test doc (D14) is used instead.
- acceptance: handbook "pulito" con owner, golden set pronto, decisione licenze presa (Phase 0 exit)
- scope: content governance (outside Milestone 1)
