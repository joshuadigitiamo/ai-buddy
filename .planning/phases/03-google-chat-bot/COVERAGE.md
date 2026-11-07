# API Coverage — Phase 3

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 3 integrates the Google Chat API and Chat events, Cloud Pub/Sub, the Anthropic Messages API (directly or through Meridian), Cloud Firestore for thread memory, Google ID tokens, and the client side of the MCP protocol. Each surface is listed below.

## Google Chat API, app authentication (plans 03-10, 03-11, 03-12)

| capability | decision | reason |
|---|---|---|
| spaces.messages.create (reply in thread, REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD) | INTEGRATE | |
| spaces.messages.patch / update (text and cards_v2 field mask) | INTEGRATE | |
| cardsV2 message cards (header, image, textParagraph, buttonList with openLink) | INTEGRATE | |
| spaces.messages.get / list | OPT-OUT | not needed: the bot only updates the message it created and keeps no Chat history (D-10/D-11 use its own memory port) |
| spaces.messages.delete | OPT-OUT | not needed: the placeholder is always updated in place (D-09) |
| reactions, attachments, media upload/download | OPT-OUT | not needed: answers are text plus cards |
| private messages (privateMessageViewer) | OPT-OUT | not needed yet: DMs are already private; revisit for room use before rollout |
| accessory widgets, dialogs, interactive card actions | OPT-OUT | not needed: the only buttons open links (D15) |
| spaces / members / spaceEvents / read-state / custom emoji APIs | OPT-OUT | not needed: the bot never manages spaces or reads membership |
| user authentication (acting as a user) | OPT-OUT | explicitly out of scope: app authentication with the chat.bot scope only (least privilege) |

## Google Chat events (plans 03-03, 03-04, 03-09, 03-10)

| capability | decision | reason |
|---|---|---|
| MESSAGE in DM and @mention in rooms, legacy and add-on formats | INTEGRATE | |
| ADDED_TO_SPACE (intro text) | INTEGRATE | |
| REMOVED_FROM_SPACE (ignored, no reply possible) | INTEGRATE | |
| slash command / app command (/aiuto) | INTEGRATE | |
| HTTP endpoint delivery with Google-signed JWT (audience = endpoint URL) | INTEGRATE | |
| Pub/Sub delivery (pull subscription) | INTEGRATE | |
| self-signed JWT with project-number audience | OPT-OUT | not needed: only the endpoint-URL audience mode is configured and documented (RESEARCH Pitfall 7) |
| CARD_CLICKED / widget updates / dialogs | OPT-OUT | not needed: cards carry only openLink buttons |
| link previews (matchedUrl), app home | OPT-OUT | not needed: no preview or home surface in BOT-01..BOT-11 |
| Google Workspace Events API subscriptions | OPT-OUT | not needed: Chat app events cover DMs and mentions |

## Cloud Pub/Sub (plans 03-10, 03-11, 03-12)

| capability | decision | reason |
|---|---|---|
| streaming pull subscribe with flow control | INTEGRATE | |
| ack (after handle, always) | INTEGRATE | |
| automatic lease extension (modify ack deadline by the client library) | INTEGRATE | |
| publish | OPT-OUT | not needed at runtime: Google Chat publishes; tests publish only on the emulator |
| topic and subscription admin | OPT-OUT | not needed at runtime: created manually per the README; tests create them only on the emulator |
| nack / explicit redelivery | OPT-OUT | not needed: handle never raises and every message is acked (poison messages must not loop) |
| dead-letter topics | OPT-OUT | not needed: single user, ack-always policy |
| ordering keys, exactly-once delivery | OPT-OUT | not needed: events are independent; duplicates are absorbed by message-name dedupe |
| push subscriptions | OPT-OUT | explicitly out of scope: D-15 uses a pull subscription so no public URL is needed in dev |
| filters, schemas, snapshots/seek, BigQuery/Cloud Storage subscriptions | OPT-OUT | not needed |

## Anthropic Messages API via the anthropic SDK (Meridian or API key) (plans 03-06, 03-11, 03-12)

| capability | decision | reason |
|---|---|---|
| messages.create with system prompt and max_tokens | INTEGRATE | |
| base_url and api_key selection by LLM_BACKEND (meridian, api) | INTEGRATE | |
| request timeout and client retries | INTEGRATE | |
| Vertex AI backend | OPT-OUT | not needed yet: BOT-07 requires it configured but not enabled; refused at startup |
| streaming responses | OPT-OUT | not needed: the placeholder is replaced once with the final answer (D-09) |
| tool use / function calling | OPT-OUT | explicitly out of scope: fixed 2-step workflow, the model never decides to search (BOT-04) |
| native structured output (output_config, messages.parse) | OPT-OUT | not needed yet: Meridian support is undocumented (RESEARCH A6); JSON-in-prompt keeps the backend switch configuration-only; revisit after a live probe |
| native citations / search-result content blocks | OPT-OUT | explicitly out of scope: D-02 locks the bot-side citation check on source ids |
| prompt caching | OPT-OUT | not needed yet: cost tuning belongs to Phase 5 |
| extended thinking | OPT-OUT | not needed: short grounded answers |
| message batches, token counting, files API, models list | OPT-OUT | not needed: interactive single requests |

## Cloud Firestore, thread memory (plans 03-07, 03-11)

| capability | decision | reason |
|---|---|---|
| get document by id | INTEGRATE | |
| set (overwrite) document | INTEGRATE | |
| TTL policy on expire_at | INTEGRATE | |
| transactions | OPT-OUT | not needed: last write wins is accepted for one user (backstop truth in 03-07) |
| queries, aggregation, listeners | OPT-OUT | not needed: access is by key only |
| explicit delete | OPT-OUT | not needed: TTL and read-side expiry remove old turns |

## Google identity tokens (plans 03-10, 03-11)

| capability | decision | reason |
|---|---|---|
| verify_oauth2_token for Chat requests (signature, issuer, expiry, audience) | INTEGRATE | |
| fetch_id_token for bot-to-MCP calls (service-account file or metadata server) | INTEGRATE | |
| IAM Credentials generateIdToken (impersonation) | OPT-OUT | not needed: the bot runs as its own service account |

## MCP protocol, client side (plans 03-03, 03-05, 03-11)

| capability | decision | reason |
|---|---|---|
| initialize over streamable HTTP (stateless JSON) | INTEGRATE | |
| tools/call handbook_search | INTEGRATE | |
| tools/call guides_search | INTEGRATE | |
| tools/call buddy_report_gap | INTEGRATE | |
| bearer auth with a Google ID token | INTEGRATE | |
| tools/call handbook_get | OPT-OUT | not needed yet: handbook_search already returns whole pages (Phase 2 D-03) |
| tools/call guides_get_section | OPT-OUT | not needed yet: guides_search returns the full section text; revisit if Phase 5 shows truncated evidence |
| tools/list | OPT-OUT | not needed: tool names are fixed by buddy_mcp.models.TOOL_NAMES and each call costs rate-limit tokens (RESEARCH Pitfall 9) |
| resources/read (handbook://{pagina}) | OPT-OUT | not needed: search results carry the page text |
| prompts, sampling, elicitation, roots, notifications | OPT-OUT | not needed: the server is stateless and exposes none of these |
