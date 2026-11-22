---
phase: 05-evaluation-and-milestone-gate
plan: 09
subsystem: evaluation-golden-lint-and-recall
tags: [eval, golden, lint, recall, D5-trigger, privacy, EVAL-01, EVAL-02]
requires:
  - phase: 05-07
    provides: SourceIndex.has_expected, matches, ResultCache, key_for, bot_version, reformulation namespace
  - phase: 05-03
    provides: GoldenItem, GoldenSet, load_golden, cli subcommand pattern
  - phase: 05-08
    provides: report.write_json_report
provides:
  - "`python -m buddy_eval lint`: schema load, index existence, 30-50 range, kind and sensitive-branch coverage, duplicate questions, clickup string, missing private file"
  - "`python -m buddy_eval recall [--item ID]...`: Recall@5 per source over approved handbook and Guides items, with the D5 trigger"
  - LintIssue, lint_golden, format_lint, normalize_question, KIND_TARGETS in golden.py
  - RecallItem, RecallResult, measure_recall, format_recall, default_connector_factory in recall.py
  - Committed-golden privacy guard in tests/unit/test_repo_layout.py
affects: [05-10, 05-11, 05-12]
tech-stack:
  added: []
  patterns: [reuse the bot's reformulate node through RunContext and Runtime, integer arithmetic for the 0.8 boundary, lazy model client so a fully cached rerun builds none, per-command connector default]
key-files:
  created:
    - jobs/eval/buddy_eval/recall.py
    - tests/unit/buddy_eval/test_golden.py
    - tests/unit/buddy_eval/test_recall.py
  modified:
    - jobs/eval/buddy_eval/golden.py
    - jobs/eval/buddy_eval/cli.py
    - tests/unit/test_repo_layout.py
decisions:
  - "Lint issue text is `<severity>: <subject>: <field>: <problem>`; a load error is one `error: golden_set: <GoldenError text>` line followed by `lint: 1 errors`, since GoldenError already names file, item id and field and never question text"
  - "Sensitive-branch errors are emitted only when at least one sensitive item exists; zero sensitive items is already the `kind sensitive: no items` error"
  - "Items that count toward the 30-50 range, the per-kind mix and the duplicate check are the non-rejected ones; rejected items are not checked against the index"
  - "Recall totals count measured (non-errored) items; an errored item is listed in `recall: INCOMPLETE` and exits 1, so a partial D5 verdict is never silent. A source whose items all errored prints `n/a (0 measured)` instead of `n/a (0 items)`"
  - "cli.main now passes connector_factory through unresolved: run and gate default to FastMcpConnector (bot limits 3 and 4), recall defaults to default_connector_factory (limit 5 for both tools). An injected factory serves every command"
  - "The model client is built lazily on the first reformulation cache miss, so a fully cached recall run builds none"
  - "measure_recall opens no session when there is nothing to measure"
metrics:
  duration: single session
  completed: 2026-11-22
status: complete
actuals:
  tokens: 14000
  tasks: 2
  commits: 2
plan_head_before: 006dd424e7153298d39ab289c18228886078ed56
plan_head_after: adf43c7739b6e324c95153d36ebb0e962eb274d8
---

# Phase 5 Plan 09: Golden lint and Recall@5 with the D5 trigger Summary

`lint` proves a golden set is schema-valid, sourced from the current index, within 30-50 non-rejected items with both sensitive branches and free of ClickUp strings, and `recall` prints Recall@5 for handbook and Guides search from the bot's own cached reformulation, flagging the hybrid-upgrade trigger exactly below 0.8.

## What was built

**Task 1 (d2d2a39): golden lint and the privacy guard**
- `golden.py`: `LintIssue`, `normalize_question` (casefold, punctuation removed, whitespace collapsed, A-09-3), `lint_golden(golden_set, index, *, raw_texts)`, `format_lint`. Errors: missing private file, clickup (any case) in either raw file, count outside 30-50, a kind with zero items, a missing sensitive branch, an expected source `index.has_expected` rejects, two equal normalized questions (names both ids). Kind counts away from 15/13/7/5 are warnings. Errors print before warnings.
- `cli.py`: `lint` subcommand, no model, MCP or MLflow use. Prints `lint: OK (<n> items: handbook=.. guides=.. no_answer=.. sensitive=..; draft=.. approved=.. rejected=..)` or `lint: <k> errors`; exit 0 only without errors.
- `tests/unit/test_repo_layout.py`: `_handbook_violations`, a fail-first checker test, `test_committed_golden_files_hold_no_handbook_reference` (git ls-files plus a glob of `jobs/eval/golden/`), `test_private_golden_path_is_gitignored`.

**Task 2 (adf43c7): Recall@5**
- `recall.py`: `measure_recall` opens one MCP session, paces `item_pause_seconds` between items, and per approved handbook or Guides item (id order) gets the reformulation from the `reformulation` cache or from the real `reformulate` node (`RunContext` plus `Runtime`). Key: question, reformulate model, sha256 of the reformulate system prompt, bot version. Only a `Reformulation` is cached. Queries are the keywords joined by spaces (`keywords_it` to `handbook_search`, `keywords_en` to `guides_search`); the first five results are scored with `sources.matches`. `McpToolError` or a reformulation error marks the item errored.
- Trigger: `guides_total > 0 and guides_hits * 5 < guides_total * 4`.
- `cli.py`: `recall` subcommand with repeatable `--item`; per-item JSON (retrieved private ids) written under `PRIVATE_DIR/eval/reports/recall-<UTC>.json`; exit 1 on any errored item. No MLflow sink is built.

## Verification

- `./run-unit-tests.sh --single-file test_golden.py tests/unit/buddy_eval`: 24 passed.
- `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit`: 14 passed, including `test_committed_golden_files_hold_no_handbook_reference`.
- `./run-unit-tests.sh --single-file test_recall.py tests/unit/buddy_eval`: 29 passed.
- `./run-unit-tests.sh --all`: ruff, ruff format and mypy clean; 1941 passed, 26 skipped (emulator and live-source tests); total coverage 97.94% against the 80% floor.
- Acceptance greps: `handbook_limit=5` 1, `D5 TRIGGER: guides recall@5 < 0.8` 1, mlflow imports in recall.py 0, `def test_committed_golden_files_hold_no_handbook_reference` 1, `def lint_golden` 1.

## Deviations from Plan

None. Plan executed as written; the points the plan left open are recorded under `decisions` above. `jobs/eval/golden/` does not exist yet (05-11 creates the committed file), so the committed-golden privacy test passes vacuously today and starts checking real files as soon as they are added.

## Carry-forward

- `_gate_inputs` still passes `invented=None`; its wiring stays with 05-12 (unchanged here).
- `emit` remains the only presentation call for run results. `lint` and `recall` print their own lines in the way `gate` prints its verdict lines.
- 05-11 should run `lint` against a fresh index before approving any item, and `recall` for the first real D5 reading.

## Known Stubs

None.

## Threat Flags

None. T-05-24 (committed golden files) is mitigated by the privacy test and its fail-first checker; T-05-25 by keeping retrieved ids in the PRIVATE_DIR report and printing ids and numbers only; T-05-26 by one session, pacing and errored (never silent-miss) failed calls.

## Self-Check: PASSED

- FOUND: jobs/eval/buddy_eval/recall.py, tests/unit/buddy_eval/test_golden.py, tests/unit/buddy_eval/test_recall.py
- FOUND commits: d2d2a39, adf43c7
