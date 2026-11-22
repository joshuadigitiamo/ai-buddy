# CLAUDE.md

AI Buddy: onboarding assistant answering only from the company handbook and the Guides repo, via a sync job (`index.db`), an MCP server and a Google Chat bot. Layout and component READMEs: see `README.md`.

## Language and tooling

- Python 3.12 only (`pyproject.toml`).
- Dependencies: pip with `requirements.txt` / `requirements-dev.txt` plus per-component `requirements.txt` files.
- Hashed lock files: `requirements-dev.lock`, `services/*/requirements.lock`, `jobs/*/requirements.lock`. Never edit by hand; regenerate with `scripts/lock-requirements.sh` (Docker, needs PyPI). Images install them with `pip install --require-hashes`.
- Lint/format: ruff (config in `pyproject.toml`, line length 100). Types: mypy `strict = true`. Tests: pytest, coverage gate 80% in `--all`.
- Type hints on all public functions (mypy strict covers `tests` too).

## Always run in Docker

- Never use host Python. Tests:
  ```
  ./run-unit-tests.sh --all
  ./run-unit-tests.sh --single <test_file> <test_name> <test_directory>
  ./run-unit-tests.sh --single-file <test_file> <test_directory>
  ./run-unit-tests.sh --emulator
  ```
- `--all`: ruff check, ruff format --check, mypy, pytest with coverage. `--emulator`: Firestore and Pub/Sub emulators via `docker-compose.test.yml`, tests marked `firestore` or `pubsub`.
- Run `./run-unit-tests.sh --all` after code changes before claiming done.

## Docker Compose

- Always use project name `aibuddy`: `docker compose -p aibuddy ...`.
- Profiles in `docker-compose.yml`:
  - default: hermetic (emulators, stub LLM, sync, mcp-server, chat-bot). No real Chat API, LLM or GCP.
  - `live`: real Chat bot with Meridian (`mcp-server meridian chat-bot-live`).
  - `eval`: MLflow (127.0.0.1:5000 only), fixture index, `mcp-server-empty`, Meridian, `eval` job.
- Required shell vars: `HANDBOOK_SRC_DIR`, `GUIDES_SRC_DIR`, `REDACT_PAGE_FILES`, `THREAD_KEY_SECRET` (>= 32 chars). `eval` and `chat-bot-live` run as `HOST_UID:HOST_GID` (default 1000).
- Meridian needs `MERIDIAN_OAUTH_TOKEN` and `MERIDIAN_API_KEY` in `.env` (see `.env.example`).
- Run the `sync` service once first so the artifacts volume holds an index.
- Eval:
  ```
  docker compose -p aibuddy --profile eval run --rm eval <lint|recall|run|empty-context|gate|preflight>
  ```
  `lint` makes no model call. `recall`, `run`, `empty-context`, `gate`, `preflight` can call the LLM. Details: `jobs/eval/README.md`.

## Hard rules

- Never read or print `.env` or any secret. `.env.example` is fine to read.
- The repo is public. Anything internal or private lives only in gitignored `docs/internal/`. Never commit handbook text, handbook page ids, real names or project ids.
- No live LLM (Meridian) calls and no eval `run`/`gate` re-runs without the owner's OK.
- After an eval gate result, change no golden item, threshold, judge prompt or bot behaviour without a recorded decision (EVAL-06; see `.planning/phases/05-evaluation-and-milestone-gate/05-GAP-DECISION.md`).
- Work on `main`. No push unless asked.
- Planning lives in `.planning/` (GSD workflow).
