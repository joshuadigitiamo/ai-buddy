---
phase: 03-google-chat-bot
fixed_at: 2026-11-07T00:00:00Z
review_path: .planning/phases/03-google-chat-bot/03-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 9
skipped: 1
status: partial
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-11-07
**Source review:** .planning/phases/03-google-chat-bot/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10 (WR-01..WR-05, IN-01..IN-05; fix scope "all")
- Fixed: 9
- Skipped (no_change, reviewed and left as designed): 1 (IN-05)

**Verification:** every gate ran in the main checkout, through `./run-unit-tests.sh --all` in Docker (ruff check, ruff format --check, mypy --strict, pytest). Final run: 999 passed, 26 skipped (local-only live-artifact tests), all gates green. No worktree was used (edits and commits went directly to `main`, as requested). Each behaviour change has a regression test that failed before the fix.

## Fixed Issues

### WR-01: A failed `update_message` leaves the placeholder as the final reply

**Files modified:** `services/chat_bot/buddy_bot/service.py`, `services/chat_bot/buddy_bot/render.py`, `tests/unit/chat_bot/test_service.py`, `tests/unit/chat_bot/test_render.py`
**Commit:** c375a4d
**Applied fix:** new `BotService._deliver`: patch with the card, on failure patch text-only, on a second failure post `ERROR_TEXT` as a new message; each failure is logged by type only and never raised. Memory is appended only when the answer was delivered. `render._video_card` now also requires an http(s) `source_url` before it builds a section, so a bad Guides link cannot get a card rejected. Tests: flaky `update_message` (one failure, two failures, permanent failure).

### WR-02: `extract_json` breaks when the answer contains a code fence

**Files modified:** `services/chat_bot/buddy_bot/llm.py`, `tests/unit/chat_bot/test_llm_client.py`
**Commit:** edce2d7
**Applied fix:** the whole text is tried first (first "{" to last "}" slice that must parse as a JSON object); fence content and the loose slice remain as fallbacks. Tests: a fence inside a string value, with and without surrounding prose, and an end-to-end parse with no repair call.

### WR-03: `sensitive_topic` not validated against the table

**Files modified:** `services/chat_bot/buddy_bot/workflow.py`, `tests/unit/chat_bot/test_sensitive.py`
**Commit:** 37c43ce
**Applied fix:** `reformulate` normalises the topic (strip, lowercase) and keeps it only when it is a table id; blank, "none", "nessuno" and invented ids become `None`. A known id whose role resolves through the table keeps its role; `EscalationTable.referente_role` still falls back to the fallback role. Test `test_unknown_topic_id_is_treated_as_sensitive_with_the_fallback_role` was replaced by tests for the new rule, because it pinned the behaviour this finding reports as a defect (the 03-05 "unknown id is sensitive, HR fallback" safe branch).
**Status:** fixed: requires human verification (logic change that reverses a 03-05 documented choice, as the coordinator instructed).

### WR-04: Unauthenticated outbound certificate fetch per request

**Files modified:** `services/chat_bot/buddy_bot/intake/http.py`, `tests/unit/chat_bot/test_http_intake.py`
**Commit:** be67b2a
**Applied fix:** an in-process caching `google.auth.transport.Request` wrapper (TTL 3600 s, lock so concurrent misses make one fetch, only HTTP 200 cached, fetch timeout 5 s) wraps the injected or default transport. `verify` rejects non-JWT-shaped tokens (three non-empty base64url parts, at most 8192 characters) before any thread or network use. No new dependency. Tests: one fetch for five verifications, timeout passed, TTL expiry via injected clock, failed fetch not cached, eight malformed-token shapes never reach the network.

### WR-05: `sanitize_prose` leaves several link forms

**Files modified:** `services/chat_bot/buddy_bot/render.py`, `tests/unit/chat_bot/test_render.py`
**Commit:** faf4fb9
**Applied fix:** Markdown links keep their label and drop the target (images included); `http(s)`, `ftp(s)`, `file`, `handbook`, `mailto:` and `www.` tokens, e-mail addresses and bare domains with a common TLD are removed, sparing trailing sentence punctuation; a space left before punctuation is closed. Tests: nine removal cases plus six negatives ("e.g.", decimals, "v1.2.3", `main.py`, "9.30", "Dr.").
**Note:** bare-domain detection uses a fixed TLD list, so an unusual TLD is not caught (conservative on purpose to avoid mangling prose).

### IN-01: Fallback mention stripping removes only the first word of a two-word bot name

**Files modified:** `services/chat_bot/buddy_bot/events.py`, `tests/unit/chat_bot/test_events.py`
**Commit:** 671aafa
**Applied fix:** when `argumentText` is absent, the bot's `USER_MENTION` annotation (`startIndex` defaulting to 0, `length`) is cut from the text, wherever it sits; the old leading `@word` regex remains only when no annotation applies. Not exercised against a real room event (03-12 lists room @mention as unverified live).

### IN-02: `.env.example` ships an `MCP_URL` that fails

**Files modified:** `.env.example`, `tests/unit/test_dev_compose.py`
**Commit:** 904782e
**Applied fix:** `MCP_URL=http://localhost:8000/mcp` with a comment about the loopback-only Host guard; a test ties the value to the dev compose wiring. `test_repo_layout` still passes.

### IN-03: Dev compose gives the MCP server the bot's secrets

**Files modified:** `docker-compose.dev.yml`, `tests/unit/test_dev_compose.py`
**Commit:** cddf408
**Applied fix:** `mcp_server` no longer has `env_file`; it gets an explicit `environment` list (`GUIDES_WEB_BASE` required from `.env` via interpolation, plus `GAP_*` and `RATE_LIMIT_*` with the code defaults). `docker compose config -q` validates. Tests: no env_file, no `*_KEY/_SECRET/_TOKEN` keys, required variables still present.
**Note:** a developer who sets other MCP server variables in `.env` (for example `GAP_TTL_DAYS` is passed through, but `ALLOWED_EMAIL_DOMAIN` is not) must add them to the compose file. Auth stays off in dev, so no server secret is needed.

### IN-04: Pub/Sub callback acks even when the handler never ran

**Files modified:** `services/chat_bot/buddy_bot/intake/pubsub.py`, `tests/unit/chat_bot/test_pubsub_intake_unit.py`
**Commit:** 5e27c58
**Applied fix:** `_dispatch` returns whether the handler could run. A closed loop (`run_coroutine_threadsafe` raising) or a run cancelled at shutdown gives `message.nack()`; a handler that ran (even raising) and undecodable payloads are still acked. `PubSubMessage` gained `nack`. Tests: closed loop, cancelled mid-run, and ack for raising and undecodable messages.
**Note:** a run cancelled mid-flight may already have sent the placeholder, so redelivery can show a second reply after a restart; the in-memory dedupe table does not survive a restart.

## Skipped Issues

### IN-05: `retry_plan` handles `LlmOutputError` only; `_compose` drops Fonte lines

**File:** `services/chat_bot/buddy_bot/workflow.py:144-154`, `services/chat_bot/buddy_bot/render.py` (`_compose`)
**Reason:** no_change. Both points are documented decisions with tests, and the finding shows no defect beyond them.
- `LlmUnavailableError` at `retry_plan` propagating was chosen in 03-05 (SUMMARY deviation: "only `LlmOutputError` skips the retry; `LlmUnavailableError` propagates so the service shows the error text", pinned by `test_model_unavailable_during_answer_propagates_without_a_gap`). A model outage then shows the error text and logs no false gap, instead of a refusal plus a false gap.
- Dropping whole trailing Fonte lines to fit 4,000 characters is the 03-08 behaviour ("Message fitting by dropping whole trailing Fonte lines, with a last-resort clamp"). The prose cap (3,500) leaves room for roughly three Fonte lines, and the prompt's 1,200-character instruction makes the drop path rare.
**Original issue:** an outage at retry turns a refusal into a generic error; long messages can lose citations.

---

_Fixed: 2026-11-07_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
