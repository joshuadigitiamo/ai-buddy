# 05 — Modelli open-weight self-hosted per la Fase 2

**Data:** 2026-09-24 · **Ambito:** alternativa alla Claude API (decisione D6 di `PLAN.md`) per il bot dedicato della Fase 2.
**Fuori ambito:** dove ospitare e quanto costa (lo copre un altro documento). Qui si danno solo i requisiti di VRAM.

Legenda di confidenza: `[High]` = fonte primaria (model card / repo ufficiale); `[Medium]` = più fonti secondarie concordi; `[Low]` = fonte singola o stima mia.

---

## 0. Requisiti del caso d'uso (cosa conta davvero)

| Requisito | Implicazione sul modello |
|---|---|
| Handbook ~8k token sempre in contesto + 3–6 sezioni Guides | Serve un contesto utile di **~32k token**. Quasi tutti i modelli 2026 arrivano a 128k–256k, quindi non è un filtro. |
| Risposte in italiano, registro professionale | Qualità dell'italiano **generato**, non solo capito. |
| Citazioni obbligatorie + rifiuto se manca la fonte | Contano faithfulness e instruction following più di MMLU o dei benchmark di coding. |
| Tool calling (`handbook_get`, `guides_search`, ecc.) | Parser di tool call maturo in vLLM/SGLang. Loop brevi (1–3 chiamate). |
| ~3.300 domande/mese, 1–3 utenti in contemporanea | Il throughput non è un problema. Contano latenza a richiesta singola e **costo di una GPU accesa 24/7**. |
| Licenza | Uso commerciale interno libero, **nessun blocco UE**. |

---

## 1. Panorama dei candidati (stato al settembre 2026)

### 1.1 Modelli generalisti

| Modello | Uscita | Parametri (totali / attivi) | Licenza | Contesto | Tool calling | VRAM pesi FP8 / 4-bit (stima) |
|---|---|---|---|---|---|---|
| **Qwen3.8-27B** (dense) | ago 2026 | 27B | Apache 2.0 `[High]` | 262k `[High]` | Sì, parser `qwen3_coder` in vLLM/SGLang `[High]`. IFBench 79,5 `[High]` | ~28 GB / ~17 GB. Esiste un checkpoint ufficiale `-FP8` `[High]` |
| **Qwen3.6-27B** (dense) | apr 2026 | 27B | Apache 2.0 `[High]` | 262k | Sì, `qwen3_coder` `[High]` | ~28 GB / ~17 GB |
| **Qwen3.6-35B-A3B** (MoE) | apr 2026 | 35B / 3B | Apache 2.0 `[High]` | 262k | Sì `[High]` | ~35 GB (FP8 ufficiale) / ~21 GB (Q4_K_M, sta su una 24 GB) `[Medium]` |
| Qwen3.5-122B-A10B (MoE) | feb 2026 | 122B / 10B | Apache 2.0 `[High]` | 256k | Sì | ~122 GB / ~65 GB |
| Qwen3.5-9B / 4B | mar 2026 | 9B / 4B | Apache 2.0 `[High]` | 256k | Sì (da 4B in su) `[Medium]` | ~9 GB / ~6 GB |
| **Gemma 4 31B** (dense) | apr 2026 | 30,7B | **Apache 2.0** (prima c'erano i Gemma Terms) `[High]` | 256k `[High]` | Nativo `[High]` | ~31 GB / ~19 GB |
| Gemma 4 26B-A4B (MoE) | apr 2026 | 26B / 3,8B | Apache 2.0 `[High]` | 256k | Nativo | ~26 GB / ~15 GB |
| Gemma 4 12B / E4B / E2B | apr 2026 | 12B / 4,5B / 2,3B | Apache 2.0 | 256k / 128k | Nativo | ≤12 GB |
| **Mistral Small 4** (MoE) | mar 2026 | 119B / 6,5B | Apache 2.0 `[High]` | 256k `[High]` | Sì, parser `mistral` `[High]` | ~111 GB (FP8 ufficiale) / ~60–65 GB (NVFP4 ufficiale): servono 80–96 GB `[Medium]` |
| Mistral Medium 3.5 (dense) | apr 2026 | 128B | MIT modificata, con soglia di fatturato per le grandi aziende `[Medium]` | 256k | Sì | ~128 GB / ~70 GB. Essendo dense, è lento |
| Ministral 3 14B / 8B / 3B | dic 2025 | 14B / 8B / 3B | Apache 2.0 `[High]` | 256k | Nativo; italiano esplicitamente supportato `[High]` | ~14 GB / ~9 GB |
| **gpt-oss-120b** (MoE) | ago 2025 | 117B / 5,1B | Apache 2.0 `[High]` | 128k | Forte (formato Harmony) `[High]` | MXFP4 nativo: 80 GB, cioè 1× H100 `[High]` |
| gpt-oss-20b (MoE) | ago 2025 | 21B / 3,6B | Apache 2.0 `[High]` | 128k | Forte | ~12–16 GB `[High]` |
| DeepSeek V4-Flash (MoE) | lug 2026 | 284B / 13B | MIT `[Medium]` | 1M | Sì | ~284 GB FP8: fuori scala per questo caso |
| Llama 4 Scout / Maverick | 2025 | 109B / 17B · 400B / 17B | Llama 4 Community: **restrizioni per aziende UE** (almeno sulla parte multimodale) `[Medium]` | 10M / 1M | Sì | **Escluso**: rischio di licenza per un'azienda italiana |
| Muse Glimmer 30B (Meta) | ago 2026 | 30B | Apache 2.0 (secondo una sola fonte) `[Low]` | 128k | ? | ~30 GB. Da verificare prima di considerarlo |

### 1.2 Modelli "italiani"

| Modello | Parametri | Licenza | Contesto | Tool calling | Note |
|---|---|---|---|---|---|
| **Minerva-7B-instruct** (Sapienza NLP) | 7B | Apache 2.0 `[High]` | breve (≤4–8k) `[Low]` | Non documentato | Addestrato da zero con ~50% di italiano. Ottimo come ricerca, ma come agente non basta: contesto troppo corto per handbook + guide, niente tool calling. |
| **Velvet-14B** (Almawave) | 14B | Apache 2.0 `[High]` | 128k `[High]` | Sì, BFCL AST 67,5 `[High]` | Uscito a gen 2025. Punteggi IT modesti (MMLU-IT 58,6) `[High]`: una generazione dietro Qwen e Gemma 2026. |
| **Domyn-Small** (Domyn, ex iGenius; deriva da Italia 10B) | 10B | MIT `[High]` | 32k nativo, 131k con YaRN `[High]` | Sì: BFCL v3 non-live 75,9, live 68,3, **multi-turn 7,0** `[High]` | Molto efficiente nei token, ma il multi-turn debole è un problema per un loop agentico. |
| **EngGPT2** (Engineering) | 16B / 3B MoE | open-weight, licenza da verificare `[Low]` | ? | ? | ~25% del corpus in italiano. Gli autori dichiarano prestazioni pari a dense 8–16B `[Medium]`. |
| Italia-10B / Colosseum-355B (Domyn) | 10B / 355B | Italia: NIM; Colosseum: on-prem enterprise `[Medium]` | 16k (Italia) | ? | Il canale commerciale è enterprise, non adatto a <15 dipendenti. |

**Giudizio sui modelli italiani `[Medium]`:** conoscono bene lingua e cultura, ma nel 2026 restano indietro proprio dove questo progetto chiede di più: tool use, contesto lungo e instruction following. Anche la stampa di settore lo ammette ("gap su capacità agentica e tool use", Tom's Hardware 2026). Per un QA con citazioni e tool conviene un generalista multilingue forte. Un modello italiano ha senso solo se diventa un requisito di sovranità o di marketing.

### 1.3 Qualità dell'italiano: cosa sappiamo e cosa no

- **Evalita-LLM** (leaderboard HF, CLiC-it 2025) e **ItaEval / ITA-Bench** esistono, ma le versioni pubbliche valutano soprattutto modelli 2024–2025. Nel few-shot guidava **Gemma 3** (CPS medio 57,42) `[Medium]`. I modelli open più aggiornati **non risultano valutati** su un benchmark italiano indipendente. **Evidenza insufficiente** per ordinare Qwen3.8, Gemma 4 e Mistral Small 4 sull'italiano. `[High]` sul fatto che manchino dati.
- Segnali indiretti: Gemma 4 31B ha MMMLU (multilingue) 88,4 `[High]`. Qwen dichiara 201 lingue. Mistral è storicamente forte su FR/DE/IT/ES e Ministral 3 elenca l'italiano tra le lingue supportate `[Medium]`.
- Impressione della comunità: Mistral e Gemma scrivono un italiano più naturale, Qwen è più forte su ragionamento e tool, ma a volte ha un registro rigido o lascia calchi dall'inglese `[Low]`.
- **Conseguenza operativa:** la scelta finale si fa sul **golden set della Fase 1** (lo stesso del gate ≥90% corrette con citazione), non sui benchmark.

---

## 2. Shortlist a 3 livelli

### Piccolo: **Qwen3.6-35B-A3B** (alternativa: Gemma 4 26B-A4B)
- **Perché:** MoE con 3B attivi, quindi molto veloce anche con una sola GPU. Apache 2.0, tool calling con parser ufficiale in vLLM, contesto 262k, checkpoint FP8 ufficiale.
- **VRAM:** FP8 su una GPU da 48 GB (ad es. L40S), oppure Q4 su una da 24 GB (L4 da 24 GB o RTX 4090), con un contesto di 32k.
- **Rischi:** con pochi parametri attivi la faithfulness sulle regole sottili dell'handbook è più fragile `[Medium]`. L'alternativa Gemma 4 26B-A4B probabilmente scrive un italiano migliore `[Low]`: vanno confrontati tutti e due.

### Medio (**raccomandato**): **Qwen3.8-27B** in FP8 (alternativa A/B: **Gemma 4 31B**)
- **Perché:** è il dense più recente (ago 2026), Apache 2.0, con checkpoint FP8 ufficiale. IFBench 79,5 lo rende il migliore della fascia nel seguire le istruzioni, cioè nel rispettare "cita sempre, rifiuta se non c'è la fonte". Tool calling nativo con `qwen3_coder`. Un modello dense è più prevedibile di un MoE piccolo nel grounding `[Medium]`.
- **VRAM:** ~28 GB di pesi FP8 + KV cache per 32k × 3 sequenze, quindi **1 GPU da 48 GB** (L40S / RTX 6000 Ada), oppure 4-bit su 24 GB con un margine stretto.
- **Gemma 4 31B** come contendente, per l'italiano (MMMLU 88,4) e la licenza ora Apache 2.0. Stessa fascia di VRAM.
- **Accorgimento:** disattivare o limitare il "thinking" (`reasoning_effort` basso, oppure solo la modalità non-thinking) per ridurre latenza e verbosità. Per un QA su documenti il ragionamento lungo aggiunge poco `[Medium]`.

### Grande: **Mistral Small 4 (119B-A6.5B)** (alternativa: gpt-oss-120b)
- **Perché:** è europeo (utile per GDPR e per la narrativa della sovranità), Apache 2.0, forte sulle lingue europee, 256k di contesto, reasoning attivabile per singola richiesta. Solo 6,5B attivi, quindi è veloce nonostante i 119B totali.
- **VRAM:** NVFP4 ufficiale in 80–96 GB (1× H100 80 GB con un margine stretto, oppure RTX Pro 6000 96 GB). In FP8 servono ~111 GB, cioè H200 141 GB o 2× 80 GB.
- **gpt-oss-120b** in alternativa: su una sola H100 con MXFP4, tool calling tra i più solidi degli open, ma l'italiano è meno curato dei concorrenti europei `[Low]`.
- **Onestamente:** per ~110 domande al giorno questa fascia è **sovradimensionata**. Si giustifica solo se il medio non passa il gate.

**Scartati:** Llama 4 (licenza UE), Mistral Medium 3.5 (dense da 128B, lento, licenza con carve-out), DeepSeek V4 (troppo grande), Minerva (contesto e tool), Velvet e Domyn-Small (di una generazione dietro sui tool e sul multi-turn).

---

## 3. Stack di serving

| Engine | API OpenAI-compatibile | Tool calling | Adatto a 1–3 utenti? | Note |
|---|---|---|---|---|
| **vLLM** | Sì `[High]` | Parser dedicati: `qwen3_coder`, `mistral`, Harmony per gpt-oss, `--enable-auto-tool-choice` `[High]` | Sì. Sovradimensionato come throughput, ma è lo standard | Ha ricette ufficiali per Qwen3.6 e Mistral Small 4 (recipes.vllm.ai). Il **prefix caching** fa risparmiare molto, perché l'handbook da 8k è un prefisso fisso a ogni richiesta. **Consigliato.** |
| **SGLang** | Sì `[High]` | Stessi parser di Qwen `[High]` | Sì | RadixAttention riusa i prefissi in modo ancora più aggressivo. Sui loop agentici ha latenza leggermente migliore `[Medium]`. Alternativa valida a vLLM. |
| **Ollama** | Sì (`/v1`) `[High]` | Sì, tramite il template del modello `[Medium]` | Sì, a bassa concorrenza va bene `[Medium]` | È il più semplice. Però usa GGUF (quantizzazione di solito 4-bit), il parsing dei tool dipende dal template e sotto carico degrada molto (41 contro 793 tok/s rispetto a vLLM nel benchmark Red Hat 2026) `[Medium]`. Ottimo per prototipi e dev locale. |
| **llama.cpp** (`llama-server`) | Sì `[High]` | Sì, con template Jinja `[Medium]` | Sì | Gira su CPU o GPU piccole. Controllo fine sulla quantizzazione GGUF. È il motore sotto Ollama. |
| **TGI** (Hugging Face) | Sì | Sì | — | **In maintenance mode dal 11/12/2025 e repo archiviato il 21/03/2026** `[High]`. **Escluso**: HF stessa consiglia vLLM o SGLang. |

**Raccomandazione:** **vLLM** in produzione (immagine Docker ufficiale `vllm/vllm-openai`) e **Ollama** o llama.cpp per lo sviluppo locale. L'API è OpenAI-compatibile, quindi l'orchestratore della Fase 2 cambia solo `base_url` e modello. Due cautele. Primo, i tool MCP vanno esposti come function schema OpenAI (un adapter MCP→OpenAI tools nell'orchestratore), perché vLLM non parla MCP nativamente `[High]`. Secondo, lo scale-to-zero ha un cold start di minuti: bisogna caricare 20–30 GB di pesi `[Medium]`. Chi si occupa dell'hosting deve tenerne conto.

---

## 4. Divario onesto rispetto a Claude

| Aspetto | Valutazione | Confidenza |
|---|---|---|
| Tool calling in loop brevi (1–3 chiamate, pochi tool) | Divario piccolo. I top open 2026 sono a 3–4 punti dai modelli chiusi su BFCL v4 | `[Medium]` |
| Seguire "cita sempre la fonte nel formato X" | Buono su Qwen3.8 e Gemma 4. Serve un formato di citazione rigido (id sezione + URL restituiti dal tool) e una validazione lato orchestratore | `[Medium]` |
| **Rifiutare quando la fonte non c'è** (0 policy inventate) | È **il divario più grande**. Gli open ~30B tendono di più a "completare" con conoscenza generale plausibile, soprattutto su domande HR e policy. Serve un gate esterno (controllo che ogni citazione punti a un chunk recuperato + soglia di retrieval) | `[Medium]` |
| Qualità dell'italiano scritto | Buona nei modelli ~30B, con qualche calco e un registro meno naturale di Claude. Accettabile per un QA interno | `[Low]` (mancano benchmark indipendenti 2026) |
| Contesto lungo (8k handbook + 10–20k guide) | Nessun problema reale a 32k per i modelli 2026 | `[Medium]` |
| Robustezza a domande ambigue e multi-turn | Inferiore. Riformulare le query e chiedere chiarimenti riesce meno bene | `[Medium]` |
| Gate ≥90% corrette con citazione, 0 inventate | **Raggiungibile** con Qwen3.8-27B o Gemma 4 31B **più un guardrail di citazione**. Senza guardrail, "0 inventate" è a rischio | `[Low]`: va misurato sul golden set |

**Nota sui costi, senza sovrapposizioni con l'altro documento:** a 3.300 domande al mese D6 stima 35–70 $/mese per la Claude API. Una GPU da 24–48 GB accesa 24/7 costa di solito un ordine di grandezza in più `[Medium]`. Il self-hosting quindi **non si giustifica sul costo** a questo volume. Si giustifica solo per sovranità dei dati, requisiti contrattuali o dipendenza zero dal fornitore.

---

## 5. Embeddings (se si esce da FTS5)

`PLAN.md` usa **SQLite FTS5**. Con ~15 guide da ~100 KB, il BM25 più una buona divisione per sezioni probabilmente basta: gli embedding vanno aggiunti solo se il golden set mostra errori di recall su parafrasi. In quel caso:

| Modello | Licenza | Note |
|---|---|---|
| **Qwen3-Embedding-0.6B / 4B / 8B** | Apache 2.0 | L'8B guida MTEB/MMTEB tra gli open (~70 su MTEB multilingue) `[Medium]`. **Lo 0.6B gira su CPU** ed è la scelta pragmatica. |
| **bge-m3** (568M) | MIT | Dense + sparse + multi-vector in un solo modello, 8k di contesto, ottimo per il retrieval ibrido con FTS5 `[Medium]`. |
| multilingual-e5-large-instruct | MIT | Solido e collaudato, un gradino sotto i due precedenti `[Medium]`. |

**Consiglio:** **bge-m3** se si vuole il retrieval ibrido (lo sparse si integra con BM25), altrimenti **Qwen3-Embedding-0.6B**. Entrambi girano su CPU a questo volume. Un reranker è facoltativo.

---

## 6. Raccomandazione

1. **Default: resta la Claude API (D6).** A questo volume costa meno e ha il grounding migliore `[Medium]`.
2. **Se serve self-hosting:** **Qwen3.8-27B-FP8 su vLLM**, su una sola GPU da 48 GB, con thinking limitato e parser `qwen3_coder`. **Gemma 4 31B** va messo in A/B sul golden set italiano, con decisione solo sui numeri.
3. **Guardrail obbligatorio** per qualunque modello open: validare che ogni citazione corrisponda a un chunk restituito dal tool, e rifiutare in automatico se il retrieval non trova niente sopra la soglia.
4. Se il medio non passa il gate: salire a **Mistral Small 4** (NVFP4, 80–96 GB).

---

## Fonti

- Qwen3.8 / 3.6 / 3.5, repo ufficiale: https://github.com/QwenLM/Qwen3.8
- Qwen3.8-27B, model card: https://huggingface.co/Qwen/Qwen3.8-27B
- Qwen3.6-27B, model card: https://huggingface.co/Qwen/Qwen3.6-27B
- Qwen3.6-35B-A3B FP8: https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8 · ricetta vLLM: https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B
- Qwen 3.5–3.8, panoramica: https://codersera.com/blog/qwen-3-5-complete-guide-2026/
- Gemma 4 31B, model card: https://huggingface.co/google/gemma-4-31B · annuncio: https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/
- Mistral Small 4: https://huggingface.co/mistralai/Mistral-Small-4-119B-2603 · ricetta vLLM: https://recipes.vllm.ai/mistralai/Mistral-Small-4-119B-2603
- Mistral Medium 3.5: https://huggingface.co/mistralai/Mistral-Medium-3.5-128B
- Ministral 3: https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512-BF16
- gpt-oss: https://github.com/openai/gpt-oss · https://developers.openai.com/cookbook/articles/gpt-oss/run-vllm
- DeepSeek V4-Flash: https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash
- Llama 4, licenza UE: https://ioplus.nl/en/posts/european-union-excluded-from-llama-4-multimodal-models · https://codersera.com/blog/llama-4-complete-guide-2026/
- Lista curata di modelli open-weight (licenze, UE): https://github.com/xigh/open-weight-models
- Velvet-14B: https://huggingface.co/Almawave/Velvet-14B
- Minerva-7B-instruct: https://huggingface.co/sapienzanlp/Minerva-7B-instruct-v1.0
- Domyn-Small (arXiv 2607.20448): https://huggingface.co/papers/2607.20448
- EngGPT2 (arXiv 2603.16430): https://arxiv.org/abs/2603.16430
- Mappa degli LLM italiani 2026: https://www.tomshw.it/business/llm-italiani-mappa-minerva-italia-10b-velvet-domyn-2026
- Evalita-LLM leaderboard: https://huggingface.co/spaces/evalitahf/evalita_llm_leaderboard · paper: https://pith.science/paper/2502.02289
- Leaderboard italiana (CLiC-it 2025): https://aclanthology.org/2025.clicit-1.61.pdf
- BFCL: https://gorilla.cs.berkeley.edu/leaderboard.html · https://www.spheron.network/blog/tool-calling-benchmarks-bfcl-tau-bench-latency-optimization/
- llama.cpp vs vLLM (Red Hat, 2026): https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine
- vLLM, Ollama, llama.cpp e SGLang sotto carico: https://pub.towardsai.net/vllm-vs-ollama-vs-llama-cpp-vs-sglang-ollama-collapses-to-41-tokens-under-load-8f7a850d1e07
- TGI in maintenance mode: https://github.com/huggingface/text-generation-inference · https://www.spheron.network/blog/migrate-tgi-to-vllm-sglang-2026/
- Embeddings: https://arxiv.org/abs/2502.13595 (MMTEB) · https://www.codesota.com/benchmarks/mteb · https://presenc.ai/research/best-open-weight-embedding-models-2026
- RAG faithfulness (FaithJudge): https://aclanthology.org/2025.emnlp-industry.54/
