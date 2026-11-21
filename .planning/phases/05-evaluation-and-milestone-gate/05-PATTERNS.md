# Phase 5: Evaluation and Milestone Gate - Pattern Map

**Mapped:** 2026-11-21
**Files analyzed:** 33 new/modified
**Analogs found:** 31 / 33

All analog paths below were taken from `git ls-files` (tracked). No handbook content is quoted. Golden items must never be excerpted here.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `jobs/eval/buddy_eval/__main__.py` | entry | request-response | `jobs/sync/buddy_sync/__main__.py` | exact |
| `jobs/eval/buddy_eval/cli.py` | CLI | batch | `jobs/sync/buddy_sync/cli.py` (`main`, `_EXPECTED_ERRORS`) | exact |
| `jobs/eval/buddy_eval/config.py` | config | request-response | `jobs/sync/buddy_sync/config.py` + `services/chat_bot/buddy_bot/config.py` | exact |
| `jobs/eval/buddy_eval/golden.py` | model/loader | file-I/O | `buddy_bot/schemas.py` (pydantic) + `buddy_sync` yaml/pydantic usage | role-match |
| `jobs/eval/buddy_eval/sources.py` | utility | transform | `buddy_core.index_reader` consumers (`buddy_sync/cli.py` `_search`) | role-match |
| `jobs/eval/buddy_eval/cache.py` | utility | file-I/O | none close (see No Analog) | none |
| `jobs/eval/buddy_eval/runner.py` | service | request-response | `services/chat_bot/buddy_bot/workflow.py` `run_workflow`; `buddy_bot/mcp_client.py` `FastMcpConnector` | role-match |
| `jobs/eval/buddy_eval/judge.py` | service | request-response | `buddy_bot/ports.py` `LlmClient` + `buddy_bot/llm.py` + `buddy_bot/prompts.py` | role-match |
| `jobs/eval/buddy_eval/scoring.py`, `gate.py`, `recall.py` | pure utility | transform | `buddy_bot/gate.py` (pure functions) | role-match |
| `jobs/eval/buddy_eval/empty_context.py`, `fixture.py` | service | batch | `tests/unit/mcp_server/conftest.py` `make_content`/`write_index` (uses `build_index`) | role-match |
| `jobs/eval/buddy_eval/tracing.py` | adapter | event-driven | none (only module importing mlflow; port per `buddy_bot/ports.py`) | none |
| `jobs/eval/buddy_eval/report.py` | utility | transform | `buddy_sync/coverage.py` `format_report` | role-match |
| `jobs/eval/requirements.txt` / `.lock` | config | n/a | `jobs/sync/requirements.txt` / `.lock` | exact |
| `Dockerfile` (new `eval` stage) | config | n/a | `sync` stage | exact |
| `scripts/lock-requirements.sh` (edit) | config | batch | itself, `compile_stage jobs/sync/...` line | exact |
| `docker-compose.yml` (`eval` profile: mlflow, eval, mcp-server-empty, eval-fixture) | config | n/a | `meridian`, `mcp-server`, `sync` services | exact |
| `deploy/compose/stub_llm.py` (judge schema branch) | utility | request-response | `_payload` in same file | exact |
| `tests/unit/buddy_eval/conftest.py` | test | n/a | `tests/unit/chat_bot/conftest.py` + `tests/unit/mcp_server/conftest.py` | exact |
| `tests/unit/buddy_eval/test_*.py` | test | n/a | `tests/unit/chat_bot/test_workflow.py`, `tests/unit/buddy_sync/test_cli.py` | role-match |
| `tests/unit/test_compose.py` (edit) | test | n/a | itself | exact |
| `tests/unit/test_dockerfile_stages.py` (edit) | test | n/a | itself | exact |
| `tests/unit/test_requirements_lock.py` (edit) | test | n/a | itself | exact |
| `tests/unit/test_repo_layout.py` (edit) | test | n/a | itself | exact |
| `tests/unit/test_workflows.py` (edit) | test | n/a | itself | exact |
| `tests/unit/test_stub_llm.py` (edit) | test | n/a | itself | exact |
| `pyproject.toml` (edit) | config | n/a | `jobs/sync` entries | exact |
| `.github/dependabot.yml`, `.github/workflows/tests.yml` (edit) | config | n/a | `/jobs/sync` pip entry | exact |
| `services/chat_bot/buddy_bot/llm.py` (optional Protocol edit, Open Q3) | adapter | n/a | itself | exact |
| `scripts/eval-smoke.sh` | script | batch | `scripts/compose-smoke.sh`, `scripts/sync-image-smoke.sh` | exact |
| `jobs/eval/README.md`, `jobs/eval/golden/guides.yaml`, `jobs/eval/fixtures/empty_context/*.md` | docs/data | n/a | `jobs/sync/README.md`; `tests/fixtures/guides_repo/` | role-match |

## Pattern Assignments

### `jobs/eval/buddy_eval/__main__.py` (entry)

**Analog:** `jobs/sync/buddy_sync/__main__.py` (all 5 lines)
```python
"""Entry point for ``python -m buddy_sync``."""

from buddy_sync.cli import main

raise SystemExit(main())
```

### `jobs/eval/buddy_eval/cli.py` (CLI, batch)

**Analog:** `jobs/sync/buddy_sync/cli.py`

**Header / logger / expected-errors pattern** (lines 1-60 region): module docstring stating "Output is limited to counts, ids ... never content" (SYNC-03; copy this posture: eval logs counts/ids only, never question or evidence text), `LOGGER_NAME: Final`, `LOG_FORMAT`, tuple `_EXPECTED_ERRORS` ending a command with one ERROR line and exit 1.

**main() pattern** (lines 297-327): returns int, 0 success / 1 reported failure / 2 bad args; argparse `SystemExit` converted to a code; `match args.command:` dispatch; `except ValidationError` printed via `_describe_validation_error`.
```python
def main(argv: Sequence[str] | None = None, *, now: NowFn | None = None, ...) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    ...
    match args.command:
        case "run": return _run(args, logger, clock)
```
Eval adaptations: subcommands `lint preflight recall run empty-context gate build-fixture`; gate returns non-zero on FAIL (assumption A5); injectable collaborators (llm factory, connector factory, tracing sink, clock) as keyword args to `main` so tests call `main([...])` with fakes (same shape as `bucket_factory`).

### `jobs/eval/buddy_eval/config.py` (config)

**Analogs:** `jobs/sync/buddy_sync/config.py` lines 1-45; `services/chat_bot/buddy_bot/config.py` lines 1-80.

**Settings pattern** (sync config.py:30-40, bot config.py:48-60):
```python
class SyncSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, env_ignore_empty=True, extra="ignore", hide_input_in_errors=True,
    )
```
Bot fields to mirror in `EvalSettings`: `llm_backend: Literal["meridian","api","vertex"]`, `llm_base_url`, `anthropic_api_key: SecretStr | None`, `meridian_api_key: SecretStr | None`, `reformulate_model="claude-haiku-5-5"`, `answer_model="claude-sonnet-5-5"`, `llm_timeout_seconds: float = Field(default=60, gt=0)`, `confidence_threshold`. Add `judge_model="claude-opus-5-5"`, `mcp_url`, `mcp_empty_url`, `artifact_dir`, golden paths, cache dir (under `docs/internal/`).
Use `_require(mode, applies=..., needs=...)` (bot config.py:27-32) for errors that name variables, never values. Copy the `_TRACING_VARIABLES = ("LANGSMITH_TRACING","LANGCHAIN_TRACING_V2")` refusal (config.py:20,162-165) so eval refuses third-party tracing. `_split_csv` helper (config.py:35-39) if needed.

### `jobs/eval/buddy_eval/runner.py` (service, request-response)

**Analogs:** `buddy_bot/workflow.py` lines 270-304 and `buddy_bot/mcp_client.py` lines 130-171.

**Predict entry** (workflow.py:292-304): `run_workflow(question, history, deps) -> BotReply`; gap is logged inside via `_log_gap`, setting `gap_reported=True` only after `tools.report_gap` returned.
```python
async def run_workflow(question: str, history: Sequence[Turn], deps: WorkflowDeps) -> BotReply:
    async with deps.mcp.session() as tools:
        context = RunContext(llm=deps.llm, tools=tools, config=deps.config, escalation=deps.escalation)
        final = await _graph().ainvoke({"question": question, "history": history}, context=context)
        ...
```
**Real MCP adapter** (mcp_client.py:151-171): `FastMcpConnector(target: str | FastMCP, *, handbook_limit=3, guides_limit=4)`; construct with the compose URL `http://mcp-server:8000/mcp`. For Recall use `handbook_limit=5, guides_limit=5` (research Recall section).
**Error handling:** catch `LlmError` (`buddy_bot/ports.py:27-37`) and `McpToolError` (mcp_client.py `_call`, lines ~110-125) per item; classify `errored`, never cache (Pitfall 8). Deps built inside the coroutine (fresh async clients per call).
Deps: `WorkflowDeps(llm=..., mcp=..., config=WorkflowConfig(reformulate_model, answer_model, confidence_threshold))` (workflow.py:56-70).

### `jobs/eval/buddy_eval/judge.py` (service, request-response)

**Analogs:** `buddy_bot/ports.py:40-46` (LlmClient Protocol), `buddy_bot/llm.py` lines 76-140, `buddy_bot/prompts.py` (`format_evidence`).
```python
class LlmClient(Protocol):
    async def structured(self, schema: type[M], *, model: str, system: str, user: str, max_tokens: int) -> M: ...
```
Judge = pydantic `JudgeVerdict` passed to `structured(...)`; the client appends the JSON schema to `system` (`_json_instruction`, llm.py:62-66), validates, and repairs once, raising only `LlmError` subclasses. Fence answer and sources as data, mirror `prompts.format_evidence` `<fonte id=... >` blocks. Build the client through `build_llm_client` (llm.py:118-140); see `llm.py` Open Question 3 for the settings Protocol edit.
Hygiene copy: `_repair_note` and `raise ... from None` keep model output out of tracebacks (llm.py:68-74, 100).

### `jobs/eval/buddy_eval/scoring.py`, `gate.py`, `recall.py` (pure functions)

**Analog:** `services/chat_bot/buddy_bot/gate.py` (47 lines: `check`, `cited_sources`), the repo's pure-function style: typed, no I/O, table-testable. `BotReply` fields (`schemas.py:78-83`): `kind`, `answer`, `sources: list[Evidence]`, `referente`, `gap_reported`, `gate_reason`. `Evidence` (`schemas.py:8-19`) has `source_url`, `kind`, `title`, `text`. Keep frozen dataclasses/pydantic result types; no mlflow imports.
Recall reformulation: call the node `reformulate` directly with `Runtime(context=RunContext(llm=..., tools=None, config=cfg))` (research Pattern 1).

### `jobs/eval/buddy_eval/golden.py` (model + loader, file-I/O)

**Analog:** `buddy_bot/schemas.py` pydantic models; research Don't-Hand-Roll: `yaml.safe_load` + pydantic `model_config = ConfigDict(extra="forbid")` (PyYAML 6.0.3 and pydantic already pinned). Items whose `expected_sources` contain `handbook://` live only in `docs/internal/golden-handbook.yaml`. Loader warns loudly if the private file is missing (log line via the `LOGGER_NAME` pattern).

### `jobs/eval/buddy_eval/fixture.py` and `empty_context.py`

**Analog:** `tests/unit/mcp_server/conftest.py` lines 1-140.
```python
def make_content(*, pages=None, chunks=None, videos=None) -> IndexContent:
    return IndexContent(handbook=..., chunks=..., videos=..., source_doc_id="handbook-local-synthetic",
        guides_commit_sha=SHA, pipeline_version="test-1", redaction_version="test-1")

def write_index(directory: Path, content: IndexContent) -> Path:
    path = directory / "index.db"
    build_index(content, path, now=NOW)
```
Imports: `from buddy_core.index_writer import build_index`; `from buddy_core.models import GuideChunk, HandbookPage, IndexContent, VideoLink, make_chunk_key`. `make_page` / `make_chunk` constructors (lines 60-100) show required fields (`url=f"handbook://{page_id}"`, `content_hash`, `chunk_key=make_chunk_key(file,h2,h3,part_index,occurrence)`). Fixture content must be vocabulary-disjoint (Pitfall 10) and synthetic.
Index reading for source resolution: `buddy_core.index_reader.open_index(...)`, `.meta`, `.guide_chunks()`.

### `jobs/eval/buddy_eval/report.py`

**Analog:** `jobs/sync/buddy_sync/coverage.py` `format_report` (console table from counts, prints no content). JSON artifact goes under `docs/internal/` (gitignored).

### `jobs/eval/requirements.txt` and `requirements.lock`

**Analog:** `jobs/sync/requirements.txt` (full file):
```text
# Sync job runtime dependencies (Phase 4). The version below is the one approved at the 04-01
# legitimacy gate; ...
google-cloud-storage==3.17.1  # shared pin; owner: services/mcp_server/requirements.txt
```
New file declares `mlflow-skinny==3.18.0`, `pandas==3.1.1`, with a comment naming the approving checkpoint (both SUS: `checkpoint:human-verify` before install). Lock header is added by `add_header` in `scripts/lock-requirements.sh` (do not hand-edit). Add `-r jobs/eval/requirements.txt` to `requirements-dev.txt` (see how `jobs/sync/requirements.txt` is referenced by `DEV_INPUTS` in `tests/unit/test_requirements_lock.py:36-42`).

### `scripts/lock-requirements.sh` (edit)

**Analog:** its own last `compile_stage` line (line ~67):
```bash
compile_stage jobs/sync/requirements.lock requirements.txt jobs/sync/requirements.txt
```
Add `compile_stage jobs/eval/requirements.lock requirements.txt services/chat_bot/requirements.txt jobs/eval/requirements.txt` (the eval stage also needs the bot deps). Update the header comment and the log lines "four locks"/"three stage locks". Expect the cachetools/python-multipart moves in other locks.

### `Dockerfile` (new `eval` stage)

**Analog:** `sync` stage (final stage of the file). Pattern to copy:
```dockerfile
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS sync
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=...
RUN apt-get update && apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY jobs/sync/requirements.lock jobs/sync/requirements.lock
RUN pip install --require-hashes -r jobs/sync/requirements.lock
COPY packages/buddy_core packages/buddy_core
COPY jobs/sync jobs/sync
USER 10001
ENTRYPOINT ["python", "-m", "buddy_sync"]
CMD ["run"]
```
Eval stage differences: `PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server:/app/services/chat_bot:/app/jobs/eval`; `LANGSMITH_TRACING=false` and add MLflow env (`MLFLOW_DISABLE_TELEMETRY=true`, `GIT_PYTHON_REFRESH=quiet`); no git needed (do not install it); copy only `buddy_mcp/__init__.py` and `models.py` from the server exactly like the `chat_bot` stage; `COPY services/chat_bot/buddy_bot`; `COPY jobs/eval jobs/eval`; `USER 10001`; `ENTRYPOINT ["python","-m","buddy_eval"]`. Also extend `base` stage `PYTHONPATH` with `/app/jobs/eval`. Do not COPY `docs`, `artifacts`, `.cache` (private-prefix guard). Eval cache/report dir must be writable by uid 10001 or the service runs with `user: ${HOST_UID}` like `chat-bot-live`.

### `docker-compose.yml` (eval profile)

**Analogs:** `meridian` (profile + `[live]`), `mcp-server` (env/healthcheck/volumes), `sync` (long-syntax read-only binds).

**Profile pattern** (meridian): `profiles: [live]`. Change meridian to `profiles: [live, eval]` and add `MERIDIAN_OPUS_MODEL: opus` for eval (Open Q1). New services: `mlflow`, `eval`, `mcp-server-empty`, `eval-fixture` (one-shot building the fixture volume via `python -m buddy_eval build-fixture`), all `profiles: [eval]`.
**mcp-server-empty:** copy the whole `mcp-server` block, but `volumes: - eval-empty:/artifacts:ro`; keep `MCP_ALLOWED_HOSTS: mcp-server-empty`; same Firestore gap collection override if gaps must be separated (`GAP_COLLECTION`); `depends_on: eval-fixture: condition: service_completed_successfully`, `firestore: service_healthy`.
**Healthcheck pattern** (mcp-server): python urllib probe, `interval: 3s, timeout: 5s, retries: 30`; MLflow healthcheck hits an API path, not `/health` (Pitfall 3).
**Read-only bind** (sync):
```yaml
- type: bind
  source: ${HANDBOOK_SRC_DIR:?...}
  target: /handbook
  read_only: true
```
But profile services must require nothing at load time (`test_profile_services_require_nothing_at_load_time`, test_compose.py:288): use `${VAR:-default}`, never `:?`, inside the eval services.
**Secrets:** only `${...}` interpolation (`MERIDIAN_API_KEY: ${MERIDIAN_API_KEY:-}`); eval must not get `THREAD_KEY_SECRET`. `LANGSMITH_TRACING: "false"`.
**LLM wiring:** `LLM_BACKEND: meridian`, `LLM_BASE_URL: http://meridian:3456`, `MCP_URL: http://mcp-server:8000/mcp` (as `chat-bot-live`).
**mlflow service:** use the YAML in RESEARCH.md "Compose service for MLflow" (digest-pinned image, `127.0.0.1:5000:5000`, `--allowed-hosts`, `cap_drop`, volume `mlflow-data`). Add volumes `eval-empty:` and `mlflow-data:` to the `volumes:` block. Update the file header comment ("No service publishes a port to the host") to except mlflow loopback.

### `deploy/compose/stub_llm.py` (judge schema branch)

**Analog:** `_payload` (lines 85-108): add a title branch for the judge schema (`JudgeVerdict`), returning a deterministic object (all facts present, no invented claims). Unknown titles currently return 400 (lines 126-130); keep that behavior for others. Log counts only (BOT-11 posture, module docstring).

### `tests/unit/buddy_eval/conftest.py`

**Analogs:** `tests/unit/chat_bot/conftest.py` lines 1-100 and `tests/unit/mcp_server/conftest.py`.
Imports to copy:
```python
from tests.unit.mcp_server.conftest import NOW, WEB_BASE, make_content, make_page, write_index
from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps
from buddy_mcp.server import build_server
from buddy_mcp.gaplog import InMemoryGapLog
```
Reuse `FakeLlm` (script per schema; exhausted queue raises `LlmOutputError`; `calls` recorded) by importing from `tests.unit.chat_bot.conftest` (or a shared helper) and `REFORMULATION`, `GOOD_DRAFT`. In-process connector: `FastMcpConnector(build_server(...))` over `write_index(tmp, make_content())`; keep on one event loop (anyio). Synthetic data only; no handbook text. Fake tracing sink replaces `tracing.py`.

### `tests/unit/buddy_eval/test_*.py`

**Analogs:** `tests/unit/chat_bot/test_workflow.py` (workflow with FakeLlm + in-process MCP), `tests/unit/buddy_sync/test_cli.py` (call `main([...])`, assert exit codes and output hygiene), `tests/unit/chat_bot/test_log_hygiene.py` (assert no question text in logs). Test-name convention: long descriptive `test_<behavior>` names; `@pytest.mark.anyio` for async. Structure and file names follow research Validation map (`test_golden.py`, `test_recall.py`, `test_scoring.py`, `test_judge.py`, `test_cache.py`, `test_runner.py`, `test_empty_context.py`, `test_gate.py`).

### Edits to structural tests (exact hard-coded shapes to update)

- `tests/unit/test_compose.py`: `HERMETIC_SERVICES` (stays the 7, line 25-33); `LIVE_SERVICES` (line 34); `test_profile_live_adds_exactly_meridian_and_the_live_bot` (line 79) and `test_no_service_publishes_a_port...` (line 86-89: `assert "ports" not in service`) must allow only mlflow's `127.0.0.1:5000:5000`; `test_meridian_*` assume `profiles == ["live"]`; add eval-profile structural tests in the same style (`_services()`, `_profiles()`, `_environment()` helpers).
- `tests/unit/test_dockerfile_stages.py`: `RUNTIME_STAGES` (line 9), `STAGE_LOCK` (line 15), `test_every_stage_exists` (line 67-68: `["base","test","mcp_server","chat_bot","sync"]`), `PINNED_FROM` stage alternation (line 71), add an `EVAL_COPY_SOURCES` test mirroring `SYNC_COPY_SOURCES`/`test_sync_stage_copies_exactly_its_sources` (line 145), `PIN_FILES` (line 24), `test_test_image_installs_the_sync_requirements` (line 202).
- `tests/unit/test_requirements_lock.py`: add `"jobs/eval/requirements.lock": ("requirements.txt","services/chat_bot/requirements.txt","jobs/eval/requirements.txt")` to `STAGE_LOCKS` (lines 20-30) and `jobs/eval/requirements.txt` to `DEV_INPUTS` (lines 31-37).
- `tests/unit/test_repo_layout.py`: add `jobs/eval` to `D11_PATHS` (lines 10-19); `GITIGNORE_REQUIRED` (lines 84-90) already covers `docs/internal/`; add the "committed golden has no `handbook://`/`clickup`" test in this file's style.
- `tests/unit/test_workflows.py`: `STAGE_WORKFLOWS` (line 28, `sync.yml` precedent) only if an eval workflow is added (not planned: eval is not in CI); dependabot set must gain `("pip", "/jobs/eval")` if the dependabot entry is added; `.github/workflows/tests.yml` paths gain `jobs/eval/**`. Pitfall 12: edits under `services/chat_bot` trigger the chat-bot workflow.
- `tests/unit/test_stub_llm.py`: mirror `test_each_workflow_schema_gets_one_text_block_the_real_class_accepts` (line 88) for the judge schema.
- `pyproject.toml`: add `jobs/eval` next to `jobs/sync` in `pytest.pythonpath` (line 8), `coverage.run.source` `buddy_eval` (line 17), `mypy_path` (line 23), mypy `files` `jobs/eval/buddy_eval`, ruff `src` (line 58), isort `known-first-party` (line 66).
- `.github/dependabot.yml`: copy the last block (`package-ecosystem: pip`, `directory: /jobs/sync`, weekly) for `/jobs/eval`.

### `scripts/eval-smoke.sh`

**Analog:** `scripts/compose-smoke.sh` lines 1-50: `set -euo pipefail`, `SCRIPT_DIR`/`ROOT_DIR`, `log()` helper, `PROJECT_NAME`, `compose=(docker compose -p ... -f ...)`, `cleanup` trap with `down -v --remove-orphans`, `mktemp -d` WORK_DIR, fixture Guides git repo built from `tests/fixtures/guides_repo`, `HANDBOOK_SRC_DIR=tests/fixtures/handbook`, random never-printed secrets, bounded `SMOKE_TIMEOUT_SECONDS` polling. Also see `test_smoke_script_is_executable_and_bounded` (test_compose.py:310) and extend it to the new script. Uses `stub-llm` (hermetic), not Meridian. Assert trace count == item count via MLflow REST.

## Shared Patterns

### Ports and adapters
**Source:** `services/chat_bot/buddy_bot/ports.py`. Protocol per external system; eval defines a `TraceSink` Protocol and a fake; `tracing.py` is the only mlflow importer. The `chat_bot` image must stay mlflow-free (D-18; existing `test_chat_bot_stage_disables_tracing`).

### Output and error hygiene (public repo + private data)
**Source:** `buddy_sync/cli.py` docstring (counts/ids only), `buddy_bot/llm.py:68-74,100` (`from None`, error names the schema/loc, never the text), `buddy_bot/config.py` `_require` (names variables, never values), `hide_input_in_errors=True`. Apply to every eval module: logs never contain questions, answers, or evidence text; judge rationale goes to the MLflow trace and `docs/internal/` report only.

### Settings
**Source:** `jobs/sync/buddy_sync/config.py:30-40` `SettingsConfigDict(case_sensitive=False, env_ignore_empty=True, extra="ignore", hide_input_in_errors=True)`.

### Docker everything
**Source:** `run-unit-tests.sh` (`--all`, `--single-file <file> <dir>`, `--network none` for unit suite) and CLAUDE.md. Eval unit tests stay offline; MLflow/Meridian only in smoke/live checkpoints.

### Hashed locks and legitimacy gate
**Source:** `scripts/lock-requirements.sh` + `tests/unit/test_requirements_lock.py` (`ENTRY`, `HASH` regexes). New pins each need a `checkpoint:human-verify` plan task.

### Compose structure guards
**Source:** `tests/unit/test_compose.py` helpers `_services`, `_profiles`, `_environment`, `_depends_on`; rules: no `:?` in profile services, secrets only by `${...}`, one-shots `restart: "no"`, artifacts mounted `:ro` for readers.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `jobs/eval/buddy_eval/cache.py` | utility | file-I/O | No JSON result cache exists in the repo; use research Pitfall 9 for the key ingredients and namespaces (`reformulation`, `outcome`, `verdict`); atomic write, never cache `errored`; store under gitignored `docs/internal/` |
| `jobs/eval/buddy_eval/tracing.py` | adapter | event-driven | No tracing code in the repo (the bot disables it); use RESEARCH.md Pattern 2 executed example and env list under the MLflow compose service |

## Metadata

**Analog search scope:** `jobs/sync`, `services/chat_bot`, `services/mcp_server` (via tests), `deploy/compose`, `docker-compose.yml`, `Dockerfile`, `scripts/`, `tests/unit/**` structural tests, `pyproject.toml`, `.github/`
**Files scanned:** about 45 (read in part)
**Pattern extraction date:** 2026-11-21
