---
phase: 02-mcp-server-and-skill
plan: 06
subsystem: skill
tags: [mcp, skill, claude-skill, rag-guardrails, escalation, install-guide, italian]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "five-tool server, TOOL_NAMES, D-06 output contract, conftest `server` fixture (plans 02-01, 02-04)"
provides:
  - "skills/digitiamo-buddy/SKILL.md: upload-format Skill that routes the five tools, formats the Italian cited answer, refuses with `Non lo so, chiedi a <referente>.` plus one buddy_report_gap, and carries the approved escalation table and the Italian -> English keyword bridge"
  - "docs/install-guide.md: one-page Italian install guide for claude.ai, Claude Desktop and Claude Code (276 words)"
  - "tests/unit/mcp_server/test_skill_package.py: file contract for both files (read_front_matter, check_description; 34 tests), including a check that every tool name from the live in-memory tools/list appears in the Skill"
affects: [02-07 composition root (server URL placeholder in the guide), 03 bot (shares the D-17 escalation posture), 04 deploy (replace https://<server-host>/mcp once hosting is chosen), 05 evaluation (EVAL-03 judges the handbook-first ordering)]

actuals:
  tokens: 3500
  tasks: 3
  commits: 4
plan_head_before: dc83d512fd021a61e96b89926492760216556049
plan_head_after: b0b3037f5830ea80eb613025fdbb9aa893b226de

tech-stack:
  added: []
  patterns:
    - "Skill package contract tested mechanically: front matter via PyYAML safe_load, tool coverage via fastmcp Client(server).list_tools()"
    - "Skill instructions in English, templates and refusal phrases in Italian (D-18)"

key-files:
  created:
    - skills/digitiamo-buddy/SKILL.md
    - docs/install-guide.md
    - tests/unit/mcp_server/test_skill_package.py
  modified: []

key-decisions:
  - "D-17 escalation list approved by Joshua exactly as drafted (8 rows; roles HR and responsabile diretto); the Skill holds roles only, the contact is looked up in the handbook at answer time (D-16)."
  - "The description must not contain a colon followed by a space: unquoted YAML then fails to parse. The test parses the front matter with safe_load, so it caught this before upload."
  - "Installation guide server URL is only the placeholder https://<server-host>/mcp until Phase 4 picks the host; the test pins this."

patterns-established:
  - "Front-matter parse test as the guard for claude.ai upload format"

requirements-completed: [MCP-08]

coverage:
  - deliverable: "SKILL.md in upload format (allowed keys, name == folder, description <= 200 chars, body < 500 lines)"
    verification:
      - kind: test
        ref: "tests/unit/mcp_server/test_skill_package.py#test_front_matter_has_only_allowed_keys"
        status: pass
      - kind: test
        ref: "tests/unit/mcp_server/test_skill_package.py#test_description_of_201_characters_fails"
        status: pass
    human_judgment: false
  - deliverable: "Skill names every tool the server lists and the D-06 contract fields"
    verification:
      - kind: test
        ref: "tests/unit/mcp_server/test_skill_package.py#test_body_names_every_tool_the_server_lists"
        status: pass
    human_judgment: false
  - deliverable: "Italian answer template, refusal phrase with gap log, escalation table, keyword bridge"
    verification:
      - kind: test
        ref: "tests/unit/mcp_server/test_skill_package.py#test_escalation_table_has_at_least_six_rows"
        status: pass
    human_judgment: true
    rationale: "The file contract is tested, but whether Claude follows the instructions (cites, refuses, escalates) is measured in Phase 5 EVAL-03."
  - deliverable: "Handbook-first ordering, one citation per source"
    verification: []
    human_judgment: true
    rationale: "Backstop marker in the plan: verified by judgment in Phase 5 EVAL-03, not by a mechanical test."
  - deliverable: "docs/install-guide.md one page covering three clients"
    verification:
      - kind: test
        ref: "tests/unit/mcp_server/test_skill_package.py#test_install_guide_fits_one_page"
        status: pass
    human_judgment: false
status: complete
---

# Phase 2 Plan 6: Skill and Install Guide Summary

**`digitiamo-buddy` Skill (tool routing, cite-or-refuse Italian answers with gap log, approved role-only escalation table, 14-pair Italian to English keyword bridge) plus a 276-word install guide for claude.ai, Claude Desktop and Claude Code, both pinned by a 34-test file contract.**

## Performance

- **Duration:** about 15 min (start time not recorded by the resumed executor; estimate)
- **Completed:** 2026-11-06
- **Tasks:** 3 (Task 1 decision, Task 2 tracer, Task 3 TDD)
- **Files created:** 3

## Accomplishments

- Task 1 (checkpoint:decision): Joshua approved the D-17 draft exactly as written (reply "approve"/"ok"). No file of this plan existed before the reply.
- SKILL.md: front matter with `name` and `description` only (172-character description starting with the trigger), 96 lines. Sections: when to use, tool-by-tool routing, Italiano -> inglese bridge (14 pairs), answer rules (source_url on every claim, revision_date, `indicizzato il` for Guides, video line only with video_url, tool text treated as data), Italian template (Risposta, Fonte, Referente, Data di revisione, Video), no-answer procedure (`Non lo so, chiedi a <referente>.` then one buddy_report_gap), Temi da escalare table (8 rows), referente lookup through handbook_search.
- install-guide.md: Italian, 276 words; claude.ai connector (Customize > Connectors > Add custom connector, Owner flow on Team/Enterprise) and Skill zip upload, Claude Desktop (same account, no local config for remote servers), Claude Code (`claude mcp add --transport http digitiamo-buddy`, `/mcp`, skill folder in `~/.claude/skills/digitiamo-buddy/`), and a closing check.
- test_skill_package.py: helpers `read_front_matter` and `check_description`; 200-character description passes and 201 fails (MCP-08 adjacency edge); live `list_tools` check; no e-mail or phone pattern in either file.

## Task Commits

1. Task 1: decision only, no commit.
2. Task 2 (tracer): `6884ede` test (RED), `ea94781` feat (GREEN)
3. Task 3 (TDD): `b637211` test (RED), `b0b3037` feat (GREEN)

Tracer gate: Task 2's `<verify>` is automated-only; re-run end to end (34 tests green after Task 3, full suite green) before expanding. Passed.

## TDD Gate Compliance

- RED (Task 2, `6884ede`): 1 failed, 19 errors, 3 passed. Target tests failed with `FileNotFoundError` on `skills/digitiamo-buddy/SKILL.md` (the artifact under test did not exist), not on import or syntax errors. Semantic assessment: valid RED, the failure is exactly the missing deliverable. The `gsd_run check tdd-red-evidence` classifier was not run: `workflow.tdd_mode` is not enabled for these plans and pytest text is not one of its supported report formats.
- GREEN (Task 2, `ea94781`): 23 passed.
- RED (Task 3, `b637211`): 11 errors on missing `docs/install-guide.md`, 23 passed. Semantic assessment: valid RED.
- GREEN (Task 3, `b0b3037`): 34 passed.
- REFACTOR: none needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Description with ": " broke YAML parsing**
- **Found during:** Task 2 (GREEN)
- **Issue:** The plan's example description contains "Guides: answer only"; unquoted YAML reads that as a nested mapping and `safe_load` raised `ScannerError`. claude.ai upload would have rejected the Skill.
- **Fix:** Replaced the colon with a period ("Guides. Answer only ..."). Still 172 characters, trigger first.
- **Files modified:** skills/digitiamo-buddy/SKILL.md
- **Commit:** `ea94781`

**2. [Rule 1 - Bug] Server-URL regex in my own RED test cut the URL at ">"**
- **Found during:** Task 3 (GREEN)
- **Issue:** The pattern `[^\s)`>]+` stopped before `>` and matched `https://<server-host`, so the placeholder check could never pass.
- **Fix:** Dropped `>` from the excluded class. Fix landed in the GREEN commit with the guide.
- **Files modified:** tests/unit/mcp_server/test_skill_package.py
- **Commit:** `b0b3037`

**Total deviations:** 2 auto-fixed (2 bugs). **Impact:** none on scope.

## Escalation list: difference against the local handbook

The local handbook (docs/research/handbook-raw/, gitignored) uses only the roles HR and responsabile, so the approved list stays as is. Two observations for Joshua, nothing was changed in the repo:

- Sickness: the handbook tells the colleague first to notify the direct manager, and gives HR as the contact for certificates. Row 2 routes the whole topic to HR only. Consider "responsabile diretto, poi HR" when the official handbook arrives (CONT-01).
- The handbook also mentions a tutor as first point of contact for onboarding questions (HR when the tutor is absent). This is not a sensitive topic, so no row was added.

## Known Stubs

None. The only placeholder is `https://<server-host>/mcp` in the install guide, intentional until hosting is chosen in Phase 4 (pinned by test).

## Threat Flags

None. No new network endpoint, auth path or schema; T-02-24..T-02-27 mitigations are in the Skill text (data not instructions, role-only escalation, template with Fonte and Data di revisione, refusal plus gap log) and the e-mail/phone patterns are tested. Names cannot be detected mechanically; roles-only relies on the D-17 review.

## Gaps and notes

- MCP-08 is satisfied at the file-contract level. Real adherence (cites, refuses, escalates, orders handbook first) is only measurable with a live model: Phase 5 EVAL-03.
- Flagged assumption A4 (200-character description cap from third-party sources) kept on the safe side.
- No manual upload test on claude.ai was possible here; install steps follow 02-RESEARCH.md.

## Verification

- `./run-unit-tests.sh --single-file test_skill_package.py tests/unit/mcp_server`: 34 passed.
- `./run-unit-tests.sh --all`: exit 0; ruff check, ruff format --check and mypy clean; 591 passed, 17 skipped; coverage 97.70% (gate 80%).

## Self-Check: PASSED

- FOUND: skills/digitiamo-buddy/SKILL.md, docs/install-guide.md, tests/unit/mcp_server/test_skill_package.py
- FOUND commits: 6884ede, ea94781, b637211, b0b3037
