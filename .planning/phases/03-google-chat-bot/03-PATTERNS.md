# Phase 3: Google Chat Bot - Pattern Map

**Mapped:** 2026-11-07
**Files analyzed:** 27 (new) + 6 (modified)
**Analogs found:** 26 / 33. All analog paths verified tracked via `git ls-files`.

`services/chat_bot/` holds only `.gitkeep`. Everything under `buddy_bot/` is new. The file list comes from RESEARCH.md "Recommended Project Structure".

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `services/chat_bot/buddy_bot/__main__.py` | entrypoint | n/a | `services/mcp_server/buddy_mcp/__main__.py` | exact |
| `.../buddy_bot/cli.py` | composition root | batch | `services/mcp_server/buddy_mcp/cli.py` | exact |
| `.../buddy_bot/config.py` | config | n/a | `services/mcp_server/buddy_mcp/config.py` | exact |
| `.../buddy_bot/ports.py` | port | n/a | `gaplog.py` (`GapLog` Protocol) | role-match |
| `.../buddy_bot/memory.py` | adapter (Firestore + in-memory) | CRUD | `services/mcp_server/buddy_mcp/gaplog.py` | exact |
| `.../buddy_bot/mcp_client.py` | client adapter | request-response | `tests/unit/mcp_server/test_source_fields.py::_call` + `buddy_mcp/models.py` | partial |
| `.../buddy_bot/chat_api.py` | client adapter | request-response | `gaplog.py` (lazy client factory) | role-match |
| `.../buddy_bot/intake/http.py` | adapter | request-response | `buddy_mcp/auth.py`, `buddy_mcp/server.py` | partial |
| `.../buddy_bot/intake/pubsub.py` | adapter | event-driven | none | no analog |
| `.../buddy_bot/llm.py` | adapter | request-response | none (use RESEARCH Pattern 5) | no analog |
| `.../buddy_bot/service.py`, `workflow.py`, `gate.py`, `schemas.py`, `prompts.py`, `render.py`, `events.py` | service / transform | request-response | none (pure logic; RESEARCH Patterns 2-6) | no analog |
| `packages/buddy_core/buddy_core/escalation.py` + `data/escalation_topics.yaml` | utility + data | transform | `buddy_core/models.py`, `buddy_core/index_reader.py` (loader style) | role-match |
| `tests/unit/chat_bot/conftest.py` | test fixtures | n/a | `tests/unit/mcp_server/conftest.py` | exact |
| `tests/unit/chat_bot/test_log_hygiene.py` | test | n/a | `tests/unit/mcp_server/test_log_hygiene.py` | exact |
| `tests/unit/chat_bot/test_config.py` | test | n/a | `tests/unit/mcp_server/test_config.py` | exact |
| `tests/integration/test_firestore_thread_memory.py` | test | CRUD | `tests/integration/test_firestore_gaplog.py` | exact |
| `tests/integration/test_bot_process.py` | test | process | `tests/integration/test_server_process.py` | exact |
| `tests/integration/test_pubsub_intake.py` | test | event-driven | `tests/integration/conftest.py` (emulator skipif) | partial |
| escalation drift test | test | transform | none | no analog |
| MODIFY `Dockerfile`, `docker-compose.test.yml`, `pyproject.toml`, `requirements-dev.txt`, `tests/unit/test_repo_layout.py`, `run-unit-tests.sh`, `skills/digitiamo-buddy/SKILL.md` | config | n/a | themselves | n/a |
| NEW `docker-compose.dev.yml`, `services/chat_bot/requirements.txt`, `services/chat_bot/README.md` | config/docs | n/a | `docker-compose.test.yml`, `services/mcp_server/requirements.txt`, `services/mcp_server/README.md` | role-match |

## Pattern Assignments

### `buddy_bot/config.py` (config)

**Analog:** `services/mcp_server/buddy_mcp/config.py`

Settings class, lines 28-36:
```python
class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, env_ignore_empty=True, extra="ignore", hide_input_in_errors=True)
```
CSV parsing (lines 21-25, 51, 58-61). Reuse for `ALLOWED_USERS` (note it lowercases; `users/<id>` is fine):
```python
def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    return value
bot_sa_emails: Annotated[frozenset[str], NoDecode] = frozenset()
@field_validator("bot_sa_emails", mode="before")
@classmethod
def _parse_bot_sa_emails(cls, value): return _split_csv(value)
```
Cross-field guard (lines 83-107) is the template for BOT-07/BOT-08. Names only, never values; the K_SERVICE check is the D-13 mirror:
```python
@model_validator(mode="after")
def _check_auth_and_storage(self) -> McpSettings:
    if self.auth_mode == "off" and "K_SERVICE" in os.environ:
        raise ValueError("AUTH_MODE=off is refused when K_SERVICE is set (deployed on Cloud Run)")
    missing = [name for name, value in (("MCP_PUBLIC_BASE_URL", ...), ...) if value is None]
    if missing: raise ValueError(f"AUTH_MODE=on requires: {', '.join(missing)}")
```
Secrets use `SecretStr` (lines 48-49, 53); use for `THREAD_KEY_SECRET`, `ANTHROPIC_API_KEY`, `MERIDIAN_API_KEY`. Also `Field(default=5.0, gt=0)` for numeric bounds (lines 55-56); use for `CONFIDENCE_THRESHOLD`.

---

### `buddy_bot/cli.py` + `__main__.py` (composition root)

**Analog:** `services/mcp_server/buddy_mcp/cli.py`, `__main__.py`

`__main__.py` is 3 lines (copy verbatim, swap package):
```python
from buddy_mcp.cli import main
raise SystemExit(main())
```
cli.py conventions: `LOGGER_NAME`, `LOG_FORMAT`, `_EXPECTED_ERRORS` tuple, `_describe_validation_error` (lines 43-52, copy as is), `main(argv=None, *, serve=None) -> int` with injectable `serve` for tests (lines 69-83), `_run` building real adapters, lazy Firestore client via lambda (lines 94-99):
```python
gaplog = FirestoreGapLog(lambda: firestore.AsyncClient(project=project), collection=settings.gap_collection)
```
Logging must be counts/modes only (docstring lines 3-5). Note `main()` attaches and removes its own handler in `finally`.

---

### `buddy_bot/memory.py` (adapter, CRUD)

**Analog:** `services/mcp_server/buddy_mcp/gaplog.py`

Port + lazy Firestore adapter + in-memory test double, same file. Lines 76-114:
```python
class GapLog(Protocol):
    async def record(self, gap: GapRecord) -> str: ...

class FirestoreGapLog:
    def __init__(self, client_factory: Callable[[], firestore.AsyncClient], collection: str = "gaps") -> None:
        self._client_factory = client_factory
        self._client: firestore.AsyncClient | None = None
    async def record(self, gap):
        if self._client is None:
            self._client = self._client_factory()   # lazily, inside the running loop
        ref = self._client.collection(self._collection).document()
        await ref.set(gap_document(gap))

class InMemoryGapLog:
    def __init__(self) -> None:
        self.records: list[GapRecord] = []
```
Also copy: frozen slots dataclass with `.new()` validating tz-aware `now` and computing `expire_at = created_at + timedelta(...)` (lines 24-61); an explicit `*_document()` function returning the exact stored keys (lines 64-73), so a test can assert the key set (BOT-11: only `turns`, `updated_at`, `expire_at`). Use `ref = collection.document(hmac_hex)` and `set`, not `.document()` auto-id. Add a read-side `expire_at` check (README says emulator does not enforce TTL).

---

### `buddy_bot/ports.py`

**Analog:** `gaplog.py` lines 76-80 (`Protocol` with async method). Define `LlmClient`, `McpRetriever`, `ChatApi`, `ThreadMemory`, `IntakePort` the same way; fakes live next to real adapters or in tests (`InMemoryGapLog` style).

---

### `buddy_bot/mcp_client.py` (request-response)

**Analogs:** `buddy_mcp/models.py` (shapes), `tests/unit/mcp_server/test_source_fields.py::_call` (in-memory `Client(server)`), and `buddy_mcp/gap_tool.py` for the `buddy_report_gap(question, tried)` signature (line 55). Re-read `test_source_fields.py::_call` before writing; I did not excerpt it. The real contract (RESEARCH lines 424-437): import `buddy_mcp.models` (`HandbookSearchOutput`, `GuidesSearchOutput`, `GapReportOutput`, `TOOL_NAMES`, `GAP_MARKER`) and `model_validate(result.structured_content)`. One `async with Client(url, auth=...)` per run (RESEARCH Pitfall 9). The `GoogleIdTokenAuth(httpx2.Auth)` has no in-repo analog; use RESEARCH Code Examples. The server side (`ServiceAccountIdTokenVerifier`, `auth.py` lines 1-50) shows what the token must satisfy (issuer `GOOGLE_ISSUERS`, bot SA email in `BOT_SA_EMAILS`).

---

### `buddy_bot/intake/http.py`

**Analogs:** `buddy_mcp/server.py` (`host_kwargs`, Starlette/Host guard) and `buddy_mcp/auth.py` (Google issuer constants, cache TTL, module `_LOGGER = logging.getLogger("buddy_mcp.auth")`). Read `server.py` for the Starlette app pattern before writing. JWT verification itself: `google.oauth2.id_token.verify_oauth2_token` (RESEARCH Don't Hand-Roll). Tests sign JWTs with `RSAKeyPair` (see conftest below).

---

### `packages/buddy_core/buddy_core/escalation.py` + YAML (D-08)

**Analog:** `buddy_core/models.py` (pydantic/dataclass models) and `index_reader.py` (loader). Source data to migrate verbatim is `skills/digitiamo-buddy/SKILL.md` lines 79-92 ("Temi da escalare" table: columns `Tema | Referente`, 8 rows). Keep `SKILL.md` text; the drift test parses the markdown table and compares with YAML (no analog; write fresh, place in `tests/unit/buddy_core/`). Note: package data must be reachable in the `chat_bot` Docker stage, which copies `packages/buddy_core` whole (Dockerfile line 27 pattern), so `data/` ships automatically.

---

### Tests

**`tests/unit/chat_bot/conftest.py`** — analog `tests/unit/mcp_server/conftest.py`: module docstring "Synthetic fixtures only", constants (`NOW`, `BOT_EMAIL`, `GOOGLE_ISSUER`, obviously fake secrets lines 23-33), `make_page`/`make_chunk` builders, `build_server(settings, snapshot=..., gaplog=InMemoryGapLog(), auth=...)` plus `RSAKeyPair` for JWTs. Reuse by importing as `test_server_process.py` does: `from tests.unit.mcp_server.conftest import MAPPED, WEB_BASE, make_content, make_page, write_index`. Needs `anyio_backend` fixture returning "asyncio" (see `tests/integration/conftest.py` lines 16-18) and `pytestmark = pytest.mark.anyio`.

**`test_log_hygiene.py`** — analog `tests/unit/mcp_server/test_log_hygiene.py`. Sentinel pattern lines 11-30: call everything with `sentinella-...` strings, assert `"sentinella-" not in caplog.text` and in every `record.getMessage()`. Keep the companion "capture wiring" probe test (lines 33-42) so the test cannot pass vacuously. Extend sentinels to sender email, `users/` id, space and thread names.

**`test_firestore_thread_memory.py`** — analog `tests/integration/test_firestore_gaplog.py`: `pytestmark = [pytest.mark.firestore, pytest.mark.anyio, pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason=...)]`; fixtures `firestore_client_factory`, `unique_collection` (rename prefix), assert `set(data) == {...}` exact key set; identity-key regex `(?i)user|email|ip|session|client|sub` (line 22).

**`test_bot_process.py`** — analog `tests/integration/test_server_process.py`: `_free_port`, `_wait_for_port` with stderr tail on early exit, `STARTUP_TIMEOUT_SECONDS = 30`, spawn `python -m buddy_bot` with `subprocess.Popen`. Read lines 60+ for the fixture before copying.

**`test_pubsub_intake.py`** — no analog beyond the emulator skipif pattern; use `PUBSUB_EMULATOR_HOST` as the guard variable.

## Shared Patterns

### Errors name variables, never values
Source: `config.py` lines 83-107, `cli.py` lines 43-52. Apply to `BotSettings` and bot `cli.py`.

### Port plus lazy adapter plus in-memory fake
Source: `gaplog.py` lines 76-114. Apply to `ThreadMemory`, `ChatApi`, `LlmClient`, `McpRetriever`, `IntakePort`.

### No identifiers/question text in logs
Source: `cli.py` docstring lines 3-5 and `test_log_hygiene.py`. Apply to every `buddy_bot` module.

### Build wiring (modify)
- `Dockerfile` lines 5, 11, 22-31: `PYTHONPATH` in base line 5 and add `:/app/services/chat_bot`; add `COPY services/chat_bot/requirements.txt ...` next to line 11; add a `FROM python:3.12-slim AS chat_bot` stage mirroring the `mcp_server` stage (non-root `USER 10001`, `CMD ["python","-m","buddy_bot"]`). The bot stage must also get `services/mcp_server` on `PYTHONPATH` if it imports `buddy_mcp.models` (RESEARCH line 439).
- `docker-compose.test.yml`: add a `pubsub` service beside `firestore` (same image pin style, healthcheck block lines 6-10) and `depends_on` + `PUBSUB_EMULATOR_HOST` in `tests`.
- `tests/unit/test_repo_layout.py` line 74-79: add `services/chat_bot/requirements.txt` to the pinned list.
- `pyproject.toml`: add `buddy_bot` to pythonpath, mypy path/files, ruff `src`, isort `known-first-party`, coverage `source` (read the file before editing; not excerpted here).
- `requirements-dev.txt`: `-r services/chat_bot/requirements.txt`.

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `intake/pubsub.py` | event-driven adapter | No Pub/Sub code exists; use RESEARCH "Pub/Sub adapter" example |
| `llm.py` | LLM client | No Anthropic code; RESEARCH Pattern 5 |
| `workflow.py`, `gate.py`, `schemas.py`, `prompts.py`, `render.py`, `events.py`, `service.py` | pure logic | New domain; RESEARCH Patterns 2-6 and Pitfall 7 fixtures |
| escalation drift test | test | No markdown-vs-data test exists |
| `docker-compose.dev.yml` / Meridian service | config | No dev compose exists |

## Metadata

**Analog search scope:** `services/mcp_server`, `packages/buddy_core`, `jobs/sync` (file list only), `tests/`, `Dockerfile`, `docker-compose.test.yml`, `skills/`.
**Not read in detail (planner should read before implementing):** `buddy_mcp/server.py`, `test_source_fields.py`, `test_server_process.py` lines 60+, `pyproject.toml`, `run-unit-tests.sh`, `jobs/sync/buddy_sync/config.py`. RESEARCH.md lines 463-689 were not read.
**Pattern extraction date:** 2026-11-07
