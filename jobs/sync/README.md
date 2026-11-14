# buddy_sync: content sync job

Batch job, run on demand from the developer laptop (there is no schedule and no Cloud Run job), that builds the AI Buddy knowledge artifact and publishes it to the private bucket the hosted MCP server reads. One run reads the local handbook folder (`HANDBOOK_DIR`, mounted read-only) and the Guides git repository (the local checkout, mounted read-only and cloned into `GUIDES_CHECKOUT_DIR`), redacts secrets and denylisted pages, resolves Guides video links, and publishes one `index.db` (SQLite with FTS5) to `ARTIFACT_DIR`. An unchanged input writes nothing, and a failed run leaves the previous `index.db` in place, so a run can always be repeated.

No variable is secret, and `run` needs no network: both sources are local directories. Only `publish` talks to the network, and it needs Application Default Credentials (see "Publish to the bucket").

Everything runs in Docker. Do not run it with the host Python.

## Environment variables

Every setting comes from the environment. Pass them with `--env-file .env`. Copy `.env.example` to `.env`; `.env` is gitignored. The example values already match the mounts used below.

| Variable | Meaning |
|----------|---------|
| `HANDBOOK_DIR` | Directory of handbook page files (see "Handbook folder"). Required. Mount it read-only. |
| `REDACT_PAGE_FILES` | Comma-separated file names of handbook pages that are dropped entirely, for example the file name of the Wi-Fi page. Each name must be a bare `*.md` file name and must name an existing file in `HANDBOOK_DIR`; a listed file is skipped before it is read. `run` refuses an empty list unless `--allow-empty-denylist` is given. |
| `REDACT_EMAIL_ALLOW_DOMAINS` | Comma-separated email domains that stay readable. Other addresses are masked. Optional, defaults to `digitiamo.com`. |
| `GUIDES_REPO_URL` | Git URL of the Guides repository, or a local path such as `/guides-src` (the read-only mount). Required. |
| `GUIDES_BRANCH` | Branch to index. Optional, defaults to `master`. |
| `GUIDES_CHECKOUT_DIR` | Directory where the job keeps its Guides clone. Required. |
| `ARTIFACT_DIR` | Directory where `index.db` and `index.manifest.json` are published. Required. |
| `ARTIFACT_BUCKET` | Name of the private bucket that receives the index. Used by `publish` only, required there. Lowercase bucket name; the convention is `<project id>-ai-buddy-index`. |
| `ARTIFACT_PREFIX` | Object prefix inside the bucket. Used by `publish` only, optional, empty by default. Lowercase segments each ending with `/`, for example `index/`. The server must be configured with the same bucket and prefix. |

If you still have an older `.env` that holds task-tracker variables or an API token, delete those lines (or the file) and revoke that token in the tracker. The job never reads them, and nobody needs to open `.env` to do this.

## Handbook folder

The handbook is a folder of Markdown files, one file per page, named `NN-slug.md` (for example `07-some-page.md`). Each file starts with YAML front matter between two `---` lines:

| Key | Rule |
|-----|------|
| `title` | Required, non-empty text. |
| `last_updated` | Required. A YAML date (`2026-11-03`), or the export form `YYYY-MM-DD (date_edited YYYY-MM-DD)`, in which case the `date_edited` date is the revision date. |
| `date_created` | Optional date. |

Any other key is legacy export metadata: it is ignored and never stored. The page id is the file name without `.md`, and the citation for a page is `handbook://<page id>`. The Phase 2 server resolves that URI.

- To change a page, edit its file and its `last_updated`. A page is re-indexed only when its revision date or its redacted content changes; a changed file modification time alone does nothing.
- To remove a page, delete its file.
- To hide a page, add its file name to `REDACT_PAGE_FILES`.

In this repository the folder is `docs/research/handbook-raw/` (23 files). It is gitignored. The repository is public, so never commit it.

## Commands

Build the image once (the test image doubles as the job image):

```bash
docker build --target test -t ai-buddy-test .
```

Define a shorthand for the common flags. It runs with no network, mounts the handbook and the Guides checkout read-only, and mounts the repo at `/app` (the clone and the artifact are written under it).

```bash
buddy() {
  docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp --env-file .env \
    -v "$PWD:/app" \
    -v "$PWD/docs/research/handbook-raw:/handbook:ro" \
    -v "$HOME/Desktop/WORK/Guides:/guides-src:ro" \
    -w /app "$@"
}
```

### `python -m buddy_sync run [--strict] [--allow-empty-denylist]`

Runs the whole sync and prints a JSON report on stdout: counts, booleans, the Guides commit, the content hash and the build id. It never prints page content. Logs go to stderr.

```bash
buddy ai-buddy-test python -m buddy_sync run
buddy ai-buddy-test python -m buddy_sync run --strict
```

`--strict` makes the run fail when the committed `GUIDES_INDEX.md` in the Guides repository disagrees with the Guides headings. Without it the drift is logged as a warning and the run continues.

Only committed Guides content is indexed, because the job clones the repository. Uncommitted edits in the mounted Guides folder are not seen.

### `python -m buddy_sync guides-index --checkout DIR`

Writes `DIR/GUIDES_INDEX.md` from the headings of the Guides in `DIR` and prints the path. It reads no handbook. Commit the generated file in the Guides repository whenever the Guides headings change, so `run --strict` stays green. The checkout must be writable here, so mount it without `:ro`.

```bash
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/app" -v "$HOME/Desktop/WORK/Guides:/guides-src" -w /app \
  ai-buddy-test python -m buddy_sync guides-index --checkout /guides-src
```

### `python -m buddy_sync search QUERY [--limit N] [--artifact-dir DIR]`

Keyword search over the published Guides chunks. One line per hit:

```
<file>:<line_start>-<line_end>  <h2> > <h3 or (intro)>  <video link or ->
```

`--artifact-dir` defaults to `ARTIFACT_DIR`, then to `artifacts`. `--limit` defaults to 5.

```bash
buddy ai-buddy-test python -m buddy_sync search "chunking"
```

### `python -m buddy_sync publish`

Publishes the `index.db` that `run` left in `ARTIFACT_DIR` to `ARTIFACT_BUCKET` under `ARTIFACT_PREFIX` (D-06). It reads `ARTIFACT_DIR` and never writes to it, so the directory can be mounted read-only. Output is one line with the build id and nothing else:

```
published build_id=<id>     the db object and then the pointer were uploaded
unchanged build_id=<id>     the bucket pointer already holds this content hash; nothing was uploaded
```

Behaviour:

- It checks `index.db` against `index.manifest.json` (sha256 and size) before any upload. A mismatch, a missing file or a damaged manifest ends with one `ERROR` line and exit 1.
- The db object `index-<build_id>.db` is uploaded first and the pointer `index.manifest.json` last, so a failed or interrupted publish never changes what the server loads.
- Running it twice is safe: the second run finds the same content hash in the pointer and uploads nothing.
- Credentials are Application Default Credentials, read by the storage client from `GOOGLE_APPLICATION_CREDENTIALS` (a user credentials file from `gcloud auth application-default login`, mounted read-only). They are never printed. A bucket failure prints the error type name only.

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD/artifacts:/artifacts:ro" \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/adc.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc.json -e GOOGLE_CLOUD_PROJECT="$PROJECT_ID" \
  -e ARTIFACT_DIR=/artifacts -e ARTIFACT_BUCKET="$PROJECT_ID-ai-buddy-index" -e ARTIFACT_PREFIX=index/ \
  ai-buddy-sync:laptop publish
```

## One command: scripts/sync-and-publish.sh

`scripts/sync-and-publish.sh` is the laptop command that refreshes the hosted index end to end. It needs `HANDBOOK_SRC_DIR`, `GUIDES_SRC_DIR` and `REDACT_PAGE_FILES`; `PROJECT_ID` enables the publish steps.

```bash
HANDBOOK_SRC_DIR=docs/research/handbook-raw GUIDES_SRC_DIR=~/Desktop/WORK/Guides \
REDACT_PAGE_FILES=<denylisted page files> PROJECT_ID=<project id> \
  scripts/sync-and-publish.sh
```

Steps:

1. Builds the `sync` image (`docker build --target sync`).
2. Runs `run` with `--network none`, the handbook and the Guides checkout mounted read-only, as the host user, writing `ARTIFACTS_DIR` (default `./artifacts`).
3. Runs `publish` in the same image with network access, `ARTIFACTS_DIR` read-only and the credentials file mounted read-only. The credentials file is mounted only in this step, never in the sync run.
4. Only when step 3 printed `published`, forces a new `mcp-server` revision in `europe-west8` with `gcloud run services update mcp-server --update-env-vars INDEX_BUILD_ID=<build id>`, run through the pinned Cloud SDK image. The next request cold-starts on the new index (D-08). With `unchanged` no revision is created. If the `mcp-server` service does not exist yet, the script says so and ends successfully: the first CI deploy loads the published index.

`--local-only` stops after step 2: no bucket call and no gcloud call. So does an unset `PROJECT_ID`. Other settings: `ARTIFACT_BUCKET` (default `<PROJECT_ID>-ai-buddy-index`), `ARTIFACT_PREFIX` (default `index/`) and `ADC_FILE` (default `~/.config/gcloud/application_default_credentials.json`). The script logs step names and build ids only.

Nothing deletes old builds, neither a bucket rule nor this script; see `docs/index-format.md`, "Publishing to a bucket".

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | The command succeeded. For `run`, this includes a run that found nothing to change. |
| 1 | The command failed. One `ERROR` line on stderr names the cause, for example a missing variable, a handbook folder error (missing folder, malformed front matter, a `REDACT_PAGE_FILES` entry that names no file), a git error, `--strict` drift, or for `publish` a missing or inconsistent local index and a failed bucket call. |
| 2 | The command line is invalid (no subcommand, unknown subcommand or bad option). |

## Never commit these

`ARTIFACT_DIR` contents (`index.db`, `index.manifest.json`), the Guides checkout, the handbook folder `docs/research/handbook-raw/` and `.env` hold handbook content or local settings. `artifacts/`, `*.db`, `.cache/`, `docs/research/handbook-raw/` and `.env` are gitignored. The repository is public: do not add any of them with `git add -f`.
