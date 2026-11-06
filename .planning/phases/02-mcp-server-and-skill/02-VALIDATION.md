---
phase: "02"
slug: "mcp-server-and-skill"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-06"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 + pytest-cov 7.1.0, anyio pytest plugin for async tests (`@pytest.mark.anyio` + `anyio_backend` fixture); ruff 0.17.3; mypy 2.4.1 `--strict` (pydantic plugin) |
| **Config file** | `pyproject.toml` (02-01 adds `services/mcp_server` / `buddy_mcp` to pythonpath, mypy, ruff, coverage; 02-03 adds the `firestore` marker) |
| **Quick run command** | `./run-unit-tests.sh --single-file <test_file> tests/unit/mcp_server` |
| **Full suite command** | `./run-unit-tests.sh --all` (ruff check, ruff format --check, mypy, pytest --cov-fail-under=80, `--network none`) |
| **Emulator suite** | `./run-unit-tests.sh --emulator` (02-03: docker compose Firestore emulator + `pytest -m firestore tests/integration`) |
| **Estimated runtime** | ~60-90 s for `--all` (image cached); ~60 s for `--emulator` (emulator start ~25 s) |

---

## Sampling Rate

- **After every task commit:** Run `./run-unit-tests.sh --single-file <touched test> tests/unit/mcp_server`
- **After every plan wave:** Run `./run-unit-tests.sh --all` (and `--emulator` after waves 2, 3 and 5)
- **Before `/gsd-verify-work`:** `--all` and `--emulator` must both be green; 02-07 Task 3 resolved (approved or deferred)
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | (supply chain) | T-02-SC | no install before the legitimacy approval | manual checkpoint | — (blocking-human) | n/a | ⬜ pending |
| 02-01-02 | 01 | 1 | MCP-01, MCP-03 | T-02-01 | stateless JSON (no session id, GET 405); cited Guides result over HTTP | integration (ASGI) | `./run-unit-tests.sh --single-file test_http_transport.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | MCP-02, MCP-03, MCP-04 | T-02-02, T-02-04 | read-only index, limit clamp, operators inert, fail-fast cold start | unit | `./run-unit-tests.sh --single-file test_guides_tools.py tests/unit/mcp_server`; `test_snapshot.py`; `test_models.py` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | MCP-03, MCP-04 | T-02-05 | stemmed FTS with bound MATCH; accents/case fold; no_results | unit | `./run-unit-tests.sh --single-file test_handbook_search.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | MCP-02, MCP-06 | T-02-06 | dict lookup only, traversal ids rejected | unit | `./run-unit-tests.sh --single-file test_handbook_get.py tests/unit/mcp_server`; `test_handbook_resource.py` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | MCP-05 | T-02-08, T-02-10 | gap doc has six keys, no identity; emulator only | integration (emulator) | `./run-unit-tests.sh --emulator` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | MCP-05 | T-02-11 | question bounds, exact TTL, lazy client | unit | `./run-unit-tests.sh --single-file test_gaplog.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 2 | MCP-07, MCP-01 | T-02-09 | OAuth state encrypted at rest, no file store | unit + integration | `./run-unit-tests.sh --single-file test_oauth_storage.py tests/unit/mcp_server`; `./run-unit-tests.sh --emulator` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | MCP-05 | T-02-12, T-02-13 | gap tool records no identity; bad question rejected without echo | unit | `./run-unit-tests.sh --single-file test_gap_tool.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 3 | MCP-02, MCP-07 | T-02-14, T-02-12 | exactly five tools; only gap tool non-read-only; index unchanged; no question text in logs | unit | `./run-unit-tests.sh --single-file test_tool_surface.py tests/unit/mcp_server`; `test_read_only.py`; `test_log_hygiene.py` | ❌ W0 | ⬜ pending |
| 02-04-03 | 04 | 3 | MCP-03, MCP-04 | — | every item cited; explicit no_results on all content tools | unit | `./run-unit-tests.sh --single-file test_source_fields.py tests/unit/mcp_server`; `test_no_results.py` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 4 | MCP-07 | T-02-20 | 401 + resource_metadata; bot SA token accepted, forged/expired/wrong-aud rejected | unit (ASGI, fake keys) | `./run-unit-tests.sh --single-file test_auth.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-05-02 | 05 | 4 | MCP-07, MCP-01 | T-02-16, T-02-17, T-02-18, T-02-23, T-02-33 | exact-domain + verified e-mail; redirect allowlist; Host/Origin protection; no disk writes with auth on | unit (ASGI) | `./run-unit-tests.sh --single-file test_auth.py tests/unit/mcp_server`; `./run-unit-tests.sh --single test_http_transport.py test_serving_writes_nothing_to_disk tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-05-03 | 05 | 4 | MCP-07 | T-02-19, T-02-21, T-02-22 | auth off refused under K_SERVICE; secrets never in errors; per-identity rate limit | unit | `./run-unit-tests.sh --single-file test_auth_mode.py tests/unit/mcp_server`; `test_config.py`; `test_rate_limit.py` | ❌ W0 | ⬜ pending |
| 02-06-01 | 06 | 4 | MCP-08 | T-02-26 | escalation list approved by Joshua (D-17) | manual checkpoint | — (blocking) | n/a | ⬜ pending |
| 02-06-02 | 06 | 4 | MCP-08 | T-02-24, T-02-25, T-02-27 | Skill format, tool coverage vs live tools/list, refusal + gap, no contacts committed | unit (file contract) | `./run-unit-tests.sh --single-file test_skill_package.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-06-03 | 06 | 4 | MCP-08 | T-02-25 | one-page guide, three clients, no contacts | unit (file contract) | `./run-unit-tests.sh --single-file test_skill_package.py tests/unit/mcp_server` | ❌ W0 | ⬜ pending |
| 02-07-01 | 07 | 5 | MCP-01, MCP-05 | T-02-29, T-02-30, T-02-32 | real process: stateless JSON, five tools, gap in emulator; non-root image; safe startup errors | unit + integration (emulator) + image | `./run-unit-tests.sh --single-file test_main.py tests/unit/mcp_server`; `./run-unit-tests.sh --emulator`; `docker build --target mcp_server -t ai-buddy-mcp .` | ❌ W0 | ⬜ pending |
| 02-07-02 | 07 | 5 | MCP-07 | T-02-28 | no secret-named key or emulator host in `.env.example` | unit | `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit` | ✅ (extended) | ⬜ pending |
| 02-07-03 | 07 | 5 | MCP-07 | T-02-31 | live Google login, non-domain account refused | manual checkpoint | — (blocking-human; may defer to Phase 4) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is folded into the first task of each plan (tracer-first): each tracer creates its own test file before or with the code.

- [ ] `tests/unit/mcp_server/conftest.py` — synthetic fixture index (4 Italian pages, 3 Guides chunks, 1 video), `anyio_backend`, `settings`, `make_server`, `server` (02-01); `gaplog` default fake (02-04); bot key + auth settings (02-05)
- [ ] `tests/unit/mcp_server/test_http_transport.py`, `test_guides_tools.py`, `test_snapshot.py`, `test_models.py` — MCP-01..04 (02-01)
- [ ] `tests/unit/mcp_server/test_handbook_search.py`, `test_handbook_get.py`, `test_handbook_resource.py` — MCP-03/04/06 (02-02)
- [ ] `tests/integration/conftest.py`, `test_firestore_gaplog.py`, `test_firestore_oauth_store.py`; `tests/unit/mcp_server/test_gaplog.py`, `test_oauth_storage.py` — MCP-05, OAuth state (02-03)
- [ ] `docker-compose.test.yml` + `./run-unit-tests.sh --emulator` (02-03)
- [ ] `tests/unit/mcp_server/test_gap_tool.py`, `test_tool_surface.py`, `test_read_only.py`, `test_log_hygiene.py`, `test_source_fields.py`, `test_no_results.py` (02-04)
- [ ] `tests/unit/mcp_server/test_auth.py`, `test_auth_mode.py`, `test_config.py`, `test_rate_limit.py` (02-05)
- [ ] `tests/unit/mcp_server/test_skill_package.py` (02-06)
- [ ] `tests/unit/mcp_server/test_main.py`, `tests/integration/test_server_process.py` (02-07)
- [ ] Framework install: `requirements-dev.txt` gains `-r services/mcp_server/requirements.txt` after the 02-01 legitimacy checkpoint

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Package legitimacy of fastmcp, snowballstemmer, google-cloud-firestore | (supply chain) | registry trust judgment (user decision 5) | 02-01 Task 1 how-to-verify steps |
| Escalation topic -> role list | MCP-08 | content approval by Joshua (D-17) | 02-06 Task 1 options |
| Live Google login from claude.ai and Claude Code, non-domain account refused | MCP-07 | needs a public HTTPS URL, a real Google OAuth client and real accounts (user decision 4) | 02-07 Task 3 how-to-verify; may be deferred to Phase 4 with the reason recorded |
| Skill behaviour in a real Claude session (answer ordering, sensitive-topic handling) | MCP-08 | model behaviour; measured by Phase 5 EVAL-03 | backstop truth in 02-06; Phase 5 golden set |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are checkpoints with a manual protocol
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (each tracer creates its test file)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter (set by validate-phase after execution)

**Approval:** pending
