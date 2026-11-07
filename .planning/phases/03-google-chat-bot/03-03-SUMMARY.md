---
phase: 03-google-chat-bot
plan: 03
subsystem: bot-core
tags: [langgraph, fastmcp, citation-gate, ports, tracer, google-chat]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "buddy_mcp.models D-06 contract, build_server, in-memory Client pattern, mcp test conftest helpers"
  - phase: 03-google-chat-bot (03-01)
    provides: "approved pins (langgraph 1.2.20, fastmcp 4.1.6), buddy_bot package wired into pytest, mypy, ruff, coverage"
provides:
  - "buddy_bot.ports: LlmClient, McpTools, McpConnector, ChatApi, ThreadMemory, IntakePort, EventHandler, Turn, LlmError/LlmOutputError/LlmUnavailableError (all I/O ports async)"
  - "buddy_bot.schemas: Evidence, Referente, Reformulation, AnswerDraft, BotReply"
  - "buddy_bot.gate: check (five ordered failure reasons) and cited_sources"
  - "buddy_bot.mcp_client: FastMcpConnector/FastMcpTools (one session per run, D-06 parsing), McpToolError, evidence_from"
  - "buddy_bot.workflow: LangGraph 2-step RAG (reformulate, retrieve, answer, gate, finish/refuse), RunContext, State, WorkflowConfig, WorkflowDeps, build_graph, run_workflow"
  - "buddy_bot.render and buddy_bot.service: text rendering with bot-built Fonte lines; BotService.handle (allowlist, placeholder, run, in-place patch, never raises)"
  - "tests/unit/chat_bot/conftest.py: FakeLlm, FakeChatApi, RecordingConnector over the real in-memory buddy_mcp server, load_event, ALLOWED"
  - "tests/fixtures/chat_events/legacy_dm_message.json"
affects: [03-04, 03-05, 03-06, 03-07, 03-08, 03-09, 03-10, 03-11, 03-12]

actuals:
  tokens: 9560
  tasks: 2
  commits: 2
plan_head_before: de0f0a8b8349b9ac056ada7d18bcb3cf16ff0286
commits: 2
plan_head_after: 63d9c0d0d4185864a66ff506724bb49f6cd7d73a

tech-stack:
  added: []
  patterns:
    - "Ports & Adapters: Protocol ports in ports.py, fakes in the test conftest"
    - "LangGraph StateGraph with context_schema; dependencies read from runtime.context, routing by conditional edges only"
    - "Citation gate on exact source_url equality against evidence built only from this run's tool results"
    - "Real in-memory buddy_mcp server behind the bot's MCP client in tests (D-06 parser exercised against the real contract)"

key-files:
  created:
    - services/chat_bot/buddy_bot/ports.py
    - services/chat_bot/buddy_bot/schemas.py
    - services/chat_bot/buddy_bot/events.py
    - services/chat_bot/buddy_bot/prompts.py
    - services/chat_bot/buddy_bot/gate.py
    - services/chat_bot/buddy_bot/mcp_client.py
    - services/chat_bot/buddy_bot/workflow.py
    - services/chat_bot/buddy_bot/render.py
    - services/chat_bot/buddy_bot/service.py
    - tests/unit/chat_bot/conftest.py
    - tests/unit/chat_bot/test_tracer.py
    - tests/fixtures/chat_events/legacy_dm_message.json
  modified: []

key-decisions:
  - "All I/O ports are async (create_message, update_message, recent, append, IntakePort.run, MCP tool methods): the interfaces block omitted `async`, but the Chat, Firestore and Pub/Sub adapters planned in 03-07 and 03-10 are awaited"
  - "RunContext and State are public names in workflow.py because 03-05 cites them"
  - "render strips http(s):// and handbook:// tokens from model prose, so the only links in a message are the bot-built Fonte lines (T-03-01)"
  - "The gate node receives an empty AnswerDraft when retrieval found nothing, so check() reports no_evidence without an answer call"

requirements-completed: [BOT-01, BOT-03, BOT-04, BOT-05, BOT-10]

coverage:
  - id: D1
    description: "A legacy DM from an allowlisted sender gets one placeholder, then one update of the same message with the answer, Fonte line, handbook://02-ferie and revisione 2026-10-03"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_dm_gets_placeholder_then_cited_answer"
        status: pass
    human_judgment: false
  - id: D2
    description: "The run calls only handbook_search and guides_search on the real in-memory server and the answer prompt holds only evidence ids the calls returned"
    requirement: BOT-04
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_dm_gets_placeholder_then_cited_answer"
        status: pass
    human_judgment: false
  - id: D3
    description: "A draft citing a source_url the run did not return yields `Non lo so, chiedi a HR.`"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_forged_citation_is_refused"
        status: pass
    human_judgment: false
  - id: D4
    description: "A sender outside the allowlist causes zero LLM, MCP and Chat API calls"
    requirement: BOT-03
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_stranger_reaches_nothing"
        status: pass
    human_judgment: false
  - id: D5
    description: "gate.check fails in the fixed order no_evidence, no_citation, unsupported_citation, not_grounded, low_confidence; cited_sources keeps first-appearance order, each once"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_gate_reasons_in_fixed_order"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_tracer.py#test_cited_sources_returns_each_source_once_after_strip"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every port later plans implement is fixed in ports.py; a recorded Chat event reaches BotService.handle (event path, not live Chat)"
    requirement: BOT-01
    verification:
      - kind: command
        ref: "./run-unit-tests.sh --all"
        status: pass
    human_judgment: true
    rationale: "Pub/Sub delivery and the live Chat round trip are covered by 03-10 and the 03-12 live checkpoint; this plan proves only the in-process event-to-answer path"

duration: 5min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 03: Tracer, a Chat DM to a Cited Answer Summary

**A recorded Google Chat DM from the allowlisted user reaches `BotService.handle`, which posts the placeholder, runs a LangGraph 2-step RAG (reformulate, retrieve through the real in-memory `buddy_mcp` server, answer, deterministic source_url citation gate) and patches the same message with the answer and bot-built `Fonte:` lines; a forged citation is refused and a stranger reaches nothing.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-11-07T11:16:31Z
- **Completed:** 2026-11-07T11:21:17Z
- **Tasks:** 2 (1 tracer, 1 auto)
- **Files modified:** 12 (all created)

## Accomplishments

- Tracer end to end on the approved pins: placeholder `Sto cercando nelle fonti…` in the event's space and thread, one update of that message by name, `Fonte: Manuale – Ferie e permessi (handbook://02-ferie), revisione 2026-10-03`.
- BOT-04 by construction: `FastMcpConnector` opens one `fastmcp.Client` per run, calls only `handbook_search`, `guides_search` (and `buddy_report_gap` for later plans), parses `structured_content` into `buddy_mcp.models` and never reads prose. The test asserts the answer prompt's `<fonte id=...>` ids are a subset of the `source_url`s the recorded tool calls returned.
- BOT-05 core: `gate.check` applies no_evidence, no_citation, unsupported_citation (exact string equality after strip), not_grounded, low_confidence in that order; the table test pins the order with a draft that breaks two rules at once. Links are rendered from `Evidence`, and URL-looking tokens in model prose are stripped.
- BOT-03 core: the allowlist check runs right after normalization; the stranger test asserts zero calls on the LLM, MCP connector and Chat fakes.
- Every port is fixed in `ports.py` so later plans never edit it; `FakeLlm` raises `LlmOutputError` when no scripted item remains for a schema, so later plans can add LLM steps without breaking these tests.
- Full gate `./run-unit-tests.sh --all`: ruff, ruff format, mypy --strict and pytest pass; 636 passed, 18 skipped; total coverage 96.73%.

## Task Commits

1. **Task 1: tracer (ports, schemas, events, prompts, gate, mcp_client, workflow, render, service, conftest, fixture, 3 tests)** - `d669a1c` (feat)
2. **Task 2: gate contract table and cited_sources order** - `63d9c0d` (test)

Tracer feedback gate: auto mode off, `human_verify_mode` default `end-of-phase`, the tracer's `<verify>` is automated-only, so it was re-run end to end after the commit (3 passed) before expansion. Task 2 did not require a gate.py change: the first implementation already ran the checks in the specified order.

## Deviations from Plan

None - plan executed exactly as written.

Interpretation notes (not deviations):
- The interfaces block lists port methods without `async`. They are `async def` because every adapter behind them performs awaited I/O.
- `ruff check --fix` reordered one import line (`Referente` before `Reformulation`) and the prompt line lengths were shortened to satisfy E501. No behavior change.

## Issues Encountered

None.

## Known Stubs

None that block the plan goal. These are intentional scaffolds each resolved by a named later plan:

- `render.render_reply`: `cards_v2` is always empty and `video_thumbnail_url` is accepted but unused (03-08).
- `events.normalize_event`: only the legacy flat MESSAGE shape; `added`, `removed`, `command` kinds are never produced (03-04).
- `service.BotService`: handles only kind `message`, no thread memory or deduplication yet (03-09).
- `workflow`: no retry, no referente lookup from the escalation table, no gap reporting, `intent` and `sensitive_topic` are parsed but not acted on; refusal always names role HR (03-05).
- `prompts.REFORMULATE_SYSTEM`: `sensitive_topic` is always null until 03-05.

Not added to `.planning/WINDOWS.md`: these are planned phase scope, not defects.

## Threat Flags

None. New surface is internal (no endpoint, no auth path, no file access); T-03-01, T-03-02 and T-03-03 mitigations from the plan's threat model are implemented and tested (log lines in `service.py` carry fixed text and exception type names only; the full log-hygiene test is 03-11).

## User Setup Required

None.

## Next Phase Readiness

- 03-04 can extend `events.normalize_event` without touching `ports.py`.
- 03-05 can add retry, referente, gap reporting and intent routing inside `workflow.py` using `RunContext`, `State` and the existing node functions.
- 03-06 implements `LlmClient` (raise only `LlmError` subclasses); 03-07 implements `ThreadMemory` (async methods); 03-10 implements `IntakePort.run` (async).

## Self-Check: PASSED

- FOUND: all 12 created files on disk
- FOUND commits d669a1c and 63d9c0d on HEAD (`git merge-base --is-ancestor`)
- Acceptance criteria re-run: `context_schema=` 1, `model_validate(...structured_content` 1, `run_workflow(` 1, `class FakeLlm` 1, gate reason names 12, `cited_sources` 3, `git diff --quiet 7d772e2 -- services/mcp_server jobs/sync` exit 0
- Plan verification: `--single-file test_tracer.py tests/unit/chat_bot` 11 passed; `--all` exit 0
