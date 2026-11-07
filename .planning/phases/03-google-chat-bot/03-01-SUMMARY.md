---
phase: 03-google-chat-bot
plan: 01
subsystem: bot-build
tags: [supply-chain, langgraph, anthropic, google-cloud-pubsub, google-apps-chat, pinning, amendments]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "services/mcp_server/requirements.txt pins (fastmcp, google-cloud-firestore) shared with the bot"
provides:
  - "services/chat_bot/requirements.txt: approved pins langgraph, anthropic, google-cloud-pubsub, google-apps-chat, requests plus shared fastmcp and google-cloud-firestore"
  - "buddy_bot package root (buddy_bot.__version__ == 0.1.0) wired into pytest, coverage, mypy, ruff and the test image"
  - "Approved Meridian source commit SHA for the 03-12 dev compose"
  - "03-CONTEXT.md '## Amendments (03-01 checkpoint)': D-16, D-11, D-09 overridden; BOT-09, D-10, D-07 interpreted"
  - "test_shared_pins_agree and test_chat_bot_pins_installed"
affects: [03-03, 03-04, 03-05, 03-06, 03-07, 03-08, 03-09, 03-10, 03-11, 03-12]

actuals:
  tokens: 1960
  tasks: 3
  commits: 1
plan_head_before: 1aa0d489087ed6665d398ed29d9eacdb5d2b6a10
commits: 1
plan_head_after: 2e3273ed372f602e8465a6207b336f7216d26519

tech-stack:
  added: [langgraph==1.2.20, anthropic==2.6.0, google-cloud-pubsub==2.43.0, google-apps-chat==0.10.9, requests==2.34.2]
  patterns:
    - "Shared pins duplicated across requirements files are asserted equal by a test"
    - "Installed distribution versions are asserted equal to the pins inside the test image"
    - "Overrides of locked decisions recorded additively in CONTEXT.md, original lines untouched"

key-files:
  created:
    - services/chat_bot/requirements.txt
    - services/chat_bot/buddy_bot/__init__.py
  modified:
    - requirements-dev.txt
    - Dockerfile
    - pyproject.toml
    - tests/unit/test_repo_layout.py
    - .planning/phases/03-google-chat-bot/03-CONTEXT.md
  deleted:
    - services/chat_bot/.gitkeep

key-decisions:
  - "Supply chain approved: langgraph==1.2.20, anthropic==2.6.0, google-cloud-pubsub==2.43.0, google-apps-chat==0.10.9, requests==2.34.2 (pin-only); Meridian commit cafdcf780f1b40c8f0dee17481132f47b4cbb353"
  - "D-16 overridden: Meridian credentials live in a dedicated Docker named volume, not a read-only host bind"
  - "D-11 overridden: DM spaces key thread memory on HMAC(space name), rooms on HMAC(thread name)"
  - "D-09 overridden: HTTP handler awaits the run up to 25 s before returning {}"
  - "BOT-09 interpreted: handbook citation as text, VIDEO_THUMBNAIL_URL required HTTPS setting"
  - "D-10 interpreted: dev compose uses the Firestore emulator; Firestore EU stays the deployed store"
  - "D-07 interpreted: gap log stores the standalone reformulated question"

requirements-completed: [BOT-07, BOT-09, BOT-10, BOT-11]

coverage:
  - id: D1
    description: "Supply chain approved by Joshua before any install of a new pin"
    requirement: "BOT-07"
    verification: []
    human_judgment: true
    rationale: "Legitimacy of third-party packages is a human decision recorded at the blocking-human checkpoint"
  - id: D2
    description: "Six phase decisions recorded in SUMMARY and amendments written into 03-CONTEXT.md"
    requirement: "BOT-09"
    verification: []
    human_judgment: true
    rationale: "Decision content was chosen by Joshua; correctness of the wording is a human review item"
  - id: D3
    description: "Test image carries exactly the approved pins and shared pins agree across requirements files"
    requirement: "BOT-10"
    verification:
      - kind: unit
        ref: "tests/unit/test_repo_layout.py#test_shared_pins_agree"
        status: pass
      - kind: unit
        ref: "tests/unit/test_repo_layout.py#test_chat_bot_pins_installed"
        status: pass
    human_judgment: false
  - id: D4
    description: "buddy_bot importable and wired into pytest, coverage, mypy and ruff; full suite green"
    requirement: "BOT-11"
    verification:
      - kind: command
        ref: "./run-unit-tests.sh --all"
        status: pass
    human_judgment: false

duration: 2min (this continuation; checkpoints answered earlier)
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 01: Supply chain gate, phase decisions and buddy_bot build wiring Summary

**Approved chat-bot pins (langgraph 1.2.20, anthropic 2.6.0, google-cloud-pubsub 2.43.0, google-apps-chat 0.10.9) installed in the test image, six phase decisions recorded with three amendments to locked decisions in 03-CONTEXT.md, and an empty `buddy_bot` package wired into pytest, coverage, mypy and ruff.**

## Performance

- **Duration:** about 2 min for the continuation (Tasks 1 and 2 were checkpoints answered by Joshua in an earlier session)
- **Started:** 2026-11-07T11:12:38Z (continuation)
- **Completed:** 2026-11-07T11:14:39Z (code commit; metadata commit follows)
- **Tasks:** 3 (2 checkpoints, 1 auto)
- **Files modified:** 8

## Supply chain (03-01 Task 1)

Joshua approved the package legitimacy gate as presented ("DO your suggestions").

Approved pins (services/chat_bot/requirements.txt):

| Package | Pin | Note |
|---------|-----|------|
| langgraph | 1.2.20 | new direct pin |
| anthropic | 2.6.0 | new direct pin |
| google-cloud-pubsub | 2.43.0 | new direct pin |
| google-apps-chat | 0.10.9 | new direct pin |
| requests | 2.34.2 | pin-only (already a transitive in the test image; the bot imports it directly) |
| fastmcp | 4.1.6 | shared, equal to services/mcp_server/requirements.txt |
| google-cloud-firestore | 2.34.1 | shared, equal to services/mcp_server/requirements.txt |

Meridian source commit approved for the 03-12 dev compose (never a Python dependency): `cafdcf780f1b40c8f0dee17481132f47b4cbb353`, checked with `git ls-remote https://github.com/rynfar/meridian HEAD` on 2026-11-07.

Evidence recorded at the gate: PyPI checks on 2026-11-07 showed each pin exists and is the current latest; langgraph, anthropic and google-apps-chat were uploaded 2026-11-05. The research seam's SUS verdict came from missing download counts on recent releases, none was SLOP. Installed transitives in the test image: langchain-core 1.7.6, langgraph-checkpoint 4.3.1, langgraph-prebuilt 1.1.1, langsmith 0.14.17, protobuf 7.36.2, grpcio 1.85.1 (match the research dry run). No install of a new pin and no image build including the bot requirements ran before approval.

## Phase decisions (03-01 Task 2)

Joshua replied "defaults" (1b, 2a+2c, 3b, 4a, 5b, 6b).

- meridian_credentials: (b) dedicated Docker named volume seeded once by copying the host credentials file, writable only by the Meridian container, never baked into an image, host ~/.claude untouched — overrides D-16
- bot09_rendering: (2a+2c) handbook source as text citation `Manuale – <title> (handbook://<page_id>), revisione <YYYY-MM-DD>` until CONT-01 gives a URL; `VIDEO_THUMBNAIL_URL` is a required HTTPS setting, startup fails without it — interprets BOT-09
- memory_key: (b) DM spaces use HMAC(space name), rooms use HMAC(thread name), HMAC with THREAD_KEY_SECRET, same 24 h TTL and N turns — overrides D-11
- dev_firestore: (a) dev compose uses the Firestore emulator for thread memory and the gap log; Firestore EU stays the deployed store — interprets D-10
- gap_question: (b) the standalone question from the reformulation step is logged, not the raw message text — interprets D-07
- http_ack: (b) await the run inside the request for up to 25 s, then return `{}` and let any remainder continue in the background — overrides D-09

Open item for 03-12: Joshua has not yet supplied the image for `VIDEO_THUMBNAIL_URL`. The value is supplied at the 03-12 live checkpoint through `.env`; no URL was invented here, and `.env.example` is untouched by this plan.

## Accomplishments

- Pins approved and installed: the test image now builds with all five approved pins plus the two shared pins, verified by `test_chat_bot_pins_installed`.
- 03-CONTEXT.md carries `## Amendments (03-01 checkpoint)` with 3 `overridden` lines (D-16, D-11, D-09) and 3 `interpreted` lines (BOT-09, D-10, D-07); 11 lines added, 0 removed against 7d772e2.
- `buddy_bot` package created and wired into PYTHONPATH (Dockerfile), pytest pythonpath, coverage source, mypy_path and files, ruff src and isort first-party; later plans add modules without touching build files.
- Full gate green: ruff, ruff format, mypy --strict (87 source files), pytest with coverage 98% (floor 80%).

## Task Commits

1. **Task 1: Package legitimacy gate** - no commit (checkpoint, approved)
2. **Task 2: Six phase decisions** - no commit (checkpoint, settled; recorded in this SUMMARY and as CONTEXT amendments)
3. **Task 3: Record decisions, install pins, wire buddy_bot** - `2e3273e` (feat)

**Plan metadata:** the docs commit that adds this SUMMARY with STATE.md and ROADMAP.md.

## Files Created/Modified

- `services/chat_bot/requirements.txt` - pinned bot runtime dependencies
- `services/chat_bot/buddy_bot/__init__.py` - package root with `__version__`
- `requirements-dev.txt` - `-r services/chat_bot/requirements.txt`
- `Dockerfile` - PYTHONPATH and COPY of the bot requirements in the base stage
- `pyproject.toml` - buddy_bot added to pytest, coverage, mypy, ruff, isort
- `tests/unit/test_repo_layout.py` - bot requirements in the pinned list; `test_shared_pins_agree`; `test_chat_bot_pins_installed`
- `.planning/phases/03-google-chat-bot/03-CONTEXT.md` - amendments block
- `services/chat_bot/.gitkeep` - deleted

## Decisions Made

See "Phase decisions (03-01 Task 2)" and "Supply chain (03-01 Task 1)" above. No mypy override block was needed: mypy --strict reported no untyped third-party module for `buddy_bot`.

## Deviations from Plan

None - plan executed exactly as written.

Note on sequencing: plan 03-02 ran and committed on main between the checkpoint and this continuation (404982c..1aa0d48). It touched only buddy_core and its tests, so no merge adjustment was needed; STATE.md position was corrected after this plan finished.

## Issues Encountered

None.

## Known Stubs

None. `buddy_bot/__init__.py` holds only the docstring and version; it feeds no UI or data path.

## User Setup Required

None for this plan. Carried to 03-12: Joshua supplies the `VIDEO_THUMBNAIL_URL` image through `.env`.

## Next Phase Readiness

- 03-03 (tracer) can import `buddy_bot` and the approved libraries in the test image.
- Later plans read the amendments in 03-CONTEXT.md together with D-07, D-09, D-10, D-11 and D-16.

## Self-Check: PASSED

- FOUND: services/chat_bot/requirements.txt, services/chat_bot/buddy_bot/__init__.py, 03-CONTEXT.md amendments block
- FOUND commit 2e3273e on HEAD (`git merge-base --is-ancestor`)
- All Task 3 acceptance criteria re-run: amendments heading 1, overridden lines 3 (equals `overrides D-xx` lines in this SUMMARY: 3), CONTEXT diff `11 0`, pins 5, `-r` line 1, Dockerfile 1, pyproject buddy_bot 3, tests 2, .gitkeep absent, mcp_server and jobs/sync untouched.
