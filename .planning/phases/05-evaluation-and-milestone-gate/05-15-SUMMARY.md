---
phase: 05-evaluation-and-milestone-gate
plan: 15
subsystem: eval
tags: [golden-set, lint, recall, gap-closure, privacy]
status: complete
requires:
  - 05-GAP-DECISION.md item 4 (approved golden edits)
  - 05-REVIEW.md WR-01 (recall part), WR-03
provides:
  - gd-05 with two expected sources (ETL vs ELT and BigQuery SCD Type 2 sections)
  - gd-02 key facts 1-2 narrowed (public); sr-02 key fact 1 narrowed (private, local only)
  - lint names a missing handbook source by position, never by page id
  - measure_recall turns an MCP session failure into errored items (INCOMPLETE)
affects:
  - 05-17 live gate re-run (measures these golden edits)
tech-stack:
  added: []
  patterns:
    - "session-level except Exception around the MCP async with; unmeasured items errored"
key-files:
  created: []
  modified:
    - jobs/eval/golden/guides.yaml
    - jobs/eval/buddy_eval/golden.py
    - jobs/eval/buddy_eval/recall.py
    - tests/unit/buddy_eval/test_golden.py
    - tests/unit/buddy_eval/test_recall.py
decisions:
  - "A session that fails on close after every item was measured keeps all results and errors nothing; only the class name is logged"
metrics:
  duration: ~10 min
  completed: 2026-11-22
actuals:
  tokens: 3700
  tasks: 3
  commits: 4
plan_head_before: 9b215a1e48e1f831e9bcf3cee81a988cb62be359
plan_head_after: 7f9217370e1efd46126a55cf5de1e002d538009a
---

# Phase 5 Plan 15: Golden edits for gd-02, gd-05 and sr-02, plus the WR-03 lint and WR-01 recall fixes Summary

This plan makes the three golden edits approved in 05-GAP-DECISION item 4, all lint-clean on the live compose index (build 20261122T094743Z-55ce792552d8). It also adds two fixes: lint no longer prints handbook page ids, and a failed MCP session now ends the recall measurement as INCOMPLETE instead of raising a traceback.

## Tasks

| Task | Name | Commit | Result |
|------|------|--------|--------|
| 1 | Tracer: second gd-05 expected source | be25a16 | lint on live index: `lint: OK (40 items: handbook=15 guides=13 no_answer=7 sensitive=5; draft=0 approved=40 rejected=0)` |
| 2 | Narrow gd-02 facts 1-2 (public) and sr-02 fact 1 (private) | 8d973cb | id-level diff: public `['gd-02', 'gd-05']`, private `['sr-02']`; lint OK as above; `git ls-files docs/internal` empty |
| 3 RED | Failing tests for WR-03 and WR-01 | 6458f9c | 2 golden and 3 recall tests failed as expected |
| 3 GREEN | WR-03 lint position label, WR-01 recall session handler | 7f92173 | test_golden 25 passed, test_recall 32 passed; `--all`: 2068 passed, 26 skipped, ruff/format/mypy clean, coverage 98.11% |

## What changed

- **gd-05**: the BigQuery `scd-type-2-versioned-rows-full-history` section is now the second expected source; the ETL entry stays first. The review_note cites 05-GAP-DECISION.md.
- **gd-02**: key facts 1 and 2 were rewritten along the diagnosis "Fix" line and no longer include the mechanism detail. Key fact 3, the question, expected_answer and expected_sources are unchanged (A-15-1). There are still 3 key facts, the item stays `review: approved`, and the review_note cites 05-GAP-DECISION.md.
- **sr-02** (private file, not committed): key fact 1 now uses the first option of the diagnosis "Fix" line. The item stays approved and the review_note cites the decision. The pre-edit copy `docs/internal/golden-handbook.pre-gap.yaml` exists locally as rollback and diff baseline. It is gitignored.
- **golden.py**: the new `_missing_source(position, entry)` helper labels a `handbook://` entry as `expected_sources[<position>]` and still prints a Guides entry in full. The LintIssue docstring now says an issue never holds a handbook page id.
- **recall.py**: an `except Exception` handler now wraps the whole `async with ...session()` block. On failure it logs `recall session failed: <ClassName>` and appends `_errored(item)` for every item not yet measured. The per-item McpToolError handling is unchanged. The module docstring now says the Recall@5 query stays the keyword query (D-15), while the 05-14 search of the question text in Guides is not measured (A-15-3).

## Verification

- The acceptance greps passed: `05-GAP-DECISION` appears 2 times in guides.yaml and once in the private file; `expected_sources[` appears once in golden.py (non-comment lines); `except Exception` appears once in recall.py.
- guides.yaml contains no `clickup` or `handbook://` reference.
- The test `test_a_missing_handbook_source_is_named_by_position_never_by_page_id` checks that the rendered line contains neither `handbook://` nor the page id.
- STATE.md and ROADMAP.md were not touched by this plan. The ROADMAP.md modification already in the working tree came from the orchestrator and is not staged.

## Deviations from Plan

### Auto-fixed Issues

None. The plan was executed as written, with one addition: a test for a session that fails on close after all items were measured. That test confirms that every measured item keeps its result and nothing is errored.

## TDD Gate Compliance

The RED commit 6458f9c (5 failing tests) comes before the GREEN commit 7f92173. No refactor commit was needed.

## Known Stubs

None.

## Threat Flags

None. The mitigations T-05-46 through T-05-49 were applied as planned.

## Self-Check: PASSED

- FOUND: jobs/eval/golden/guides.yaml, jobs/eval/buddy_eval/golden.py, jobs/eval/buddy_eval/recall.py, tests/unit/buddy_eval/test_golden.py, tests/unit/buddy_eval/test_recall.py
- FOUND commits: be25a16, 8d973cb, 6458f9c, 7f92173
- `git ls-files docs/internal` returns nothing
