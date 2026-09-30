# Costi di hosting del server MCP su Cloud Run

*Data: 2026-09-30 · Fonti: pagine prezzi ufficiali Google Cloud · Confidenza: High sui numeri, Medium sulle stime di traffico*

## Sintesi

Il server MCP della Fase 1 costa **~0 €/mese** con scale-to-zero e billing request-based, al traffico previsto (<15 persone, ~10–20k richieste/mese). Serve comunque un account di fatturazione attivo. L'unico rischio di costo concreto sono le connessioni lunghe (stream SSE di MCP), che tengono l'istanza fatturata: si evita con il server in modalità stateless e risposte JSON.

## Free tier Cloud Run (request-based billing)

Dalla [pagina prezzi di Cloud Run](https://cloud.google.com/run/pricing):

- "CPU - First **180,000 vCPU-seconds** free per month"
- "RAM - First **360,000 GiB-seconds** free per month"
- "Requests - **2 million requests** free per month"
- "The free tier usage is aggregated across projects by billing account and resets every month"
- "The free tier is applied as a spending based discount using Tier 1 pricing"
- **europe-west8 (Milano) è Tier 1**, quindi lo sconto copre per intero i prezzi di Milano.
- Si fattura solo il tempo in cui l'istanza elabora almeno una richiesta, arrotondato ai 100 ms.
- Le richieste negate da IAM non si pagano.

Prezzi Tier 1 oltre il free tier: CPU $0.000024/vCPU-s attivo, $0.0000025 idle (solo min-instances); memoria $0.0000025/GiB-s; $0.40 per milione di richieste.

Per i job (sync notturno come Cloud Run Job): free tier di 240,000 vCPU-s e 450,000 GiB-s al mese ([stessa pagina](https://cloud.google.com/run/pricing)).

## Servizi di contorno

Da [Free Tier features](https://docs.cloud.google.com/free/docs/free-cloud-features) e [Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing):

| Servizio | Free tier | Uso previsto |
|---|---|---|
| Cloud Scheduler | 3 job al mese per billing account | 1 job (sync notturno) |
| Artifact Registry | 0,5 GB di storage al mese | 1 immagine Python slim, da tenere sotto 0,5 GB con cleanup delle vecchie versioni |
| Firestore | 1 GiB storage, 50k letture e 20k scritture al giorno per progetto | gap log: poche scritture al giorno |
| Secret Manager | 6 versioni attive, 10k accessi al mese | token ClickUp, client OAuth |
| Cloud Build | 2.500 build-minute al mese (e2-standard-2) | build dell'immagine |

"A Google Cloud billing account is required to access the Google Cloud Free Tier." Serve quindi la decisione 05 (progetto GCP con fatturazione).

Cloud Storage **non** va bene per il gap log a costo zero: il suo free tier vale solo in us-east1, us-west1 e us-central1.

## Stima di consumo

Inferenza, non misurata:

- **Caso normale:** 20k richieste × ~0,5 s × 1 vCPU ≈ 10k vCPU-s, circa il 6% del free tier. Richieste: l'1% della quota.
- **Rischio stream lunghi:** con request-based billing l'istanza si paga finché c'è una richiesta aperta. Il transport streamable-http di MCP può tenere aperto uno stream SSE. Se il client lo tiene aperto per tutto l'orario d'ufficio (10 h × 22 giorni ≈ 792k s), si esce dal free tier: ~15 $/mese a 1 vCPU. Non ho verificato come si comporta il client di claude.ai [Low]. **Mitigazione:** server MCP stateless con risposte JSON, senza stream persistenti. Poi va controllata la metrica `container/billable_instance_time` durante il pilota.
- **min-instances=1** (per evitare il cold start): tariffa idle ~$0.0000025/s per vCPU e per GiB. Tenuto acceso tutto il mese: ~6–10 $/mese [stima]. Acceso solo in orario d'ufficio: ~2–3 $.

## Lacune

- Cold start di un container Python piccolo: nessuna fonte ufficiale con numeri. Di solito sono pochi secondi [Low].
- Comportamento del client MCP di claude.ai sugli stream SSE: non verificato.
- Egress: il free tier Cloud Run di 1 GB vale "from North America". Il traffico da Milano verso Anthropic è comunque di pochi MB (testo), quindi pochi centesimi al massimo [Medium].

## Fonti

1. [Cloud Run pricing](https://cloud.google.com/run/pricing) — free tier, prezzi Tier 1/2, lista regioni, regole di fatturazione
2. [Google Cloud Free Tier features](https://docs.cloud.google.com/free/docs/free-cloud-features) — limiti di Artifact Registry, Firestore, Secret Manager, Cloud Build e Cloud Storage; obbligo del billing account
3. [Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing) — 3 job gratis per billing account
