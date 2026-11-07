---
phase: 03-google-chat-bot
verified: 2026-11-07T15:00:00Z
status: passed
score: 8/8 must-haves verified
score_note: "Human items resolved by live check 2026-11-07 or explicitly accepted/deferred by Joshua; the video-hosting issue (Guarda button downloads the mp4) is accepted for M1 and deferred to Phase 4"
covered_files:
  - ".env.example"
  - ".planning/phases/03-google-chat-bot/03-01-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-01-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-02-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-02-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-03-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-03-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-04-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-04-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-05-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-05-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-06-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-06-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-07-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-07-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-08-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-08-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-09-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-09-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-10-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-10-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-11-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-11-SUMMARY.md"
  - ".planning/phases/03-google-chat-bot/03-12-PLAN.md"
  - ".planning/phases/03-google-chat-bot/03-12-SUMMARY.md"
  - "docker-compose.dev.yml"
  - "packages/buddy_core/buddy_core/data/escalation_topics.yaml"
  - "packages/buddy_core/buddy_core/escalation.py"
  - "services/chat_bot/README.md"
  - "services/chat_bot/buddy_bot/__init__.py"
  - "services/chat_bot/buddy_bot/__main__.py"
  - "services/chat_bot/buddy_bot/chat_api.py"
  - "services/chat_bot/buddy_bot/cli.py"
  - "services/chat_bot/buddy_bot/config.py"
  - "services/chat_bot/buddy_bot/events.py"
  - "services/chat_bot/buddy_bot/gate.py"
  - "services/chat_bot/buddy_bot/intake/__init__.py"
  - "services/chat_bot/buddy_bot/intake/http.py"
  - "services/chat_bot/buddy_bot/intake/pubsub.py"
  - "services/chat_bot/buddy_bot/llm.py"
  - "services/chat_bot/buddy_bot/mcp_client.py"
  - "services/chat_bot/buddy_bot/memory.py"
  - "services/chat_bot/buddy_bot/ports.py"
  - "services/chat_bot/buddy_bot/prompts.py"
  - "services/chat_bot/buddy_bot/referral.py"
  - "services/chat_bot/buddy_bot/render.py"
  - "services/chat_bot/buddy_bot/schemas.py"
  - "services/chat_bot/buddy_bot/service.py"
  - "services/chat_bot/buddy_bot/workflow.py"
  - "services/chat_bot/requirements.txt"
covered_digest: "v4:sha256:913b830c7f2e3fc400b0e8c0e8e63b94a3307c66cc23527799e1a7df14f580b9"
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth: "A room @mention (and a bare '@AI Buddy' with blank argumentText) from an allowlisted user gets the placeholder in the room thread and then the answer"
    test: "In a Google Chat room that contains the bot and Joshua, post '@AI Buddy Come richiedo le ferie?' and then a bare '@AI Buddy'"
    expected: "The first gets a placeholder in the same thread, replaced by a cited answer, with the mention text absent from the question the bot reformulates; the second gets the /aiuto usage text and no workflow run"
    why_human: "Only synthetic fixtures (spaces/AAAAsyntheticRoom) cover it; Google's real room payload shape, argumentText behaviour and the two-word mention fallback cannot be exercised without a real room (WINDOWS.md #2)"
human_verification:
  - test: "Room @mention and bare '@AI Buddy' in a real room"
    expected: "See behavior_unverified_items; BOT-01 and ROADMAP SC1 name @mention explicitly"
    why_human: "Live only; unit tests use synthetic fixtures"
  - test: "Click Guarda on the video card of a Guides answer with a scene-mapped video"
    expected: "The video opens at the scene offset (URL carries #t=<seconds>); a section with no scene opens the full video"
    why_human: "The bot passes the index's video_url unchanged to an openLink button and buddy_core composes the #t= suffix (unit tested), but Chat buttons expose no href, so the opened result needs a human click (WINDOWS.md #3)"
  - test: "Confirm the Guides source line renders as a clickable title link in Chat"
    expected: "'Fonte: Guida – <title>' is a live link to the permalink (Markdown [title](url) under the MARKDOWN app markup)"
    why_human: "03-12-SUMMARY says this was 'not yet seen rendered live'; the orchestrator reports it seen. One look in Chat closes the discrepancy"
  - test: "Bot-to-MCP call with a real Google ID token (AUTH_MODE on) and the HTTP endpoint with a real Google-signed Chat JWT"
    expected: "MCP server accepts the bot's token; HTTP intake accepts a genuine Chat request and rejects a missing or forged one"
    why_human: "Live check ran with AUTH_MODE=off over Pub/Sub; both paths are unit-tested with real RSA keys and mocked token minting but need a deployed environment (WINDOWS.md #1, Phase 4)"
  - test: "ADDED_TO_SPACE intro message after install"
    expected: "Short Italian intro text is posted"
    why_human: "First install hit the Pub/Sub publish permission error and was not re-triggered (WINDOWS.md #4). Not a BOT requirement; D-13 behaviour"
---

# Phase 3: Google Chat Bot Verification Report

**Phase Goal:** Joshua can ask the bot a question in Google Chat and get a cited, grounded answer (or an honest refusal or escalation) with a video card when one exists.
**Verified:** 2026-11-07
**Status:** passed
**Re-verification:** No, initial verification

## Goal Achievement

The goal is achieved for the DM path, which is what the live check exercised: a real Google Chat DM through Pub/Sub, real Meridian, real MCP server. I read the code that implements each success criterion and re-ran both test gates myself. One roadmap-named path, a room @mention, has only synthetic-fixture evidence, so the status is human_needed rather than passed. I found no code defect and no gap.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1a: An allowlisted DM delivered through Pub/Sub gets a placeholder then an in-place answer within the window or as an async follow-up | VERIFIED | `service.py` `_answer`: create placeholder, `_run` under `asyncio.timeout(run_deadline_seconds)`, `_deliver` patches the same message (card, then text-only, then new error message). `intake/pubsub.py` pull intake wired in `cli.py` `_build_intake`. Live DM on 2026-11-07 (03-12-SUMMARY). `tests/integration/test_pubsub_intake.py` and `test_bot_process.py` pass in `--emulator` (12 passed, re-run by me) |
| 2 | SC1b: An @mention in a room from an allowlisted user gets the same | PRESENT_BEHAVIOR_UNVERIFIED | `events.py` normalizes `addon_room_mention.json` and `legacy_room_mention.json`; `test_tracer.py::test_addon_room_mention_gets_placeholder_in_thread_then_answer` passes. Fixtures are synthetic (`spaces/AAAAsyntheticRoom`). Never run in a real room (WINDOWS.md #2); the two-word `@AI Buddy` fallback path (IN-01 fix) is also unexercised live |
| 3 | SC1c: The HTTP endpoint accepts a valid Google JWT and rejects missing or invalid ones | VERIFIED | `intake/http.py`: `ChatTokenVerifier` (empty audience refused, `verify_oauth2_token` with audience, issuer-email match, JWT-shape and 8192-char pre-check, cached cert fetch with 5 s timeout). `build_http_app` returns 401 on a missing or failing token before reading the body, 413/400 on bad bodies. `test_http_intake.py` uses a real RSA signature and google-auth's real verifier. Live JWT not exercised (Phase 4 deploy) |
| 4 | SC2: A non-allowlisted sender gets no content and triggers no MCP or LLM call; meridian refuses to start with more than one allowed user; backend switch is configuration only | VERIFIED | `service.py` `_handle`: allowlist check precedes every send, MCP or LLM call, and it logs no identity. `config.py` `_check_startup_guards`: raises for meridian with more than one entry, empty list, vertex, and `LANGSMITH_TRACING`. `tests/unit/chat_bot/test_allowlist.py::test_stranger_gets_no_call_for_any_event_kind`, `test_config.py`, `test_llm_client.py`. `llm.py` `build_llm_client` selects base_url/key by `LLM_BACKEND` |
| 5 | SC3: Every citation maps to content the tools returned in this run; no source, unsupported citation or low confidence gives "Non lo so, chiedi a ..." and a gap with no user id | VERIFIED | `gate.py` `check` (no_evidence, no_citation, unsupported_citation, not_grounded, low_confidence). `workflow.py`: failure gives one `retry_plan` then `refuse`; `run_workflow` calls `report_gap` once after the graph, with the standalone question. Sources and links are built by `render.py` from Evidence, never from model text. Live: refusal plus gap doc with fields `build_id, created_at, expire_at, marker, question, tried`, no identity. `test_gate.py`, `test_refusal.py`, `test_workflow.py`, `test_log_hygiene.py` |
| 6 | SC4: Sensitive topics get at most the general written rule plus a referral to a person | VERIFIED | `workflow.py` `reformulate` normalises `sensitive_topic` to table ids only (WR-03 fix); `answer` uses `ANSWER_SENSITIVE_SYSTEM`; `finish` and `refuse` attach `resolve_referente`; `render._referral_sentence` gives "Per il tuo caso specifico chiedi a ...". Escalation table is shared data in `buddy_core` with a drift test against SKILL.md. Live: general rule plus referral to HR. `test_sensitive.py` |
| 7 | SC5: A Guides answer with a mapped video shows a card with source link, thumbnail and "Guarda" button; handbook answers show the source link | VERIFIED (card) | `render._video_card` builds cardsV2 (header, image, textParagraph, buttonList with `Fonte` and `Guarda` openLink); `evidence_from` carries `video_url` from the MCP structured output. Handbook answers get `Fonte: Manuale – <title> (handbook://<id>), revisione <date>` per the 03-01 bot09_rendering decision. Live card with thumbnail, Fonte and Guarda confirmed; the `["text","cards_v2"]` patch mask worked live. The `#t=` offset behaviour of Guarda is a human item below |
| 8 | BOT-11: No log or store persists user identity next to question text | VERIFIED | Every `_LOGGER` call in `buddy_bot` carries fixed text and exception type names only; `uvicorn` access log off; memory document is `{turns, updated_at, expire_at}` keyed by HMAC with a 24 h TTL and a read-side expiry check; gap stores the standalone question. `test_log_hygiene.py::test_no_log_record_carries_identity_question_or_answer`, `test_memory.py` |

**Score:** 7/8 truths verified (1 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `services/chat_bot/buddy_bot/workflow.py` | LangGraph 2-step RAG, gate, retry, refusal | VERIFIED | 302 lines, real graph, wired from `service.py`; tools reached over MCP, no retrieval logic in the bot |
| `gate.py`, `render.py`, `referral.py`, `schemas.py` | Citation and confidence gate, rendering, referente | VERIFIED | Substantive, imported by workflow and service |
| `service.py`, `events.py`, `chat_api.py` | Allowlist, dedupe, placeholder-patch, event normalisation, Chat API | VERIFIED | Wired from `cli.py` composition root |
| `intake/pubsub.py`, `intake/http.py` | One intake port, two adapters | VERIFIED | Both implement `IntakePort`; `cli._build_intake` selects by `INTAKE` |
| `llm.py`, `config.py` | One client by `LLM_BACKEND`, startup guards | VERIFIED | `build_llm_client`, `BotSettings` validators |
| `memory.py` | HMAC-keyed Firestore memory with TTL | VERIFIED | Port plus Firestore adapter, emulator test passes |
| `mcp_client.py` | MCP client with Google ID token auth | VERIFIED (token path unrun live) | `FastMcpConnector`, `GoogleIdTokenAuth`; live token minting is WINDOWS.md #1 |
| `packages/buddy_core/buddy_core/escalation.py` + YAML | Shared topic to role table | VERIFIED | Loaded by the bot, drift test with SKILL.md |
| `docker-compose.dev.yml`, `services/chat_bot/README.md` | Dev stack and manual settings | VERIFIED | Guard tests `test_dev_compose.py`, `test_readme_contract.py` pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli._run` | `BotService` | `service.handle` passed to `run(intake, ...)` | WIRED | |
| `BotService._run` | `run_workflow` | direct call under `asyncio.timeout` | WIRED | |
| `workflow.retrieve` | MCP server | `FastMcpTools.handbook_search` and `guides_search` | WIRED | live over HTTP to the MCP container |
| `workflow.run_workflow` | `buddy_report_gap` | `_log_gap` on refusal and referral | WIRED | gap docs seen live |
| `render.render_reply` | Chat message | `service._deliver` to `ChatApi.update_message(text, cards_v2)` | WIRED | |
| `BotSettings` | startup | `BotSettings()` in `cli._run` raises before any intake starts | WIRED | |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `render._source_line`, `_video_card` | `reply.sources` (Evidence) | `evidence_from(handbook, guides)` over the real MCP structured output | Yes (live handbook and Guides answers) | FLOWING |
| `render._video_section` thumbnail | `video_thumbnail_url` | `BotSettings.video_thumbnail_url` (required https env) | Yes (a Google sample image live, not Digitiamo's logo) | FLOWING (placeholder value) |
| `workflow._referente` | contact | `resolve_referente` via `handbook_search`, HR fallback | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full gate: ruff, ruff format, mypy --strict, pytest | `./run-unit-tests.sh --all` | 1018 passed, 26 skipped (local-only live-artifact tests), exit 0 | PASS |
| Emulator integration (Pub/Sub, Firestore, bot process) | `./run-unit-tests.sh --emulator` | 12 passed | PASS |

### Probe Execution

Step 7c: SKIPPED. The plans declare no `probe-*.sh` scripts.

### Requirements Coverage

All 11 IDs are claimed by at least one PLAN frontmatter; REQUIREMENTS.md maps BOT-01..BOT-11 to Phase 3 and lists no further Phase 3 IDs (no orphans).

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BOT-01 | 03-03, 03-04, 03-10, 03-11, 03-12 | Pub/Sub intake, DM and @mention | SATISFIED for DM, NEEDS HUMAN for room @mention | Truths 1, 2 |
| BOT-02 | 03-10, 03-11 | HTTP endpoint with JWT verification, one intake interface | SATISFIED (unit, real RSA) | Truth 3; live JWT is a Phase 4 item |
| BOT-03 | 03-03, 03-09, 03-12 | `ALLOWED_USERS` guard before any MCP or LLM call | SATISFIED | Truth 4. The "visible to Joshua only" setting is manual and documented in the README; live app was configured so |
| BOT-04 | 03-03, 03-05 | LangGraph 2-step RAG over MCP, no duplicate retrieval | SATISFIED | `workflow.py`, `mcp_client.py` |
| BOT-05 | 03-03, 03-05, 03-08 | Citation check, refusal and gap | SATISFIED | Truth 5 |
| BOT-06 | 03-02, 03-05 | Sensitive topics: general rule plus referral | SATISFIED | Truth 6 |
| BOT-07 | 03-01, 03-06, 03-11, 03-12 | One LLM client by `LLM_BACKEND` | SATISFIED | `llm.py`, `config.py`; the `api` backend is unit-tested, only Meridian was run live |
| BOT-08 | 03-06, 03-11, 03-12 | Refuse to start with meridian and more than one user | SATISFIED | `config.py` guard, `test_config.py` |
| BOT-09 | 03-01, 03-08, 03-12 | Video card, thumbnail, Guarda; handbook source link | SATISFIED (card live); Guarda `#t=` offset needs a human click | Truth 7 |
| BOT-10 | 03-01, 03-03, 03-04, 03-08, 03-09, 03-10, 03-12 | Answer within the window or async follow-up | SATISFIED | Placeholder then patch; HTTP path waits up to 25 s then acks and continues |
| BOT-11 | 03-01, 03-05, 03-07, 03-09, 03-11 | No identifiers next to question text | SATISFIED | Truth 8 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (all phase source files) | n/a | grep for TBD, FIXME, XXX, TODO, HACK: no matches | none | n/a |
| `.env.example` | 57 | `VIDEO_THUMBNAIL_URL` is a placeholder value (example.invalid); the live run used Google's sample image | Warning | A thumbnail shows, but it is not Digitiamo's. Tracked as WINDOWS.md #6; replace before wider use |

### Review Findings

03-REVIEW.md found 0 critical, 5 warnings and 5 info items. 03-REVIEW-FIX.md fixed 9, with regression tests. IN-05 was skipped as a documented design decision (a model outage shows the error text and logs no false gap; trailing Fonte lines are dropped to fit 4,000 characters). The WR-03 fix reverses a 03-05 choice and is marked "requires human verification" there. Its behaviour is pinned by `test_sensitive.py` and the sensitive path passed live, but the model's `sensitive_topic` choices are covered only by the Phase 5 golden set.

### Human Verification Required

#### 1. Room @mention and bare "@AI Buddy"
**Test:** In a Chat room with the bot and Joshua, post "@AI Buddy Come richiedo le ferie?", then a bare "@AI Buddy".
**Expected:** Placeholder in the same thread, then a cited answer, with no "@AI Buddy" text in the reformulated question. The bare mention gets the usage text.
**Why human:** BOT-01 and SC1 name @mention. Only synthetic fixtures exist. Non-blocking if Joshua accepts the DM-only live evidence for M1 (the bot is single-user, so DMs are the main channel).

#### 2. Guarda button offset
**Test:** Click Guarda on a Guides video card.
**Expected:** The clip opens at the scene offset, or the full video when the section has no scene.
**Why human:** Chat buttons expose no href.

#### 3. Guides source link rendering
**Test:** Look at the "Fonte: Guida" line of a Guides answer.
**Expected:** The section title is a clickable link.
**Why human:** 03-12-SUMMARY says unseen live, the orchestrator says seen; confirm once.

#### 4. Authenticated bot-to-MCP and HTTP-JWT paths
**Test:** Deployed check (Phase 4) with `MCP_AUTH=google_id_token` and a real Chat HTTP request.
**Expected:** Accepted with a valid token, rejected otherwise.
**Why human:** Needs a deployed environment; the live check ran with auth off.

#### 5. Intro message on install
**Test:** Remove and re-add the app.
**Expected:** The intro text appears.
**Why human:** Not re-triggered after the permission error. Not a BOT requirement.

### Gaps Summary

No gaps. Every roadmap success criterion has implementation, wiring and test evidence, and all 11 requirement IDs are accounted for. Both gates pass when re-run (1018 passed and 12 emulator tests). The live check covers the DM goal end to end: handbook answer, Guides video card, sensitive referral, refusal with gap, follow-up memory, and `/aiuto`. The status is `human_needed` only because the room @mention path, which BOT-01 and SC1 name, has never run against a real room. The other open items (Guarda offset, authenticated live paths, intro on install) are tracked in `.planning/WINDOWS.md` (open_count 6) and do not contradict the goal. Model-behaviour items (parking classification, brevity, sensitive topic choice) are deferred to Phase 5 goldens.

---

_Verified: 2026-11-07_
_Verifier: Claude (gsd-verifier)_

## Human verification (2026-11-07)

Live checks run by the orchestrator in Google Chat, in a private space "AI Buddy test" (only Joshua and the bot, deleted afterwards).

| Item | Result |
|------|--------|
| Room @mention "come richiedo le ferie?" | PASS. Answer posted in the message's thread, answer-first, with a Fonte line (BOT-01 room path). |
| Bare "@AI Buddy" | PASS. Usage text returned (the IN-01 fix works live). |
| Intro on add to space | PASS. "Ciao, sono AI Buddy..." posted. |
| Guides Fonte line as Markdown link | PASS. Renders as a clickable title. |
| Guarda button | ISSUE, accepted and deferred. Joshua clicked it and the browser downloaded the mp4 instead of playing it. |
| Live bot-to-MCP google_id_token call; real Chat-signed HTTP JWT | Still unverified until the Phase 4 deploy (both unit-tested). |

### Guarda button: root causes

The bot builds the button correctly from the index. The problem is hosting and index data:

1. GitHub release assets are served as attachments, so the browser downloads them and the `#t=` offset never applies.
2. The joshuadigitiamo/Guides repo is private. All 17 distinct video URLs and the repo page return 404 anonymously; the video worked for Joshua only because he was signed in.
3. Only 238 of 2524 video_map rows have `start_seconds` (source=scene). The other 2286 are `readme_fallback` rows with no offset.

### Decision

Joshua accepts this as a known issue for M1 and defers the fix to Phase 4 (hosting). Recommended path: Cloud Storage serving `video/mp4` inline with access control (the Guides are private, so not public), plus better timestamp coverage in the Phase 2 index. Recorded as a Phase 4 success criterion in ROADMAP.md and in WINDOWS.md.
