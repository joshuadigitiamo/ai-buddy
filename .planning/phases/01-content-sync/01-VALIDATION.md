---
phase: "01"
slug: "content-sync"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-03"
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `01-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 + pytest-cov 7.1.0; ruff 0.17.3; mypy 2.4.1 (strict) |
| **Config file** | `pyproject.toml` (none yet — Wave 0 installs) |
| **Quick run command** | `./run-unit-tests.sh --single-file <test_file> <test_directory>` |
| **Full suite command** | `./run-unit-tests.sh --all` (ruff check, ruff format --check, mypy, pytest --cov) |
| **Estimated runtime** | ~60 seconds (image build cached) |

---

## Sampling Rate

- **After every task commit:** Run `./run-unit-tests.sh --single-file <file> <dir>` for the touched module
- **After every plan wave:** Run `./run-unit-tests.sh --all`
- **Before `/gsd-verify-work`:** Full suite must be green, plus manual rows below
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

Task IDs are filled by the planner/executor; rows below are seeded per requirement from research.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T2 | 01-01 | 1 | FND-01, FND-02 | T-01-02, T-01-03 | No host Python; `--network none`; no root-owned files | smoke + host checks | `./run-unit-tests.sh --all`; `./run-unit-tests.sh --bogus; test $? -eq 1` | ❌ W0 | ⬜ pending |
| 01-01-T3 | 01-01 | 1 | FND-01 | T-01-01 | `.env.example` has empty secrets; artifacts gitignored | unit | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit` | ❌ W0 | ⬜ pending |
| 01-02-T1 | 01-02 | 2 | SYNC-05, SYNC-07 | T-01-06 | Atomic publish | unit | `./run-unit-tests.sh --single-file test_index_roundtrip.py tests/unit/buddy_core` | ❌ W0 | ⬜ pending |
| 01-02-T2 | 01-02 | 2 | SYNC-07, SYNC-04 | T-01-05, T-01-07 | Hostile queries never raise; version refusal | unit | `./run-unit-tests.sh --single-file test_index_format.py tests/unit/buddy_core`; `test_artifact_store.py`; `test_search_guides.py` | ❌ W0 | ⬜ pending |
| 01-02-T3 | 01-02 | 2 | SYNC-07 | — | N/A | doc check | `test -f docs/index-format.md && test -f docs/adr/0001-index-handoff.md` | ❌ W0 | ⬜ pending |
| 01-03-T1 | 01-03 | 2 | SYNC-01, SYNC-03 | T-01-11, T-01-12 | Token never in repr/log/errors; log has rule name only | unit | `./run-unit-tests.sh --single-file test_config.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-03-T2 | 01-03 | 2 | SYNC-03 | T-01-10, T-01-13 | Every D-15 rule masks; D-16 survives | unit | `./run-unit-tests.sh --single-file test_redaction.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-03-T3 | 01-03 | 2 | SYNC-03 | T-01-10 | Corpus false positives measured (local only) | unit (local) | `./run-unit-tests.sh --single-file test_corpus_local.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-04-T1 | 01-04 | 3 | SYNC-03, SYNC-05 | T-01-15 | Denylisted page absent from every byte | unit | `./run-unit-tests.sh --single test_redaction_pipeline.py test_denylisted_page_absent tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-04-T2 | 01-04 | 3 | SYNC-01 | T-01-16, T-01-17 | Token absent from errors; bounded retries | unit | `./run-unit-tests.sh --single-file test_clickup_client.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-04-T3 | 01-04 | 3 | SYNC-02 | T-01-18 | Empty denylist refused | unit | `./run-unit-tests.sh --single-file test_handbook_sync.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-05-T1 | 01-05 | 3 | SYNC-04 | — | N/A | unit | `./run-unit-tests.sh --single-file test_guides_source.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-05-T2 | 01-05 | 3 | SYNC-04 | T-01-24 | Symlink escape excluded | unit | `./run-unit-tests.sh --single-file test_chunker.py tests/unit/buddy_sync`; `--single test_guides_scope.py test_globs tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-05-T3 | 01-05 | 3 | SYNC-04 | T-01-21, T-01-22, T-01-23 | Token absent from argv/.git/config/errors; no reset outside marked checkout | unit | `./run-unit-tests.sh --single-file test_guides_git.py tests/unit/buddy_sync`; `test_guides_index.py` | ❌ W0 | ⬜ pending |
| 01-06-T1 | 01-06 | 3 | SYNC-06 | T-01-27 | safe_load only | unit | `./run-unit-tests.sh --single test_video_map.py test_mapped_section_has_timestamped_link tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-06-T2 | 01-06 | 3 | SYNC-06 | T-01-26, T-01-28 | Path escape and oversize fail the load | unit | `./run-unit-tests.sh --single-file test_video_map.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-06-T3 | 01-06 | 3 | SYNC-06 | — | README drift fails loudly | unit | `./run-unit-tests.sh --single-file test_readme_videos.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-07-T1 | 01-07 | 4 | (phase) SYNC-01..07 | T-01-33 | Failed build keeps previous artifact | integration (in-process) | `./run-unit-tests.sh --single test_sync_e2e.py test_end_to_end tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-07-T2 | 01-07 | 4 | SYNC-01, SYNC-03, SYNC-04 | T-01-30 | CLI prints no content or token | unit | `./run-unit-tests.sh --single-file test_cli.py tests/unit/buddy_sync` | ❌ W0 | ⬜ pending |
| 01-08-T1 | 01-08 | 5 | SYNC-04, SYNC-06 | T-01-37 | Guides edits uncommitted until Joshua reviews | local-only | docker run with `GUIDES_LOCAL_DIR=/guides` (see plan 08 Task 1) | ❌ W0 | ⬜ pending |
| 01-08-T3 | 01-08 | 5 | SYNC-01, SYNC-03, SYNC-05 | T-01-34, T-01-35, T-01-36 | Live artifact clean; `.env` never printed | live (manual trigger) | docker run with `LIVE_ARTIFACT_DIR=/app/artifacts` (see plan 08 Task 3) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Dockerfile`, `run-unit-tests.sh`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.env.example`, `.gitignore` additions
- [ ] `tests/unit/buddy_core/`, `tests/unit/buddy_sync/`, `tests/fixtures/` (synthetic ClickUp JSON, fixture Guides tree) and `tests/conftest.py` (fixture git repo builder)
- [ ] Framework install inside Docker `test` stage (no host install)
- [ ] Remove `main.py` stub; `requires-python >=3.12`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Runner modes `--all`, `--single`, `--single-file`, bad args → exit 1 | FND-02 | Needs Docker daemon on host | Run each mode on host; `./run-unit-tests.sh --bogus; echo $?` → 1 |
| No root-owned files after run | FND-02 | Host filesystem check | `find . -user root -not -path './.git/*' \| head` → empty |
| Guides sections + exceptions listed in plan | GUIDE-01 | Plan-review artifact | Plan checker reads "Guides applied" block |
| `docs/index-format.md`, `docs/adr/0001-index-handoff.md` exist | SYNC-07 | Doc review | Read files |
| Live smoke against `xkwgt-39975`, Wi-Fi page absent | SYNC-01/03 | Needs credentials + network | `docker run … python -m buddy_sync` with `.env` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
