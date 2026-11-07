---
phase: 03-google-chat-bot
plan: 02
subsystem: bot-core
tags: [yaml, escalation, safe_load, drift-test, buddy_core]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "SKILL.md 'Temi da escalare' table approved by Joshua in 02-06"
provides:
  - "buddy_core/data/escalation_topics.yaml: eight topic -> role rows, fallback_role HR, version 1"
  - "buddy_core.escalation: EscalationTopic, EscalationTable (ids, topic, referente_role), EscalationTableError, load_escalation_table, DEFAULT_TABLE_PATH"
  - "test_yaml_matches_skill_table: fails with the row number when YAML and SKILL.md drift"
affects: [03-05 reformulation and sensitive-topic handling, skills/digitiamo-buddy/SKILL.md]

actuals:
  tokens: 3200
  tasks: 2
  commits: 3
plan_head_before: 5d8e46cb43a55af5c88efc21daa311fd29848b57
commits: 3
plan_head_after: 7e96af9969aa67a617e4abe6e4f4ac86c25d2687

tech-stack:
  added: []
  patterns:
    - "Shared reviewed data file in buddy_core/data, loaded with yaml.safe_load and a schema check that names field and row, never the value"
    - "Text-vs-data drift guard: test parses the Skill Markdown table and compares rows in order"

key-files:
  created:
    - packages/buddy_core/buddy_core/data/escalation_topics.yaml
    - packages/buddy_core/buddy_core/escalation.py
    - tests/unit/buddy_core/test_escalation.py
  modified: []

key-decisions:
  - "ruolo is the role the bot searches for and names; referente keeps the Skill's full wording for the drift check (plan's flagged D-08 assumption, kept)"
  - "Topic ids fixed: stipendio, malattia, molestie, disciplinare, contratto, privacy, ferie_personali, rimborsi"
  - "A tmp YAML's version field is checked against the constant 1; any other value is an EscalationTableError"

requirements-completed: [BOT-06]

coverage:
  - id: D1
    description: "Shared escalation table in buddy_core, loaded by a typed loader and kept equal to SKILL.md by a drift test"
    requirement: BOT-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_yaml_matches_skill_table"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_default_table_loads"
        status: pass
    human_judgment: false
  - id: D2
    description: "Drift check is proven to fail on a one-cell change and on a missing row"
    requirement: BOT-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_drift_check_reports_the_changed_row"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_drift_check_reports_a_missing_row"
        status: pass
    human_judgment: false
  - id: D3
    description: "referente_role maps a topic id, None or an unknown id to a role with HR fallback"
    requirement: BOT-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_referente_role"
        status: pass
    human_judgment: false
  - id: D4
    description: "Malformed tables raise EscalationTableError naming field and row index without echoing values"
    requirement: BOT-06
    verification:
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_malformed_table_names_the_field"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_core/test_escalation.py#test_error_message_does_not_echo_the_value"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 02: Shared Escalation Table Summary

**Shared YAML table of eight sensitive topics and referral roles in buddy_core, read by a validating `yaml.safe_load` loader with HR fallback, and a drift test that fails with the row number when SKILL.md and the YAML disagree.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-11-07T11:08:47Z
- **Completed:** 2026-11-07T11:14:00Z (approx.)
- **Tasks:** 2
- **Files modified:** 3 (all created)

## Accomplishments

- `escalation_topics.yaml` holds the eight "Temi da escalare" rows with `id`, `tema`, `referente` (copied character for character from SKILL.md) and `ruolo`; `fallback_role: HR`, `version: 1`. Roles only, no contacts.
- `escalation.py` exposes the typed interface 03-05 needs: `EscalationTable.ids()`, `.topic(id)`, `.referente_role(id | None)`; unknown or `None` id gives the fallback role HR (D-04).
- Validation: non-mapping top level, version other than 1, empty `fallback_role`, empty or non-list `topics`, non-mapping row, empty field, id not matching `[a-z][a-z0-9_]*`, duplicate id. Each raises `EscalationTableError` naming the field and row index (e.g. `topics[1].id duplicates topics[0].id`), never the value.
- Drift guard: `test_yaml_matches_skill_table` compares (tema, referente) pairs with SKILL.md in order. `first_drift` is proven to report the right 1-based row for a changed cell (row 7) and a missing row (row 6).
- Full gate `./run-unit-tests.sh --all`: ruff, mypy strict and pytest pass, 623 passed / 18 skipped, total coverage 97.76%, `escalation.py` 100%.

## Task Commits

1. **Task 1: Tracer - shared escalation table loads and matches the Skill table** - `404982c` (feat)
2. **Task 2: Validation, role lookup with HR fallback, negative drift case** (TDD)
   - RED: `e41e5ec` (test)
   - GREEN: `7e96af9` (feat)
   - REFACTOR: none needed

**Plan metadata:** committed separately after this file (docs: complete plan).

## TDD Gate Compliance

Task 2 only (Task 1 is a tracer, not TDD). Gate sequence present: `test(03-02)` `e41e5ec` precedes `feat(03-02)` `7e96af9`, and the GREEN commit descends from the RED commit.

- **RED:** 19 tests collected, 15 failed, 4 passed. The 15 failures run inside the target tests and fail on the planned missing behavior: `AttributeError: 'EscalationTable' object has no attribute 'referente_role' / 'topic' / 'ids'` and `module 'buddy_core.escalation' has no attribute 'EscalationTableError'`. No collection, import or fixture errors (the new symbol was reached through `escalation.EscalationTableError` at test time so the module imported cleanly). The 4 that passed are `test_default_table_loads`, `test_yaml_matches_skill_table` (Task 1 behavior) and the two drift-helper tests, which exercise `first_drift`, a helper that lives in the test module by plan design, so they cannot be red.
- **Semantic assessment:** the failing targets executed and failed because the validation errors and lookup methods did not exist yet, which is the intended reason. The failure is an `AttributeError`, not an assertion on a returned value, because the API under test did not exist.
- **Machine check not run:** `gsd_run check tdd-red-evidence` was not run. The plan is `type: execute` with a task-level `tdd="true"`, and the classifier has no adapter for pytest text output. RED evidence is the pytest output recorded above.
- **GREEN:** minimal validation plus the three lookup methods; all 19 target tests pass.

## Files Created/Modified

- `packages/buddy_core/buddy_core/data/escalation_topics.yaml` - source-of-truth table shared by the bot and the Skill
- `packages/buddy_core/buddy_core/escalation.py` - frozen slotted dataclasses, `EscalationTableError`, validating loader
- `tests/unit/buddy_core/test_escalation.py` - loader, validation, lookup and drift tests (19 collected, 10 `def test_`)

## Decisions Made

- Followed the plan's flagged D-08 assumption: `ruolo` is what the bot searches for and names, `referente` keeps the Skill wording for the drift check.
- The loader returns `version=1` from a constant after checking the file says 1, so a table with another version is rejected rather than silently accepted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lint and type errors in the test module**
- **Found during:** Task 2 (GREEN verification, `./run-unit-tests.sh --all`)
- **Issue:** The RED commit's `first_drift` used `zip()` without `strict=` (ruff B905), and `valid_table()` carried a `# type: ignore[no-any-return]` that mypy reported as unused.
- **Fix:** `zip(..., strict=False)` (lengths are compared explicitly right after), removed the unused ignore.
- **Files modified:** `tests/unit/buddy_core/test_escalation.py`
- **Verification:** `--all` exits 0 (ruff, mypy, pytest).
- **Committed in:** `7e96af9` (GREEN commit; the RED commit `e41e5ec` therefore carries the B905 error)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test-only lint fix, no behavior change, no scope creep.

## Issues Encountered

- RED commit `e41e5ec` was made before running ruff on the test file's `zip` call, so that single commit does not pass `ruff check`. Fixed in the next commit.
- Constraint from 03-01 respected: no package installed, nothing touched under `services/chat_bot/`, requirements files, Dockerfile or `pyproject.toml`. PyYAML was already pinned.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None. T-03-04 mitigated (`yaml.safe_load` only, field-named errors, drift test); T-03-05 mitigated (acceptance grep finds 0 e-mail patterns in the YAML); T-03-SC accepted (no new package).

## Next Phase Readiness

- 03-05 can call `load_escalation_table().referente_role(sensitive_topic)` and `.ids()` to build the reformulation prompt's allowed values.
- If a Skill table row changes, the YAML and the Skill must be edited together or `test_yaml_matches_skill_table` fails with the row number.

## Self-Check: PASSED

- FOUND: packages/buddy_core/buddy_core/data/escalation_topics.yaml, packages/buddy_core/buddy_core/escalation.py, tests/unit/buddy_core/test_escalation.py
- FOUND commits: 404982c, e41e5ec, 7e96af9
- Acceptance criteria: 8 topic ids, 1 `fallback_role: HR`, 0 e-mail patterns, SKILL.md and services/mcp_server unchanged since 7d772e2, 10 `def test_`, `safe_load` present.

---
*Phase: 03-google-chat-bot*
*Completed: 2026-11-07*
