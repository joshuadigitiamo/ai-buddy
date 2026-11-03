---
phase: 01-content-sync
plan: 03
subsystem: sync
tags: [pydantic-settings, secretstr, redaction, regex, privacy, gdpr, tdd]

requires:
  - phase: 01-01
    provides: Dockerized runner, pinned pydantic-settings, buddy_sync package root, .env.example contract
provides:
  - SyncSettings and ConfigError (env-only settings, SecretStr tokens, csv sets, validators)
  - Redactor with ten ordered rules, MASK, REDACTION_VERSION, RULE_NAMES, RuleHit, RedactionResult, log_hits
  - Local-only corpus false-positive check over the gitignored raw handbook snapshot
affects: [01-04, 01-05, 01-07, 01-08]

plan_head_before: 7512fa67802b9c63738c3f7d83699d52a6f443cd
plan_head_after: 0fba9f7eebac57fc59a6124b8307732c2b9d168f

actuals:
  tokens: 7117
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Table-driven rule registry: one Rule(name, pattern, replace) per detector, applied in fixed RULE_NAMES order, per-rule counts returned as RuleHit"
    - "Logs carry source id, rule name and count only; tests assert booleans/integers so failures never print values"
    - "Secret-shaped test fixtures are assembled at runtime so no literal in the repo resembles a real credential"

key-files:
  created:
    - jobs/sync/buddy_sync/config.py
    - jobs/sync/buddy_sync/redaction.py
    - tests/unit/buddy_sync/test_config.py
    - tests/unit/buddy_sync/test_redaction.py
    - tests/unit/buddy_sync/test_corpus_local.py
  modified: []

key-decisions:
  - "IBAN rule retries shorter heads when an uppercase word is swallowed by the candidate, so 'IBAN SDI' still masks the IBAN"
  - "signed_url_query keeps a URL fragment and trailing sentence punctuation; only the query string is dropped"
  - "high_entropy matches URLs in the same alternation and returns them untouched, so URL path segments are never masked"
  - "Non-company e-mails stay masked by default; allow-listing calendar/reply-to domains is deferred to plan 08 (flagged assumption)"

requirements-completed: [SYNC-01, SYNC-03, GUIDE-01]

coverage:
  - id: D1
    description: "SyncSettings loads from env; CLICKUP_TOKEN and GUIDES_REPO_TOKEN never appear in repr, str, model_dump_json or validation errors; csv sets parse; branch and doc-id validators reject unsafe values; require_clickup names missing variables only"
    requirement: SYNC-01
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_config.py (10 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each of the ten D-15 rules masks its synthetic positive; labelled credentials keep the label; images reduce to alt text; signed-URL queries are stripped"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction.py (34 test cases)"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-16 keeps survive byte-identical (names, roles, company e-mails, office numbers, P.IVA, SDI, address, bare 'codice', UUID URLs, 40-char SHAs) and the same Redactor handles Guides markdown incl. code fences"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction.py#test_d16_work_contacts_and_company_data_survive_byte_identical"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction.py#test_token_prefix_also_applies_inside_guides_code_fences"
        status: pass
    human_judgment: false
  - id: D4
    description: "Log records carry source id, rule name and count only; the matched value is absent from caplog; 1 MB adversarial input redacts in under 2 s"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction.py#test_labelled_password_is_masked_and_logged_by_rule_name_only"
        status: pass
      - kind: unit
        ref: "tests/unit/buddy_sync/test_redaction.py#test_redaction_of_one_megabyte_is_fast"
        status: pass
    human_judgment: false
  - id: D5
    description: "Local corpus check: over the 22 non-Wi-Fi pages D-16 counts are unchanged, every mask is reported by rule, the Wi-Fi page's credential label is caught"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/buddy_sync/test_corpus_local.py (47 tests, passed on this machine, skipped elsewhere)"
        status: pass
    human_judgment: true
    rationale: "Two of four D-16 baselines are zero in this snapshot (company e-mails, leading-0 office numbers), so those checks pass vacuously on the real corpus; they are exercised only by the synthetic D-16 block test"
  - id: D6
    description: "GUIDE-01: plan carries a Guides applied block"
    requirement: GUIDE-01
    verification: []
    human_judgment: true
    rationale: "Convention compliance is a review judgment; only the block's presence is mechanical"

duration: 5min
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 03: Settings and Redaction Summary

**Env-only `SyncSettings` with SecretStr tokens and a ten-rule `Redactor` (labels, key blocks, token prefixes, JWT, mod-97 IBAN, IT mobiles, private e-mails, entropy, signed URLs, image alt) that keeps work contacts and company data, proven on synthetic fixtures and on the local handbook snapshot.**

## Performance

- **Duration:** ~5 min (2026-11-03T19:14:48Z to 19:19:53Z)
- **Tasks:** 3 (Task 1 tracer, Task 2 TDD, Task 3 corpus check)
- **Files:** 5 created, 0 modified

## Accomplishments

- Tracer: env to settings to Redactor to log record, end to end; a labelled password is masked (`**Password:** [REDATTO]`), the surrounding text stays, and the log record has rule name and source id only.
- `SyncSettings`: `hide_input_in_errors=True`, no env file, tokens `SecretStr`, comma-separated `frozenset` fields via `NoDecode`, `GUIDES_BRANCH` rejects leading hyphen and exotic characters (T-01-14).
- Ten rules registered in `RULE_NAMES` order with bounded quantifiers; 1 MB adversarial text (long digit/letter/hyphen runs, repeated `+39`, `IT60`, dotted words) redacts under 2 s.
- Corpus check on the 22 non-Wi-Fi pages: per-rule hits are image_link 10, private_email 5, all others 0; D-16 counts identical before and after; Wi-Fi page reports at least one labelled_secret hit.

## Task Commits

1. **Task 1: Tracer, settings and labelled-secret redaction** - `5244198` (feat)
2. **Task 2 RED: failing tests for the full rule set** - `6566ce8` (test)
3. **Task 2 GREEN: ten-rule implementation** - `554eeef` (feat)
4. **Task 3: local-only corpus check** - `0fba9f7` (test)

**Plan metadata:** committed separately (docs: complete plan).

## TDD Notes (Task 2)

- **RED:** 34 cases in `test_redaction.py`; 21 positive-case tests failed with `AssertionError` on the planned masked output (the labelled-secret rule from Task 1 was the only one registered). Keep-cases (negatives, D-16 block, perf guard) already passed, as expected for behaviour the code had not yet changed. Semantic assessment: every failure was the planned assertion on unmasked input, no import, collection or fixture faults. The `gsd_run check tdd-red-evidence` classifier was not run: the plan is `type: execute` with a per-task `tdd="true"`, `workflow.tdd_mode` is not enabled, and the classifier has no pytest-native adapter.
- **GREEN:** `554eeef`, 35/35 in `test_redaction.py`, `--all` exit 0.
- **REFACTOR:** none needed.

## Files Created

- `jobs/sync/buddy_sync/config.py` - `SyncSettings`, `ConfigError`
- `jobs/sync/buddy_sync/redaction.py` - rules, `Redactor`, `log_hits`, `_shannon_entropy`, `_iban_checksum_ok`
- `tests/unit/buddy_sync/test_config.py` - 10 tests
- `tests/unit/buddy_sync/test_redaction.py` - 20 test functions (35 cases)
- `tests/unit/buddy_sync/test_corpus_local.py` - 47 cases, skipif when corpus absent

## Decisions Made

See key-decisions. Corpus tuning: no change to `redaction.py` was needed after the corpus run; all D-16 counts were already equal on the first run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff format drift on new files**
- **Found during:** Task 1 and Task 2 `--all` runs
- **Fix:** ran `ruff format` in the test image on the new files (the runner only has `--check`)
- **Files modified:** redaction.py, test_redaction.py
- **Commit:** included in the task commits

**Total deviations:** 1 auto-fixed (formatting). **Impact:** none.

Process note: commits made directly on `main` as instructed (branching_strategy=none, sequential executor).

## Authentication Gates

None.

## Issues Encountered

- **Two D-16 corpus checks are vacuous.** The snapshot has zero `@digitiamo.com` addresses and zero leading-0 office numbers (baselines printed by `test_per_rule_hit_table`), so only P.IVA-like (2) and SDI (1) are exercised on real text. The company e-mail and office-number keeps are proven only by the synthetic D-16 block test.
- **All 5 e-mails in the snapshot are non-company and are masked** under the default allow-list (consistent with research: calendar group, reply-to, third-party contact). Plan 08 must decide whether to allow-list any of those domains via `REDACT_EMAIL_ALLOW_DOMAINS`.
- Entropy threshold (4.2 bits/char, 24+ chars) produced zero hits on the corpus, so it is untuned against real positives; it is untested against Guides content until plan 05/07.

## Known Stubs

None.

## Threat Flags

None. No new endpoints, auth paths or schema; T-01-10 to T-01-14 mitigated as planned (synthetic per-rule tests, caplog test, SecretStr and error-hiding tests, 1 MB timing test, branch validator).

## Next Phase Readiness

Ready for 01-04 (ClickUp client can call `SyncSettings.require_clickup()` and the `Redactor`; the page denylist D-13 is still to be enforced there). `REDACTION_VERSION = "1"` is available for the `meta` row.

## Self-Check: PASSED

- Created files exist; commits `5244198`, `6566ce8`, `554eeef`, `0fba9f7` are on `main`; `git rev-list --count 7512fa6..HEAD` = 4.
- `./run-unit-tests.sh --all`: ruff, ruff format, mypy strict, 156 passed, coverage 97%.
- `git check-ignore docs/research/handbook-raw/07-wi-fi.md` exits 0; corpus run output contains only file names, rule names and integers.
