---
phase: 03-google-chat-bot
reviewed_at: 2026-11-07T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - .env.example
  - Dockerfile
  - docker-compose.dev.yml
  - docker-compose.test.yml
  - packages/buddy_core/buddy_core/data/escalation_topics.yaml
  - packages/buddy_core/buddy_core/escalation.py
  - pyproject.toml
  - requirements-dev.txt
  - run-unit-tests.sh
  - services/chat_bot/requirements.txt
  - services/chat_bot/buddy_bot/__init__.py
  - services/chat_bot/buddy_bot/__main__.py
  - services/chat_bot/buddy_bot/chat_api.py
  - services/chat_bot/buddy_bot/cli.py
  - services/chat_bot/buddy_bot/config.py
  - services/chat_bot/buddy_bot/events.py
  - services/chat_bot/buddy_bot/gate.py
  - services/chat_bot/buddy_bot/intake/__init__.py
  - services/chat_bot/buddy_bot/intake/http.py
  - services/chat_bot/buddy_bot/intake/pubsub.py
  - services/chat_bot/buddy_bot/llm.py
  - services/chat_bot/buddy_bot/mcp_client.py
  - services/chat_bot/buddy_bot/memory.py
  - services/chat_bot/buddy_bot/ports.py
  - services/chat_bot/buddy_bot/prompts.py
  - services/chat_bot/buddy_bot/referral.py
  - services/chat_bot/buddy_bot/render.py
  - services/chat_bot/buddy_bot/schemas.py
  - services/chat_bot/buddy_bot/service.py
  - services/chat_bot/buddy_bot/workflow.py
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-11-07
**Depth:** standard
**Files Reviewed:** 30 source/config files (tests skimmed for false-confidence patterns)
**Status:** issues_found

## Summary

The service is well structured. The JWT audience and issuer checks, the empty-audience guard, the HMAC thread keys, the log hygiene (exception type names only), the citation gate and the settings guards all hold up when traced through. I found no critical issue.

Five warnings affect behavior the live check did not exercise. A failed Chat API patch strands the placeholder. Model answers that contain a code fence fail JSON extraction. An unvalidated `sensitive_topic` string flips a general question into the sensitive path. The JWT verifier makes an unauthenticated outbound certificate fetch per request. The link stripper leaves several link forms in place.

The tests I skimmed assert real behavior (for example the HTTP intake tests use a real RSA signature and google-auth's real verifier). No assertion-that-cannot-fail pattern turned up. There is no test for a failing `update_message` (WR-01) or for a code fence in the model's JSON (WR-02).

No structural findings were provided.

## Warnings

### WR-01: A failed `update_message` leaves "Sto cercando nelle fonti…" as the final reply

**File:** `services/chat_bot/buddy_bot/service.py:399-409`
**Issue:** `_answer` calls `self._chat.update_message(...)` outside any `try`. `_run` guards the workflow, but the patch call is not guarded. `BotService.handle` catches the exception and logs `event handling failed: ChatApiError`, and nothing else happens.

**Failure scenario:** any of these ends with the user seeing the placeholder forever and no error text:
- a transient Chat API 5xx or 429;
- a `ParseError` or 400 because a card is rejected, for example a Guides `source_url` that is not http(s) (`_video_card` checks only `video_url`'s scheme, and `render.py:416` puts `source.source_url` into an `openLink` unchecked);
- an expired credential.

Pub/Sub acks the message regardless, so there is no redelivery. The turn is also not remembered, because `_remember` comes after the failing call.

**Fix:** wrap the patch in a fallback.

```python
try:
    await self._chat.update_message(name=name, text=rendered.text, cards_v2=rendered.cards_v2)
except ChatApiError:
    # retry text-only (drops a rejected card), then give up quietly
    await self._chat.update_message(name=name, text=rendered.text, cards_v2=[])
```

Wrap the fallback too, so the text-only retry is the last attempt. Add a test with a fake `ChatApi` whose first `update_message` raises. Also validate that `source_url` starts with http(s) before building the "Fonte" button.

### WR-02: `extract_json` breaks when the answer text contains a Markdown code fence

**File:** `services/chat_bot/buddy_bot/llm.py:27-37`
**Issue:** `_FENCE.search(text)` runs on the whole model output even when the output is bare JSON. If the `answer` string contains a triple-backtick block, the regex matches inside the JSON string, and `body` becomes the code snippet. I reproduced this with `{"answer":"Usa:\n```python\nx = 1\n```\nfine", ...}`: `extract_json` returns `\nx = 1\n`, so validation fails. If the snippet contains `{`, the slice is garbage instead.

**Failure scenario:** Guides questions are technical and the model likes to quote code. The first call fails validation, the repair call usually repeats the same output, and `LlmOutputError` follows. `answer` returns `_NO_DRAFT`, the gate fails with `invalid_output`, and a legitimate Guides answer becomes "Non lo so" plus a false gap entry. The only fence test (`test_llm_client.py:202`) wraps the whole JSON and does not cover this.

**Fix:** prefer the unfenced reading and fall back to the fence only when the text does not parse.

```python
def extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    fenced = _FENCE.search(text)
    ...
```

Add a test with a code fence inside `answer`.

### WR-03: `sensitive_topic` is not validated against the table; a stray string makes any question "sensitive"

**File:** `services/chat_bot/buddy_bot/schemas.py:41`, used at `workflow.py:159, 200, 212`
**Issue:** `sensitive_topic` is `str | None`. Every consumer tests `is not None`. The prompt asks for "an id from the table, or null", but Haiku may return `""`, `"none"`, `"nessuno"` or an invented id. All of those count as sensitive. `EscalationTable.referente_role` then silently maps the unknown id to the fallback role HR.

**Failure scenario:** a general question such as "Come richiedo le ferie?" gets `sensitive_topic="none"`. The answer step switches to `ANSWER_SENSITIVE_SYSTEM`, and a "Per il tuo caso specifico chiedi a HR." line is appended to an ordinary answer. If the gate fails, the reply is a referral instead of "Non lo so, chiedi a …". The behavior depends on model whim and contradicts D-05/D-06.

**Fix:** normalize in the schema or the node.

```python
@field_validator("sensitive_topic", mode="before")
@classmethod
def _blank_is_none(cls, v): return v.strip() or None if isinstance(v, str) else v
```

In `reformulate`, set the topic to `None` when `ctx.escalation.topic(value) is None`, or fail validation so the existing one-shot repair path runs. Test with `"none"`, `""` and an unknown id.

### WR-04: Every request with any Bearer string triggers a blocking outbound certificate fetch (unauthenticated amplification)

**File:** `services/chat_bot/buddy_bot/intake/http.py:47-62, 104`
**Issue:** `id_token.verify_oauth2_token` fetches Google's certificate map on every call. google-auth does no caching unless the transport is wrapped in a cache-aware session. As I recall google-auth's `verify_token` (the library is not installed on this host, so I could not re-check it), it fetches certificates before checking the signature. The fetch runs through `asyncio.to_thread` with the sync `requests` transport, whose default timeout is long, and it happens before the 401 decision.

**Failure scenario:** the endpoint is public on Cloud Run. A flood of requests with garbage `Authorization: Bearer x` headers drives the same number of outbound HTTPS calls to Google. These saturate the default thread pool, which is also used by `GoogleIdTokenAuth` and other `to_thread` work. Legitimate Chat events wait behind them or time out. Google may also rate-limit the bot's egress IP, which would break real verification.

**Fix:**
- Build the transport from a `requests.Session` wrapped with cachecontrol, as the google-auth docs recommend, or cache the cert map yourself for its `max-age`.
- Pre-check the JWT shape cheaply (three dot-separated parts and a decodable header with `alg=RS256`) before dispatching to a thread.
- Set an explicit short timeout on the fetch.
- Add a small concurrency semaphore around `verify`.

### WR-05: `sanitize_prose` does not remove all model-written links

**File:** `services/chat_bot/buddy_bot/render.py:362-371`
**Issue:** the module promises "Links come from Evidence, never from model text", but `_URL_TOKEN` handles only `http(s)://` and `handbook://`. I verified these outputs:
- `www.evil.example`, bare `evil.example/login`, `mailto:x@y.z`, `ftp://…` and a plain email address pass through unchanged.
- `[il portale](https://evil.example/x) ora` becomes the dangling `[il portale]( ora`. The `\S+` also swallows the closing `)`.

Chat auto-links `www.` hosts and bare domains. The model sees retrieved text that could be attacker-influenced (prompt injection through Guides content), and the prompt rule is the only other defense.

**Failure scenario:** a poisoned Guides section yields "vedi evil.example/login" in an answer that carries a legitimate "Fonte" line, which gives it the appearance of an official link.

**Fix:** extend the pattern, for example `r"(?:\b[a-z][a-z0-9+.-]*://|\bwww\.|\bmailto:)\S+"` plus a bare-domain rule. Remove Markdown link syntax as a whole with `\[([^\]]*)\]\([^)]*\)` replaced by `\1`, before the URL pass. Add tests for each form.

## Info

### IN-01: Fallback mention stripping removes only the first word of a two-word bot name

**File:** `services/chat_bot/buddy_bot/events.py:37, 50-55`
**Issue:** when `argumentText` is absent or blank, `_LEADING_MENTION = ^@\S+\s*` turns `@AI Buddy come richiedo le ferie?` into `Buddy come richiedo le ferie?`. 03-12 lists room @mention as not verified, so this fallback is untested live. The stray "Buddy" ends up in the standalone question and the keywords.
**Fix:** strip the exact configured display name, or take the text after the first `@Name` token using the Chat `annotations` (user mention `startIndex` and `length`) when present.

### IN-02: `.env.example` ships an `MCP_URL` that the live check showed fails

**File:** `.env.example:195`
**Issue:** `MCP_URL=http://mcp_server:8000/mcp` is the exact value that got `421 Misdirected Request` (03-12 deviation 1). The dev compose overrides it, so only a manual or kind run that copies `.env.example` hits it.
**Fix:** use `http://localhost:8000/mcp` with a comment about the Host guard. Alternatively, document that http works only on loopback.

### IN-03: Dev compose gives the MCP server the bot's secrets

**File:** `docker-compose.dev.yml:98-100`
**Issue:** `mcp_server` loads the whole `.env`, which holds `THREAD_KEY_SECRET`, `MERIDIAN_API_KEY` and any `ANTHROPIC_API_KEY`. The server needs none of them. This is dev only and the container is local, so the exposure is small. It still breaks least privilege, and the server's environment then holds the key that derives the thread-memory ids.
**Fix:** pass the server only the variables it reads through `environment:`, or split into `.env.bot` and `.env.mcp`.

### IN-04: Pub/Sub callback acks even when the loop is gone

**File:** `services/chat_bot/buddy_bot/intake/pubsub.py:200-204, 224-227`
**Issue:** `callback` acks in `finally`, including when `run_coroutine_threadsafe(...).result()` fails because the loop is closed or cancelled at shutdown. That event is dropped with no reply and no placeholder. The docstring justifies ack-always for poison messages. It does not cover this case: it applies to undecodable data and to the service's no-raise contract, not to a handler that never ran.
**Fix:** ack only when the payload was undecodable or the handler actually ran. Otherwise `message.nack()` so Pub/Sub redelivers after restart.

### IN-05: `retry_plan` handles `LlmOutputError` only, so a transient outage turns a refusal into a generic error

**File:** `services/chat_bot/buddy_bot/workflow.py:144-154`
**Issue:** `answer` and `retry_plan` catch only `LlmOutputError`. An `LlmUnavailableError` there propagates to `_run`, which sends the "Non riesco a rispondere" error and logs no gap. For `retry_plan` this is inconsistent. The failure there should degrade to the refusal path, because the retry is optional, and the `retrieve`, `gate` and `refuse` path already exists. Likewise, `_compose` in `render.py:475-482` silently drops "Fonte" lines when the message is long (prose capped at 3500 of 4000 characters), so an answer can go out with fewer citations than it used. This only happens when the model ignores the 1200-character instruction.
**Fix:** catch `LlmError` in `retry_plan` and return `{"attempt": 1}`. Keep at least the first "Fonte" line by lowering `MAX_ANSWER_CHARS`, or cap the prose to whatever room the lines leave.

---

_Reviewed: 2026-11-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
