# Phase 3: Google Chat Bot - Research

**Researched:** 2026-11-07
**Domain:** Python 3.12 Google Chat bot (Pub/Sub + HTTP intake), LangGraph 2-step RAG, MCP client, Anthropic Messages client (Meridian or API key), Firestore thread memory, cardsV2 rendering
**Confidence:** MEDIUM-HIGH (stack and in-repo contracts HIGH; Chat event details, Meridian behaviour and Chat card limits MEDIUM, flagged in the Assumptions Log)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
(copied from `03-CONTEXT.md` `## Implementation Decisions`; the planner MUST honor these)

**Carried forward (not re-discussed)**
- Phase 2 D-06: MCP tools return structured output (`source_url`, `revision_date`, `video_url`, `text`, ...); the bot reads these fields, never the prose rendering.
- Phase 2 D-08: no match = `status: "no_results"`, not an MCP error.
- Phase 2 D-10: gap log never stores user identity (no user id, email, IP, session id).
- Phase 2 D-12: the bot authenticates to the MCP server with a Google-signed ID token minted by its service account. D-13: `AUTH_MODE=off` only off Cloud Run.
- Phase 1 D-21: the Guides index is English. The bot bridges Italian -> English keywords for `guides_search` (the Skill already has the bridge table).
- PROJECT D1a: Meridian only for Joshua as the single user. D4/D5: no vector DB. D11: the bot holds no retrieval logic of its own. D15: video shown as thumbnail + "Guarda" button.

**Confidence and citation gate**
- **D-01:** The gate has two independent signals. (a) Deterministic: refuse if every tool returned `no_results` or the citation check fails. (b) LLM: the answer step returns structured output with a `grounded` flag and a `confidence` score; the bot refuses below a threshold set by env.
- **D-02:** Citation check matches on source id. The model cites by `source_url` (`handbook://<page_id>` or the Guides permalink). Every cited id must be among the `source_url`s the tools returned in this run, and the bot renders the links itself, never the model. No quoted-span check.
- **D-03:** When the gate fails, the bot retries once: it reformulates with different keywords or the other source, retrieves again and answers again. If that also fails, it replies `Non lo so, chiedi a <referente>.` and calls `buddy_report_gap`.
- **D-04:** The referente comes from the shared topic -> role table (D-08). The bot resolves the actual contact through `handbook_search` and quotes it exactly as the handbook writes it; with no row match it falls back to HR. No names come from model memory or the repo.

**Sensitive topics**
- **D-05:** Detection is done by the LLM inside the reformulation step, which outputs a structured `sensitive_topic` field: one of the table's rows, or none. There is no keyword list.
- **D-06:** For a sensitive question the bot still retrieves. It answers with only the general written rule, cited, plus "per il tuo caso specifico chiedi a <referente>". If no rule is found it replies with the referral only. It never assesses an individual situation (BOT-06).
- **D-07:** A sensitive question with no rule found is logged to the gap log like any other gap (question text, no user identity).
- **D-08:** The topic -> role table moves out of `skills/digitiamo-buddy/SKILL.md` into a shared data file (YAML; location chosen by the planner, e.g. `packages/buddy_core` or `skills/`). The bot reads it; SKILL.md stays in sync, enforced by a test that fails on drift. - **Reversibility:** costly - the Skill and the bot both depend on the file's shape.

**Conversation flow**
- **D-09:** The bot posts a placeholder ("Sto cercando nelle fonti...") at once, then updates that same message through the Chat API with the answer or card. The path is the same for Pub/Sub and HTTP: the HTTP handler acks fast and finishes in the background. This covers BOT-10 without racing the 30 s window.
- **D-10:** Thread context is persisted in Firestore (EU) through a LangGraph checkpointer or an equivalent store behind a port. - **Reversibility:** costly - introduces stored conversation data and a privacy posture to revisit before rollout.
- **D-11:** Memory safeguards (BOT-11 / art. 4; the conflict was raised in discussion and accepted with these limits):
  - The key is `HMAC(thread name, secret from env)`; the raw space, thread or user id is never stored.
  - Only the last N turns are kept, and a Firestore TTL expires them after **24 h**.
  - No sender fields (name, email, user id) are stored.
  - This posture must be re-checked before a second user (add to the rollout checklist).
- **D-12:** History (the last **3** Q/A) goes only to the reformulation step, to turn a follow-up into a standalone query. The answer step sees only this run's retrieval and never earlier answers, so BOT-05 holds.
- **D-13:** Messages that aren't questions get canned replies with no LLM call: `ADDED_TO_SPACE` -> a short Italian intro; slash command `/aiuto` -> usage text. Everything else goes into the RAG flow.
- **D-14:** The reformulation step also outputs `intent: question | chitchat | off_topic`. Only company questions with no source are gap-logged. Chit-chat or off-topic messages get a polite no-source reply and no gap entry.

**Dev wiring**
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

### Deferred Ideas (OUT OF SCOPE)
- Re-check the thread-memory privacy posture (D-11) before any second user. Add it to the rollout checklist next to the `LLM_BACKEND` switch (D1a).
- Card layout refinements (multi-source carousel and similar): Claude's discretion now; revisit after Phase 5 feedback.

Out of this phase: Cloud Run deploy, CI, kind manifests (Phase 4); golden set, MLflow scoring (Phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOT-01 | Dev: Chat events (DM, @mention) via Pub/Sub subscription, reply in chat | Pub/Sub streaming-pull adapter bridged to asyncio; both Chat event formats normalized; emulator test (sections Architecture, Code Examples) |
| BOT-02 | HTTP endpoint verifies Google JWT on every request; one intake interface | Starlette adapter + `google.oauth2.id_token.verify_oauth2_token`; issuer email and audience from env; `IntakePort` (Architecture, Pitfall 7) |
| BOT-03 | `ALLOWED_USERS` guard before any MCP/LLM call | Guard runs in `BotService.handle` before the graph; matches `user.name` (`users/<id>`) or `user.email`; silent drop (Pitfall 3, Validation) |
| BOT-04 | LangGraph 2-step RAG (reformulate, retrieve via MCP over HTTP, answer, gate); no duplicate retrieval logic | StateGraph without checkpointer; bot calls the 5 tools only through `fastmcp.Client` (Architecture, Code Examples) |
| BOT-05 | Every citation in text the tools returned in this run; else refusal + `buddy_report_gap` | Deterministic citation gate on source ids, one retry, refusal path (Pattern 3, Pitfall 1) |
| BOT-06 | Sensitive topics: general written rule + referral only | `sensitive_topic` from the reformulation step, constrained answer prompt, bot-rendered referral suffix (Pattern 4) |
| BOT-07 | One LLM client module, `LLM_BACKEND=meridian\|api`, Vertex configured not enabled | `LlmClient` port + one `AnthropicMessagesClient`; backend only changes `base_url`/key (Standard Stack, Pattern 5) |
| BOT-08 | Refuse to start with `meridian` and more than one allowed user | pydantic `model_validator` in `BotSettings`, same style as `McpSettings` (Code Examples) |
| BOT-09 | Guides+video answer renders a card (source link, thumbnail, "Guarda"); handbook shows source link | cardsV2 builder; thumbnail = optional static `VIDEO_THUMBNAIL_URL`, no index change (Pattern 6, Open Question 2) |
| BOT-10 | Answer within ~30 s or asynchronous follow-up | Placeholder then `update_message`; HTTP awaits the run inside the request (Pitfall 6) |
| BOT-11 | No user identifiers persisted next to question text | HMAC thread key, no sender fields, 24 h TTL plus read-side expiry check, log-hygiene test (Pattern 7, Pitfalls 4, 8) |
</phase_requirements>

## Summary

The bot is a new package `services/chat_bot/buddy_bot` that sits between Google Chat and the Phase 2 MCP server. Events enter through one `IntakePort` (Pub/Sub streaming pull in dev, Starlette HTTP with Google JWT verification for Cloud Run), are normalized from either of Google's two event shapes into one internal `ChatEvent`, pass an allowlist guard, and go through a single `BotService.handle()` that posts a placeholder, runs a LangGraph `StateGraph` (reformulate -> retrieve -> answer -> deterministic gate -> optional single retry -> refuse), renders the result as text plus an optional cardsV2 card, and patches the placeholder message. The workflow is a plain callable with injected ports so Phase 5 can run the golden set through it without Chat.

Most of the stack already exists in the repo and the test image: `fastmcp` 4.1.6 (its `Client` is the MCP client; auth takes an `httpx2.Auth` or a bearer string), `pydantic-settings`, `starlette`/`uvicorn`, `google-auth`, `google-cloud-firestore`. New direct dependencies: `langgraph`, `anthropic`, `google-cloud-pubsub`, `google-apps-chat`, and `requests` (already transitive, now imported directly). A dry-run resolution against the current pins succeeds with no conflicts (versions below). Recommendation that departs from D-10's first option: do not use a LangGraph checkpointer; use a small `ThreadMemory` port with a Firestore adapter (one document per HMAC key, `turns` capped, `expire_at`). A checkpointer stores full graph state per step (all tool text), has no TTL field, and the only Firestore saver is a single-maintainer third-party package. D-10 explicitly allows "an equivalent store behind a port".

The risky areas are not the libraries. They are: (1) the two Google Chat event shapes (add-on vs legacy) and what the allowlist can match on; (2) Meridian behaviour (credentials mount must be writable for token refresh, sampling parameters are not honoured, structured output support is undocumented), which is why structured output must be done with prompt-instructed JSON plus pydantic validation rather than a native API feature; (3) the handbook has no clickable URL (`handbook://<page_id>`) and the index has no thumbnail field; (4) OR-semantics in both search tools, which makes the deterministic `no_results` signal rare, so the LLM gate and the citation check carry the load.

**Primary recommendation:** Build `buddy_bot` as ports + adapters with one `BotService.handle(event)` entry; structured LLM output via JSON-in-prompt validated by pydantic (one retry); thread memory via a Firestore port (no checkpointer); cite by exact `source_url` equality against the set returned in the run; support both Chat event shapes in one normalizer; render handbook sources as title plus `handbook://` text and Guides+video as a cardsV2 card with a "Guarda" button.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Receive Chat events | Intake adapter (Pub/Sub dev, HTTP Cloud Run) | Google Chat platform | Transport differs, workflow identical (BOT-02) |
| Verify caller (Google JWT) | HTTP intake adapter | — | Only the HTTP path carries a bearer token; Pub/Sub trust comes from IAM on the subscription |
| Allowlist guard | Bot service (before graph) | — | Must precede any MCP/LLM call (BOT-03) |
| Event normalization | Anti-corruption layer in bot | — | Two Google payload shapes -> one internal type |
| Query reformulation, intent, sensitive topic | LLM (Haiku) via LLM port | Bot graph node | D-05, D-14, D-17 |
| Retrieval | MCP server (Phase 2) | Bot MCP client | D11: bot holds no retrieval logic |
| Answer + grounded/confidence | LLM (Sonnet) via LLM port | Bot graph node | D-01b, D-17 |
| Citation check, confidence gate, refusal | Bot (deterministic code) | — | Never delegated to the model (D-01a, D-02) |
| Gap logging | MCP server tool `buddy_report_gap` | Bot calls it | Server owns the Firestore gap schema (D-10) |
| Thread memory | Firestore via `ThreadMemory` port | Bot | D-10/D-11 |
| Escalation table | Shared YAML (`buddy_core`) | SKILL.md (checked by test) | D-08 |
| Rendering (text, cardsV2) | Bot | Chat platform | Links rendered by bot, never by the model (D-02) |
| Post/update messages | Chat API (app auth) via `ChatApi` port | — | D-09 |
| ID token for MCP | Bot (`google.oauth2.id_token`) | MCP server verifies | D-12 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.2.20 | 2-step RAG `StateGraph` (BOT-04) | Required by BOT-04; LANGGRAPH_GUIDE s.2-6 |
| anthropic | 2.6.0 | Messages client; `base_url` selects Meridian or Anthropic (BOT-07) | D-16: "same Anthropic Messages client" |
| fastmcp | 4.1.6 (already pinned) | MCP client (`fastmcp.Client`), in-memory client for tests | Same lib as the server; `Client(url, auth=httpx2.Auth\|str)` [VERIFIED: introspection of installed `fastmcp.client.transports.StreamableHttpTransport.__init__`: `auth: "httpx2.Auth \| Literal['oauth'] \| str \| None"`] |
| google-cloud-pubsub | 2.43.0 | Streaming-pull subscriber (BOT-01) | Official sample path |
| google-apps-chat | 0.10.9 | `ChatServiceAsyncClient.create_message` / `update_message` (app auth, scope `chat.bot`) | Official GAPIC client; async methods verified |
| google-auth | 2.62.1 (already installed) | `id_token.fetch_id_token` (mint), `id_token.verify_oauth2_token` (verify Chat JWT) | Already a transitive dep of firestore |
| requests | 2.34.2 (installed transitively) | Transport for `google.auth.transport.requests.Request` | Imported directly now, so pin it |
| pydantic / pydantic-settings | 2.14.2 / 2.16.2 (pinned) | Config, structured LLM output schemas, MCP output parsing | Existing pattern |
| starlette + uvicorn | 1.10.0 / 0.54.0 (transitive of fastmcp) | HTTP intake | No new dep; do not add FastAPI |
| google-cloud-firestore | 2.34.1 (pinned) | `ThreadMemory` adapter | Existing |

[VERIFIED: `pip index versions` 2026-11-07 for langgraph 1.2.20, anthropic 2.6.0, google-cloud-pubsub 2.43.0, google-apps-chat 0.10.9, requests; `pip install --dry-run` of existing pins plus these succeeded in `python:3.12-slim`, resolving fastmcp 4.1.6, mcp 2.3.0, httpx2 2.16.0, langchain-core 1.7.6, langgraph-checkpoint 4.3.1, langgraph-prebuilt 1.1.1, langsmith 0.14.17, protobuf 7.36.2, grpcio 1.85.1.]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | 6.0.3 (pinned) | Load the shared escalation table | D-08 |
| anyio pytest plugin | 4.16.0 (installed) | `pytest.mark.anyio` async tests | Existing pattern (`anyio_backend` fixture) |
| `fastmcp.server.auth.providers.jwt.RSAKeyPair` | in fastmcp | Sign test JWTs for the HTTP intake tests | Already used in `tests/unit/mcp_server/conftest.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Firestore `ThreadMemory` port | `langgraph-checkpoint-firestore` 0.4.0 | Single maintainer (skamalj), stores whole graph state (all tool text), no TTL field; would still need the HMAC key and a 24 h expiry bolted on. Rejected. |
| `anthropic` SDK directly | `langchain-anthropic` 1.7.10 + `init_chat_model` | Adds a layer; LANGCHAIN_GUIDE s.3 `base_url` doc says OpenAI-compatible endpoints; the Messages client is exactly what D-16 names |
| Prompt-JSON structured output | `client.messages.parse(...)` / `output_config.format` json_schema (exists in anthropic 2.6.0) | Native schema enforcement but Meridian support is undocumented and a native path would break "config only" switching (BOT-07). Switch later only if a live probe passes. |
| `fastmcp.Client` | `langchain.mcp.MCPAdapter` | Beta (`LangChainBetaWarning`), tool-calling agent shape; the workflow calls five tools deterministically, so no adapter is needed (LANGCHAIN_GUIDE s.15) |
| Starlette | FastAPI | FastAPI is not installed; one POST route does not justify a new dep |

**Installation** (pins go in a new `services/chat_bot/requirements.txt`, listed by `requirements-dev.txt` with `-r`; rebuild the test image):
```bash
# services/chat_bot/requirements.txt
langgraph==1.2.20
anthropic==2.6.0
google-cloud-pubsub==2.43.0
google-apps-chat==0.10.9
requests==2.34.2
```
`tests/unit/test_repo_layout.py::test_requirements_are_pinned` iterates an explicit file list; add the new file to it.

**Version verification:** run in Docker, not on the host: `docker run --rm python:3.12-slim pip index versions <pkg>` (host `pip index` was used here for registry lookup only; it installs nothing).

## Package Legitimacy Audit

> Seam run: `gsd-tools query package-legitimacy check --ecosystem pypi langgraph anthropic google-cloud-pubsub google-apps-chat` (2026-11-07).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| langgraph 1.2.20 | PyPI | years (latest release 2026-11-05) | not reported by seam | github.com/langchain-ai/langgraph | SUS (`too-new`, `unknown-downloads`) | Flagged: seam judges the latest release date; established vendor package. Planner adds `checkpoint:human-verify` before install (same gate as 02-01) |
| anthropic 2.6.0 | PyPI | years (latest release 2026-11-05) | not reported | github.com/anthropics/anthropic-sdk-python | SUS (`too-new`, `unknown-downloads`) | Flagged, same reason, same checkpoint |
| google-cloud-pubsub 2.43.0 | PyPI | years (latest release 2026-10-15) | not reported | github.com/googleapis/google-cloud-python | SUS (`too-new`, `unknown-downloads`) | Flagged, same checkpoint |
| google-apps-chat 0.10.9 | PyPI | latest release 2026-11-05 | not reported | github.com/googleapis/google-cloud-python (packages/google-apps-chat) | SUS (`too-new`, `unknown-downloads`) | Flagged, same checkpoint |
| requests 2.34.2 | PyPI | years | very high | github.com/psf/requests | not run (already installed in the test image) | Approved: pin only |
| @rynfar/meridian 1.88.0 | npm (Node, Docker only) | release 2026-11-02 | 3,837/wk | github.com/rynfar/meridian | SLOP (`too-new`, `suspicious-postinstall`) | NOT removed: it is a locked user decision (D-16, D1a), not a research recommendation. Mitigation below; planner adds `checkpoint:human-verify` before building the image |

**Packages removed due to SLOP verdict:** none. Meridian received a SLOP verdict from the seam but is retained because CONTEXT D-16 locks it; it is not a Python dependency and runs only in its own container. Reasons for the verdict: the npm `postinstall` runs `@anthropic-ai/claude-code/install.cjs` (downloads a native binary). The repo's own Dockerfile avoids this by `bun install --ignore-scripts` in the build stage and running that install explicitly in the runtime stage [VERIFIED: raw.githubusercontent.com/rynfar/meridian/main/Dockerfile]. Build the image from the repo Dockerfile pinned to a **commit SHA** (git tags stop at v1.29.2 while npm is at 1.88.0, so tags are not usable pins) [VERIFIED: `git ls-remote --tags`]. Both D1 (Anthropic terms) and D1a (personal use grey area) stay as recorded in PROJECT.md.
**Packages flagged as suspicious [SUS]:** langgraph, anthropic, google-cloud-pubsub, google-apps-chat (planner inserts `checkpoint:human-verify` before the dependency task installs them). Package names above were taken from the Guides, official Google docs and sample `requirements.txt`, not from a search result, and all four resolve on PyPI.

## Architecture Patterns

### System Architecture Diagram

```
Google Chat ──(dev)── Pub/Sub topic ── pull subscription ──┐
     │                                                      ▼
     └──(Cloud Run)── HTTPS POST + Bearer JWT ──► [HTTP intake: verify JWT, 401 otherwise]
                                                            │
                         IntakePort.run(handler)  ◄─────────┘  (Pub/Sub adapter: thread -> loop bridge)
                                   │ raw JSON dict
                                   ▼
                     normalize_event()  (add-on EventObject | legacy Event) ──► ChatEvent
                                   │
                                   ▼
                       BotService.handle(ChatEvent)  — never raises
        ┌──────────────────────────┼───────────────────────────────┐
        │ dedupe on message.name   │ sender not in ALLOWED_USERS?  │ ──► silent drop (no MCP/LLM)
        │ REMOVED_FROM_SPACE ──► ignore                            │
        │ ADDED_TO_SPACE / /aiuto ──► canned text (no LLM)         │
        ▼                                                          
   ChatApi.create_message(placeholder "Sto cercando nelle fonti…")  ──► message.name
        │
        ▼
   ThreadMemory.recent(HMAC(thread), 3)  ──► history (reformulation only, D-12)
        │
        ▼
   ┌────────────────────────── LangGraph StateGraph ───────────────────────────┐
   │ reformulate (Haiku) ─► intent? ─ chitchat/off_topic ─► canned no-source ─► END (no gap)
   │        │ question                                                          │
   │        ▼                                                                   │
   │ retrieve ── fastmcp.Client(+Google ID token) ─► handbook_search / guides_search (parallel)
   │        │        evidence = every result of this run, keyed by source_url   │
   │        ▼                                                                   │
   │ answer (Sonnet, evidence only) ─► {answer, citations[], grounded, confidence}
   │        ▼                                                                   │
   │ gate (pure code): all no_results? ─ citation ∉ evidence? ─ !grounded? ─ confidence < τ?
   │   pass ─────────────────────────────► render                               │
   │   fail, attempt 0 ─► retry_plan (Haiku: other keywords/other source) ─► retrieve
   │   fail, attempt 1 ─► refuse: referente lookup ─► buddy_report_gap (if intent=question)
   └─────────────────────────────────────────────────────────────────────────────┘
        │ BotReply(text, sources[], referral?)
        ▼
   render: text + (cardsV2 iff a cited Guides source has video_url)
        │
        ▼
   ChatApi.update_message(placeholder.name, text, cards_v2)   ;  ThreadMemory.append(q, a)
        │
        ▼
   intake acks (Pub/Sub ack after handle returns; HTTP returns {})
```

### Recommended Project Structure
```
services/chat_bot/
├── README.md                    # env contract, how to run, manual Chat app settings, rollout checklist item (D-11)
├── requirements.txt
└── buddy_bot/
    ├── __main__.py              # raise SystemExit(main())   (as buddy_mcp)
    ├── cli.py                   # composition root: the only place real adapters are built
    ├── config.py                # BotSettings (pydantic-settings), BOT-07/08 guards, errors name variables only
    ├── events.py                # ChatEvent + normalize_event (anti-corruption layer for both Google shapes)
    ├── service.py               # BotService.handle: allowlist, dedupe, canned replies, placeholder, run, patch
    ├── workflow.py              # build_graph(ports) + run_workflow(); pure of Chat/intake (Phase 5 reuses it)
    ├── schemas.py               # Reformulation, AnswerDraft, Evidence, BotReply (pydantic)
    ├── prompts.py               # Italian/English prompt text, evidence formatter, delimiters
    ├── gate.py                  # citation + confidence gate (pure functions)
    ├── render.py                # text + cardsV2 builders, Chat markup escaping, length caps
    ├── ports.py                 # Protocols: LlmClient, McpRetriever, ChatApi, ThreadMemory, IntakePort
    ├── llm.py                   # AnthropicMessagesClient + structured_call() (JSON-in-prompt + 1 repair retry)
    ├── mcp_client.py            # fastmcp.Client wrapper + GoogleIdTokenAuth(httpx2.Auth); parses D-06 outputs
    ├── chat_api.py              # ChatServiceAsyncClient adapter (lazy client, chat.bot scope)
    ├── memory.py                # FirestoreThreadMemory + InMemoryThreadMemory (HMAC key, TTL, N turns)
    └── intake/
        ├── pubsub.py            # streaming pull -> asyncio bridge
        └── http.py              # Starlette app + Chat JWT verification
packages/buddy_core/buddy_core/
├── escalation.py                # loader + pydantic model for the shared table (D-08)
└── data/escalation_topics.yaml  # id, tema (IT label), referente role, fallback
tests/unit/chat_bot/             # offline, --network none
tests/integration/test_pubsub_intake.py, test_firestore_thread_memory.py, test_bot_process.py
docker-compose.test.yml          # + pubsub emulator service
docker-compose.dev.yml           # live dev: meridian, mcp_server, chat_bot (+ firestore emulator); Phase 4 supersedes
```
Mirrors `jobs/sync` and `services/mcp_server` (package name `buddy_bot`; add to `pyproject.toml` pythonpath, mypy `mypy_path`/`files`, ruff `src`, isort `known-first-party`, coverage `source`, Dockerfile `PYTHONPATH` and a new `chat_bot` stage, `.dockerignore` unchanged). [VERIFIED: read `pyproject.toml`, `Dockerfile`, `docker-compose.test.yml`, `run-unit-tests.sh` this session.]

### Pattern 1: Intake port with two adapters (BOT-01/02, DESIGN_PATTERNS s.9 Ports & Adapters, s.4 Adapter)
**What:** `IntakePort.run(handler: Callable[[dict[str, Any]], Awaitable[None]])`. `BotService.handle` takes the already-JSON-decoded dict. The Pub/Sub adapter owns ack; the HTTP adapter owns the JWT check and the `{}` reply. Pick one adapter per process by `INTAKE=pubsub|http`.
**When to use:** always; the workflow never learns which transport delivered the event.
**Why this ack policy:** `handle` never raises (it converts failures into a user-visible Italian error text and a log line with exception type only). The Pub/Sub callback therefore always acks after `handle` returns; a poison message cannot loop. Streaming pull lease management extends the ack deadline while the callback blocks [ASSUMED: google-cloud-pubsub default lease management, `FlowControl.max_lease_duration`; confirm in the emulator test]. Duplicates (Pub/Sub redelivery, Chat retry) are dropped by an in-memory TTL set keyed on `message.name`.

### Pattern 2: Two-step RAG as a `StateGraph` without a checkpointer (BOT-04; LANGGRAPH_GUIDE s.2, s.4, s.6, LANGCHAIN_GUIDE s.14 "2-step RAG")
State is a `TypedDict`: `question`, `history`, `reformulation`, `evidence: dict[str, Evidence]` (source_url -> evidence, accumulated across the retry), `draft`, `attempt`, `reply`. Ports are bound by closure in `build_graph(llm, mcp, ...)` (LANGGRAPH_GUIDE s.5.2: dependencies are context, not state). Route with conditional edges only (s.6.2: one routing mechanism per node). Nodes are plain async functions testable without the graph (s.21.3). Always retrieve (no tool-calling agent): the model never decides whether to search.
`run_workflow(question, history, deps) -> BotReply` is the public function Phase 5 calls.

### Pattern 3: Deterministic citation and confidence gate (BOT-05; RAG_CHATBOT_GUIDE s.24; D-01, D-02)
Gate order, all in pure code (`gate.py`):
1. every tool result of the run was `no_results` -> fail, and skip the answer LLM call (saves a Sonnet call and cannot answer).
2. `draft.citations` empty -> fail.
3. any cited id not in `evidence.keys()` (exact string equality after `.strip()`; no fuzzy matching) -> fail.
4. `not draft.grounded` -> fail.
5. `draft.confidence < CONFIDENCE_THRESHOLD` -> fail.
The model is shown each evidence block labelled with the exact `source_url` it must copy; the bot renders titles, dates and links from `evidence[cited]`, never from model text. The answer prompt forbids URLs inside `answer`; `render` additionally strips any `http(s)://` or `handbook://` token the model put in prose, so the only links in the message are bot-rendered.
`evidence` must be built **only** from tool results returned in this run (no history, no memory), which is what makes BOT-05 true by construction.

### Pattern 4: Sensitive topics (BOT-06; D-05..D-07)
`Reformulation.sensitive_topic` is a topic id from the YAML table or `null`. Retrieval still runs. For sensitive questions the answer prompt is switched to "report only the general written rule, no assessment of the person's situation, no advice", the bot appends the fixed suffix `per il tuo caso specifico chiedi a <referente>` itself (never model-written), and if the gate fails the reply is the referral only plus a gap entry (D-07). Backstop for classifier failure: when the reformulation call fails validation twice, reply with a generic error and log nothing about the question; do not fall through to an unconstrained answer.

### Pattern 5: Pluggable LLM client (BOT-07; DESIGN_PATTERNS s.5 Strategy, s.3 Factory)
One `AnthropicMessagesClient(base_url, api_key, timeout)` built by a factory from `LLM_BACKEND`:
- `meridian`: `base_url=LLM_BASE_URL` (e.g. `http://meridian:3456`), `api_key` = placeholder, or `MERIDIAN_API_KEY` if the gate is on.
- `api`: default Anthropic base URL, `ANTHROPIC_API_KEY`.
- `vertex`: settings fields (`VERTEX_PROJECT`, `VERTEX_REGION`) exist; `LLM_BACKEND=vertex` is rejected at startup with "not enabled" (BOT-07 "configured, not enabled").
Both backends use the same request code, so switching is configuration only. `structured_call(schema, model, system, user)` appends the JSON schema (`schema.model_json_schema()`) to the system prompt, asks for a single JSON object, parses with `schema.model_validate_json`, and retries once with the validation error text on failure (LANGCHAIN_GUIDE s.7: "Retries cost a full model call each. Cap it"). Do not pass `temperature`: [VERIFIED: introspection of `anthropic==2.6.0` `AsyncMessages.create` parameters: `max_tokens, messages, model, cache_control, container, diagnostics, inference_geo, metadata, output_config, service_tier, speed, stop_sequences, stream, system, thinking, tool_choice, tools, user_profile_id, workspace_id, extra_headers, extra_query, extra_body, timeout` — no `temperature`/`top_p`/`top_k`], and Meridian documents that the CLI "doesn't expose ... sampling controls" [CITED: github.com/rynfar/meridian README].

### Pattern 6: Rendering (BOT-09)
`Message.text` carries the answer plus a `Fonte:` line per cited source; `Message.cards_v2` is added only when at least one cited Guides source has `video_url`. Chat link syntax in text is `<url|label>` [ASSUMED: Chat text formatting]. cardsV2 shape per Google docs: `cardsV2: [{cardId, card: {header{title, subtitle, imageUrl}, sections[{header, widgets[]}]}}]`; widgets `textParagraph`, `decoratedText`, `image{imageUrl}`, `buttonList{buttons[{text, onClick{openLink{url}}}]}`; image URLs must be HTTPS; max 100 widgets per card; every section needs a widget [CITED: developers.google.com/workspace/chat/api/reference/rest/v1/cards].
```json
{"cardsV2": [{"cardId": "video-1", "card": {
  "header": {"title": "Guida: <heading>", "subtitle": "indicizzato il <YYYY-MM-DD>"},
  "sections": [{"widgets": [
    {"image": {"imageUrl": "<VIDEO_THUMBNAIL_URL>", "altText": "Video della guida"}},
    {"buttonList": {"buttons": [
      {"text": "Fonte", "onClick": {"openLink": {"url": "<guides permalink>"}}},
      {"text": "Guarda", "onClick": {"openLink": {"url": "<video_url, with #t=N when a scene clip>"}}}]}}]}]}}]}
```
Omit the `image` widget when `VIDEO_THUMBNAIL_URL` is unset (never an empty `imageUrl`). Handbook sources have no web URL (see Pitfall 5): render `Manuale: <title> (handbook://<page_id>), revisione <YYYY-MM-DD>` as plain text.

### Pattern 7: Thread memory port (D-10, D-11, D-12; LANGGRAPH_GUIDE s.10.6-10.7 as the exception rationale)
`ThreadMemory.recent(thread_key, n) -> list[Turn]`, `append(thread_key, turn)`. Firestore document id = `HMAC-SHA256(THREAD_KEY_SECRET, key_source).hexdigest()`; fields exactly `turns` (list of `{q, a}` capped to N), `updated_at`, `expire_at` (= now + 24 h). Read side ignores a document whose `expire_at` is in the past, because Firestore TTL deletion is not immediate: the repo's own README says "Firestore deletes expired documents within about a day. The emulator does not enforce TTL." [VERIFIED: `services/mcp_server/README.md`, Gap log section]. Apply the TTL policy (`gcloud firestore fields ttls update expire_at --collection-group=<collection> --enable-ttl`) in Phase 4, same as `gaps`; record it on the rollout checklist. Use the lazy-client pattern of `FirestoreGapLog` (client created on first call inside the running loop) [VERIFIED: `gaplog.py` class docstring]. `key_source` = `thread.name`, except for direct-message spaces where it should be `space.name` if follow-ups turn out to get distinct thread names (Open Question 3; still HMAC'd, still D-11 compliant).

### Anti-Patterns to Avoid
- **LangGraph checkpointer for D-10:** stores all tool output per step, no TTL, third-party Firestore saver. Use `ThreadMemory`.
- **Tool-calling agent for retrieval:** adds a model call to decide to search and lets the model invent queries; D-11/BOT-04 want a fixed 2-step flow.
- **Parsing the prose rendering of tool results:** parse `result.structured_content` into the `buddy_mcp.models` shapes only (D-06).
- **Letting the model write links or the referral:** the bot renders both (D-02, D-06).
- **Logging events or questions:** log counts, ids of nothing identifying, exception types (same policy as `buddy_mcp`).
- **Fuzzy citation matching or auto-repairing citations:** a mismatch is a gate failure (D-02).
- **Mixing `Command` and static edges from one node** (LANGGRAPH_GUIDE s.6.2).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT signature/issuer/audience/expiry check for the Chat HTTP endpoint | Custom JWT parsing | `google.oauth2.id_token.verify_oauth2_token(token, Request(), audience)` then check `email` claim | Cert fetching, caching, clock skew handled [VERIFIED: signature `(id_token, request, audience=None, clock_skew_in_seconds=0)`] |
| Minting the Google ID token for the MCP server | Service-account JWT signing | `google.oauth2.id_token.fetch_id_token(request, audience)` | Reads `GOOGLE_APPLICATION_CREDENTIALS` SA file, else metadata server (Cloud Run) [VERIFIED: function docstring in installed google-auth 2.62.1] |
| Pub/Sub flow control, leases, reconnects | Own pull loop | `SubscriberClient.subscribe(..., flow_control=FlowControl(max_messages=...))` | Streaming pull with lease management |
| MCP protocol client | Own JSON-RPC over httpx | `fastmcp.Client` (HTTP) and `Client(server)` in tests | Already used by the server tests |
| FTS/retrieval, stemming, source ids | Any search in the bot | The five MCP tools | D11 |
| Chat message update | Raw REST | `ChatServiceAsyncClient.update_message(message=..., update_mask=FieldMask(paths=[...]))` | Typed; signature verified |
| Gap persistence | Own Firestore writes for gaps | `buddy_report_gap` | Server enforces the six-key document and the no-identity rule |
| HMAC key | Custom hashing | stdlib `hmac.new(secret, name.encode(), hashlib.sha256).hexdigest()` | Standard |
| Env parsing/validation | `os.environ` | `pydantic-settings` as in `McpSettings` | Errors name variables, not values |

**Key insight:** every deceptively hard part (token verification, leases, protocol, retrieval, gap schema) already has an owner. The bot's own logic is small and deterministic: normalize, guard, orchestrate, gate, render.

## Runtime State Inventory

Not applicable (greenfield package; no rename or migration). One related item: `skills/digitiamo-buddy/SKILL.md` keeps its "Temi da escalare" table text and is verified against the new YAML by a drift test (D-08), so no stored state needs migration.

## Common Pitfalls

### Pitfall 1: OR-semantics make `no_results` rare
**What goes wrong:** `to_match_query` joins every token with `OR` [VERIFIED: `packages/buddy_core/buddy_core/index_reader.py:36` `return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)`]. A query with a stopword ("come", "the") returns hits for almost any question, so the deterministic "all no_results" signal seldom fires.
**Why it happens:** FTS5 BM25 ranks, it does not require all terms.
**How to avoid:** the reformulation schema asks for `keywords_it` and `keywords_en` as content words only (nouns/verbs, no stopwords, 2-5 terms); the answer step plus citation check and `grounded`/`confidence` carry the refusal decision. Phase 5 empty-context test (EVAL-04) is the real check.
**Warning signs:** off-topic questions getting an answer citing an unrelated page.

### Pitfall 2: Meridian specifics
**What goes wrong:** (a) The Meridian Docker doc says the container runs as UID 1000 and the mounted `~/.claude` "must be writable by that user so tokens can refresh" [CITED: raw.githubusercontent.com/rynfar/meridian/main/docs/deployment.md], which conflicts with D-16's "mounted read-only". (b) Sampling controls and exact output-token caps are not honoured. (c) Structured output via `output_config` is undocumented for the Claude backend. (d) With `MERIDIAN_HOST` default `127.0.0.1` the proxy is unreachable from another container unless bound to `0.0.0.0` (the repo Dockerfile sets `CLAUDE_PROXY_HOST=0.0.0.0`) and, if reachable beyond loopback, should have `MERIDIAN_API_KEY` set [CITED: configuration.md].
**How to avoid:** put the credentials in a dedicated Docker named volume or a copied-once directory that the container can write, not a read-only bind of the live `~/.claude` (never bake them into an image, which keeps the intent of D-16); publish the port only on the compose network (no host port, or `127.0.0.1:` only); set `MERIDIAN_API_KEY` and pass it as the Anthropic key; use JSON-in-prompt structured output; set a generous client timeout (Meridian spawns a CLI turn per request). Flag the read-only deviation to Joshua at the plan checkpoint as a decision, not a silent change. [ASSUMED: Joshua's host uid is 1000; `~/.claude/.credentials.json` exists, mode 600, 573 bytes (checked with `ls`, contents not read).]
**Warning signs:** `401`/auth errors after about an hour; JSON wrapped in prose; slow first token.

### Pitfall 3: Allowlist identity
**What goes wrong:** matching on email assumes the event carries it. The User resource documents `email` but is silent on whether app authentication populates it; `name` is `users/{id}` and "only the canonical ID ... is returned" [CITED: developers.google.com/workspace/chat/api/reference/rest/v1/User].
**How to avoid:** `ALLOWED_USERS` accepts a comma list of `users/<id>` and/or lowercase emails; the guard allows when `event.user.name` or `event.user.email` (if present) matches. The rejected-sender path logs one counter line with no identifier. To learn his own id, Joshua reads it once from the live checkpoint (document the step in the bot README; do not add a code path that logs ids).
**Behaviour for non-allowlisted senders:** drop silently (no reply text, no MCP, no LLM, no memory write). Applies to every event type including `ADDED_TO_SPACE`.

### Pitfall 4: Memory and log privacy (BOT-11)
**What goes wrong:** LangSmith/LangChain tracing can ship prompts off-host; `logging` of the event dict leaks sender and question together; placeholders and gaps carry text.
**How to avoid:** set `LANGSMITH_TRACING=false` in the bot image environment (langsmith 0.14.17 is a transitive dependency of langgraph) [ASSUMED: tracing is opt-in via env]; never log event bodies, question text, history, evidence text or sender fields; log only counters, node names, durations, tool names, exception types. A `caplog` test across a full run asserts none of the known sentinel strings (sender email, `users/` id, space name, thread name, question text) appears in any record, mirroring `tests/unit/mcp_server/test_log_hygiene.py`. Gap records use the **standalone reformulated question**, not the raw message, so incidental personal detail is less likely to land in the gap log (a design choice: flag to the planner, D-07 says "question text").

### Pitfall 5: Handbook sources are not clickable; thumbnails do not exist
**What goes wrong:** BOT-09 says "handbook answers show the source link", but handbook `source_url` is `handbook://<page_id>` (not an openable URL), and `index.db` 1.0.0 has no thumbnail field [VERIFIED: `docs/index-format.md` video_map columns `chunk_key, video_url, part, start_seconds?, source`; CONTEXT "no thumbnail field"]. Video URLs are GitHub release assets (`.../releases/download/videos/<name>.mp4`), so no frame can be derived without downloading and decoding.
**How to avoid:** show the handbook citation as text with page title and `handbook://<page_id>`; thumbnail = optional static HTTPS image from `VIDEO_THUMBNAIL_URL` (the ai-buddy repo is public, so a committed generic image served from a raw URL works), omitted when unset. Do not change `index.db`. Ask Joshua whether a text-only handbook citation satisfies BOT-09 (Open Question 1). Per-video thumbnails belong to ROLL-02 when videos move to Drive.

### Pitfall 6: 30 s window and Cloud Run CPU
**What goes wrong:** a Meridian turn plus MCP plus a possible D-03 retry can exceed 30 s. In HTTP mode on Cloud Run with request-based billing, CPU is throttled after the response, so "ack fast, finish in the background" may stall [ASSUMED: Cloud Run request-based CPU allocation behaviour].
**How to avoid:** the placeholder (D-09) is the user-visible ack. In the HTTP adapter, `await` the whole `handle()` inside the request under `asyncio.timeout(~25 s)` and then return `{}`; if the timeout fires, return `{}` and let the task finish (best effort, patch still happens when CPU allows). Pub/Sub path has no such limit (ack after `handle`). Add an overall run deadline (env, default 120 s) that ends in an error text patched onto the placeholder. The hold-open design is a Phase 3 interface decision; Phase 4 can flip Cloud Run to instance-based CPU if needed.

### Pitfall 7: Two Google Chat event shapes and two JWT identities
**What goes wrong:** Apps created after July 2025 default to the add-on format (`chat.messagePayload.message`, `chat.user`, `chat.eventTime`); the older format is flat (`type`, `message`, `user`, `space`) [CITED: developers.google.com/workspace/chat/events and /convert]. HTTP JWT identity differs: add-on tokens are signed by `service-PROJECT_NUMBER@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`; non-add-on apps use `chat@system.gserviceaccount.com`; audience is the endpoint URL (ID token) or the project number (self-signed JWT) [CITED: developers.google.com/workspace/chat/verify-requests-from-chat].
**How to avoid:** `normalize_event` accepts both (decide by `"chat" in payload`), with one recorded fixture per shape and event kind. Support only the **HTTP-endpoint-URL audience** mode for JWT verification (`verify_oauth2_token`), with `CHAT_JWT_AUDIENCE` and `CHAT_JWT_ISSUER_EMAIL` from env; document "Authentication Audience: HTTP endpoint URL" as a manual Chat app setting. Self-signed project-number mode is out of scope. Slash command: legacy `message.slashCommand` on a `MESSAGE` event; add-on `chat.appCommandPayload` with `appCommandMetadata.appCommandId`; match `/aiuto` by command id (env `HELP_COMMAND_ID`) or by text prefix.
**Warning signs:** a live DM that parses to "unknown event" and is silently dropped.

### Pitfall 8: Redelivery and duplicate events
**What goes wrong:** Chat "may retry a few times" on HTTP failure and Pub/Sub is at-least-once [CITED: /workspace/chat/events]; duplicate events would create two placeholders and two answers (and two gaps).
**How to avoid:** TTL dedupe on `message.name` inside `BotService` (10 min). Node side effects (gap write, memory append) happen once per run, after the gate, never inside a node that LangGraph might re-execute (LANGGRAPH_GUIDE s.5.3). The graph has no checkpointer, so there is no resume re-execution; keep side effects out of nodes anyway by doing them in `BotService` after `run_workflow` returns, except `buddy_report_gap`, which belongs in the refuse node's caller too (return `BotReply.gap_question` and let `BotService` call the tool).

### Pitfall 9: Rate limiting and MCP session cost
**What goes wrong:** the server rate limit is per caller, token bucket `RATE_LIMIT_RPS=5`, burst 30, counting `initialize` and `tools/list` [VERIFIED: `services/mcp_server/README.md` Rate limiting; `.env.example` `RATE_LIMIT_RPS=5`, `RATE_LIMIT_BURST=30`]. Opening a `Client` per tool call spends several requests each.
**How to avoid:** one `async with Client(...)` per run, both searches inside it, then close; no `tools/list` call from the bot.

### Pitfall 10: Chat message limits and formatting
Chat text has a length ceiling (about 4,096 characters before truncation) [ASSUMED]; cap `answer` to ~3,500 characters and instruct brevity. Escape or strip characters that Chat treats as markup if they break rendering (`*`, `_`, `<`) in model prose; links come only from the renderer. Updating a message needs the field mask `text` and `cards_v2` (python GAPIC proto field names; REST uses `cardsV2`) [ASSUMED: confirm in the live checkpoint]; app auth can only update messages the app created [CITED: developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/patch].

## Code Examples

### Settings guards (BOT-07, BOT-08) in the style of `McpSettings`
```python
# Source: pattern from services/mcp_server/buddy_mcp/config.py (model_validator mode="after", errors name variables)
class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, env_ignore_empty=True,
                                      extra="ignore", hide_input_in_errors=True)
    allowed_users: Annotated[frozenset[str], NoDecode]          # required, lowercased csv
    llm_backend: Literal["meridian", "api", "vertex"]
    ...
    @model_validator(mode="after")
    def _guards(self) -> "BotSettings":
        if self.llm_backend == "vertex":
            raise ValueError("LLM_BACKEND=vertex is not enabled")
        if not self.allowed_users:
            raise ValueError("ALLOWED_USERS must list at least one user")
        if self.llm_backend == "meridian" and len(self.allowed_users) > 1:
            raise ValueError("LLM_BACKEND=meridian requires exactly one ALLOWED_USERS entry (D1a)")
        if self.mcp_auth == "none" and "K_SERVICE" in os.environ:   # mirror D-13
            raise ValueError("MCP_AUTH=none is refused when K_SERVICE is set")
        return self
```

### MCP client: Google ID token as `httpx2.Auth`, one session per run
```python
# Source: fastmcp.Client / StreamableHttpTransport accept auth: httpx2.Auth | str  [VERIFIED introspection];
# id_token.fetch_id_token(request, audience) [VERIFIED docstring, google-auth 2.62.1]
class GoogleIdTokenAuth(httpx2.Auth):
    def __init__(self, audience: str) -> None: ...
    def auth_flow(self, request: httpx2.Request) -> Generator[httpx2.Request, httpx2.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._token()}"   # cached ~50 min; blocking fetch -> prefetch via to_thread
        yield request

async def retrieve(url: str, auth: httpx2.Auth | None, hb_query: str | None, g_query: str | None):
    async with Client(url, auth=auth) as client:
        hb = await client.call_tool("handbook_search", {"query": hb_query, "limit": 3})
        gd = await client.call_tool("guides_search", {"query": g_query, "limit": 4})
    # hb.structured_content -> HandbookSearchOutput.model_validate(...)   (status, query, results[])
```
Tests use `Client(build_server(...))` in memory (MCP_SERVERS_GUIDE s.4.1; `tests/unit/mcp_server/test_source_fields.py::_call` does exactly this) so the bot's parser is exercised against the **real** server contract with no network.

D-06 contract the parser relies on (read this session):
```python
# services/mcp_server/buddy_mcp/models.py:10, 13-22
Status = Literal["ok", "no_results"]
TOOL_NAMES: Final = ("handbook_get", "handbook_search", "guides_search", "guides_get_section", "buddy_report_gap")
GAP_MARKER: Final = "nessuna fonte trovata"
DEFAULT_LIMIT: Final = 5
MAX_LIMIT: Final = 10
# models.py:40-79  HandbookPageResult: page_id, title, text, source_url, revision_date, revision_kind = "last_updated"
#                  GuidesSectionResult: section_id, file, heading, line_start, line_end, text,
#                                       source_url, revision_date, revision_kind = "indexed_on", video_url: str | None = None
# models.py:82-107 *SearchOutput: status, query, results
# models.py:115-119 GapReportOutput: status Literal["recorded"], gap_id, marker Literal["nessuna fonte trovata"]
# gap_tool.py:55   async def buddy_report_gap(question: str, tried: list[str] | None = None)
```
Import `buddy_mcp.models` directly in the bot (single source of truth; its header says "Rename only together with both") and put `services/mcp_server` on the bot's `PYTHONPATH`/image (`buddy_mcp/__init__.py` imports nothing heavy, so only pydantic is pulled in). If Joshua prefers the bot image to exclude server code, mirror the models and keep the in-memory contract test as the drift guard.

### Citation gate
```python
def gate(evidence: Mapping[str, Evidence], draft: AnswerDraft, threshold: float) -> GateResult:
    if not evidence:                                   return GateResult.fail("no_evidence")
    if not draft.citations:                            return GateResult.fail("no_citation")
    if any(c.strip() not in evidence for c in draft.citations):
                                                       return GateResult.fail("unsupported_citation")
    if not draft.grounded:                             return GateResult.fail("not_grounded")
    if draft.confidence < threshold:                   return GateResult.fail("low_confidence")
    return GateResult.ok()
```
Gate failure reasons are internal (logged as enum names, never question text); the user only sees the refusal.

### Pub/Sub adapter (thread-to-loop bridge)
```python
# Source: official sample uses SubscriberClient.subscribe(path, callback=...)
# [CITED: github.com/googleworkspace/google-chat-samples python/pub-sub-app/app.py]
def run(self, handler):
    loop = asyncio.get_running_loop()
    def callback(message):
        fut = asyncio.run_coroutine_threadsafe(handler(json.loads(message.data)), loop)
        try:    fut.result()            # blocks this worker thread; lease is extended meanwhile
        finally: message.ack()          # handle() never raises; poison messages must not loop
    self._future = self._subscriber.subscribe(self._path, callback=callback,
                                              flow_control=pubsub_v1.types.FlowControl(max_messages=2))
```
Bad JSON in `message.data` -> log type only, ack. Emulator: set `PUBSUB_EMULATOR_HOST`; create topic and subscription through the admin clients in the test fixture, publish recorded fixtures, assert the fake ChatApi saw placeholder then update.

### Chat API adapter
```python
# google-apps-chat 0.10.9: ChatServiceAsyncClient.create_message / update_message(message=, update_mask=)  [VERIFIED introspection]
# CreateMessageRequest.MessageReplyOption has REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD [VERIFIED]
# Credentials: service account, scope https://www.googleapis.com/auth/chat.bot [CITED: quickstart-pubsub]
created = await client.create_message(request=chat_v1.CreateMessageRequest(
    parent=space_name, message_reply_option=chat_v1.CreateMessageRequest.MessageReplyOption.REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD,
    message=chat_v1.Message(text="Sto cercando nelle fonti…", thread=chat_v1.Thread(name=thread_name))))
await client.update_message(message=chat_v1.Message(name=created.name, text=text, cards_v2=cards),
                            update_mask=field_mask_pb2.FieldMask(paths=["text", "cards_v2"]))
```
Create the async client lazily on first use inside the running loop (same reason as `FirestoreGapLog`). mypy strict: expect `ignore_missing_imports` or narrow `# type: ignore` on the GAPIC imports; keep them behind `chat_api.py`.

### Chat JWT verification (HTTP adapter)
```python
# [VERIFIED signature] id_token.verify_oauth2_token(id_token, request, audience=None, clock_skew_in_seconds=0)
# [CITED] developers.google.com/workspace/chat/verify-requests-from-chat (audience = endpoint URL; check email claim)
def verify(bearer: str) -> bool:
    try:
        claims = id_token.verify_oauth2_token(bearer, google_requests.Request(), audience=cfg.chat_jwt_audience)
    except Exception:  return False
    return claims.get("email") == cfg.chat_jwt_issuer_email and claims.get("email_verified", True) is not False
```
Run it in `asyncio.to_thread` (blocking cert fetch; google-auth caches certs). Missing/invalid -> HTTP 401, no body detail. Unit-test with a locally signed token and an injected verifier; the real function is covered by one test that passes `certs` through a fake `Request`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Chat API `Event` flat payload | Add-on `EventObject` (`chat.messagePayload...`), default for apps created after July 2025 | July 2025 | Normalizer must accept both |
| `langchain-mcp-adapters` | `langchain.mcp.MCPAdapter` (beta) | LangChain v1 | Not used here; plain `fastmcp.Client` |
| Anthropic `temperature` on Messages | Not in `anthropic` 2.6.0 `create()` | SDK 2.x | Do not pass sampling params |
| Native structured output | Exists (`output_config.format`, `messages.parse`) but Meridian support unknown | anthropic 2.x | JSON-in-prompt used for portability |

**Deprecated/outdated:** `langgraph-checkpoint-firestore` is not deprecated, but unsuitable (see Alternatives). HTTP+SSE MCP transport is deprecated (MCP_SERVERS_GUIDE s.12.3); the server is streamable-http.

## Guides applied (D16) — sections and exceptions

| Guide | Sections applied | Exception / deviation |
|-------|------------------|-----------------------|
| LANGGRAPH_GUIDE | s.2 thinking in graphs, s.4 state/reducers, s.5.2 context for dependencies, s.5.3 idempotency, s.6.2 one routing mechanism, s.17.1 retry policy on LLM/MCP nodes, s.21.3 testing nodes as functions and with fakes | s.10.6-10.7 checkpointers: **not used**; thread memory is a Firestore port because a checkpointer persists tool output, has no TTL, and the Firestore saver is third-party (D-10 permits an equivalent store) |
| LANGCHAIN_GUIDE | s.14 "2-step RAG, without an agent" (visible `k`, join format, citation and refusal instruction), s.7 structured output (cap retries; prefer Pydantic; flat schemas) | s.3 `init_chat_model` and `ProviderStrategy` not used: raw `anthropic` Messages client per D-16; structured output via prompt JSON for Meridian portability. s.15 `MCPAdapter` not used (beta, agent-shaped) |
| RAG_CHATBOT_GUIDE | s.17-18 conversational layers and reformulation (last turns only to the rewriter), s.19 window memory, s.20 prompt structure and context order, s.24 confidence gate and citation verification, s.28 indirect injection (retrieved text is data, delimited) | s.24 cosine-threshold gate does not apply (BM25, no vectors, D4/D5); replaced by the `grounded`/`confidence` pair plus the id check. s.28 regex sanitising is not used as a defence; delimiting plus the id check is |
| MCP_SERVERS_GUIDE | s.4.1 SDK as client and in-memory `Client(server)` for tests, s.17-18.1 audience-bound tokens (the bot's ID token has `aud` = the server's `MCP_PUBLIC_BASE_URL`), s.18.4 structured output and treating tool text as untrusted | None |
| DESIGN_PATTERNS_GUIDE | s.9 ports and adapters (intake, LLM, MCP, Chat API, memory), s.4 Adapter, s.5 Strategy (LLM backend), s.3 Factory (backend selection), s.25 Anti-Corruption Layer (event normalizer), s.14 retry with backoff, s.24 timeout; Idempotency Key (dedupe on `message.name`) | No circuit breaker or DLQ: single user, ack-always policy replaces a DLQ |

Section numbers verified against the Guides headings read this session (`grep` of `##` headings in each file). The Idempotency Key pattern is a `###` under s.7 (line 617 of DESIGN_PATTERNS_GUIDE.md).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Event `user.email` is populated in DM events for human senders | Pitfall 3 | Allowlist by email never matches; fall back to `users/<id>` (guard accepts both) |
| A2 | Follow-up messages in a DM share `thread.name`; if not, key memory on `space.name` for DM spaces | Pattern 7, Open Q 3 | Follow-ups lose history (reformulation quality drops); no privacy impact |
| A3 | Chat text limit is about 4,096 chars | Pitfall 10 | Long answers truncated or rejected; cap is configurable |
| A4 | cardsV2 `imageUrl` must be publicly reachable HTTPS | Pitfall 5 | Thumbnail not shown; card still works |
| A5 | `update_message` mask paths are `["text", "cards_v2"]` in the Python GAPIC client | Pitfall 10 | Card not updated; fix mask name in the live checkpoint |
| A6 | Meridian passes through plain Messages requests (no `output_config`), ignores sampling, JSON-in-prompt works through it | Pattern 5, Pitfall 2 | Structured calls fail validation more often; tune prompts or probe `output_config` live |
| A7 | Meridian token refresh needs a writable credentials dir (per Meridian docs), conflicting with D-16 "read-only" | Pitfall 2 | Auth fails after token expiry; needs Joshua's decision |
| A8 | Default `CONFIDENCE_THRESHOLD` 0.7 is a sensible start | Pattern 3 | Over- or under-refusal; tuned in Phase 5 |
| A9 | Pub/Sub streaming pull extends ack deadlines while a callback blocks | Pattern 1 | Redelivery during slow runs; dedupe absorbs it |
| A10 | Cloud Run request-based billing throttles CPU after the response | Pitfall 6 | Background completion stalls (only matters in Phase 4) |
| A11 | `knownIcon` `VIDEO_PLAY` exists (not used by the recommended card; thumbnail is an image widget) | Pattern 6 | None while unused |
| A12 | `LANGSMITH_TRACING` unset/false disables remote tracing | Pitfall 4 | Prompts leave the host; add a test that the variable is false in the image |
| A13 | `message.argumentText` is the text without the @mention; DM `argumentText` equals text | Events | Wrong question text in @mention case; fallback to `text` |
| A14 | The Pub/Sub emulator answers a health probe on its root port | Validation | Compose healthcheck needs another probe |
| A15 | Joshua's host uid is 1000 (Meridian container runs as 1000) | Pitfall 2 | Permission errors on the credentials volume |
| A16 | Chat text link syntax `<url|label>` | Pattern 6 | Links render as plain text |

## Open Questions

1. **Is a text-only handbook citation enough for BOT-09?**
   - Known: handbook `source_url` is `handbook://<page_id>`; there is no web URL (ClickUp is shut down, handbook is a local snapshot).
   - Unclear: whether "show the source link" means a clickable link.
   - Recommendation: render title + `handbook://<page_id>` + revision date as text; record as accepted at the plan checkpoint. A real URL mapping waits for CONT-01 (official handbook).
2. **Thumbnail source.**
   - Known: no field in `index.db` 1.0.0, videos are mp4 release assets.
   - Recommendation: optional `VIDEO_THUMBNAIL_URL` static image; omit when unset. Ask Joshua if he wants a generic image committed under the public repo.
3. **Do DM follow-ups share a thread name?** Decide in the live checkpoint (D-18); the memory key source is one line to change.
4. **Meridian credentials mount (writable vs read-only).** Needs Joshua's choice (Pitfall 2).
5. **Chat app format (add-on or not) and event email.** Joshua configures the app; both shapes are supported, so this only needs recording at the checkpoint along with the manual settings (visibility Joshua only, Pub/Sub topic, slash command `/aiuto` id, authentication audience).
6. **Dev compose Firestore:** emulator (default, no cost, no real data) or the real EU project? D-15 only fixes Pub/Sub and Chat as real.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | everything | yes | 29.9.1 | — |
| Docker Compose | dev compose, emulators | yes | v5.6.0 | — |
| `ai-buddy-test` image | tests | yes (built) | fastmcp 4.1.6, mcp 2.3.0, starlette 1.10.0, uvicorn 0.54.0, requests 2.34.2 | rebuild after new pins |
| Firestore emulator | memory tests | yes | `google/cloud-sdk:592.0.0-emulators` | — |
| Pub/Sub emulator | intake test | yes, same image (`pubsub-emulator` component "Installed", Java present) | 592.0.0 | — |
| PyPI network at build time | new pins | yes (dry-run resolved) | — | — |
| Meridian image | `LLM_BACKEND=meridian` live | no (must be built from rynfar/meridian at a pinned SHA) | npm 1.88.0 | `LLM_BACKEND=api` with an API key |
| Claude Max login on host | Meridian | `~/.claude/.credentials.json` present (mode 600, contents not read) | — | `claude setup-token` profile |
| Anthropic API key | `api` backend | unknown (not checked; `.env` is a protected file) | — | Meridian |
| GCP project with Chat API + Pub/Sub enabled, Chat app configured | live checkpoint, BOT-01 live | unknown (Phase 4 blocker note says no billing project yet) | — | Offline tests + emulator; defer D-18 to Phase 4 as allowed |
| Service-account key file for dev | Pub/Sub, Chat API, ID token minting | unknown | — | none for live; offline tests do not need it |

**Missing with no fallback for the live checkpoint:** GCP project, Chat app, SA key. D-18 allows deferring the checkpoint to Phase 4.
**Missing with fallback:** Meridian image (build it), API key (use Meridian).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 with anyio 4.16.0 (`pytest.mark.anyio`, `anyio_backend` fixture), pytest-cov 7.1.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`; add `services/chat_bot` to `pythonpath`; add markers `pubsub`) |
| Quick run command | `./run-unit-tests.sh --single-file test_<name>.py tests/unit/chat_bot` |
| Full suite command | `./run-unit-tests.sh --all` (ruff, ruff format --check, mypy strict, pytest with `--cov-fail-under=80`; runs `--network none`) |
| Emulator command | `./run-unit-tests.sh --emulator` (extend `docker-compose.test.yml` with a `pubsub` service: `gcloud beta emulators pubsub start --host-port=0.0.0.0:8085`, env `PUBSUB_EMULATOR_HOST: pubsub:8085`; run tests marked `firestore` or `pubsub`) |

Offline tests must need no network: LLM, Chat API and Google certs are fakes; the MCP side is the real server in memory over a synthetic index (`tests/unit/mcp_server/conftest.py` helpers `make_content`, `write_index`, `build_server`).

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOT-01 | Recorded DM and @mention fixtures (both shapes) published to the emulator get a placeholder then an update | integration (pubsub) | `./run-unit-tests.sh --emulator` | ❌ Wave 0 `tests/integration/test_pubsub_intake.py` |
| BOT-01 | `normalize_event` maps add-on and legacy fixtures (message, added, removed, slash) to `ChatEvent` | unit | `--single-file test_events.py tests/unit/chat_bot` | ❌ Wave 0 |
| BOT-02 | HTTP: valid token -> 200 `{}`, missing/invalid/wrong audience/wrong issuer email/expired -> 401 | unit | `--single-file test_http_intake.py tests/unit/chat_bot` | ❌ Wave 0 |
| BOT-03 | Non-allowlisted sender: fake LLM, fake MCP, fake ChatApi all record zero calls | unit | `--single-file test_allowlist.py tests/unit/chat_bot` | ❌ Wave 0 |
| BOT-04 | Graph runs reformulate -> retrieve -> answer; the bot only calls the 5 tool names; contract test parses real server output | unit | `--single-file test_workflow.py tests/unit/chat_bot` | ❌ Wave 0 |
| BOT-05 | Forged citation, empty citations, `grounded=false`, low confidence, all `no_results` each give the refusal, call `buddy_report_gap` once, and retry exactly once first | unit | `--single-file test_gate.py tests/unit/chat_bot` + `test_workflow.py` | ❌ Wave 0 |
| BOT-05 | Answer step never receives earlier answers (D-12): assert the fake LLM's answer-call prompt contains no history text | unit | `test_workflow.py::test_answer_step_sees_no_history` | ❌ Wave 0 |
| BOT-06 | Sensitive fixture: reply = rule + fixed referral suffix; no rule -> referral only + gap; suffix is bot-rendered | unit | `test_sensitive.py` | ❌ Wave 0 |
| BOT-06/D-08 | YAML table equals the SKILL.md "Temi da escalare" rows (fails on drift) | unit | `--single-file test_escalation_drift.py tests/unit/chat_bot` | ❌ Wave 0 |
| BOT-07 | `meridian` vs `api` build the same client class with different `base_url`/key from env only; `vertex` rejected | unit | `test_llm_client.py`, `test_config.py` | ❌ Wave 0 |
| BOT-07 | `structured_call` retries once on invalid JSON then raises | unit | `test_llm_client.py` | ❌ Wave 0 |
| BOT-08 | `meridian` + two users -> startup error naming variables; empty allowlist -> error; `api` + two users -> ok | unit | `test_config.py` | ❌ Wave 0 |
| BOT-09 | Guides+video cited -> `cards_v2` with source link, thumbnail widget (when env set), "Guarda" = `video_url` incl. `#t=`; handbook-only -> text, no card | unit | `test_render.py` | ❌ Wave 0 |
| BOT-10 | Placeholder posted before the graph runs; final patch uses the placeholder's `name`; slow fake LLM does not block placeholder; HTTP adapter returns `{}` | unit | `test_service.py` | ❌ Wave 0 |
| BOT-11 | `caplog` over a full run holds no sender id/email, space, thread or question text | unit | `test_log_hygiene.py` | ❌ Wave 0 |
| BOT-11 | Firestore doc id is the HMAC hex, fields are exactly `turns`, `updated_at`, `expire_at`, `expire_at - updated_at == 24 h`, expired doc ignored on read | integration (firestore) | `./run-unit-tests.sh --emulator` | ❌ Wave 0 `tests/integration/test_firestore_thread_memory.py` |
| BOT-11 | Gap call payload is the standalone question + `tried`, no identity (fake MCP records arguments) | unit | `test_workflow.py` | ❌ Wave 0 |
| D-13/D-14 | `ADDED_TO_SPACE` and `/aiuto`: canned text, zero LLM calls; chitchat/off_topic: no gap | unit | `test_service.py` | ❌ Wave 0 |
| Process | `python -m buddy_bot` real process: fails fast with named variables; with emulators + fake LLM base URL serves one event round trip | integration | `./run-unit-tests.sh --emulator` | ❌ Wave 0 `tests/integration/test_bot_process.py` |
| Env contract | `.env.example` keys equal `CONTRACT_KEYS` (update the set); new requirements file pinned | unit | `--single-file test_repo_layout.py tests/unit` | exists, must be edited |

### Sampling Rate
- **Per task commit:** `./run-unit-tests.sh --single-file <touched test file> tests/unit/chat_bot`
- **Per wave merge:** `./run-unit-tests.sh --all`
- **Phase gate:** `./run-unit-tests.sh --all` and `./run-unit-tests.sh --emulator` green before `/gsd-verify-work`; D-18 live checkpoint recorded (or explicitly deferred to Phase 4)

### Wave 0 Gaps
- [ ] `tests/unit/chat_bot/` package with `conftest.py`: fakes (`FakeLlm` keyed by prompt role, `FakeChatApi`, `InMemoryThreadMemory`, in-memory real MCP server fixture reusing `tests.unit.mcp_server.conftest`), recorded event JSON fixtures for both shapes (DM message, @mention, ADDED_TO_SPACE, REMOVED_FROM_SPACE, slash command) under `tests/fixtures/chat_events/` using synthetic names and `example.invalid` addresses only (public repo)
- [ ] Every test file in the map above
- [ ] `docker-compose.test.yml`: `pubsub` service and env; `run-unit-tests.sh --emulator` to start both emulators and select `-m "firestore or pubsub"`
- [ ] `pyproject.toml`: pythonpath, mypy path/files, ruff src/isort first-party, coverage source, `pubsub` marker; mypy overrides for `google.apps.chat_v1` and `google.cloud.pubsub_v1` if untyped
- [ ] `Dockerfile`: base-stage `PYTHONPATH` gains `services/chat_bot`; `chat_bot` runtime stage (non-root uid 10001, `LANGSMITH_TRACING=false`); `requirements-dev.txt` gains `-r services/chat_bot/requirements.txt`
- [ ] `tests/unit/test_repo_layout.py`: new `.env.example` keys in `CONTRACT_KEYS`; add the new requirements file to the pinned list; secrets (`THREAD_KEY_SECRET`, `ANTHROPIC_API_KEY`, `MERIDIAN_API_KEY`) stay out of `.env.example`

## Security Domain

`security_enforcement` is not set in `.planning/config.json` (file contains only `workflow._auto_chain_active`), so it is treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | HTTP intake: Google-signed ID token, audience and issuer email checked (`verify_oauth2_token`); bot to MCP: Google ID token (D-12) |
| V3 Session Management | no | Stateless; thread key is a pseudonymous HMAC, not a session |
| V4 Access Control | yes | `ALLOWED_USERS` guard before any MCP/LLM call; `LLM_BACKEND=meridian` single-user guard |
| V5 Input Validation | yes | pydantic for events, settings, LLM JSON; question length cap; treat Chat text as hostile |
| V6 Cryptography | yes | stdlib `hmac`/`hashlib` SHA-256 for thread key; secret from env (`SecretStr`, min length checked); no custom crypto |
| V7 Logging | yes | No question text, sender, space or thread in logs; exception types only; log-hygiene test |
| V8 Data Protection | yes | 24 h TTL plus read-side expiry; no sender fields stored; Firestore EU |
| V13 API | yes | Starlette route accepts POST only; 401 without detail; body size cap |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Forged Chat event on the HTTP endpoint | Spoofing | JWT verification on every request; audience = endpoint URL; issuer email allowlist |
| Event from a non-allowlisted user (DM or room) | Elevation | Silent drop before any downstream call; no reply content |
| Indirect prompt injection in retrieved text (RAG s.28; MCP s.18.4) | Tampering | Evidence delimited as data in the prompt; answer schema is JSON; citations checked against run evidence; bot renders links; no tool execution by the model |
| Prompt injection in the user question | Tampering | Same; answer limited to evidence; referral text fixed in code |
| Fabricated citation | Repudiation/Tampering | Exact `source_url` equality (D-02) |
| Token leakage (SA key, Meridian credentials, API key) | Information disclosure | Env/secret files only, never baked or committed, `.env.example` placeholders; errors name variables; Meridian port not published to the host and gated by `MERIDIAN_API_KEY` |
| Conversation data at rest (D-10) | Information disclosure | HMAC key, no sender fields, N turns, TTL, access limited to the bot service account; rollout re-check item |
| Telemetry exfiltration (LangSmith) | Information disclosure | `LANGSMITH_TRACING=false` asserted in test |
| Redelivery/duplicate event | DoS/Repudiation | Dedupe on `message.name`; ack-always |
| Rate limit exhaustion of MCP server | DoS | One MCP session per run (Pitfall 9) |

## Project Constraints (from CLAUDE.md)

No project `./CLAUDE.md` exists. Directives come from the global `~/.claude/CLAUDE.md` and the project memory, treated with the authority of locked decisions:
- Python only; everything runs in Docker (build, test, dev); tests via `run-unit-tests.sh` (`--all`, `--single`, `--single-file`), image built first, `docker run --rm` with env file and cwd mount. No Python on the host.
- `ruff` (lint + format), `pytest -v --tb=short`, type hints on public functions, `mypy --strict` where feasible.
- `pip` with pinned `requirements*.txt` (repo enforces `==`).
- No speculative abstractions or future-proofing: ports only where the repo pattern and CONTEXT require them (intake, LLM, MCP, Chat API, memory).
- Never echo `.env` or secrets; redact in examples. The repo is **public**: internal docs only under `docs/internal/`, fixtures synthetic, no real addresses or names.
- Work directly on `main`, no branches, no commits or pushes unless Joshua asks (research was not committed).
- Apply Guides sections per D16 and justify exceptions (done above).
- Never invent file paths or APIs: this document's code is marked with its verification source; unverified items are in the Assumptions Log.

## Sources

### Primary (HIGH confidence)
- In-repo, read this session: `services/mcp_server/buddy_mcp/{models,config,auth,gaplog,gap_tool,cli,guides_tools}.py`, `services/mcp_server/README.md`, `packages/buddy_core/buddy_core/{models,index_reader}.py`, `skills/digitiamo-buddy/SKILL.md`, `pyproject.toml`, `Dockerfile`, `docker-compose.test.yml`, `run-unit-tests.sh`, `.env.example`, `tests/unit/test_repo_layout.py`, `tests/integration/*`, `docs/index-format.md`, `docs/guides-contract.md`
- Guides (local): LANGGRAPH_GUIDE, LANGCHAIN_GUIDE, RAG_CHATBOT_GUIDE, MCP_SERVERS_GUIDE, DESIGN_PATTERNS_GUIDE sections listed above
- Introspection of installed/resolved packages in Docker: `fastmcp` 4.1.6 client signatures, `google.oauth2.id_token`, `anthropic` 2.6.0 `messages.create`/`OutputConfigParam`, `google-apps-chat` 0.10.9 async client, `google-cloud-pubsub` 2.43.0 `subscribe`
- developers.google.com/workspace/chat/events, /verify-requests-from-chat, /convert, /api/reference/rest/v1/{User, cards, spaces.messages/patch}; developers.google.com/workspace/add-ons/chat/quickstart-pubsub; github.com/googleworkspace/google-chat-samples `python/pub-sub-app/app.py`

### Secondary (MEDIUM confidence)
- github.com/rynfar/meridian README, `docs/deployment.md`, `docs/configuration.md` (first 100,000 characters only), `Dockerfile`; npm registry metadata for `@rynfar/meridian`
- PyPI metadata for `langgraph-checkpoint-firestore` 0.4.0 (wheel inspected)

### Tertiary (LOW confidence)
- Web search summaries on Meridian setup and terms (third-party wikis); not used for decisions beyond pointing to primary docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, every version resolved together in a dry run and the key APIs introspected
- Architecture: MEDIUM-HIGH, follows CONTEXT and repo patterns; the `ThreadMemory`-instead-of-checkpointer departure is justified but needs planner acceptance
- Pitfalls: MEDIUM, Chat event details and Meridian behaviour rest partly on docs and on assumptions A1-A7 that the D-18 live checkpoint resolves

**Research date:** 2026-11-07
**Valid until:** 2026-11-21 (fast-moving: Meridian ships near-daily, anthropic/langgraph release weekly; re-run the legitimacy and version checks at plan time)
