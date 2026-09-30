# Piano: AI Buddy Digitiamo

**Obiettivo:** un assistente conversazionale che risponde in qualsiasi momento a domande su processi, tool e cultura aziendale di Digitiamo.
**Fonti:** Handbook ClickUp (doc `xkwgt-22915`, 23 pagine) e repo Guides (15 guide tecniche).
**Stato:** solo pianificazione. Nessun codice finché il piano non è approvato.
**Complessità:** Media (Fase 1 bassa-media, Fase 2 media).
**Data:** 24/09/2026

Research di supporto, in `docs/research/`:

| File | Contenuto |
|---|---|
| `01-handbook-inventory.md` + `handbook-raw/` | Inventario completo dell'handbook: 23 pagine, ~4.000 parole, problemi di qualità |
| `02-meridian-e-backend-ai.md` | Meridian, termini Anthropic, opzioni di backend, costi |
| `03-onboarding-best-practices.md` | Deep research sull'onboarding (32 fonti) |
| `04-handbook-gap-analysis.md` | Tassonomia di un handbook completo, gap e pagine da aggiungere |
| `05-modelli-open-self-hosted.md` | Modelli open-weight per la Fase 2: shortlist, licenze, serving |
| `06-hosting-modello-self-hosted.md` | Dove ospitare un modello, costi, Docker, cold start |
| `07-costi-hosting-cloud-run.md` | Costi di hosting del server MCP: free tier Cloud Run e servizi di contorno |

---

## 1. Requisiti riformulati

- Un dipendente fa una domanda in linguaggio naturale (italiano). AI Buddy risponde **solo** in base alle fonti ufficiali e **cita sempre** la pagina di origine.
- Se la fonte non esiste, AI Buddy lo dice ("non lo so, chiedi a …") e **registra la domanda** come gap dell'handbook.
- I temi sensibili (malattia, contestazioni, retribuzione, salute, conflitti) vanno sempre a una persona. AI Buddy fornisce al massimo la regola generale scritta.
- **Fase 1:** AI Buddy vive **dentro Claude**, cioè nelle app Claude che i dipendenti già usano (claude.ai, desktop, Claude Code), tramite un connettore MCP e una Skill. Nessuna nuova UI.
- **Fase 2:** assistente conversazionale dedicato in **Google Chat** oppure in una **web app interna**. La scelta si fa al gate di fine Fase 1.
- **Tutto dockerizzato:** ogni componente che gira è un'immagine Docker. Vale per il server MCP, il job di sync, il backend della Fase 2 e l'eventuale modello self-hosted (container vLLM/Ollama). In locale si usa `docker compose` con servizi separati. I deploy (Cloud Run, VM o altro) usano la stessa immagine. Test tramite `run-unit-tests.sh` (build dell'immagine di test, poi `docker run --rm` con `--env-file .env`). Mai Python sull'host.
- Contesto: meno di 15 dipendenti, Google Workspace, ClickUp, Factorial. Una sola persona costruisce il progetto e non c'è una scadenza fissata.

## 2. Decisioni chiave (con motivazione)

| # | Decisione | Perché | Confidenza |
|---|---|---|---|
| D1 | **Non usare Meridian** | I termini Anthropic vietano espressamente di instradare richieste tramite credenziali Free/Pro/Max per conto di altri utenti, Agent SDK incluso. Il divieto viene applicato: blocchi lato server dal 9/1/2026 e ban di account. Il repo inoltre non ha un file LICENSE e ha un solo maintainer. | [High] |
| D2 | **Un seat Claude per persona**, idealmente con il passaggio da Max a **Claude Team** | Due seat Team Standard costano meno di un Max 5x. Team porta anche Commercial Terms, nessun training sui dati e connettori e Project condivisi per tutta l'organizzazione. | [High] |
| D3 | **Fase 1 = server MCP remoto + Skill**, nessun bot custom | I custom connector (MCP remoti) funzionano su Pro/Max/Team. Costo LLM aggiuntivo zero. È il minimo che rende AI Buddy disponibile a tutti. | [High] |
| D4 | **Handbook in contesto completo, niente vector DB** per l'handbook | ~8k token, e l'intero handbook sta in un solo contesto (Guides, LANGCHAIN_GUIDE §14). Un RAG su 23 pagine è complessità senza beneficio. | [High] |
| D5 | **Guides: indice per sezioni + ricerca full-text (SQLite FTS5/BM25)**, embeddings solo se l'eval lo richiede | ~15 guide da ~100 KB non stanno in un contesto. `GUIDES_INDEX.md` mappa già sezione → riga, quindi il chunking per heading è gratis. Ibrido dense+BM25 con RRF (RAG_CHATBOT_GUIDE §11) diventa l'upgrade quando Recall@5 < 0,8. | [Medium] |
| D6 | **Fase 2 via Claude API su cloud EU**: Vertex AI se si ospita su GCP, Bedrock EU in alternativa | Il bot condiviso deve usare credenziali commerciali, non abbonamenti. Serve residenza UE (GDPR). Stima ~35–70 $/mese per 15 utenti × 10 domande al giorno, inclusa la maggiorazione del 10% per il routing UE. | [Medium] costi |
| D7 | **Hosting: Cloud Run europe-west8 (Milano)**, da confermare | Il connettore MCP deve essere raggiungibile da internet (lo chiamano i server Anthropic). Ci sono già Google Workspace e un login Google che permette di restringere l'accesso al dominio `digitiamo.com`. Con scale-to-zero e billing request-based il costo è ~0 €/mese: ~20k richieste al mese usano circa il 6% del free tier (180k vCPU-s, 360k GiB-s, 2M richieste). Milano è Tier 1, quindi coperta per intero. Serve comunque un billing account attivo. Vedi `07-costi-hosting-cloud-run.md`. | [High] prezzi, [Medium] traffico |
| D10 | **Server MCP stateless, gap log su Firestore** | Cloud Run fattura l'istanza finché una richiesta è aperta: uno stream SSE tenuto aperto tutto il giorno fa uscire dal free tier (~15 $/mese). Stateless con risposte JSON lo evita. Il filesystem di Cloud Run è effimero, quindi il gap log non può stare in SQLite nel container. Firestore ha un free tier anche in UE; quello di Cloud Storage vale solo per tre regioni USA. | [High] |
| D9 | **Backend Fase 2 indipendente dal modello**: default Claude API UE. Proposta alternativa: modello open (Qwen3.8-27B) via API UE a consumo oppure self-hosted con vLLM in Docker | Tiene aperta la porta a sovranità dei dati e indipendenza dal fornitore senza pagarle da subito. A ~3.300 domande al mese una GPU è inattiva il 94–98% del tempo: il self-hosted costa 4–30 volte l'API. Vedi §3.1. | [Medium] |
| D8 | **Correggere l'handbook prima di indicizzarlo** | Password Wi-Fi in chiaro, due indirizzi legali diversi, due processi ferie in conflitto, valori L.O.V.E. solo come immagine. Un bot sopra contenuti sbagliati amplifica gli errori (caso Air Canada 2024). | [High] |

## 3. Architettura

### Fase 1: "Buddy dentro Claude"

```
Dipendente (claude.ai / Desktop / Claude Code, seat personale)
        │  Skill "digitiamo-buddy" (istruzioni: cita, rifiuta, escala)
        ▼
Custom connector ──HTTPS + OAuth (Google, solo @digitiamo.com)──► MCP server (Cloud Run, Python)
                                                                   ├─ handbook_get(section?)     → markdown + url + data revisione
                                                                   ├─ handbook_search(query)     → sezioni pertinenti
                                                                   ├─ guides_search(query)       → sezioni Guides (FTS5)
                                                                   ├─ guides_get_section(id)     → testo sezione + riferimento
                                                                   └─ buddy_report_gap(question) → log domande senza risposta
                                                                          ▲
                           Sync job (Cloud Scheduler, notturno) ── ClickUp API (get_document_pages, text/md, date_edited)
                                                               └── git pull repo Guides
```

- **Meno di 10 tool, nomi con namespace** (MCP_SERVERS_GUIDE §20). Ogni output include la fonte, perché "le citazioni che il modello non vede sono citazioni che inventa" (LANGCHAIN_GUIDE L1561).
- **Resource** `handbook://{pagina}` per chi vuole allegare pagine intere, più i **tool** di ricerca per il modello (MCP_SERVERS_GUIDE §6.3).
- **Sync ClickUp:** una chiamata `list_document_pages` restituisce tutto l'albero, `get_document_pages` restituisce markdown. Per il sync incrementale si usano `date_edited` e un hash del contenuto, non `date_updated`. Prima dell'indicizzazione si applica un filtro di redazione (pagina Wi-Fi esclusa). **Da decidere:** come i dati del sync arrivano al container, cioè se il sync ricostruisce l'immagine oppure scrive su un bucket che il server legge all'avvio.
- **Skill `digitiamo-buddy`** (SKILL.md): quando usare i tool, formato della risposta (risposta, fonte, owner, data di revisione), lista dei temi da escalare, rimando ai referenti.
- **Gap log:** collezione Firestore (D10) con domanda, timestamp e "nessuna fonte trovata", **senza user id** (vedi Rischi: Statuto dei Lavoratori art. 4). Revisione settimanale durante il pilota, mensile a regime (Fase 3), che alimenta il backlog dell'handbook.

### Fase 2: assistente dedicato

```
Google Chat app (DM / @menzione)   oppure   Web app interna (SSO Google)
                 └──────────────┬──────────────┘
                                ▼
                 Backend Python (Cloud Run): LangGraph 2-step RAG
                 riformulazione query → retrieval (stessi tool MCP) → risposta con citazioni → gate confidenza
                                ▼
                 Claude via Vertex AI (EU) / Bedrock EU, prompt caching sull'handbook
                                ▼
                 Tracing MLflow (self-hosted) + feedback 👍/👎 + gap log
```

- **Riusa il server MCP della Fase 1** come retrieval layer. Nessuna logica duplicata.
- **Workflow, non agente:** ogni domanda richiede retrieval, quindi basta un 2-step RAG (LANGCHAIN_GUIDE §14; DEEP_AGENTS_GUIDE §19: Deep Agents è lo strumento sbagliato per Q&A brevi).
- **Google Chat vs web app:** Google Chat vince su adozione (i dipendenti sono già lì) e autenticazione (l'identità Workspace arriva già verificata) e non richiede una UI. La web app vince su UI ricca e controllo. Raccomandazione: **Google Chat** [Medium]. Da confermare: l'inventario ha trovato ClickUp Chat molto attiva (40 canali). Quale chat usa davvero il team?
### 3.1 Proposta: quale modello e dove (Fase 2)

Research: `docs/research/05-modelli-open-self-hosted.md` (modelli) e `06-hosting-modello-self-hosted.md` (hosting e costi).

| Opzione | Modello | Dove | Costo/mese (stima, ~3.300 domande) | Docker | Quando sceglierla |
|---|---|---|---|---|---|
| **A (default)** | Claude Sonnet 5 / Haiku 4.5 | Vertex AI o Bedrock, regione UE | ~35–70 $ | API gestita (il nostro backend è in Docker) | Qualità migliore su risposte con citazioni, zero GPU da gestire |
| **B** | Qwen3.8-27B (Apache 2.0) o equivalente | API UE a consumo: Regolo.ai (Seeweb, Italia, zero data retention), OVH, Scaleway, Mistral | ~3–40 € | API gestita | Modello open e dati in Italia/UE, senza gestire GPU |
| **C** | Qwen3.8-27B-FP8 su vLLM (A/B test con Gemma 4 31B) | Seeweb RTX PRO 6000 (Italia) accesa solo in orario d'ufficio, oppure Cloud Run GPU europe-west4 | ~190–275 € (Seeweb in orario d'ufficio); Cloud Run ~700 $ | **Nostra immagine** vLLM, stesso `compose.yaml` in locale e in produzione | Solo con un vincolo formale "i dati non escono dalla nostra infrastruttura" |

- Modello piccolo, **Qwen3.6-35B-A3B** (GPU da 24–48 GB): più veloce, ma meno affidabile nel rispettare le regole. Modello grande, **Mistral Small 4** (europeo): 80–96 GB, sovradimensionato a questo traffico.
- Esclusi: Llama 4 (la licenza limita le aziende UE), TGI (repo archiviato), modelli nativi italiani (Minerva, Velvet: indietro su tool calling e lunghezza del contesto).
- **Decide il golden set:** A/B test tra A e B (o C) sulle stesse domande. Con un modello open serve in più il **controllo delle citazioni nell'orchestratore**: ogni citazione deve puntare a un testo che i tool hanno davvero restituito.
- **Cold start (C):** un 27–32B su vLLM impiega 1,5–5 minuti ad avviarsi, mentre Google Chat vuole una risposta entro ~30 s. Serve un warm-up programmato all'apertura dell'ufficio.
- **Server in ufficio** (DGX Spark ~5.000 €, RTX 5090 ~5.000 €): solo banco di prova, non produzione.
- **Un solo punto di contatto con il modello** nel backend: un modulo client con due implementazioni (Anthropic SDK e endpoint OpenAI-compatibile). Si cambia opzione via configurazione.
- Da verificare: modelli open su Vertex in regione UE, data center di Regolo per ogni modello, se Seeweb fattura i server spenti.

- **Proattività (Fase 2b):** messaggi al giorno 1/7/30/60/90 per i nuovi assunti e checklist 30/60/90 interrogabile.

## 4. Fasi di lavoro

### Fase 0: Prerequisiti e pulizia contenuti (nessun codice)
1. **Licenze:** un seat per persona. Valutare Claude Team al posto dei Max (decisione della direzione).
2. **Sicurezza:** togliere le password Wi-Fi in chiaro dalla pagina ClickUp e spostarle in un password manager o in un QR in ufficio.
3. **Correzioni handbook:** indirizzo legale unico, processo ferie unico (Factorial o form ClickUp), trascrizione testuale dei valori L.O.V.E., pagina Team compilata, "Luoghi utili" completata o rimossa, date scadute aggiornate, link mancanti nell'indice.
4. **Metadati per pagina:** owner (ruolo), data di ultima revisione, validità.
5. **Nuove pagine P0** (dettaglio in `04-handbook-gap-analysis.md`): chi fa cosa / a chi chiedere, canali di comunicazione e regole, tool e accessi, **policy di uso dell'AI** (tool approvati, dati ammessi nei prompt, AI literacy, informativa L. 132/2025), IT e sicurezza di base, note spese, cosa fa Digitiamo. La FAQ è P1 e nasce dal gap log.
6. **Guides:** decidere quali guide rendere pubbliche all'azienda (oggi sono personali).
7. **Golden set:** 30–50 domande reali con risposta attesa e pagina fonte, raccolte da HR e dai colleghi. Diventa il test di accettazione.
- **Uscita:** handbook "pulito" con owner, golden set pronto, decisione sulle licenze presa.

### Fase 1: MVP dentro Claude
1. Server MCP Python (SDK `mcp`, streamable-http in modalità stateless con risposte JSON, D10) con i 5 tool sopra. Handbook in memoria, Guides in SQLite FTS5, gap log su Firestore.
2. Job di sync ClickUp + Guides con redazione e hash.
3. Auth OAuth 2.1 con Google, dominio ristretto (MCP_SERVERS_GUIDE §17).
4. Deploy su Cloud Run EU, Docker (standard del team). Durante il pilota si controlla la metrica `container/billable_instance_time` per confermare che si resta nel free tier.
5. Skill `digitiamo-buddy` e guida di installazione di una pagina per i colleghi.
6. Eval: golden set eseguito contro i tool (Recall@5 del retrieval) e contro Claude con la Skill (correttezza e citazione corretta). Test "contesto vuoto": deve rifiutare.
7. Pilota con 3–4 persone per 2 settimane, poi rollout a tutti.
- **Uscita (gate):** ≥90% di risposte corrette con citazione sul golden set, 0 policy inventate, feedback del pilota raccolto. **Poi si decide se serve la Fase 2 e con quale canale.**

### Fase 2: Assistente dedicato (solo se il gate lo giustifica)
1. Backend LangGraph 2-step RAG + Claude API EU con prompt caching.
2. Google Chat app (o web app) con feedback 👍/👎 e "segnala errore".
3. Tracing MLflow con redazione PII e analytics aggregate. Eval CI con scorer `RetrievalGroundedness` e `Correctness` sul golden set (MLFLOW_GENAI_GUIDE §11, §29).
4. Disclosure "stai parlando con un'AI" (AI Act art. 50) e informativa ai lavoratori.
5. Fase 2b: nudge ai nuovi assunti e checklist 30/60/90.

### Fase 3: Governance continua (processo, non codice)
- Revisione mensile del gap log → nuove pagine o correzioni ("flag it or fix it", KCS).
- Alert sulle pagine con revisione scaduta (più di 6 mesi).
- KPI: vedi §6.

## 5. Dipendenze

| Dipendenza | Serve per | Chi |
|---|---|---|
| Decisione licenze Max → Team | D2, conformità | Direzione |
| Accesso API ClickUp (token di sola lettura) | Sync | Admin ClickUp |
| Progetto GCP + fatturazione | Hosting, Vertex AI | Admin Google |
| Owner di ogni pagina | Freschezza, escalation | HR (da confermare) |
| Consenso a rendere pubbliche le Guides | Fonte Guides | Joshua |
| Parere legale/DPO | Informativa AI, log, AI Act | Consulente esterno |

## 6. KPI

| KPI | Target iniziale |
|---|---|
| Correttezza con citazione (golden set) | ≥ 90% al gate Fase 1, ≥ 95% a regime (target di `03-onboarding-best-practices.md`) |
| Policy inventate | 0 |
| Domande senza fonte / settimana | trend in calo |
| Adozione (utenti attivi / mese) | ≥ 70% dei dipendenti |
| Feedback 👍 (Fase 2) | ≥ 80% |
| Pagine con revisione < 6 mesi | ≥ 90% |
| Nuovi assunti: "so a chi chiedere" (survey al giorno 30) | ≥ 4/5 |

## 7. Rischi

| Rischio | Livello | Mitigazione |
|---|---|---|
| Ban o violazione dei termini con Meridian | ALTO | D1, D2: niente Meridian, un seat per persona |
| Risposte inventate su policy HR (precedente Air Canada) | ALTO | Solo dalle fonti, citazione obbligatoria, rifiuto se manca la fonte, escalation dei temi sensibili, golden set |
| Contenuti vecchi o contraddittori | ALTO | Fase 0 di pulizia, owner e data di revisione, gap log |
| Password e dati sensibili indicizzati | ALTO | Rimozione dalla fonte e filtro di redazione nel sync |
| Log per persona = controllo a distanza (Statuto art. 4, Garante 2024) | MEDIO | Analytics aggregate, niente user id nel gap log, retention breve, parere del DPO |
| Connettore MCP esposto su internet | MEDIO | OAuth con dominio ristretto, sola lettura, nessun dato sensibile, rate limit |
| Seat Max: dati usati per il training se non si fa opt-out | MEDIO | Passaggio a Team, oppure opt-out obbligatorio documentato |
| Bus factor 1 (una sola persona costruisce) | MEDIO | Stack minimo (un servizio, SQLite), README e ADR |
| Obblighi normativi (L. 132/2025, AI Act art. 4 e 50) | MEDIO | Informativa e policy AI nell'handbook (Fase 0), verifica legale |
| Adozione bassa ("tanto chiedo a HR") | BASSO | Pilota, Skill semplice, lancio in riunione, Fase 2 in chat |

## 8. Esplicitamente fuori scope (per ora)

- Vector DB ed embeddings: si aggiungono quando l'eval sulle Guides mostra Recall@5 < 0,8.
- Multi-agente, Deep Agents, A2A: non servono per Q&A (MULTI_AGENT_ARCHITECTURE_DESIGN).
- ACL per sezione: tutte le fonti sono visibili a tutti i dipendenti. Si aggiungono se arrivano contenuti riservati.
- Scrittura su ClickUp o Factorial (es. aprire richieste ferie): tool di azione solo dopo una Fase 2 stabile.

## 9. Metodo di lavoro: GSD leggero (deciso)

1. `gsd-import` di questo `docs/PLAN.md`: niente roadmap o research da rifare, la research è già in `docs/research/`.
2. Fase 0 (contenuti, niente codice): i task si tracciano con `gsd-capture`.
3. Fase 1: `gsd-ai-integration-phase` (AI-SPEC con eval e guardrail, golden set come riferimento) → `gsd-mvp-phase` → `gsd-execute-phase` → `gsd-verify-work`.
4. Fase 2: stesso flusso, solo dopo il gate della Fase 1.
5. Piccoli task isolati (sync job, Skill, fix): `gsd-quick` / `gsd-fast`.

Alternative valutate e scartate: Spec Kit (manca il piano di eval già pronto), OpenSpec (pensato per il brownfield, rivalutarlo in Fase 2), BMAD (troppo pesante per una persona sola), Kiro (IDE diverso).

## 10. Domande aperte

1. Chat reale del team: Google Chat o ClickUp Chat? L'inventario vede 40 canali ClickUp attivi.
2. Budget per il passaggio a Claude Team?
3. CCNL applicato (serve per le pagine ferie, permessi e malattia)?
4. Chi è l'owner ufficiale dell'handbook?
5. Quali Guides rendere aziendali?
6. Esiste un vincolo formale di sovranità dei dati ("solo Italia" o "solo nostra infrastruttura")? Da questa risposta dipende la scelta tra l'opzione A e l'opzione B o C in §3.1.

---

**IN ATTESA DI CONFERMA:** procedere con questo piano? (sì / no / modifica)
