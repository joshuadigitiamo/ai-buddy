# Phase 4: Infrastructure and CI/CD - Pattern Map

**Mapped:** 2026-11-14
**Files analyzed:** 24 new/modified
**Analogs found:** 14 / 24 (rest are greenfield infra; use 04-RESEARCH.md Patterns 2, 5, 7)

All analog paths below were checked as git-tracked (from `git ls-files`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `packages/buddy_core/buddy_core/store.py` (add `GcsArtifactStore`) | service/adapter | file-I/O | same file, `LocalDirArtifactStore` | exact |
| `tests/unit/buddy_core/test_gcs_artifact_store.py` | test | file-I/O | `tests/unit/buddy_core/test_artifact_store.py` | exact |
| `services/mcp_server/buddy_mcp/snapshot.py` (store factory) | service | file-I/O | same file `resolve_index_path` L72-80 | exact |
| `services/mcp_server/buddy_mcp/config.py` (`ARTIFACT_STORE`, `DEPLOY_ENV`, `MCP_ALLOWED_HOSTS`) | config | request-response | same file L38-107 | exact |
| `services/chat_bot/buddy_bot/config.py` (`DEPLOY_ENV`, `CHAT_API`) | config | request-response | same file L118-135 | exact |
| `services/mcp_server/buddy_mcp/server.py` (`/healthz`, allowed hosts) | controller | request-response | same file `host_kwargs` L68-86 | exact |
| `services/mcp_server/buddy_mcp/cli.py` (wire factory) | utility | request-response | same file L86-93 | exact |
| `jobs/sync/buddy_sync/cli.py` (`upload-videos`, `publish` subcommands) | controller (CLI) | batch | same file `_build_parser` L57-80, `_run` L87 | exact |
| `jobs/sync/buddy_sync/video_map.py` (GCS URLs, D-18 coverage) | transform | transform | same file | exact |
| `Dockerfile` (add `sync` stage) | config | batch | `Dockerfile` stage `mcp_server` L19-32 | exact |
| `docker-compose.yml` (replaces dev file) | config | event-driven | `docker-compose.dev.yml` + `docker-compose.test.yml` (pubsub svc) | exact |
| `tests/unit/test_compose.py` (migrated) | test | transform | `tests/unit/test_dev_compose.py` | exact |
| `tests/unit/test_cloudrun_yaml.py`, `test_workflows.py`, `test_k8s_manifests.py`, `test_workflow_paths_match_dockerfile.py` | test | transform | `tests/unit/test_dev_compose.py` (yaml.safe_load structural guard) | role-match |
| `run-unit-tests.sh` (chmod +x in index; CI entry) | config | batch | itself | exact |
| `deploy/k8s/base/*`, `overlays/dev/*`, `kind-config.yaml` | config | event-driven | `docker-compose.dev.yml` (env contract, mounts) | partial |
| `deploy/cloudrun/mcp-server.yaml`, `chat-bot.yaml` | config | request-response | `docker-compose.dev.yml` env blocks | partial |
| `.github/workflows/*.yml` | config | batch | none | none |
| `scripts/*.sh` (sync-and-publish, validate-infra, kind-*) | utility | batch | `run-unit-tests.sh` | role-match |
| `docs/adr/0001-index-handoff.md` (update) | doc | n/a | itself | exact |

## Pattern Assignments

### `GcsArtifactStore` in `packages/buddy_core/buddy_core/store.py`

**Analog:** `LocalDirArtifactStore`, store.py L1-62. Keep the 4-method Protocol (L16-25) unchanged; reuse `INDEX_NAME`, `MANIFEST_NAME` and the manifest dict from `publish` (L46-53).

Imports/constants (L3-13):
```python
import hashlib, json, os, uuid
from pathlib import Path
from typing import Final, Protocol
from buddy_core.models import IndexMeta
INDEX_NAME: Final[str] = "index.db"
MANIFEST_NAME: Final[str] = "index.manifest.json"
```
Manifest shape to copy verbatim (L46-53): keys `schema_version, build_id, content_hash, created_at_utc, sha256, size_bytes`. GCS publish: upload `index-<build_id>.db` first, then the pointer `index.manifest.json` last (RESEARCH Pattern 1). `latest_path` returns `None` when no pointer (mirrors L35-37); verify `sha256` after download. `staging_path` returns a local temp file (L39-42 pattern). Take a `BucketPort` Protocol, not `google.cloud.storage` directly, so unit tests use a fake with no network (`run-unit-tests.sh` runs `--network none`).

### `snapshot.py` store factory

**Analog:** L72-80:
```python
def resolve_index_path(artifact_dir: Path) -> Path:
    if not artifact_dir.is_dir():
        raise SnapshotError("artifact directory does not exist")
    path = LocalDirArtifactStore(artifact_dir).latest_path()
    if path is None:
        raise SnapshotError("no index.db in artifact directory")
    return path
```
Change: accept an `ArtifactStore` (built by a factory from settings), keep the same `SnapshotError` messages, keep the "never creates the directory" check for the local branch only. Call site: `buddy_mcp/cli.py` L93 `load_snapshot(resolve_index_path(settings.artifact_dir))`. Extend tests in `tests/unit/mcp_server/test_snapshot.py`.

### `McpSettings` / `BotSettings` new fields

**Analog:** `buddy_mcp/config.py` L28-107 (pydantic-settings, `Literal` fields, `field_validator` with `_split_csv` L21-25 and `NoDecode`, names-only error text):
```python
bot_sa_emails: Annotated[frozenset[str], NoDecode] = frozenset()
@field_validator("bot_sa_emails", mode="before")
@classmethod
def _parse_bot_sa_emails(cls, value): return _split_csv(value)
```
Copy that for `mcp_allowed_hosts`. `artifact_dir: Path` (L38) is required: make it optional/defaulted when `artifact_store == "gcs"`.
Guard to replace (mcp L88-91, bot `buddy_bot/config.py` L126-130):
```python
if self.auth_mode == "off" and "K_SERVICE" in os.environ:
    raise ValueError("AUTH_MODE=off is refused when K_SERVICE is set (deployed on Cloud Run)")
```
New rule: `deploy_env: Literal["local","production"] = "production"`; off/none/recording allowed only for `local`; `K_SERVICE` still forces production. Bot uses `_require(...)` helper (config.py ~L118-135) for needs-lists. Existing tests that set `AUTH_MODE=off` (`tests/integration/test_server_process.py`, `test_bot_process.py`, unit `test_auth_mode.py`, `test_config.py`) must add `DEPLOY_ENV=local`.

### `server.py` `/healthz` and `MCP_ALLOWED_HOSTS`

**Analog:** `host_kwargs` L68-86; extend `hosts` list (L75-80) with `settings.mcp_allowed_hosts`:
```python
hosts = list(_LOOPBACK_HOSTS)
if settings is not None and settings.mcp_public_base_url:
    public = urlsplit(settings.mcp_public_base_url)
    if public.hostname and public.hostname not in hosts:
        hosts.append(public.hostname)
```
Tests assert default list unchanged (see `tests/unit/mcp_server/test_http_transport.py`). `/healthz` via `@mcp.custom_route("/healthz", methods=["GET"])` in `build_server` (L33-61); no Firestore/GCS touch.

### `jobs/sync/buddy_sync/cli.py` new subcommands

**Analog:** L57-80 argparse subparsers, `_run` L87-107, `main` L139. Imports (L19-26) show real adapters are built only in cli.py (`LocalDirArtifactStore` imported L22): build `GcsArtifactStore` / uploader here only. Output rule (docstring L1-6): counts/ids only, never content. Errors: catch typed errors (`VideoMapError`, `ValidationError`) and return exit code 1 as `_run` does. Add upload via a port + fake in `tests/unit/buddy_sync/test_cli.py` style.

### `video_map.py` (D-17/D-18)

**Analog:** itself. Anti-corruption layer; contract breaks raise `VideoMapError`; "no heuristic text matching" (docstring L1-14). Constants `SECTIONS_GLOB`, `DURATIONS_RELPATH` (L26-27). Swap URL base to GCS URLs without changing the `VideoLink` model (`buddy_core/models.py`). Tests: `tests/unit/buddy_sync/test_video_map.py`, fixtures `tests/fixtures/guides_videos/`.

### `Dockerfile` `sync` stage

**Analog:** `mcp_server` stage L19-32:
```dockerfile
FROM python:3.12-slim AS mcp_server
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server
WORKDIR /app
COPY requirements.txt ./
COPY services/mcp_server/requirements.txt services/mcp_server/requirements.txt
RUN pip install -r requirements.txt -r services/mcp_server/requirements.txt
COPY packages/buddy_core packages/buddy_core
COPY services/mcp_server services/mcp_server
USER 10001
```
Sync stage differs: needs `git` (see `base` L6-8 apt block), `COPY jobs/sync jobs/sync`, new `jobs/sync/requirements.txt`, `PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync`, `CMD ["python","-m","buddy_sync"]`. `google-cloud-storage` pin goes in `services/mcp_server/requirements.txt` and `jobs/sync/requirements.txt` (SUS flag: human-verify checkpoint, see RESEARCH). Update `base` L11-12 COPY of the new requirements file too. The chat_bot stage (L37-53) is the model for copying only specific files; workflow `paths` must cover each COPY source (L48-49 `__init__.py`, `models.py`).

### `docker-compose.yml` (replaces `docker-compose.dev.yml`)

**Analogs:** `docker-compose.dev.yml` (meridian pinned build L18-30, firestore L32-39, mcp_server L41-63, chat_bot L65-99) and `docker-compose.test.yml` L14-21 for pubsub:
```yaml
pubsub:
  image: google/cloud-sdk:592.0.0-emulators
  command: gcloud beta emulators pubsub start --host-port=0.0.0.0:8085 --project=demo-ai-buddy
  healthcheck:
    test: ["CMD", "curl", "-sf", "http://localhost:8085/"]
    interval: 2s
    timeout: 3s
    retries: 45
```
Rules to keep: no `ports:` on any service; secrets only via `${VAR:?msg}` / `.env`; mcp_server gets no `env_file`; `ARTIFACT_DIR: /artifacts` read-only mount (L59-60); chat_bot `network_mode: "service:mcp_server"` + `MCP_URL=http://localhost:8000/mcp` (L82-85) unless `MCP_ALLOWED_HOSTS` is added; Meridian context SHA `cafdcf78...` (L20) should come from `deploy/meridian.version`. Add `DEPLOY_ENV: local`. Use profiles for meridian/smoke.

### `tests/unit/test_dev_compose.py` -> migrate

**Analog:** itself (L1-60): `yaml.safe_load`, `_services()`, `_environment()`, `SECRET_SUFFIXES`, `MERIDIAN_CONTEXT` regex. Update `COMPOSE_FILE`, the expected service set (L55: `{"meridian","firestore","mcp_server","chat_bot"}` adds `pubsub`, `pubsub-init`, `sync`), delete dev file in same plan. Reuse the same structure for the new Cloud Run / k8s / workflow guards (no ports, SHA-pinned actions, no secret literals, `paths` cover Dockerfile COPY sources).

### `deploy/k8s`, `deploy/cloudrun`, workflows

No in-repo analog (dirs hold only `.gitkeep`). Take env names, probes and uid from the compose files and the Dockerfile (uid 10001, ports 8000/8080); structure from RESEARCH Patterns 2, 3, 5, 7. Validation scripts model on `run-unit-tests.sh` (`set -euo pipefail`, `log()`, build then `docker run --rm`).

## Shared Patterns

### Names-only validation errors
**Source:** `buddy_mcp/config.py` L83-107. Errors list variable names, never values; `hide_input_in_errors=True` (L35). Apply to every new setting.

### Fail loud, typed errors, exit 1
**Source:** `buddy_sync/cli.py` `_run`/`main`; `buddy_mcp/cli.py` L80-88 (`logger.error("%s: %s", type(exc).__name__, exc); return 1`). Apply to publish/upload/store-load failures.

### Ports + fakes, no network in unit tests
**Source:** `buddy_bot/ports.py` (`ChatApi`, `LlmClient`), `store.py` Protocol. Apply to `BucketPort`, uploader, recording Chat adapter.

### Config-selected adapters, one image per service
**Source:** compose env blocks (dev compose L47-58, L76-90). Same image across compose/kind/Cloud Run; behaviour from env only (`ARTIFACT_STORE`, `DEPLOY_ENV`, `INTAKE`, `MCP_AUTH`).

### Secrets
Never in manifests or images; compose `${VAR:?}`; k8s Secret created imperatively; Cloud Run `secretKeyRef`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/workflows/*.yml` | config | batch | `.github/workflows/` has only `.gitkeep` |
| `deploy/k8s/**` | config | event-driven | empty dir; use KUBERNETES_GUIDE + RESEARCH Pattern 5 |
| `deploy/cloudrun/*.yaml` | config | request-response | empty dir; RESEARCH Pattern 2 |
| `deploy/compose/` stub LLM, `pubsub_init.py` | utility | event-driven | no emulator/stub code exists |
| Recording Chat adapter | service | request-response | closest is `ChatApi` port in `buddy_bot/ports.py` and `chat_api.py` `build_chat_client` |

## Metadata

**Analog search scope:** repo root, `packages/`, `services/`, `jobs/`, `tests/unit`, compose files, Dockerfile.
**Files read:** Dockerfile, both compose files, store.py, snapshot.py (L60-99), mcp config/server/cli (ranges), bot config (range), sync cli/video_map (heads), test_dev_compose.py, test_artifact_store.py (heads).
**Pattern extraction date:** 2026-11-14
