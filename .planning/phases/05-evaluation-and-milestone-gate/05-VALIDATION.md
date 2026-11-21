---
phase: "5"
slug: "evaluation-and-milestone-gate"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-21"
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 05-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 (+ pytest-cov 7.1.0), ruff 0.17.3, mypy 2.4.1 strict |
| **Config file** | `pyproject.toml` (pytest, coverage, mypy, ruff sections) |
| **Quick run command** | `./run-unit-tests.sh --single-file test_<module>.py tests/unit/buddy_eval` |
| **Full suite command** | `./run-unit-tests.sh --all` |
| **Estimated runtime** | ~120 seconds (full), ~15 seconds (single file) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command on the touched test file
- **After every plan wave:** Run `./run-unit-tests.sh --all` (includes the structural tests this phase edits: compose, dockerfile stages, requirement locks, repo layout, workflows)
- **Before `/gsd-verify-work`:** Full suite green + `scripts/eval-smoke.sh` (hermetic: stub LLM + real MLflow container) + live checkpoints (`preflight`, `run`, `empty-context`, `gate`) with Joshua
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner and plan checker. Requirement → test mapping:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| EVAL-01 | golden schema, public+private merge, missing private file → incomplete, committed YAML has no `handbook://`/`clickup`, 30-50 count, unknown expected sources rejected | unit | `./run-unit-tests.sh --single-file test_golden.py tests/unit/buddy_eval` | ❌ W0 | ⬜ pending |
| EVAL-01 | Joshua reviews drafts (`draft` → `approved`) | manual checkpoint | human-verify task | n/a | ⬜ pending |
| EVAL-02 | recall hit-any + fractional per source, `< 0.8` flag boundary, tool failure = error not miss, cached reformulation → 0 LLM calls, permalink → chunk_key resolution | unit | `--single-file test_recall.py tests/unit/buddy_eval` | ❌ W0 | ⬜ pending |
| EVAL-03 | per-kind scoring table, invented count over answered items only, judge prompt fences full source text, cache key ingredients, errored never cached, resume | unit | `--single-file test_scoring.py` / `test_judge.py` / `test_cache.py` / `test_runner.py` | ❌ W0 | ⬜ pending |
| EVAL-03 | live scoring through Meridian | live checkpoint | `docker compose --profile eval run --rm eval run` | n/a | ⬜ pending |
| EVAL-04 | PASS when all refusal/referral with `gap_reported`; FAIL on any answer; fixture index loads and returns no hits | unit | `--single-file test_empty_context.py tests/unit/buddy_eval` | ❌ W0 | ⬜ pending |
| EVAL-04 | real-LLM empty-context | live checkpoint | `docker compose --profile eval run --rm eval empty-context` | n/a | ⬜ pending |
| EVAL-05 | compose structure: mlflow digest pin, only `127.0.0.1:5000` published, `--allowed-hosts`, telemetry off, profile `eval` | unit (structural) | `--single-file test_compose.py tests/unit` | ✅ (update) | ⬜ pending |
| EVAL-05 | one trace per item with reformulate/retrieve/answer/gate spans + assessments | smoke | `scripts/eval-smoke.sh` | ❌ W0 | ⬜ pending |
| EVAL-06 | gate boundaries (89.9 vs 90.0, invented 0 vs 1, empty-context fail, draft present, private file missing, errored items), failing metric named, exit 0 only on PASS | unit | `--single-file test_gate.py tests/unit/buddy_eval` | ❌ W0 | ⬜ pending |
| EVAL-06 | real gate | live checkpoint | `docker compose --profile eval run --rm eval gate` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/buddy_eval/conftest.py`: fixture index (reuse `tests/unit/mcp_server/conftest.py` helpers), FakeLlm, recording connector, fake tracing sink
- [ ] `jobs/eval/` skeleton + `requirements.txt` / `requirements.lock` + Dockerfile `eval` stage + `scripts/lock-requirements.sh` extension
- [ ] `pyproject.toml`: pythonpath, coverage source, mypy files, ruff first-party for `buddy_eval`
- [ ] Update structural tests: `tests/unit/test_compose.py`, `test_dockerfile_stages.py`, `test_requirements_lock.py`, `test_repo_layout.py`, `test_workflows.py`, `.github/dependabot.yml`
- [ ] `deploy/compose/stub_llm.py` + `tests/unit/test_stub_llm.py`: judge schema branch

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Golden set review | EVAL-01 | Joshua's judgement is the review | Edit `review:` fields to approved/rejected in both golden files |
| New pins legitimacy (mlflow-skinny, pandas flagged SUS: too-new) | EVAL-05 | supply-chain gate needs a human | Confirm PyPI project pages, then approve |
| Meridian preflight (Opus 5.5 id, quota) | EVAL-03 | needs Joshua's Max credentials | `docker compose --profile eval run --rm eval preflight` |
| Live run / empty-context / gate | EVAL-03/04/06 | real LLM through Max | run the commands, inspect the report and MLflow UI at 127.0.0.1:5000 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
