# Phase 2: MCP Server and Skill - Pattern Map

**Mapped:** 2026-11-06
**Files analyzed:** 22 (new/modified)
**Analogs found:** 15 / 22 (all analogs are git-tracked source; the Phase 2 server is greenfield, so server-library glue has no analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `services/mcp_server/buddy_mcp/__init__.py` | package | - | `jobs/sync/buddy_sync/__init__.py` | exact |
| `services/mcp_server/buddy_mcp/__main__.py` | entry | request-response | `jobs/sync/buddy_sync/__main__.py` + `cli.py` (only place real adapters are built) | role |
| `.../config.py` (McpSettings) | config | env | `jobs/sync/buddy_sync/config.py` | exact |
| `.../snapshot.py` (IndexSnapshot, handbook FTS) | service | batch load + read | `packages/buddy_core/buddy_core/index_reader.py` | role |
| `.../stemming.py` | utility | transform | `to_match_query` in `index_reader.py` L26-36 | partial |
| `.../models.py` (output contract) | model | transform | `packages/buddy_core/buddy_core/models.py` | role |
| `.../gaplog.py` (GapLog port + Firestore + InMemory) | port/adapter | CRUD (write) | `packages/buddy_core/buddy_core/store.py` | exact (pattern) |
| `.../tools.py` | controller | request-response | none | no analog |
| `.../auth.py` | middleware | request-response | none | no analog |
| `.../server.py` | composition root | - | `jobs/sync/buddy_sync/cli.py` | partial |
| `services/mcp_server/requirements.txt` | config | - | `requirements.txt` (root) | exact |
| `Dockerfile` (modify) | config | - | itself, L1-13 | exact |
| `pyproject.toml` (modify) | config | - | itself | exact |
| `.env.example` (modify) | config | - | itself | exact |
| `run-unit-tests.sh` (add `--emulator`) | config | - | itself | exact |
| `docker-compose.test.yml` | config | - | none | no analog |
| `tests/unit/mcp_server/conftest.py` | test | - | `tests/unit/buddy_core/conftest.py` | exact |
| `tests/unit/mcp_server/test_gaplog*.py` | test | CRUD | `tests/unit/buddy_core/test_artifact_store.py` | role |
| `tests/unit/mcp_server/test_config.py` | test | - | `tests/unit/buddy_sync/test_config.py` | exact |
| `tests/unit/test_repo_layout.py` (modify) | test | - | itself | exact |
| `skills/digitiamo-buddy/SKILL.md` | doc | - | none | no analog |
| `docs/install-guide.md` | doc | - | `docs/index-format.md` / `docs/guides-contract.md` | partial |

## Pattern Assignments

### `config.py` (config) - analog `jobs/sync/buddy_sync/config.py`

**Imports / class shape** (L8-37):
```python
from __future__ import annotations
from pathlib import Path
from typing import Annotated, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

class SyncSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )
    artifact_dir: Path
    redact_page_files: Annotated[frozenset[str], NoDecode] = frozenset()
```
**CSV env splitting** (L22-26, L47-50): `_split_csv` helper plus `@field_validator(..., mode="before")` with `NoDecode`. Reuse for `BOT_SA_EMAILS`.
**Error rule** (L55-58): raise `ValueError("<field> must ...")` with no value echoed; `hide_input_in_errors=True` keeps values out. Apply the same to `GOOGLE_CLIENT_SECRET`, `OAUTH_JWT_SIGNING_KEY`.
**Add:** `model_validator(mode="after")` for the D-13 guard (`auth_mode == "off"` and `os.environ.get("K_SERVICE")` -> `ValueError`, message names variables only). Put in settings so `__main__` and tests share it (Pitfall 12). Use `Literal["on","off"]` for `AUTH_MODE`, `Literal["memory","firestore"]` for `OAUTH_STORAGE` (no file option).

### `gaplog.py` (port + adapter) - analog `packages/buddy_core/buddy_core/store.py`

**Port as Protocol, adapter beside it** (L1-37):
```python
from typing import Final, Protocol

class ArtifactStore(Protocol):
    """Where a published index artifact lives; adapters hide the location."""
    def latest_path(self) -> Path | None: ...

class LocalDirArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root
```
Copy: `class GapLog(Protocol): async def record(self, gap: GapRecord) -> str: ...`; `FirestoreGapLog(client, collection="gaps")`; `InMemoryGapLog` fake (like the local-dir adapter, single small class, docstring cites decision id e.g. "(D-15)"). Module docstring style: one line with decision id.
**Server must only call `latest_path()`** (L35-37). Never `staging_path()` (L39-42 deletes tmp files) and note the constructor does `root.mkdir` (L33): in the server, check `artifact_dir` exists first, or accept the mkdir; fail fast when `latest_path()` is None.

### `snapshot.py` (cold-start load) - analog `index_reader.py`

Reuse the API as listed in RESEARCH "Cold-start snapshot" (`open_index`, `load_handbook`, `guide_chunks`, `video_links`, `search_guides`, `meta`). Do not re-implement SQL.
**FTS query builder to reuse** (`index_reader.py` L26-36):
```python
def to_match_query(query: str) -> str | None:
    tokens = [t for t in query.replace("\x00", " ").split() if any(ch.isalnum() for ch in t)]
    if not tokens:
        return None
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
```
Pass stemmed tokens through it; a `None` result means `status: "no_results"`. Bind the result as a `?` parameter, never format into SQL. Mirror the Guides FTS tokenizer `unicode61 remove_diacritics 2`.
Errors to surface at startup: `IndexFormatError`, `IndexVersionError`, `FileNotFoundError` (see `cli.py` which imports `IndexFormatError, open_index` L19; read it for how errors map to exit codes before copying).

### `__main__.py` / `server.py` - analog `jobs/sync/buddy_sync/__main__.py`, `cli.py`

```python
"""Entry point for ``python -m buddy_sync``."""
from buddy_sync.cli import main
raise SystemExit(main())
```
`cli.py` docstring (L1-6) states it "is the only place real adapters are built" and output never prints content (SYNC-03). Copy that rule: `build_server(settings, *, gaplog, store)` takes adapters as arguments (tests inject fakes); only `__main__`/`build_app()` constructs `FirestoreGapLog` and `LocalDirArtifactStore`. Import style: `from pydantic import ValidationError` + catch settings errors, print variable names only.

### `models.py` (output contract) - analog `buddy_core/models.py`

Fields consumed: `HandbookPage.revision_date_iso`, `GuideChunk.chunk_key/file/line_start/line_end`, `video_link(VideoLink)`, `IndexMeta.build_id/guides_commit_sha/created_at_utc`. Output models are new pydantic `BaseModel`s (RESEARCH Pattern 2); keep field names stable (D-06 costly reversibility). Guides citation snippet in RESEARCH "Guides citation".

### Tests - analogs

- `tests/unit/buddy_core/conftest.py` L1-40: synthetic-content helpers (`_make_page`, `_make_guide_chunk`, `revision_date_iso="2023-11-14"`, `https://docs.example.invalid/...`), no real ids or handbook text. Build the server fixture index from these via `build_index(content, path, now=NOW)`.
- `tests/unit/buddy_core/test_artifact_store.py` L1-24: helper `_publish(store, content)` and fixed `NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)`; use the same style for GapLog fake vs Firestore adapter contract tests (same assertions run against both).
- `tests/unit/buddy_sync/test_config.py`: settings-error tests (assert error text names variable, not value). Copy for D-13 test.
- `tests/unit/test_repo_layout.py` L1-30: `D11_PATHS`, `CONTRACT_KEYS` set of env names in `.env.example`; add new keys (`AUTH_MODE`, `GAP_TTL_DAYS`, etc.) and keep "no secrets in `.env.example`" hygiene check passing. Also asserts `services/mcp_server` exists (L10): `.gitkeep` can be removed once the package exists; check that test first.
- Async tests: `@pytest.mark.anyio` + `anyio_backend` fixture (RESEARCH), `--import-mode=importlib` is already in `pyproject.toml` L10.

### Build/config files to modify

**`Dockerfile`** (L5, L10): `PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync` -> append `:/app/services/mcp_server`; `COPY requirements.txt requirements-dev.txt ./` -> also copy `services/mcp_server/requirements.txt` (preserve the path since `requirements-dev.txt` will `-r` it). Add own stage for the server per CONTEXT (`FROM base AS mcp_server`).
**`pyproject.toml`**: `pythonpath` (L8), coverage `source` (L13), mypy `mypy_path` (L19) and `files` (L20), ruff `src` (L27), isort `known-first-party` (L35): add `services/mcp_server` / `buddy_mcp`. Add pytest marker `firestore`.
**`run-unit-tests.sh`**: copy `run_in_container` (L43-59) conventions (`--network none`, `--user`, `HOME=/tmp`, cache dirs under /tmp). New `--emulator` mode must use compose (network needed to reach the emulator), same `log()` / `set -euo pipefail` / `usage()` (L9-22). Add to `usage` and the header comment.
**`.env.example`**: header "Example values only. No variable here is a secret." Placeholders only; add `MCP_ARTIFACT_DIR` (or reuse `ARTIFACT_DIR`), `AUTH_MODE`, rate-limit and TTL vars; secrets (Google client secret, JWT key) are documented as required but not given values.

## Shared Patterns

### Config errors never echo values
**Source:** `jobs/sync/buddy_sync/config.py` L32-37, L55-58. **Apply to:** `McpSettings`, all validators.

### Ports + single adapter, adapters built only at the composition root
**Source:** `packages/buddy_core/buddy_core/store.py` L16-37; `jobs/sync/buddy_sync/cli.py` docstring. **Apply to:** `GapLog`, server build.

### Safe FTS5 queries
**Source:** `index_reader.py` `to_match_query` L26-36. **Apply to:** `handbook_search`.

### Public-repo hygiene
**Source:** `tests/conftest.py`, `tests/unit/test_repo_layout.py`. Synthetic fixtures only (`*.invalid` URLs, "Synthetic body"); no employee names; skill role map has roles only (D-16).

### Quality gates
`ruff check .`, `ruff format --check .`, `mypy` (strict, pydantic plugin), `pytest --cov` via `./run-unit-tests.sh --all`; line length 100; type hints on all public functions.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `buddy_mcp/tools.py` | controller | request-response | No server/tool code exists; use RESEARCH Patterns 1, 2, "Rate limit keyed by identity" and the Guides MCP_SERVERS_GUIDE §5, §20 |
| `buddy_mcp/auth.py` | middleware | request-response | No auth code exists; use RESEARCH Pattern 3 plus Pitfalls 3-5 (MultiAuth scopes, domain check, token cache) |
| `buddy_mcp/stemming.py` | utility | transform | Only `to_match_query` is close; use RESEARCH "Handbook FTS" and Pitfall 8 |
| `docker-compose.test.yml` | config | - | No compose file; use RESEARCH Environment Availability (emulator image and start command) |
| `skills/digitiamo-buddy/SKILL.md` | doc | - | No skills in repo; use RESEARCH "Skill constraints" (frontmatter keys, description <= 200 chars, English body with Italian templates) |
| `docs/install-guide.md` | doc | - | Only format-level analogs (`docs/index-format.md`); use RESEARCH install commands |

## Metadata

**Analog search scope:** `git ls-files` for the whole repo (non-planning), read in full: `store.py`, `config.py` (L1-90), `index_reader.py` (`to_match_query`), `__main__.py`, `cli.py` header, `Dockerfile`, `pyproject.toml`, `run-unit-tests.sh` (L1-70), test conftest/artifact-store/repo-layout heads, `.env.example`.
**Tracked check:** all analogs are in `git ls-files` output; none is a gitignored mirror.
**Not read:** `models.py`, `index_reader.py` beyond `to_match_query`, `tests/unit/buddy_sync/test_config.py` bodies, RESEARCH lines 511-605 (validation map); planner should read RESEARCH tail for the requirement-to-test map.
**Pattern extraction date:** 2026-11-06
