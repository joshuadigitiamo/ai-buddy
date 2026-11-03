# buddy_sync: content sync job

Nightly batch job that builds the AI Buddy knowledge artifact. One run reads the ClickUp handbook doc and the Guides git repository, redacts secrets and denylisted pages, resolves Guides video links, and publishes one `index.db` (SQLite with FTS5) to `ARTIFACT_DIR`. An unchanged input writes nothing, and a failed run leaves the previous `index.db` in place, so a run can always be repeated.

Everything runs in Docker. Do not run it with the host Python.

## Environment variables

Every setting comes from the environment. Pass them with `--env-file .env`. Copy `.env.example` to `.env` and fill in the values; `.env` is gitignored.

| Variable | Meaning |
|----------|---------|
| `CLICKUP_TOKEN` | ClickUp personal API token. Required by `run` and `list-pages`. |
| `CLICKUP_WORKSPACE_ID` | Numeric ClickUp workspace id. Required by `run` and `list-pages`. |
| `CLICKUP_DOC_ID` | Id of the handbook doc, as in the doc URL. |
| `CLICKUP_BASE_URL` | ClickUp API base URL. Optional, defaults to `https://api.clickup.com`. Must be https. |
| `REDACT_PAGE_IDS` | Comma-separated ids of handbook pages that are dropped entirely. `run` refuses an empty list unless `--allow-empty-denylist` is given. |
| `REDACT_EMAIL_ALLOW_DOMAINS` | Comma-separated email domains that stay readable. Other addresses are masked. |
| `GUIDES_REPO_URL` | Git URL of the Guides repository, or a local path (see the dev setup below). |
| `GUIDES_REPO_TOKEN` | Token for a private Guides repository. Optional. |
| `GUIDES_BRANCH` | Branch to index. |
| `GUIDES_CHECKOUT_DIR` | Directory where the job keeps its Guides clone. |
| `ARTIFACT_DIR` | Directory where `index.db` and `index.manifest.json` are published. |
| `HTTP_TIMEOUT_S` | Timeout in seconds for ClickUp requests. Optional. |

## Commands

Build the image once (the test image doubles as the job image):

```bash
docker build --target test -t ai-buddy-test .
```

Define a shorthand for the common flags. `run` and `list-pages` need network access; `search` and `guides-index` do not.

```bash
buddy() {
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --env-file .env \
    -v "$PWD:/app" -w /app "$@"
}
```

### `python -m buddy_sync run [--strict] [--allow-empty-denylist]`

Runs the whole sync and prints a JSON report on stdout: counts, booleans, the Guides commit, the content hash and the build id. It never prints page content or token values. Logs go to stderr.

```bash
buddy ai-buddy-test python -m buddy_sync run
buddy ai-buddy-test python -m buddy_sync run --strict
```

`--strict` makes the run fail when the committed `GUIDES_INDEX.md` in the Guides repository disagrees with the Guides headings. Without it the drift is logged as a warning and the run continues.

### `python -m buddy_sync list-pages`

Prints one line per handbook page: the page id, a tab, then the title indented by depth. Titles pass through the redactor. Pages whose id is in `REDACT_PAGE_IDS` end with `[denied]`. Page content is never printed.

```bash
buddy ai-buddy-test python -m buddy_sync list-pages
```

Use it to find the id of the Wi-Fi page: look for its title in the output, then put that id into `REDACT_PAGE_IDS` in `.env`. Run it again to confirm the page now shows `[denied]`.

### `python -m buddy_sync guides-index --checkout DIR`

Writes `DIR/GUIDES_INDEX.md` from the headings of the Guides in `DIR` and prints the path. It needs no ClickUp variables. Commit the generated file in the Guides repository whenever the Guides headings change, so `run --strict` stays green.

```bash
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/app" -v "$HOME/path/to/Guides:/guides-src" -w /app \
  ai-buddy-test python -m buddy_sync guides-index --checkout /guides-src
```

### `python -m buddy_sync search QUERY [--limit N] [--artifact-dir DIR]`

Keyword search over the published Guides chunks. One line per hit:

```
<file>:<line_start>-<line_end>  <h2> > <h3 or (intro)>  <video link or ->
```

`--artifact-dir` defaults to `ARTIFACT_DIR`, then to `artifacts`. `--limit` defaults to 5.

```bash
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp --env-file .env \
  -v "$PWD:/app" -w /app ai-buddy-test python -m buddy_sync search "chunking"
```

## Development with a local Guides checkout

Mount your local Guides clone read-only at `/guides-src` and point `GUIDES_REPO_URL` at it. The job clones from that path into `GUIDES_CHECKOUT_DIR` and never writes to the mounted directory.

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --env-file .env \
  -e GUIDES_REPO_URL=/guides-src \
  -v "$PWD:/app" -v "$HOME/path/to/Guides:/guides-src:ro" -w /app \
  ai-buddy-test python -m buddy_sync run
```

Only committed Guides content is indexed, because the job clones the repository.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | The command succeeded. For `run`, this includes a run that found nothing to change. |
| 1 | The command failed. One `ERROR` line on stderr names the cause, for example a missing variable, a ClickUp or git error, or `--strict` drift. |
| 2 | The command line is invalid (no subcommand, unknown subcommand or bad option). |

## Never commit these

`ARTIFACT_DIR` contents (`index.db`, `index.manifest.json`), the Guides checkout and `.env` hold handbook content and secrets. `artifacts/`, `*.db`, `.cache/` and `.env` are gitignored. The repository is public: do not add any of them with `git add -f`.
