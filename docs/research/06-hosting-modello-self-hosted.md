# 06 — Hosting di un LLM open-weight: dove e a che costo

**Data:** 24/09/2026 · **Scope:** solo *dove* e *quanto costa* ospitare un modello open-weight in alternativa a Claude API (D6 di `PLAN.md`). La scelta del modello è coperta da un'altra research. Qui le taglie sono generiche: ~8B, ~24–32B, ~70B+/MoE.

Legenda confidenza: [High] fonte ufficiale letta · [Medium] fonte ufficiale parziale o terza parte coerente · [Low] stima o fonte non verificata.

---

## 0. TL;DR

1. **Con questo traffico il self-hosting non conviene economicamente.** 3.300 domande/mese sono ~14 ore di GPU realmente usate al mese. Qualsiasi GPU dedicata ne fattura da 220 (orario d'ufficio) a 730 (24/7). Utilizzo reale ≈ 2–6%. [High, aritmetica]
2. **Le API pay-per-token di modelli open in UE costano 3–40 €/mese**, meno di Claude (35–70 $/mese). Zero GPU da gestire. Opzione più "italiana": **Regolo.ai** (Seeweb). [High] prezzi · [Medium] localizzazione in Italia.
3. **GPU self-hosted più economica e in Italia:** Seeweb (Milano/Frosinone) L4 a 0,38 €/h → ~84 €/mese solo in orario d'ufficio, ~277 €/mese 24/7. [Medium]
4. **Cloud Run GPU non esiste in europe-west8 (Milano).** Solo europe-west1 (Belgio) per L4 ed europe-west4 (Olanda) per L4 e RTX PRO 6000. Il costo parte da ~230–313 $/mese in orario d'ufficio con L4. [High]
5. **Cold start:** 15–21 s per un 8B su Cloud Run con Ollama, fino a 1,5–5 min per un 32B con vLLM. È incompatibile con uno scale-to-zero "puro" per le taglie ≥24B. Serve un warm-up programmato. [Medium]
6. **On-prem a Varese** (DGX Spark ~5.000 €, RTX 5090 ora ~4.850–5.800 € la sola scheda): payback lunghissimo, bus factor 1, nessuno SLA. Ha senso solo come laboratorio. [Medium]

---

## 1. Ipotesi di carico

| Parametro | Valore | Nota |
|---|---|---|
| Domande/mese | 3.300 | ~150/giorno lavorativo, 22 giorni |
| Concorrenza | 1–3 | picchi in orario d'ufficio |
| Finestra d'uso | 9:00–19:00, lun–ven | ≈ **220 h/mese** |
| Token input/domanda | ~10.000 | handbook completo in contesto (~8k, D4) + sezioni Guides + system prompt |
| Token output/domanda | ~500 | risposta con citazioni |
| **Totale mensile** | **~33 M input + ~1,65 M output** | scala linearmente: con un contesto di 4k l'input scende a ~13 M |
| GPU realmente attiva | ~3.300 × ~15 s ≈ **14 h/mese** | per il self-hosting conta invece il tempo *acceso* |

Idle timeout: Cloud Run tiene viva un'istanza **~15 minuti** dopo l'ultima richiesta, e con le GPU (billing instance-based) quei 15 minuti si pagano ([Google Cloud Blog, AI cold starts](https://cloud.google.com/blog/topics/developers-practitioners/a-guide-to-ai-cold-starts-on-cloud-run)) [High]. A ~15 domande/ora l'istanza non scende mai a zero in orario d'ufficio. **Lo "scale-to-zero" costa quindi quanto l'"orario d'ufficio"**: la differenza vera è tra accendere la GPU solo nell'orario d'ufficio e tenerla accesa 24/7. [High, deduzione]

---

## 2. Dimensionamento GPU per taglia (solo VRAM, non qualità)

| Taglia | Peso FP8 | Peso 4-bit | GPU minima sensata | Note |
|---|---|---|---|---|
| ~8B | ~9 GB | ~5 GB | L4 24 GB, RTX 4000 Ada 20 GB | Comoda anche con contesto lungo |
| ~24–32B | ~27–33 GB | ~16–20 GB | L40S 48 GB (FP8) · L4 24 GB (4-bit, contesto stretto) | Su L4 la generazione è lenta (~10–15 tok/s) [Low] |
| ~70B dense | ~70 GB | ~40 GB | RTX PRO 6000 96 GB · H100 80 GB | Su L40S 48 GB solo a 4-bit, con poco spazio per la KV cache |
| MoE ~120B (tipo gpt-oss-120b) | — | ~63 GB (MXFP4) | RTX PRO 6000 96 GB · H100 80 GB | Tanti parametri, ma pochi attivi: veloce se sta in VRAM |

[Medium] stime standard (parametri × byte/parametro + margine KV cache).

---

## 3. Opzione 1 — Google Cloud

### 3.1 Cloud Run con GPU

- **GPU disponibili:** NVIDIA L4 (24 GB) e RTX PRO 6000 Blackwell (96 GB), una GPU per istanza ([docs GPU Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/gpu)) [High].
- **Regioni UE:** L4 in europe-west1 (Belgio) ed europe-west4 (Olanda). RTX PRO 6000 **solo** in europe-west4. **europe-west8 (Milano) ed europe-west12 (Torino) non sono supportate** [High]. Il servizio GPU andrebbe quindi fuori dall'Italia, anche se resterebbe in UE. L'MCP server può restare in west8.
- **Requisiti minimi:** L4 ≥ 4 vCPU e 16 GiB (consigliati 8 vCPU e 32 GiB). RTX PRO 6000 ≥ **20 vCPU e 80 GiB**. Billing instance-based obbligatorio. Quota iniziale: 3 L4 per regione [High].
- **Prezzi Tier 1** (europe-west1/west4 sono Tier 1) ([Cloud Run pricing](https://cloud.google.com/run/pricing)) [High]:
  - L4 senza zonal redundancy: **$0,0001867/s** (con ridondanza: $0,0002909/s)
  - RTX PRO 6000 senza ridondanza: **$0,00036522/s** (con ridondanza: $0,00056913/s)
  - vCPU: $0,000018/s · RAM: $0,000002/GiB-s (instance-based)
- **Cold start:** l'infrastruttura parte in ~5 s. A questo si aggiunge il caricamento del modello. Misure: **Llama 3.1 8B con Ollama 15–21 s** dall'istanza a zero alla prima parola ([Google, cold start Ollama](https://medium.com/google-cloud/ollama-on-cloud-run-with-gpu-in-less-than-20-seconds-d324abe33d80)). **32B FP8 con vLLM: 324 s, scesi a 91 s dopo ottimizzazione** ([Runpod blog](https://www.runpod.io/blog/cut-vllm-cold-starts-runpod-serverless)) [Medium]. Best practice: pesi su GCS scaricati in parallelo, oppure nell'immagine se < 10 GB, formato safetensors/GGUF ([best practices GPU](https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices)) [High].

**Costo mensile calcolato (senza zonal redundancy, free tier CPU/RAM trascurabile, ~5 $):**

| Configurazione | $/h | Orario ufficio (220 h) | 24/7 (730 h) |
|---|---|---|---|
| L4 + 4 vCPU / 16 GiB | 1,05 | **~230 $** | ~764 $ |
| L4 + 8 vCPU / 32 GiB | 1,42 | **~313 $** | ~1.037 $ |
| RTX PRO 6000 + 20 vCPU / 80 GiB | 3,19 | **~701 $** | ~2.327 $ |

Coerente con l'esempio ufficiale "Ollama su L4 in europe-west1, picco 2 istanze" = 822 $/mese [High].

**Pattern "orario d'ufficio":** Cloud Scheduler porta `min-instances=1` alle 8:45 e lo riporta a `0` alle 19:15, così il primo utente non paga il cold start. Fuori orario lo scale-to-zero resta attivo e la prima domanda aspetta 20 s–2 min. [Medium, pattern standard, non un feature nativo]

**Ops per un solo sviluppatore:** basso. È lo stesso stack del MCP server (Docker, Cloud Run). **GDPR:** Cloud Data Processing Addendum di Google, residenza UE. Google però è un provider USA (CLOUD Act) [High].

### 3.2 Compute Engine (VM G2 con L4)

- `g2-standard-8` (1× L4, 8 vCPU, 32 GB): da ~621 $/mese 24/7 nella regione più economica ([CloudPrice](https://cloudprice.net/gcp/compute/instances/g2-standard-8)) [Medium]. Con uno *instance schedule* limitato all'orario d'ufficio si arriva a **~190–220 $/mese**, disco incluso [Low].
- Più economico di Cloud Run di ~30%, ma OS, driver, patch e TLS/ingress sono a carico tuo. Disponibilità di G2 in europe-west8: **da verificare** [Low].

### 3.3 GKE

Stesso costo GPU di Compute Engine più la gestione del cluster. Per un servizio da 1–3 utenti concorrenti è complessità senza beneficio. **Scartato.** [High, giudizio]

### 3.4 Vertex AI Model Garden (self-deploy su endpoint)

- Deploy "a un click" di modelli open su un endpoint dedicato: si paga il nodo con la GPU per ogni ora in cui è acceso, più la maggiorazione di Vertex.
- Lo scale-to-zero esiste (`min_replica_count=0`, API v1beta1), ma **le richieste durante il cold start ricevono un 429** ([autoscaling Vertex](https://docs.cloud.google.com/vertex-ai/docs/predictions/autoscaling)) [Medium]. Per una chat è pessimo.
- Realisticamente è un endpoint sempre acceso da **~700–1.000+ $/mese** con una L4 [Low]. **Scartato** per questo carico.

---

## 4. Opzione 2 — GPU cloud europee (self-hosted)

| Provider | Sede DC | GPU / prezzo | Orario ufficio (220 h) | 24/7 | Scale-to-zero | DPA | Fonte |
|---|---|---|---|---|---|---|---|
| **Seeweb** Cloud Server GPU | **Milano, Frosinone** (anche Lugano, Zurigo, Sofia) | L4 24 GB **0,38 €/h** · L40S 48 GB 0,85 €/h · RTX PRO 6000 96 GB 1,25 €/h | **84 € · 187 € · 275 €** | 277 € · 620 € · 912 € | No (VM oraria; spegnimento/distruzione via API/IaC) | Sì, azienda italiana [Medium] | [seeweb.it](https://www.seeweb.it/en/products/cloud-server-gpu) [Medium] |
| **Aruba** server dedicati GPU | Italia (DC Aruba) | RTX 4070S 193,75 €/mese · RTX 4080S 276,83 €/mese · L40S 922,28 €/mese (IVA esclusa) | — (canone fisso) | come a sinistra | No | Sì [Medium] | [HWUpgrade](https://edge9.hwupgrade.it/news/cloud/sperimentare-con-l-ai-privata-coi-server-gpu-di-aruba-e-facile-ed-economico_138607.html) [Medium, prezzi forse datati] |
| **Hetzner** GEX | Germania (NBG/FSN), Finlandia (HEL) | GEX44 RTX 4000 Ada 20 GB **184 €/mese** · GEX131 RTX PRO 6000 96 GB 889–1.199 €/mese + setup | — | 184 € · 889–1.199 € | No | Sì (AVV) [High] | [whtop](https://www.whtop.com/plans/hetzner.com/128304), [gpuhosted](https://gpuhosted.com/en/hetzner-gpu-review/) [Medium] |
| **Scaleway** GPU Instance | Parigi | L4 **0,75 €/h** | 165 € | 548 € | No | Sì [High] | [Holori](https://calculator.holori.com/scaleway/vm/L4-1-24G) [Medium] |
| **Scaleway** Managed Inference (dedicato) | Parigi | L4 0,93 €/h · L40S 1,72 €/h · H100 3,40 €/h | — | 679 € · 1.255 € · 2.482 € | No | Sì [High] | [Scaleway MaaS](https://www.scaleway.com/en/pricing/model-as-a-service/) [High] |
| **OVHcloud** AI Deploy | Francia (Gravelines) | L4 ~0,91 $/h · L40S ~1,69 $/h | ~200 $ | ~664 $ | Sì (autoscaling) [Low] | Sì [High] | [cloudgpuprices](https://cloudgpuprices.com/vendors/ovhcloud) [Low] |
| **Koyeb** (dal 2026 Mistral AI) serverless GPU | UE (Parigi/Francoforte) [Medium] | L4 0,70 $/h · L40S 1,20 $/h al secondo | ~154 $ · ~264 $ | 511 $ · 876 $ | **Sì** | Sì [Medium] | [Koyeb pricing](https://www.koyeb.com/pricing), [TechCrunch](https://techcrunch.com/2026/02/17/mistral-ai-buys-koyeb-in-first-acquisition-to-back-its-cloud-ambitions/) [Medium] |
| **Hugging Face** Inference Endpoints | AWS eu-west-1 (Irlanda) e altre | L4 0,80 $/h · L40S 1,80 $/h | ~176 $ | 584 $ | **Sì** (dopo 15 min idle) | Sì (Enterprise) [Medium] | [Spheron](https://www.spheron.network/blog/hugging-face-inference-endpoints-pricing-2026/) [Medium] |
| **Nebius** | Finlandia, Francia | L40S da 1,55 $/h · H100 3,85 $/h | ~341 $ | 1.132 $ | No | Sì [Medium] | [nebius.com/prices](https://nebius.com/prices) [Medium] |
| **Runpod** Serverless | alcuni DC UE [Low] | A6000 ~1,22 $/h equiv., al secondo | variabile | — | **Sì** (flex worker) | azienda USA, DPA da verificare [Low] | [Aliteq](https://aliteq.com/runpod-serverless-pricing-explained-2026) [Medium] |

**Note:**
- **Seeweb** è il migliore per costo × sovranità: Italia (Milano) e azienda italiana. Da verificare se un server *spento* continua a essere fatturato. Se sì, bisogna distruggerlo e ricrearlo ogni giorno via Terraform/API, e il volume con i pesi va tenuto separato [Low].
- **Hetzner GEX44** è l'"always-on" più economico per un 8B (184 €/mese flat), ma in Germania o Finlandia. Tutto a carico tuo: OS, driver, sicurezza [High].
- I serverless (Koyeb, HF, Runpod) hanno lo stesso problema di cold start di Cloud Run, spesso peggiore (minuti) per modelli ≥24B [Medium].

---

## 5. Opzione 3 — API pay-per-token di modelli open, ospitate in UE (nessuna GPU)

Costo mensile = 33 M token input × prezzo input + 1,65 M token output × prezzo output (ipotesi §1).

| Provider | Sede / residenza | Esempi (€ o $ per M token in/out) | Costo mensile stimato | DPA / retention | Fonte |
|---|---|---|---|---|---|
| **Regolo.ai** (Seeweb) | DC Seeweb UE (Italia, Svizzera, Bulgaria) [Medium] | qwen3.5-9b 0,07/0,35 · qwen3.8-27b 0,50/2,10 · gemma4-31b 0,40/2,10 · mistral-small-4-119b 0,50/2,10 · gpt-oss-120b 1,00/4,20 · apertus-70b 0,40/2,10 | **~3 € (9B) · ~17–20 € (27–31B) · ~20 € (119B MoE) · ~40 € (gpt-oss-120b)** | **Zero Data Retention**, DPA, ISO 27001/27018 [Medium] | [regolo.ai/pricing](https://regolo.ai/pricing/) [High] |
| **OVHcloud AI Endpoints** | Francia | Qwen3.5-9B 0,10/0,15 · Qwen3.8-27B 0,40/2,70 · gpt-oss-120b 0,08/0,40 · Llama-3.3-70B 0,67/0,67 | **~3,5 € · ~18 € · ~3,3 € · ~23 €** | DPA OVH [High] | [catalogo OVH](https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/) [High] |
| **Scaleway Generative APIs** | **Solo Parigi** | Qwen3.8-27B 0,60/3,30 · gpt-oss-120B 0,15/0,60 · Llama 3.3 70B 0,90/0,90 · Mistral Medium 3.5 1,50/7,50 | **~25 € · ~6 € · ~31 € · ~62 €** (primo 1 M token gratis) | Zero Data Retention di default, DPA [High] | [Scaleway MaaS](https://www.scaleway.com/en/pricing/model-as-a-service/), [privacy](https://www.scaleway.com/en/docs/generative-apis/reference-content/data-privacy/) [High] |
| **Mistral La Plateforme** | UE di default | Small 4 $0,15/0,60 · Large 3 $0,50/1,50 · Medium 3.5 $1,50/7,50 | **~6 $ · ~19 $ · ~62 $** | DPA; ZDR solo sul piano Scale [Medium] | [BenchLM](https://benchlm.ai/mistral/api-pricing), [DPA Mistral](https://legal.mistral.ai/terms/data-processing-addendum/) [Medium] |
| **Vertex AI MaaS** (open) | endpoint globale o regionale (+~10%) | gpt-oss-120b $0,09/0,36 (global) | ~4–5 $ | Cloud DPA Google [High] | [Spheron/Vertex](https://www.spheron.network/blog/vertex-ai-model-garden-pricing-2026-cost-vs-self-hosted/) [Medium]. **Disponibilità in una regione UE per i modelli open: non verificata** [Low] |
| **Amazon Bedrock** (open) | gpt-oss in Milano, Irlanda, Londra, Stoccolma · Qwen3 in Francoforte | Qwen3 32B $0,15/0,60 (tariffa USA) | ~6 $ | AWS GDPR DPA [High] | [AWS what's new](https://aws.amazon.com/about-aws/whats-new/2025/09/open-ai-open-weight-models-new-regions-aws-bedrock), [AWS](https://aws.amazon.com/about-aws/whats-new/2025/10/deepseek-openai-qwen-models-amazon-bedrock-additional-regions) [Medium] |

- I piani flat di Regolo (Core 39 €/mese con 600 M token) non servono: il consumo reale è ~35 M. Pay-as-you-go [High].
- Tutte queste API sono **OpenAI-compatible**. Il backend LangGraph della Fase 2 cambia solo `base_url` e modello [High per Regolo, Scaleway, OVH].
- Il prompt caching, dove esiste, abbassa ancora il costo dell'input (Scaleway, per esempio, fattura il cached a 0,08 €/M su alcuni modelli) [Medium].
- **Cold start: nessuno.** Latenza da API normale [High].

---

## 6. Opzione 4 — On-prem nell'ufficio di Varese

| Hardware | Capex (set. 2026) | Taglie gestibili | Consumo stimato | Fonte |
|---|---|---|---|---|
| **NVIDIA DGX Spark** (GB10, 128 GB unificata) | **~4.900–5.200 € netti** (partner da 4.889 €) | 8B–32B bene. MoE 120B ok. 70B dense lento (banda ~273 GB/s) [Medium] | ~40 W idle, ~240 W picco | [pi3g](https://pi3g.com/nvidia-dgx-spark-price/) [Medium] |
| **RTX 5090** 32 GB + PC | scheda **4.850–5.800 €** (crisi memorie) + ~2.000 € PC | 8B–32B 4-bit veloci. 70B no | ~80 W idle, ~600 W carico | [Tom's HW](https://www.tomshardware.com/pc-components/gpus/nvidias-top-end-rtx-5090-gaming-gpu-now-costs-at-least-usd5-000-blackwell-cards-continue-to-endure-drastic-price-hikes), [HDblog](https://www.hdblog.it/hardware/articoli/n645244/crisi-memorie-rtx-5090-prezzi-aumento/) [Medium] |
| **Mac Studio M3 Ultra** (96–512 GB) | da **5.099 €**, oltre 10.000 € con 256–512 GB | fino a 70B+ e MoE grandi, prefill lento [Medium] | basso (~100–200 W) | [HDblog](https://www.hdblog.it/apple/articoli/n610941/mac-studio-m3-ultra-prezzo-massimo/) [Medium] |

**TCO mensile (ammortamento in 36 mesi):**
- DGX Spark: ~140 €/mese di ammortamento + energia ~44 kWh × ~0,30 €/kWh ≈ **13 €** (media ~60 W) → **~155 €/mese** [Low]. Energia PMI 2026 volatile: PUN fino a ~0,19–0,21 €/kWh ad agosto 2026 più oneri ([PMI.it](https://www.pmi.it/economia/mercati/486775/prezzi-energia-2026-pun-psv-imprese.html)) [Medium].
- RTX 5090 workstation: ~190–220 €/mese di ammortamento + ~20–25 € di energia → **~215–245 €/mese** [Low].

**Esposizione:** il backend su Cloud Run deve raggiungere la macchina in ufficio.
- Con **Cloudflare Tunnel**: gratis, ma il TLS termina su Cloudflare (azienda USA), quindi il testo delle domande transita su un terzo.
- Con **Tailscale/WireGuard**: cifratura end-to-end, nessun terzo vede i dati.

[Medium]

**Rischi:** connessione e corrente dell'ufficio senza SLA, nessuna ridondanza, sicurezza fisica, aggiornamenti di driver/OS, bus factor 1 (già MEDIO in `PLAN.md` §7). È il massimo della sovranità (i dati non lasciano l'azienda) e il massimo del carico operativo. [High, giudizio]

---

## 7. Confronto riassuntivo

| Opzione | Costo/mese a questo carico | Residenza | Azienda UE? | DPA | Ops (solo dev) | Cold start / UX |
|---|---|---|---|---|---|---|
| **Claude API via Vertex/Bedrock EU** (piano attuale) | **35–70 $** | UE | No (USA) | Sì | Minimo | Nessuno |
| API open pay-per-token (Regolo / OVH / Scaleway / Mistral) | **3–40 €** (fino a ~62 € per un modello "medium") | UE, Italia possibile con Regolo | **Sì** | Sì | Minimo | Nessuno |
| Cloud Run GPU L4 (west1/west4) | 230–313 $ orario ufficio · 764–1.037 $ 24/7 | UE, **non Italia** | No | Sì | Basso | 15–20 s (8B) fuori orario, minuti (≥24B) |
| Cloud Run RTX PRO 6000 (west4) | ~701 $ orario ufficio · ~2.327 $ 24/7 | UE (Olanda) | No | Sì | Basso | 1–5 min per 70B/MoE senza warm-up |
| Compute Engine G2 L4 schedulato | ~190–220 $ · ~620 $+ 24/7 | UE | No | Sì | Medio | Nessuno in orario (VM accesa) |
| Vertex AI endpoint dedicato | ~700–1.000+ $ | UE | No | Sì | Basso | 429 durante il cold start: non adatto |
| **Seeweb GPU** | L4 84 € · L40S 187 € · RTX PRO 6000 275 € (orario ufficio) | **Italia** | **Sì (IT)** | Sì | Medio-alto | Nessuno in orario, se accesa dallo scheduler |
| Hetzner GEX44 / GEX131 | 184 € / 889–1.199 € flat | DE/FI | Sì | Sì | Alto (bare metal) | Nessuno (sempre acceso) |
| Koyeb / HF / Runpod serverless | ~150–260 $ orario ufficio | UE | misto | misto | Basso-medio | Come Cloud Run o peggio |
| On-prem Varese | ~155–245 € ammortizzati | **ufficio** | — | non serve | **Alto** | Nessuno, ma nessuno SLA |

### 7.1 Vincolo "tutto dockerizzato" (stessa immagine in locale e in prod)

Il vincolo riguarda i **nostri** componenti: MCP server, backend e, se c'è self-hosting, il server di inferenza. Con un'API gestita il modello non è un nostro container. Si dockerizza il backend che la chiama, e in locale il `docker compose` punta alla stessa API, oppure a un container vLLM/Ollama che espone lo stesso endpoint OpenAI-compatible (basta cambiare `base_url` via env). [High]

| Opzione | Gira la nostra immagine Docker? | Come vengono esposte le GPU al container | Parità locale ↔ prod |
|---|---|---|---|
| Claude API, Regolo, OVH AI Endpoints, Scaleway Generative APIs, Mistral, Vertex MaaS, Bedrock | **No**, API gestita senza container. Il nostro backend Docker la chiama | — | Alta: stessa immagine, cambia solo l'env (`base_url`, chiave). In locale si può sostituire con un container Ollama per i test offline |
| **Cloud Run GPU** | **Sì**: immagine OCI da Artifact Registry (es. `vllm/vllm-openai`, `ollama/ollama` o una nostra immagine derivata) | Gestito da Google: driver NVIDIA 580.x montato nel container, nessun toolkit da installare ([docs](https://docs.cloud.google.com/run/docs/configuring/services/gpu)) [High] | Alta: stessa immagine. In locale `docker compose` con `deploy.resources.reservations.devices: [driver: nvidia]` se c'è una GPU, altrimenti Ollama su CPU |
| Compute Engine G2, Seeweb, Scaleway GPU Instance, Hetzner, Aruba, Nebius (VM o bare metal) | **Sì**: `docker compose up` sulla VM | Driver NVIDIA + **NVIDIA Container Toolkit** sull'host (`--gpus all` / `runtime: nvidia`). Su GCP la COS/Deep Learning VM li ha già. Su Seeweb, Hetzner e Aruba li installiamo noi (Scaleway li preinstalla nelle immagini GPU) [Medium] | **Massima**: lo stesso `compose.yaml` in locale e sul server |
| Vertex AI endpoint dedicato | Sì, *custom container* (o il container vLLM di Model Garden) | Gestito da Vertex [High] | Media: servono il contratto health/predict di Vertex e un deploy diverso da compose |
| Koyeb, Runpod Serverless | Sì, immagine Docker. Runpod richiede un handler worker nel suo formato, oppure il worker vLLM già pronto | Gestito dal provider [Medium] | Media-alta (Runpod aggiunge l'handler specifico) |
| HF Inference Endpoints, Scaleway Managed Inference, OVH AI Deploy | HF: immagine TGI/vLLM o *custom container*. OVH AI Deploy: immagine Docker nostra. Scaleway Managed: solo modelli dal catalogo o custom, niente container nostro [Medium] | Gestito [Medium] | Media |
| On-prem Varese | Sì: `docker compose` sulla workstation | NVIDIA Container Toolkit (Linux). **DGX Spark** ha DGX OS con Docker e il toolkit preinstallati [Medium]. **Mac Studio: Docker non vede la GPU Apple** (Metal non passa nel container) [High], quindi l'inferenza gira nativa, fuori da Docker, e il vincolo è violato | Alta su NVIDIA, **nulla su Mac** |

**Effetto sulla raccomandazione:** il vincolo Docker **rafforza** la scelta API gestita più backend Docker, perché l'immagine è identica ovunque e cambia solo l'env. In caso di self-hosting, le opzioni più coerenti col vincolo sono **Cloud Run GPU** (immagine vLLM, zero driver da gestire) e **VM con Docker + NVIDIA Container Toolkit** (Seeweb, lo stesso `compose.yaml` del locale). **Mac Studio è escluso** dal vincolo. [Medium]

**Nota UX:** le app di Google Chat devono rispondere a un evento entro ~30 s, altrimenti bisogna rispondere in modo asincrono [Medium]. Un cold start di minuti costringe a mandare un "sto pensando…" seguito da un messaggio asincrono.

---

## 8. Raccomandazione per taglia

| Taglia | Se basta "UE + DPA" | Se serve "Italia + azienda UE" | Self-host solo se… |
|---|---|---|---|
| **~8B** | OVH o Regolo pay-per-token (~3 €/mese) | **Regolo** qwen3.5-9b (~3 €/mese) | Seeweb L4 in orario d'ufficio (~84 €) o Hetzner GEX44 (184 €). Qualità in italiano da validare con l'altra research |
| **~24–32B** | OVH Qwen3.8-27B (~18 €) o Scaleway (~25 €) | **Regolo** qwen3.8-27b o gemma4-31b (~17–20 €) | Seeweb L40S o RTX PRO 6000 in orario d'ufficio (187–275 €). Cloud Run RTX PRO 6000 west4 (~700 $) solo per restare tutto su GCP |
| **~70B+ / MoE** | OVH gpt-oss-120b (~3 €) · Scaleway (~6 €) · Mistral Large 3 (~19 $) | **Regolo** mistral-small-4-119b (~20 €) o gpt-oss-120b (~40 €) | Seeweb RTX PRO 6000 (275 € in orario d'ufficio, 912 € 24/7). Sconsigliato |

**Raccomandazione complessiva [Medium]:**
1. **Nessun self-hosting in Fase 2.** Con 3.300 domande/mese si pagano GPU inattive al 94–98%. Il costo è 4–30 volte quello di Claude, più ops e cold start.
2. **Tenere Claude come default** (D6). Il backend va scritto *OpenAI-compatible* o con un adattatore, con **Regolo.ai** come alternativa "sovrana" (Italia, ZDR, 3–40 €/mese). Si attiva se la direzione o il DPO richiedono un fornitore non USA, oppure se l'eval sul golden set dà un modello open ≥ al target del 90%.
3. **Se il self-hosting diventa un requisito formale** (dati solo in Italia, fornitore italiano, niente API terze): **Seeweb RTX PRO 6000** (o L40S per ≤32B) a Milano, accesa dallo scheduler 8:45–19:15, vLLM in Docker. Stima 190–275 €/mese più ~1 giorno/mese di manutenzione. Cloud Run GPU è l'alternativa a ops minime, ma è fuori dall'Italia (Olanda) e costa 2–3 volte tanto.
4. **On-prem** (DGX Spark, Docker e toolkit NVIDIA preinstallati) solo come banco di prova per l'eval dei modelli, non in produzione. Mac Studio escluso dal vincolo Docker (§7.1).

---

## 9. Da verificare prima di decidere

- Seeweb: si paga un server GPU spento? C'è un DPA standard? Si può scegliere il DC di Milano su tutte le GPU?
- Regolo: il DC effettivo per ogni modello (Italia o Svizzera/Bulgaria) e la possibilità di fissarlo per contratto.
- Vertex AI MaaS: disponibilità dei modelli open in una regione UE (non solo sull'endpoint globale).
- Disponibilità di G2/L4 su Compute Engine in europe-west8.
- Il parere del DPO: "UE + DPA" basta o serve "Italia + fornitore UE"? Questa risposta decide tra la riga 2 e la riga 3 della raccomandazione.

## Fonti

- Cloud Run GPU: https://docs.cloud.google.com/run/docs/configuring/services/gpu
- Cloud Run pricing: https://cloud.google.com/run/pricing
- Cloud Run GPU best practices: https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices
- Guida cold start AI su Cloud Run: https://cloud.google.com/blog/topics/developers-practitioners/a-guide-to-ai-cold-starts-on-cloud-run
- Ollama su Cloud Run in < 20 s: https://medium.com/google-cloud/ollama-on-cloud-run-with-gpu-in-less-than-20-seconds-d324abe33d80
- Cold start vLLM 32B: https://www.runpod.io/blog/cut-vllm-cold-starts-runpod-serverless
- Autoscaling / scale-to-zero Vertex: https://docs.cloud.google.com/vertex-ai/docs/predictions/autoscaling
- g2-standard-8: https://cloudprice.net/gcp/compute/instances/g2-standard-8
- Seeweb GPU: https://www.seeweb.it/en/products/cloud-server-gpu
- Regolo pricing: https://regolo.ai/pricing/ · Regolo e Seeweb: https://www.datamanager.it/2026/04/regolo-ai-e-seeweb-linferenza-europea-che-trasforma-la-compliance-di-euraika/
- Scaleway MaaS: https://www.scaleway.com/en/pricing/model-as-a-service/ · privacy: https://www.scaleway.com/en/docs/generative-apis/reference-content/data-privacy/
- Scaleway L4: https://calculator.holori.com/scaleway/vm/L4-1-24G
- OVH AI Endpoints: https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/ · OVH GPU: https://cloudgpuprices.com/vendors/ovhcloud
- Hetzner: https://www.hetzner.com/dedicated-rootserver/matrix-gpu/ · https://www.whtop.com/plans/hetzner.com/128304 · https://gpuhosted.com/en/hetzner-gpu-review/
- Aruba: https://edge9.hwupgrade.it/news/cloud/sperimentare-con-l-ai-privata-coi-server-gpu-di-aruba-e-facile-ed-economico_138607.html
- Koyeb: https://www.koyeb.com/pricing · acquisizione Mistral: https://techcrunch.com/2026/02/17/mistral-ai-buys-koyeb-in-first-acquisition-to-back-its-cloud-ambitions/
- HF Endpoints: https://www.spheron.network/blog/hugging-face-inference-endpoints-pricing-2026/
- Nebius: https://nebius.com/prices
- Runpod serverless: https://aliteq.com/runpod-serverless-pricing-explained-2026
- Mistral pricing: https://benchlm.ai/mistral/api-pricing · DPA: https://legal.mistral.ai/terms/data-processing-addendum/
- Vertex MaaS: https://www.spheron.network/blog/vertex-ai-model-garden-pricing-2026-cost-vs-self-hosted/
- Bedrock open-weight nelle regioni UE: https://aws.amazon.com/about-aws/whats-new/2025/09/open-ai-open-weight-models-new-regions-aws-bedrock · https://aws.amazon.com/about-aws/whats-new/2025/10/deepseek-openai-qwen-models-amazon-bedrock-additional-regions
- DGX Spark: https://pi3g.com/nvidia-dgx-spark-price/
- RTX 5090: https://www.tomshardware.com/pc-components/gpus/nvidias-top-end-rtx-5090-gaming-gpu-now-costs-at-least-usd5-000-blackwell-cards-continue-to-endure-drastic-price-hikes
- Mac Studio: https://www.hdblog.it/apple/articoli/n610941/mac-studio-m3-ultra-prezzo-massimo/
- Energia PMI 2026: https://www.pmi.it/economia/mercati/486775/prezzi-energia-2026-pun-psv-imprese.html
