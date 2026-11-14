# buddy_sync: content sync job

Batch job, run on demand from the developer laptop (there is no schedule and no Cloud Run job), that builds the AI Buddy knowledge artifact and publishes it to the private bucket the hosted MCP server reads. One run reads the local handbook folder (`HANDBOOK_DIR`, mounted read-only) and the Guides git repository (the local checkout, mounted read-only and cloned into `GUIDES_CHECKOUT_DIR`), redacts secrets and denylisted pages, resolves Guides video links, and publishes one `index.db` (SQLite with FTS5) to `ARTIFACT_DIR`. An unchanged input writes nothing, and a failed run leaves the previous `index.db` in place, so a run can always be repeated.

No variable is secret, and `run` needs no network: both sources are local directories. Only `publish` and `upload-videos` talk to the network, and they need Application Default Credentials (see `publish` and `upload-videos` below).

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
| `VIDEO_BUCKET` | Name of the private bucket that holds the Guides videos (D-16). Required by `upload-videos`. Optional for `run`: when set, `run` writes `https://storage.cloud.google.com/<bucket>/videos/<name>.mp4` as the base video URL of every video link, and `upload-videos` must have uploaded those files first. Unset, the README URLs are kept. The convention is `<project id>-ai-buddy-videos`. |

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

### `python -m buddy_sync upload-videos --guides-dir DIR --videos-dir DIR [--videos-dir DIR ...]`

Uploads the Guides videos to `VIDEO_BUCKET` (D-16, D-17). The Guides `README.md` table in `--guides-dir` is the only source of which videos exist: every `.mp4` it names must be uploaded to `videos/<name>.mp4`. Output is one line with counts and nothing else:

```
uploaded=<n> unchanged=<m>
```

Where the local files come from:

- `Guides/videos/<topic>/out/*.mp4` in the Guides working tree (about 12 of the 20 videos). Pass the tree's `videos/` directory as one `--videos-dir`.
- The rest are GitHub release assets of the private Guides repository. Download them on the host with your own login, into the gitignored `.cache/videos` directory: `gh release download videos --repo <owner>/Guides --dir .cache/videos`. Pass that directory as a second `--videos-dir`. The job never downloads them and holds no token.

Behaviour:

- Files are found by name, recursively, under every `--videos-dir`. The same name with different bytes in two places is an error; identical bytes upload once.
- An object is uploaded only when it is absent or its md5 differs from the local file, so a second run uploads nothing. Objects are sent with `Content-Type: video/mp4`, `Content-Disposition: inline` and `Cache-Control: private`, so a browser plays them instead of downloading them.
- A README video with no local file fails the command (exit 1) with the count and the names. Files found earlier in the same run are still uploaded. This is the guard that stops an index from pointing at an object that was never uploaded.
- A README file name must be a plain `*.mp4` name (letters, digits, `.`, `_`, `-`), and two different README URLs may not share a name. Anything else is refused before any bucket call.
- Access is an IAM grant on the private bucket plus the Google login that `storage.cloud.google.com` asks for. The links never use a public URL or a signed URL with an expiry. Whether the player opens inline and seeks to `#t=<seconds>` after that login redirect is checked live in plan 04-13.
- Credentials are Application Default Credentials, as for `publish`. A bucket failure prints the error type name only.

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$HOME/Desktop/WORK/Guides:/guides-src:ro" -v "$PWD/.cache/videos:/videos-extra:ro" \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/adc.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc.json -e GOOGLE_CLOUD_PROJECT="$PROJECT_ID" \
  -e VIDEO_BUCKET="$PROJECT_ID-ai-buddy-videos" \
  ai-buddy-sync:laptop upload-videos --guides-dir /guides-src \
  --videos-dir /guides-src/videos --videos-dir /videos-extra
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
2. With `PROJECT_ID` set and without `--local-only`: runs `upload-videos` with network access, the Guides tree (`GUIDES_SRC_DIR`, which holds `videos/`) and `EXTRA_VIDEOS_DIR` (default `./.cache/videos`, skipped when the directory does not exist) mounted read-only, and the credentials file mounted read-only. `VIDEO_BUCKET` defaults to `<PROJECT_ID>-ai-buddy-videos`. A missing video file stops the command here, before any index is built.
3. Runs `run` with `--network none`, the handbook and the Guides checkout mounted read-only, as the host user, writing `ARTIFACTS_DIR` (default `./artifacts`). `VIDEO_BUCKET` is passed to `run` only when step 2 ran, so the index never links to videos that were not uploaded; otherwise the README URLs are kept.
4. Runs `publish` in the same image with network access, `ARTIFACTS_DIR` read-only and the credentials file mounted read-only. The credentials file is mounted only in the upload and publish steps, never in the sync run.
5. Only when step 4 printed `published`, forces a new `mcp-server` revision in `europe-west8` with `gcloud run services update mcp-server --update-env-vars INDEX_BUILD_ID=<build id>`, run through the pinned Cloud SDK image. The next request cold-starts on the new index (D-08). With `unchanged` no revision is created. If the `mcp-server` service does not exist yet, the script says so and ends successfully: the first CI deploy loads the published index.

`--local-only` skips steps 2, 4 and 5: no bucket call, no gcloud call and no video upload, and the local index keeps the README video URLs. So does an unset `PROJECT_ID`. `PROJECT_ID` and the credentials file are checked before step 2. Other settings: `ARTIFACT_BUCKET` (default `<PROJECT_ID>-ai-buddy-index`), `ARTIFACT_PREFIX` (default `index/`), `VIDEO_BUCKET`, `EXTRA_VIDEOS_DIR` and `ADC_FILE` (default `~/.config/gcloud/application_default_credentials.json`). The script logs step names and build ids only.

Nothing deletes old builds, neither a bucket rule nor this script; see `docs/index-format.md`, "Publishing to a bucket".

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | The command succeeded. For `run`, this includes a run that found nothing to change. |
| 1 | The command failed. One `ERROR` line on stderr names the cause, for example a missing variable, a handbook folder error (missing folder, malformed front matter, a `REDACT_PAGE_FILES` entry that names no file), a git error, `--strict` drift, or for `publish` a missing or inconsistent local index and a failed bucket call, or for `upload-videos` a README video without a local file or an invalid README file name. |
| 2 | The command line is invalid (no subcommand, unknown subcommand or bad option). |

## Never commit these

`ARTIFACT_DIR` contents (`index.db`, `index.manifest.json`), the Guides checkout, the handbook folder `docs/research/handbook-raw/` and `.env` hold handbook content or local settings. `artifacts/`, `*.db`, `.cache/`, `docs/research/handbook-raw/` and `.env` are gitignored. The repository is public: do not add any of them with `git add -f`.
