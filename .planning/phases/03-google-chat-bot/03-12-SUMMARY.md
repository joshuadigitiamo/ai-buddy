---
phase: 03-google-chat-bot
plan: 12
subsystem: dev-stack-and-live-check
tags: [docker-compose, meridian, pubsub, google-chat, readme, live-check, add-on-app]
status: complete

requires:
  - phase: 03-google-chat-bot (03-01)
    provides: "approved Meridian commit SHA, meridian_credentials and dev_firestore decisions"
  - phase: 03-google-chat-bot (03-06)
    provides: "BotSettings env contract"
  - phase: 03-google-chat-bot (03-10)
    provides: "PubSubIntake, GoogleChatApi"
  - phase: 03-google-chat-bot (03-11)
    provides: "composition root, chat_bot image, GoogleIdTokenAuth"
provides:
  - "docker-compose.dev.yml: meridian (pinned SHA build), firestore emulator, mcp_server, chat_bot; no published ports"
  - "services/chat_bot/README.md: env contract, manual Chat app settings, Pub/Sub IAM, rollout checklist"
  - "Structural guard tests for the dev compose file and the README"
  - "Live Google Chat check (D-18) passed by Joshua on 2026-11-07"
affects: [phase-04-deploy, phase-05-golden-set]

actuals:
  tokens: 7400
  tasks: 3
  commits: 7
plan_head_before: 4739d359a30692dfdea22b6032150e4285a63a85
commits: 7
plan_head_after: 9b80925450a08e521ffa2122dc96673baea2b0d3

tech-stack:
  added: []
  patterns:
    - "Bot container shares the MCP server network namespace so MCP_URL is loopback and the server Host guard admits plain http"
    - "Compose guard test: no ports, 40-hex Meridian SHA, read-only mounts, secrets only as interpolations"

key-files:
  created:
    - docker-compose.dev.yml
    - tests/unit/test_dev_compose.py
    - services/chat_bot/README.md
    - tests/unit/chat_bot/test_readme_contract.py
  modified:
    - .planning/STATE.md
    - services/chat_bot/buddy_bot/prompts.py
    - services/chat_bot/buddy_bot/render.py
    - services/chat_bot/buddy_bot/service.py
    - tests/unit/chat_bot/test_prompts.py
    - tests/unit/chat_bot/test_render.py
    - tests/unit/chat_bot/test_service.py

key-decisions:
  - "Add-on Chat apps publish to Pub/Sub as the gsuiteaddons service agent, not chat-api-push; the topic publisher grant goes to that account only (RESEARCH assumption corrected, README fixed)"
  - "Bot shares the MCP server network namespace (MCP_URL on localhost) because the server Host guard admits http only for loopback"
  - "Reformulate prompt treats workplace logistics questions (parking, car, office) as in scope so they reach retrieval and end in refusal plus gap instead of off_topic"
  - "Meridian per-request logging silenced in the dev stack with MERIDIAN_SILENT=1"
  - "Chat app markup is MARKDOWN; renderer and usage text put one paragraph per line"

requirements-completed: [BOT-01, BOT-03, BOT-07, BOT-08, BOT-09, BOT-10]

coverage:
  - id: D1
    description: "One-command live dev stack (Meridian, MCP server, bot, Firestore emulator) on the real Pub/Sub subscription, no published ports, no secret in the file"
    requirement: "BOT-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_dev_compose.py"
        status: pass
      - kind: manual_procedural
        ref: "docker compose -f docker-compose.dev.yml up, live DMs on 2026-11-07"
        status: pass
  - id: D2
    description: "Bot README with every BotSettings variable, manual Chat app settings (visibility Joshua only), Pub/Sub IAM and the Prima di un secondo utente checklist"
    requirement: "BOT-03"
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_readme_contract.py"
        status: pass
  - id: D3
    description: "Live check: handbook answer, Guides answer with video card, sensitive question, no-source question, DM follow-up, /aiuto"
    requirement: "BOT-09"
    verification:
      - kind: manual_procedural
        ref: "Joshua approved after fixes and retest, 2026-11-07"
        status: pass
---

# Phase 3 Plan 12: Dev stack, bot README and live Google Chat check Summary

One compose file runs Meridian, the MCP server, the bot and the Firestore emulator against a real Google Chat app over Pub/Sub, the bot README documents every manual setting, and Joshua approved the live check after five fix commits.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Dev compose wiring (tracer) | 4eda8e1 |
| 2 | Bot README, STATE.md D-11 item | 7d9558d |
| 3 | Live Google Chat check (approved after fixes) | ff2cd1b, 78f88d8, 5aece29, 1215a3b, 9b80925 |

## Live check record (D-18)

Date 2026-11-07. GCP project `ai-buddy-dev` (trial billing, personal profile). Topic `ai-buddy-chat`: Publisher role only for the Google Workspace add-ons service agent (`service-629233348577@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`); `chat-api-push` removed. Subscription `ai-buddy-chat-sub`: Subscriber role for the bot service account. Chat app "AI Buddy": Workspace add-on app (irreversible choice), Pub/Sub connection, `/aiuto` command id 1, visible to Joshua only, markup MARKDOWN. Bot key kept outside the repo (mode 600). Meridian credentials volume seeded; Meridian reported the subscription as "team".

Step 8 observations:
- Event format: add-on. Events carry `user.email`, so `ALLOWED_USERS` holds one e-mail and it matched.
- Card update: the `["text","cards_v2"]` update mask works live (RESEARCH A5 confirmed). The Guides answer showed the video card with thumbnail, Fonte line and a Guarda button.
- DM follow-up "E per i permessi?" after the leave question was understood (memory_key 3b, thread behaviour recorded).
- Meridian accepted `Authorization: Bearer` with `MERIDIAN_API_KEY` (03-06 [Unknown] resolved).
- Meridian `[PROXY] msgs=` log field shows only role and content type, never prompt text.

Results after fixes (retest):
- Handbook answer: two Fonte lines on separate lines.
- Parking-gate question: "Non lo so, chiedi a HR." plus a gap document; two gap documents in total, fields `build_id`, `created_at`, `expire_at`, `marker`, `question`, `tried`, no identity.
- `/aiuto`: bullets on separate lines.
- Earlier in the same session (code paths unchanged since): Guides answer with video card; sensitive "malato tre giorni" gave the general rule, Fonte and "Per il tuo caso specifico chiedi a HR."; company-car policy gave refusal plus gap.

## Deviations from Plan

### Auto-fixed Issues (found at the live check)

**1. [Rule 1 - Bug] Bot to MCP returned 421 Misdirected Request**
- **Issue:** the MCP server Host guard admits plain http only for loopback; the bot reached it as `http://mcp_server:8000`.
- **Fix:** bot shares the MCP server network namespace, `MCP_URL` uses localhost.
- **Files modified:** docker-compose.dev.yml, tests/unit/test_dev_compose.py
- **Commit:** ff2cd1b

**2. [Rule 1 - Bug] Chat Markdown collapsed soft line breaks**
- **Issue:** Fonte lines, contact line and `/aiuto` bullets merged into one paragraph.
- **Fix:** renderer and usage text emit one paragraph per line.
- **Files modified:** services/chat_bot/buddy_bot/render.py, service.py, tests/unit/chat_bot/test_render.py, test_service.py
- **Commit:** 78f88d8

**3. [Rule 1 - Bug] Parking question classified off_topic**
- **Issue:** workplace logistics question never reached retrieval, so no refusal path and no gap.
- **Fix:** reformulate prompt treats workplace logistics as in scope; retest gave refusal plus gap.
- **Files modified:** services/chat_bot/buddy_bot/prompts.py, tests/unit/chat_bot/test_prompts.py
- **Commit:** 5aece29

**4. [Rule 2 - Missing critical] Meridian per-request logging**
- **Issue:** suspected prompt content in Meridian logs (BOT-11 posture); inspection showed only role and content type, but per-request lines were still noise.
- **Fix:** `MERIDIAN_SILENT=1` in the dev stack.
- **Files modified:** docker-compose.dev.yml
- **Commit:** 1215a3b

**5. [Rule 1 - Bug] README publisher guidance wrong for add-on apps**
- **Issue:** README (and RESEARCH) named `chat-api-push` as publisher; add-on apps publish as the gsuiteaddons service agent, giving PERMISSION_DENIED.
- **Fix:** README states the publisher per app format, Markdown syntax and Meridian logging; contract tests updated.
- **Files modified:** services/chat_bot/README.md, tests/unit/chat_bot/test_readme_contract.py
- **Commit:** 9b80925

## Not verified (recorded in .planning/WINDOWS.md)

- Room @mention and bare "@AI Buddy" with blank `argumentText` (03-04/03-09 risk).
- Guarda `#t=` offset (buttons expose no href).
- Intro message on install (first ADDED_TO_SPACE hit the publish permission error; not re-triggered).
- Parking classification is model behaviour, to be covered by the Phase 5 golden set.
- `VIDEO_THUMBNAIL_URL` is Google's sample avatar image because Digitiamo's logo exists only as SVG; Joshua may replace it.
- Live bot-to-MCP Google ID token call stays open (existing ledger entry 1; the live check ran with AUTH_MODE=off).

## Known Stubs

None. The thumbnail placeholder is a configuration value, tracked above.

## Threat Flags

None beyond the plan threat model. Secrets (key file, `.env`) were never read or recorded.

## Self-Check: PASSED

## Follow-up: tone and length (2026-11-07)

Trigger: after live use the answers were too long and had no persona. Source: `03-TONE-RESEARCH.md`; Joshua's decision: register **tu**, `answer` cap **600 characters**. Commits on `main`, not pushed:

| Commit | What |
|--------|------|
| 3929fce | test: Guides Markdown link and three-source Fonte cap (RED) |
| 57765dc | feat: `render.py` links Guides sources by title and caps Fonte lines at 3 |
| 8a3bef4 | test: persona, tu, 600 cap, answer-first rules and style examples in the answer prompts (RED) |
| b3c2402 | feat: `prompts.py` persona, answer-first rules, 600 cap, two style examples |
| 467e232 | docs: the research report and decision |

What changed:
- **Prompts** (`ANSWER_SYSTEM`, `ANSWER_SENSITIVE_SYSTEM`): open with the persona "Sei AI Buddy, il collega di Digitiamo ... Dai del tu."; the first sentence answers, then at most 4 short points or one condition sentence; the key condition, exception or deadline stays; no preamble, no question echo, no unasked detail. The cap went from 1200 to 600 characters. Two invented positive examples (a procedure in 3 points, a single fact) are labelled as style only, not citable and not facts. The sensitive variant keeps its scope rules (general rule only, no case assessment, no referral text) and adds a warmer tone line. JSON contract and injection guards unchanged.
- **Length enforcement:** prompt only. A schema `max_length` would turn a grounded but verbose answer into a repair or refusal, which is worse than a long answer; render's 3,500-character prose cap still bounds the message.
- **Fonte lines:** they already list only cited sources (`gate.cited_sources`); now at most 3 distinct ones (`MAX_FONTE_LINES`). Handbook format is unchanged (03-01 decision 2a): `Fonte: Manuale – <title> (handbook://<page_id>), revisione <date>`. Guides: `Fonte: Guida – [<title>](<permalink>), indicizzata il <date>`. Label brackets and newlines are neutralised, link-target parentheses, spaces and angle brackets are percent-encoded, and a non-web permalink is shown by title with no link. Bot-built, so exempt from `sanitize_prose`.
- **Chat Markdown link support:** verified read-only on Google's "Format messages" page (developers.google.com/workspace/chat/format-messages): with `MARKUP_SYNTAX_MARKDOWN` a hyperlink is `[display text](hyperlink)`; the Chat app is configured MARKDOWN (see above). Not yet seen rendered live: confirm at the next live check.
- **Tests:** `test_prompts.py` and `test_render.py` extended; one existing render assertion (raw URL in the Guides line) was replaced because it pinned the format this change removes. Gate: `./run-unit-tests.sh --all` 1018 passed, 26 skipped (local-only live tests); ruff and mypy --strict clean.

Note for Phase 5 (evals): brevity is model behaviour and is judged there, not by unit tests. Add a minimal reference answer per golden item; track excess length (YapScore, YapBench arXiv 2601.00624) and concise accuracy at 600 characters (HCA(600)) next to correctness and "conditions preserved"; pair any LLM judge with a length metric (judges prefer longer answers).
