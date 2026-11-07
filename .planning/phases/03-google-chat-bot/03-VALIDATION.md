---
phase: "3"
slug: "google-chat-bot"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-11-07"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 with anyio 4.16.0 (`pytest.mark.anyio`, `anyio_backend` fixture), pytest-cov 7.1.0; ruff 0.17.3; mypy 2.4.1 strict |
| **Config file** | `pyproject.toml` (03-01 adds `services/chat_bot` / `buddy_bot`; 03-10 adds the `pubsub` marker) |
| **Quick run command** | `./run-unit-tests.sh --single-file <test_file> tests/unit/chat_bot` |
| **Full suite command** | `./run-unit-tests.sh --all` (ruff, ruff format --check, mypy, pytest with `--cov-fail-under=80`, `--network none`) |
| **Emulator command** | `./run-unit-tests.sh --emulator` (Firestore + Pub/Sub emulators; tests marked `firestore` or `pubsub` after 03-10) |
| **Estimated runtime** | ~60 s per single file with a cached image; ~180 s for `--all`; ~120 s for `--emulator` |

---

## Sampling Rate

- **After every task commit:** Run `./run-unit-tests.sh --single-file <touched test file> tests/unit/chat_bot` (or the task's own `<automated>` command)
- **After every plan wave:** Run `./run-unit-tests.sh --all`; after waves that touch emulator tests (03-07, 03-10, 03-11) also `./run-unit-tests.sh --emulator`
- **Before `/gsd-verify-work`:** `--all` and `--emulator` green; D-18 live check approved or explicitly deferred to Phase 4
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | — | T-03-SC | no new-pin install before Joshua approves pins and the Meridian SHA | manual (checkpoint) | — | n/a | ⬜ pending |
| 03-01-02 | 01 | 1 | — | T-03-39 | six decisions settled before later plans | manual (checkpoint) | — | n/a | ⬜ pending |
| 03-01-03 | 01 | 1 | BOT-07, BOT-09, BOT-10, BOT-11 | T-03-SC, T-03-39 | overrides of D-09/D-11/D-16 written as 03-CONTEXT.md amendments matching the SUMMARY tags; image carries exactly the approved pins | unit | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | BOT-06 | T-03-04, T-03-05 | YAML equals SKILL.md table; roles only | unit | `./run-unit-tests.sh --single-file test_escalation.py tests/unit/buddy_core` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | BOT-06 | T-03-04 | malformed table rejected; HR fallback | unit | `./run-unit-tests.sh --single-file test_escalation.py tests/unit/buddy_core` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | BOT-01, BOT-03, BOT-04, BOT-05, BOT-10 | T-03-01, T-03-02, T-03-03 | forged citation refused; stranger reaches no LLM/MCP/Chat call | unit (e2e in process) | `./run-unit-tests.sh --single-file test_tracer.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | BOT-05 | T-03-01 | gate reasons in fixed order; cited sources once each | unit | `./run-unit-tests.sh --single-file test_tracer.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 3 | BOT-01, BOT-10 | — | add-on @mention: placeholder in thread then answer; mention stripped | unit (e2e in process) | `./run-unit-tests.sh --single-file test_tracer.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-04-02 | 04 | 3 | BOT-01 | T-03-09 | both event shapes normalized; malformed -> None | unit | `./run-unit-tests.sh --single-file test_events.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-05-01 | 05 | 3 | BOT-05, BOT-11 | T-03-12, T-03-13 | retry once, refusal, verbatim contact, one gap without identity | unit (real in-memory MCP) | `./run-unit-tests.sh --single-file test_refusal.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-05-02 | 05 | 3 | BOT-04, BOT-05 | T-03-10 | gate edges (prefix, case, anchor, encoding, empty); history isolation | unit | `./run-unit-tests.sh --single-file test_gate.py tests/unit/chat_bot` and `test_workflow.py` | ❌ W0 | ⬜ pending |
| 03-05-03 | 05 | 3 | BOT-06 | T-03-11 | general rule plus referral; referral-only plus gap | unit | `./run-unit-tests.sh --single-file test_sensitive.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-06-01 | 06 | 3 | BOT-07 | — | one /v1/messages call, no sampling params | unit | `./run-unit-tests.sh --single-file test_llm_client.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-06-02 | 06 | 3 | BOT-07 | T-03-17 | backend switch by config; repair once; typed timeout | unit | `./run-unit-tests.sh --single-file test_llm_client.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-06-03 | 06 | 3 | BOT-08 | T-03-14, T-03-15, T-03-16, T-03-18 | Meridian single user; tracing refused; secrets never echoed | unit | `./run-unit-tests.sh --single-file test_config.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-07-01 | 07 | 3 | BOT-11 | T-03-19 | HMAC id; keys exactly turns/updated_at/expire_at; 24 h | integration (firestore) | `./run-unit-tests.sh --emulator` | ❌ W0 | ⬜ pending |
| 03-07-02 | 07 | 3 | BOT-11 | T-03-20, T-03-21 | N-turn cap, read-side expiry, text caps, lazy client | unit | `./run-unit-tests.sh --single-file test_memory.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-08-01 | 08 | 3 | BOT-09 | T-03-22 | card with thumbnail, Fonte and Guarda from tool results | unit | `./run-unit-tests.sh --single-file test_render.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-08-02 | 08 | 3 | BOT-05, BOT-09, BOT-10 | T-03-22, T-03-23 | model URLs and markup stripped; caps; ordering | unit | `./run-unit-tests.sh --single-file test_render.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-09-01 | 09 | 4 | BOT-11 | — | history reaches reformulation only (D-12); key source per the memory_key decision | unit | `./run-unit-tests.sh --single-file test_conversation.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-09-02 | 09 | 4 | BOT-03, BOT-10, BOT-11 | T-03-06, T-03-07, T-03-08 | exact allowlist; dedupe; canned replies; never raises | unit | `./run-unit-tests.sh --single-file test_allowlist.py tests/unit/chat_bot` and `test_service.py` | ❌ W0 | ⬜ pending |
| 03-10-01 | 10 | 5 | BOT-01 | T-03-27 | Pub/Sub event answered; poison message acked | integration (pubsub) | `./run-unit-tests.sh --emulator` | ❌ W0 | ⬜ pending |
| 03-10-02 | 10 | 5 | BOT-02, BOT-10 | T-03-25, T-03-27, T-03-28 | Google JWT required; 401/400/413/405; ack window | unit | `./run-unit-tests.sh --single-file test_http_intake.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-10-03 | 10 | 5 | BOT-01, BOT-10 | T-03-28 | placeholder in thread then update; errors by type | unit | `./run-unit-tests.sh --single-file test_chat_api.py tests/unit/chat_bot` and `test_pubsub_intake_unit.py` | ❌ W0 | ⬜ pending |
| 03-11-01 | 11 | 6 | BOT-01, BOT-02, BOT-08 | T-03-29 | real process: 401 without token, stranger dropped, bad config exits 1 | unit + integration | `./run-unit-tests.sh --single-file test_main.py tests/unit/chat_bot` and `./run-unit-tests.sh --emulator` | ❌ W0 | ⬜ pending |
| 03-11-02 | 11 | 6 | BOT-07, BOT-11 | T-03-30, T-03-32, T-03-33 | ID token cached, off-loop, never logged; image uid 10001, tracing off | unit + docker | `./run-unit-tests.sh --single-file test_id_token_auth.py tests/unit/chat_bot`; `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit`; `docker build --target chat_bot -t ai-buddy-bot .` | ❌ W0 | ⬜ pending |
| 03-11-03 | 11 | 6 | BOT-11 | T-03-31 | no identity or question text in any log record | unit | `./run-unit-tests.sh --single-file test_log_hygiene.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-12-01 | 12 | 7 | BOT-01, BOT-07 | T-03-34, T-03-35, T-03-36, T-03-37 | no published ports; Meridian SHA pinned; credentials and key read-only | unit + compose | `./run-unit-tests.sh --single-file test_dev_compose.py tests/unit` and `docker compose -f docker-compose.dev.yml --env-file .env.example config --quiet` | ❌ W0 | ⬜ pending |
| 03-12-02 | 12 | 7 | BOT-03, BOT-08 | T-03-38 | README documents visibility, IAM, rollout checklist | unit | `./run-unit-tests.sh --single-file test_readme_contract.py tests/unit/chat_bot` | ❌ W0 | ⬜ pending |
| 03-12-03 | 12 | 7 | BOT-01..BOT-11 (live) | — | live Chat check or recorded deferral | manual (checkpoint) | — | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/chat_bot/conftest.py` — FakeLlm (scripted per schema, LlmOutputError when unscripted), FakeChatApi, RecordingConnector, in-memory buddy_mcp server over a synthetic index with a contacts page, event loader (03-03); DictThreadMemory and make_service (03-09)
- [ ] `tests/fixtures/chat_events/*.json` — eleven synthetic events, both formats (03-03, 03-04)
- [ ] `services/chat_bot/requirements.txt` + `requirements-dev.txt` + Dockerfile base PYTHONPATH + pyproject paths (03-01, after the legitimacy checkpoint)
- [ ] `docker-compose.test.yml` `pubsub` service, `run-unit-tests.sh --emulator` running `firestore or pubsub` (03-10)
- [ ] every test file named in the map above (created by its task, RED first for `tdd="true"` tasks)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Package and Meridian source legitimacy | — (T-03-SC) | registry pages and repository review need a human | 03-01 Task 1 how-to-verify |
| Phase decisions (Meridian mount, BOT-09 rendering, memory key, dev Firestore, gap question, HTTP ack) | BOT-07, BOT-09, BOT-10, BOT-11 | contradict or interpret locked decisions | 03-01 Task 2; accepted overrides of D-09, D-11, D-16 are checked in `## Amendments (03-01 checkpoint)` of 03-CONTEXT.md by 03-01 Task 3 |
| Chat app visibility limited to Joshua | BOT-03 | Google Cloud Console setting, not code | README "Google Chat app settings (manual)"; checked in 03-12 Task 3 |
| Live DM round trip: handbook answer, Guides video card, sensitive question, no-source refusal with gap, follow-up, /aiuto, room @mention | BOT-01, BOT-05, BOT-06, BOT-09, BOT-10 | needs a real GCP project, Chat app, Pub/Sub subscription and Meridian login | 03-12 Task 3 how-to-verify (deferrable to Phase 4 per D-18) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (checkpoints excepted)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 180s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
