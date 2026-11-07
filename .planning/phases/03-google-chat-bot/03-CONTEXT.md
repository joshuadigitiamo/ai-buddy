# Phase 3: Google Chat Bot - Context

**Gathered:** 2026-11-07
**Status:** Ready for planning

<domain>
## Phase Boundary

`services/chat_bot`: a Google Chat bot for Joshua only (`ALLOWED_USERS`). It answers in Italian through a LangGraph 2-step RAG workflow, calling the Phase 2 MCP server over HTTP as an MCP client. Events arrive through Pub/Sub in dev and through HTTP with Google JWT checks on Cloud Run; both sit behind one intake interface. Every answer either cites a source the tools returned in that run or refuses with "Non lo so, chiedi a …" and logs a gap. Sensitive topics get only the general written rule plus a referral to a person. Guides answers with a mapped video show a card with a "Guarda" button. Covers BOT-01..BOT-11.

Out of this phase: Cloud Run deploy, CI, kind manifests (Phase 4); golden set, MLflow scoring (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (not re-discussed)
- Phase 2 D-06: MCP tools return structured output (`source_url`, `revision_date`, `video_url`, `text`, …); the bot reads these fields, never the prose rendering.
- Phase 2 D-08: no match = `status: "no_results"`, not an MCP error.
- Phase 2 D-10: gap log never stores user identity (no user id, email, IP, session id).
- Phase 2 D-12: the bot authenticates to the MCP server with a Google-signed ID token minted by its service account. D-13: `AUTH_MODE=off` only off Cloud Run.
- Phase 1 D-21: the Guides index is English. The bot bridges Italian → English keywords for `guides_search` (the Skill already has the bridge table).
- PROJECT D1a: Meridian only for Joshua as the single user. D4/D5: no vector DB. D11: the bot holds no retrieval logic of its own. D15: video shown as thumbnail + "Guarda" button.

### Confidence and citation gate
- **D-01:** The gate has two independent signals. (a) Deterministic: refuse if every tool returned `no_results` or the citation check fails. (b) LLM: the answer step returns structured output with a `grounded` flag and a `confidence` score; the bot refuses below a threshold set by env.
- **D-02:** Citation check matches on source id. The model cites by `source_url` (`handbook://<page_id>` or the Guides permalink). Every cited id must be among the `source_url`s the tools returned in this run, and the bot renders the links itself, never the model. No quoted-span check.
- **D-03:** When the gate fails, the bot retries once: it reformulates with different keywords or the other source, retrieves again and answers again. If that also fails, it replies `Non lo so, chiedi a <referente>.` and calls `buddy_report_gap`.
- **D-04:** The referente comes from the shared topic → role table (D-08). The bot resolves the actual contact through `handbook_search` and quotes it exactly as the handbook writes it; with no row match it falls back to HR. No names come from model memory or the repo.

### Sensitive topics
- **D-05:** Detection is done by the LLM inside the reformulation step, which outputs a structured `sensitive_topic` field: one of the table's rows, or none. There is no keyword list.
- **D-06:** For a sensitive question the bot still retrieves. It answers with only the general written rule, cited, plus "per il tuo caso specifico chiedi a <referente>". If no rule is found it replies with the referral only. It never assesses an individual situation (BOT-06).
- **D-07:** A sensitive question with no rule found is logged to the gap log like any other gap (question text, no user identity).
- **D-08:** The topic → role table moves out of `skills/digitiamo-buddy/SKILL.md` into a shared data file (YAML; location chosen by the planner, e.g. `packages/buddy_core` or `skills/`). The bot reads it; SKILL.md stays in sync, enforced by a test that fails on drift. — **Reversibility:** costly — the Skill and the bot both depend on the file's shape.

### Conversation flow
- **D-09:** The bot posts a placeholder ("Sto cercando nelle fonti…") at once, then updates that same message through the Chat API with the answer or card. The path is the same for Pub/Sub and HTTP: the HTTP handler acks fast and finishes in the background. This covers BOT-10 without racing the 30 s window.
- **D-10:** Thread context is persisted in Firestore (EU) through a LangGraph checkpointer or an equivalent store behind a port. — **Reversibility:** costly — introduces stored conversation data and a privacy posture to revisit before rollout.
- **D-11:** Memory safeguards (BOT-11 / art. 4; the conflict was raised in discussion and accepted with these limits):
  - The key is `HMAC(thread name, secret from env)`; the raw space, thread or user id is never stored.
  - Only the last N turns are kept, and a Firestore TTL expires them after **24 h**.
  - No sender fields (name, email, user id) are stored.
  - This posture must be re-checked before a second user (add to the rollout checklist).
- **D-12:** History (the last **3** Q/A) goes only to the reformulation step, to turn a follow-up into a standalone query. The answer step sees only this run's retrieval and never earlier answers, so BOT-05 holds.
- **D-13:** Messages that aren't questions get canned replies with no LLM call: `ADDED_TO_SPACE` → a short Italian intro; slash command `/aiuto` → usage text. Everything else goes into the RAG flow.
- **D-14:** The reformulation step also outputs `intent: question | chitchat | off_topic`. Only company questions with no source are gap-logged. Chit-chat or off-topic messages get a polite no-source reply and no gap entry.

### Dev wiring
- **D-15:** Live dev uses a real GCP project: the Chat app is configured to publish to a Pub/Sub topic, and the bot consumes a pull subscription from compose or kind, so no public URL is needed. Automated tests use the Pub/Sub emulator in Docker with recorded Chat event JSON fixtures. Uses the Pub/Sub free tier.
- **D-16:** Meridian runs in its own compose service: a pinned Node image, with Joshua's Max credentials mounted read-only from the host config dir and never baked into an image. The bot uses it as the Anthropic `base_url` (`http://meridian:<port>`). The `api` backend uses the same Anthropic Messages client with an API key (BOT-07).
- **D-17:** Two models: Haiku 5.5 (`claude-haiku-5-5`) for reformulate/classify (standalone query, English keywords, `intent`, `sensitive_topic`), and Sonnet 5.5 (`claude-sonnet-5-5`) for the cited answer plus `grounded`/`confidence`. Both model ids come from env so Phase 5 can A/B them.
- **D-18:** The last plan ends with a live Chat checkpoint: Joshua DMs the bot scripted questions (one answerable from the handbook, one from the Guides with a video, one sensitive, one with no source) and confirms the results. The checkpoint may be deferred to Phase 4 if GCP setup blocks it (as with 02-07).

### Claude's Discretion
- Card layout (cardsV2 structure, multi-source answers, thumbnail source) and the exact Italian strings, following BOT-09 and the Skill answer template.
- Graph node layout and naming, the structured-output schemas, the default confidence threshold and default N turns kept.
- Pub/Sub ack and redelivery handling, and idempotency on duplicate events.
- Config shape (pydantic-settings, as in `jobs/sync` and `mcp_server`) and env var names.
- How the startup guard enforces BOT-08 (the bot refuses to start with `meridian` and more than one allowed user).
- The intake port design (one interface, a Pub/Sub adapter and an HTTP+JWT adapter).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and plan
- `.planning/REQUIREMENTS.md` — BOT-01..BOT-11
- `.planning/ROADMAP.md` — Phase 3 goal, 5 success criteria, Guides applied (D16)
- `.planning/PROJECT.md` — locked D1/D1a, D4, D5, D6, D9 (the bot checks citations), D11, D13, D15, D16; privacy posture; constraints
- `docs/PLAN.md` — §2 and §2.1 decisions (D1a, D13), bot architecture

### Phase 2 contract (the bot consumes it)
- `.planning/phases/02-mcp-server-and-skill/02-CONTEXT.md` — D-06 output contract, D-08 no_results, D-10 gap log, D-12/D-13 auth
- `services/mcp_server/buddy_mcp/models.py` — `HandbookPageResult`, `GuidesSectionResult` (`video_url`), `*Output` models, `GapReportOutput`
- `services/mcp_server/buddy_mcp/auth.py` — `ServiceAccountIdTokenVerifier` (what the bot's token must satisfy)
- `services/mcp_server/README.md` — env contract, how to run the server
- `skills/digitiamo-buddy/SKILL.md` — keyword bridge (IT→EN), answer template, refusal phrase, "Temi da escalare" table (moves to a shared file per D-08), "Finding the referente"

### Best practices (D16) — `~/Desktop/WORK/Guides/`
- `AI-Engineering/LangChain/LANGGRAPH_GUIDE.md` — 2-step RAG workflow, structured output, checkpointer
- `AI-Engineering/LangChain/LANGCHAIN_GUIDE.md` — citations the model sees, model and client setup
- `AI-Engineering/RAG_CHATBOT_GUIDE.md` — confidence gate, refusal, citation grounding
- `AI-Engineering/MCP_SERVERS_GUIDE.md` — client side (streamable-http, auth header)
- `Foundations/DESIGN_PATTERNS_GUIDE.md` — pluggable LLM client (strategy), intake transport port, adapters
- The plan cites exact sections and justifies exceptions (section numbers not yet verified).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/mcp_server/buddy_mcp/models.py`: typed tool outputs; the bot can import or mirror these to parse `structuredContent`.
- `buddy_core` models: `video_link` composes `url#t=<s>` for the scene clip. There is **no thumbnail field** in the index today; the researcher must find a source for BOT-09's thumbnail (derive it from the video asset, a static image, or omit it) without changing `index.db` 1.0.0 unless that is justified.
- The `GapLog` port and Firestore emulator setup from Phase 2 show the pattern to follow for the thread-memory store (D-10).

### Established Patterns
- A port plus one adapter, with fakes in tests (ArtifactStore, GapLog). Apply it to the intake transport, LLM client, MCP client and memory store.
- pydantic-settings config; errors name variables, never values.
- Pinned `==` deps; ruff, mypy --strict and pytest in Docker via `run-unit-tests.sh`; `docker-compose.test.yml` already has a `firestore` emulator service. Add Pub/Sub emulator and Meridian services.
- Composition root `python -m <pkg>` with a real-process emulator test (as in 02-07).

### Integration Points
- `services/chat_bot/` is empty. It is a new package and gets its own Dockerfile stage.
- MCP server URL and audience from env; the ID token comes from the bot's service account (D-12).
- `buddy_report_gap` is called by the bot on refusal (D-03, D-07).

</code_context>

<specifics>
## Specific Ideas

- Placeholder text: "Sto cercando nelle fonti…"; refusal: `Non lo so, chiedi a <referente>.`; sensitive suffix: "per il tuo caso specifico chiedi a <referente>".
- Live checkpoint scripted with 4 question types: handbook, Guides+video, sensitive, no source.

</specifics>

<deferred>
## Deferred Ideas

- Re-check the thread-memory privacy posture (D-11) before any second user. Add it to the rollout checklist next to the `LLM_BACKEND` switch (D1a).
- Card layout refinements (multi-source carousel and similar): Claude's discretion now; revisit after Phase 5 feedback.

</deferred>

<amendments>
## Amendments (03-01 checkpoint)

- D-16 overridden by 03-01 checkpoint: meridian_credentials (b) — dedicated Docker named volume seeded once by copying the host credentials file, writable only by the Meridian container, never baked into an image, host ~/.claude untouched
- D-11 overridden by 03-01 checkpoint: memory_key (b) — DM spaces use HMAC(space name), rooms use HMAC(thread name); still HMAC with THREAD_KEY_SECRET, no raw id stored, same 24 h TTL and N turns
- D-09 overridden by 03-01 checkpoint: http_ack (b) — await the run inside the request for up to 25 s, then return `{}` and let any remainder continue in the background
- BOT-09 interpreted by 03-01 checkpoint: bot09_rendering (2a+2c) — handbook source link is a text citation `Manuale – <title> (handbook://<page_id>), revisione <YYYY-MM-DD>` until CONT-01 gives a URL; `VIDEO_THUMBNAIL_URL` is a required HTTPS setting (value supplied via .env at the 03-12 live checkpoint)
- D-10 interpreted by 03-01 checkpoint: dev_firestore (a) — dev compose uses the Firestore emulator for thread memory and the gap log; Firestore EU stays the deployed store
- D-07 interpreted by 03-01 checkpoint: gap_question (b) — the gap log stores the standalone question from the reformulation step, not the raw message text
</amendments>

---

*Phase: 03-google-chat-bot*
