# AI Buddy

AI Buddy is an onboarding assistant that answers employees' questions about company processes, tools and culture using only official sources: the company handbook and the Guides repo. Every answer cites its source page; when no source exists it says so and logs the gap. It has three parts: a sync job that builds the search index (`index.db`) from a local handbook snapshot and a local Guides checkout, an MCP server that serves that index to Claude clients, and a Google Chat bot that answers over the same MCP tools. Milestone 1 is personal development use only.

## Repository layout

| Path | Role |
|------|------|
| `services/mcp_server` | MCP server (`buddy_mcp`): serves the published `index.db` over stateless HTTP with cited tools |
| `services/chat_bot` | Google Chat bot (`buddy_bot`): RAG workflow over the MCP tools, cites sources or logs the gap |
| `jobs/sync` | Content sync job (`buddy_sync`): builds and publishes `index.db` from the handbook and Guides |
| `jobs/eval` | Evaluation job (`buddy_eval`): golden set, recall, scoring and the Milestone 1 gate |
| `packages/buddy_core` | Shared library: index schema, writer and reader, models, storage helpers |
| `deploy/cloudrun` | Cloud Run service definitions and deploy notes |
| `deploy/k8s` | Kustomize manifests for a local kind cluster |
| `docs/` | Contracts, install guide and ADRs |
| `skills/digitiamo-buddy` | Claude Skill that teaches Claude how to use the MCP tools |
| `scripts/` | Smoke tests, lock regeneration, deploy and infra helpers |
| `tests/` | Unit and integration tests (`tests/unit`, `tests/integration`) |

Each component has its own README with setup and configuration details:
[mcp_server](services/mcp_server/README.md),
[chat_bot](services/chat_bot/README.md),
[sync](jobs/sync/README.md),
[eval](jobs/eval/README.md),
[cloudrun](deploy/cloudrun/README.md),
[k8s](deploy/k8s/README.md).

## Quick start

Everything runs in Docker; do not use the host Python.

- **Tests** (ruff, mypy, pytest with coverage, inside the test image):
  ```bash
  ./run-unit-tests.sh --all
  ```
  Other modes: `--single`, `--single-file`, `--emulator` (see the usage text in `run-unit-tests.sh`).
- **Local stack** (emulators, stub LLM, sync, MCP server, chat bot): `docker compose`, configured from `docker-compose.yml`; see [services/chat_bot/README.md](services/chat_bot/README.md). Copy `.env.example` to `.env` for secrets.
- **Evaluation gate**: Milestone 1 evaluation gate, see [jobs/eval/README.md](jobs/eval/README.md).
- **Deploy**: see [deploy/cloudrun/README.md](deploy/cloudrun/README.md).

Dependencies are pinned in hashed lock files (`requirements-dev.lock` and one `requirements.lock` per service or job), regenerated with `scripts/lock-requirements.sh`.

## Documentation

- [docs/index-format.md](docs/index-format.md): the `index.db` contract for every reader
- [docs/guides-contract.md](docs/guides-contract.md): files the sync job reads from the Guides repo
- [docs/install-guide.md](docs/install-guide.md): installing the connector and Skill in Claude (Italian)
- [docs/adr/](docs/adr/): architecture decision records
