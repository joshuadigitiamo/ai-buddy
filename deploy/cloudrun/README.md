# Cloud Run deployment

Two Cloud Run services in `europe-west8` (Milan), both scale to zero and are capped at one instance:

| Service | File | What it runs |
|---------|------|--------------|
| `mcp-server` | `mcp-server.yaml` | the MCP server; reads its index from a private bucket at cold start |
| `chat-bot` | `chat-bot.yaml` | the Google Chat bot (HTTP intake) plus Meridian, the Claude Max proxy, as a sidecar on `127.0.0.1:3456` |

The YAML files are templates. They carry `${PLACEHOLDER}` markers instead of project identifiers,
because this repository is public. `scripts/render-cloudrun.sh` fills them from environment
variables, on the laptop and in CI alike. **No project id, project number, organization id, personal
id or secret value is ever committed.** The id of the project lives in `docs/internal/gcp-project.md`
(gitignored) and reaches the scripts only as `PROJECT_ID` and `PROJECT_NUMBER`.

This directory holds static files only. Nothing here deploys by itself: the live run is the Phase 4
live checkpoint (04-13), with Joshua present.

## Prerequisites

- The existing GCP project, under the digitiamo.com organization, with billing linked (D-02). Its id
  and number are in `docs/internal/gcp-project.md`. **`bootstrap.sh` never creates a project**; it
  checks that the project exists and that `PROJECT_NUMBER` matches it.
- A `gcloud` login for the owner account (`gcloud auth login` on the host).
- Docker (the scripts run in the `google/cloud-sdk` image, as the rest of the repository runs in Docker).
- The numeric id of the GitHub repository that may deploy (not its name). On the host with `gh`
  logged in: `gh api repos/<owner>/<repo> --jq .id`.
- Decisions recorded in `04-01-SUMMARY.md`: `billing_mode` (a) request-based, `token_chain` (b) a fresh
  separate login seeds the Cloud Run bucket, `org_policy` yes.

## Bootstrap

Run once. It creates everything the services need outside git: APIs, the Firestore `(default)` database
in `europe-west8` (one-way, confirmed by typing the region), Firestore TTL on `expire_at` for the `gaps`
and `thread_memory` collections (D-05), the Artifact Registry repository `ai-buddy` (cleanup policy: keep
the 3 most recent versions per image), three private buckets, three service accounts with their roles,
six empty secrets, and the Workload Identity Federation pool `github` with provider `monorepo`.

```bash
export PROJECT_ID=...        # from docs/internal/gcp-project.md
export PROJECT_NUMBER=...    # numeric, same file
export GITHUB_REPO_ID=...    # numeric repository id
export OWNER_EMAIL=...       # the owner's Google account

docker run --rm -it \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e CLOUDSDK_CONFIG=/gcloud \
  -v "$HOME/.config/gcloud:/gcloud" \
  -v "$PWD:/app:ro" -w /app \
  -e PROJECT_ID -e PROJECT_NUMBER -e GITHUB_REPO_ID -e OWNER_EMAIL \
  google/cloud-sdk:592.0.0-emulators bash deploy/cloudrun/bootstrap.sh
```

`-it` is required: the Firestore step asks for the region at a prompt. The script prints resource names
and the non-secret GitHub variable values; it never prints a secret and never enables shell tracing.
Re-running it is safe: each step describes the resource first.

| Resource | Name |
|----------|------|
| Artifact Registry repository | `ai-buddy` |
| Buckets | `<PROJECT_ID>-ai-buddy-index`, `<PROJECT_ID>-ai-buddy-videos`, `<PROJECT_ID>-ai-buddy-claude` |
| Service accounts | `sa-mcp-server`, `sa-chat-bot`, `ci-deployer` |
| WIF | pool `github`, provider `monorepo`, limited to the repository id and `refs/heads/main` |

Roles, least privilege: `ci-deployer` pushes images, deploys, and acts as the two runtime accounts;
`sa-mcp-server` uses Firestore, reads the index bucket and reads its three secrets; `sa-chat-bot` uses
Firestore, reads and writes the credentials bucket (and only that one) and reads its three secrets. The
owner reads the videos bucket, publishes to the index and videos buckets and can deploy.

The region is fixed to `europe-west8` (D-03). Any other `REGION` is refused unless
`ALLOW_REGION_FALLBACK` names the same region, which is set only after asking Joshua.

## Secrets

Six secrets are created empty. Add each value from stdin, so it never reaches a command line, the shell
history or the terminal:

| Secret | Used by | How to produce the value |
|--------|---------|--------------------------|
| `google-client-secret` | mcp-server | the OAuth client secret from the Google Auth platform |
| `oauth-jwt-signing-key` | mcp-server | random, at least 32 characters |
| `oauth-storage-encryption-key` | mcp-server | random, never reused |
| `thread-key-secret` | chat-bot | random, at least 32 characters |
| `meridian-api-key` | chat-bot and Meridian | random; the bot and the sidecar must hold the same value |
| `allowed-users` | chat-bot | one Chat user id (the bot refuses more than one with Meridian) |

```bash
# A generated value: nothing is shown.
openssl rand -base64 48 | gcloud secrets versions add thread-key-secret --project="$PROJECT_ID" --data-file=-

# A value you hold: read it silently.
read -rs VALUE && printf '%s' "$VALUE" | gcloud secrets versions add google-client-secret \
  --project="$PROJECT_ID" --data-file=- && unset VALUE
```

The six secrets equal the free quota of six active secret versions. Rotating a value adds a version, so
disable the old version at once to stay inside the quota.

## Seeding the Meridian credentials bucket

Decision `token_chain` (b): the Cloud Run bucket gets a **fresh, separate** `claude` login. Never copy
the local `meridian-claude` volume: two copies of one OAuth refresh-token chain invalidate each other
(RESEARCH Pitfall 5), and the local volume keeps its own chain. The login runs in the Meridian image into
a temporary directory, and the file is never printed.

```bash
SEED_DIR="$(mktemp -d)" && chmod 700 "$SEED_DIR"
docker run --rm -it --entrypoint claude \
  -v "$SEED_DIR:/home/claude/.claude" \
  "ai-buddy/meridian:$(cat deploy/meridian.version)" auth login
gcloud storage cp "$SEED_DIR/.credentials.json" "gs://${PROJECT_ID}-ai-buddy-claude/.credentials.json" \
  --project="$PROJECT_ID"
rm -rf "$SEED_DIR"
```

The image `ai-buddy/meridian:<commit>` exists after `scripts/kind-up.sh` or a Compose build. After the
copy, only the Cloud Run instance refreshes this chain. The bucket is mounted read-write in the Meridian
container only, owned by uid 1000 (the Meridian image user) through the mount option `uid=1000,gid=1000`.

## GitHub repository variables

Set these as repository **variables** (not secrets); none of them is a secret. `bootstrap.sh` prints the
first four.

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER` | the project id and number |
| `GCP_WIF_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github/providers/monorepo` |
| `GCP_DEPLOYER_SA` | `ci-deployer@<PROJECT_ID>.iam.gserviceaccount.com` |
| `GCP_OAUTH_CLIENT_ID` | the OAuth client id of the MCP server |
| `GUIDES_WEB_BASE` | the `https://` base URL of the Guides repository |
| `CHAT_JWT_ISSUER_EMAIL` | the account that signs Chat requests (see the Chat app section) |
| `VIDEO_THUMBNAIL_URL` | the `https://` URL of the card thumbnail |
| `HELP_COMMAND_ID` | the Chat app help command id |

## Render and deploy

```bash
export IMAGE_TAG="$(git rev-parse --short HEAD)"   # the tag CI pushed
export GOOGLE_CLIENT_ID=... GUIDES_WEB_BASE=... CHAT_JWT_ISSUER_EMAIL=... \
       VIDEO_THUMBNAIL_URL=... HELP_COMMAND_ID=...
# PROJECT_ID and PROJECT_NUMBER as above; MERIDIAN_TAG defaults to deploy/meridian.version.

scripts/render-cloudrun.sh mcp-server .cache/rendered/mcp-server.yaml
scripts/render-cloudrun.sh chat-bot   .cache/rendered/chat-bot.yaml

gcloud run services replace .cache/rendered/mcp-server.yaml --region europe-west8 --project "$PROJECT_ID" --dry-run
gcloud run services replace .cache/rendered/mcp-server.yaml --region europe-west8 --project "$PROJECT_ID"
gcloud run services replace .cache/rendered/chat-bot.yaml   --region europe-west8 --project "$PROJECT_ID"
```

The render script needs every variable to be set and non-empty (it names the missing ones, never the
values), substitutes only its fixed variable list, refuses a value that holds a quote, backslash, `$` or
newline, and fails if any `${` is left in the output. It never prints the rendered file. `.cache/` is
gitignored.

The service URLs are deterministic (`https://<service>-<PROJECT_NUMBER>.europe-west8.run.app`), so both
files can name each other before the first deploy: the bot's `MCP_AUDIENCE` equals the server's
`MCP_PUBLIC_BASE_URL`, `MCP_URL` is that URL plus `/mcp`, and the server's `BOT_SA_EMAILS` names the bot's
runtime account. `tests/unit/test_cloudrun_yaml.py` keeps the two files in step; the live authenticated
call is checked in 04-13.

## Connecting Chat and claude.ai

**Google Chat app.** In the Chat API configuration choose the HTTP endpoint URL
`https://chat-bot-<PROJECT_NUMBER>.europe-west8.run.app` and set **Authentication Audience = HTTP endpoint
URL**. `CHAT_JWT_AUDIENCE` in `chat-bot.yaml` is that same URL. `CHAT_JWT_ISSUER_EMAIL` depends on the app
format: `chat@system.gserviceaccount.com` for the legacy format, or
`service-<PROJECT_NUMBER>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com` for the add-on format. Only the
endpoint-URL audience mode is supported (`services/chat_bot/README.md`).

**claude.ai connector.** The connector URL is `https://mcp-server-<PROJECT_NUMBER>.europe-west8.run.app/mcp`.
Add `https://mcp-server-<PROJECT_NUMBER>.europe-west8.run.app/auth/callback` as an authorized redirect URI
on the Google OAuth client (`services/mcp_server/README.md`).

Both services set `run.googleapis.com/invoker-iam-disabled: 'true'`, because Chat and claude.ai are not
Google IAM principals. This is not an open door: the server checks every token (`AUTH_MODE=on`) and the bot
verifies Google's JWT on every request before any model call (`INTAKE=http`).

## Organization policies

The project sits under the digitiamo.com organization (decision `org_policy`: yes), so organization
policies may block a step. Likely candidates: a resource-location constraint that does not list
`europe-west8`, domain-restricted sharing on an IAM binding, a constraint on service accounts or buckets.
If a step fails with a policy error, **record the exact error text and report it to Joshua**. Do not
change a policy and do not switch region or approach on your own.

## Cost

Not zero, but small. Figures are from the Google Cloud free-tier pages (RESEARCH, Pitfall 16).

| Service | Free tier | Use here | Verdict |
|---------|-----------|----------|---------|
| Cloud Storage | 5 GB-months only in three US regions | index (a few MB), videos (about 1 GB), credentials; all in `europe-west8` | not free, cents per month |
| Artifact Registry | 0.5 GB | three images; Meridian is large | likely over; the cleanup policy limits it |
| Secret Manager | 6 active versions, 10k accesses | six secrets | within; no spare for rotation without cost |
| Firestore | 1 GiB, 50k reads and 20k writes per day | gap log, thread memory, OAuth state | fine |
| Cloud Run, request-based | 2M requests, 360,000 GiB-s, 180,000 vCPU-s | both services | fine |

## Prepared fallbacks

Each fallback below is prepared and **not applied**. Apply one only with Joshua's consent, because each
changes cost or behaviour that Joshua signed off.

- **Background work stalls (Pitfall 1).** If a slow answer never replaces the "Sto cercando nelle fonti..."
  placeholder, add `run.googleapis.com/cpu-throttling: 'false'` to the template annotations of `chat-bot`
  only. It switches that service to instance-based billing.
- **Cold start exceeds Chat's deadline (Pitfall 2).** Set `autoscaling.knative.dev/minScale: '1'` on
  `chat-bot`. It bills idle time, roughly a few euros per month (`docs/research/07-costi-hosting-cloud-run.md`).
- **Chat API replies fail with 403 (Pitfall 3).** Keep the keyless approach: the runtime account
  impersonates a dedicated Chat-app account through `google.auth.impersonated_credentials` with the
  `chat.bot` scope (needs `roles/iam.serviceAccountTokenCreator` on that account).
- **The video link does not play inline at the timestamp (Pitfall 13).** First a small HTML player page
  that sets `currentTime` from `?t=`; only then signed URLs, which contradicts D-16.
- **The Meridian start-up probe cannot reach the loopback port.** Cloud Run has no exec probe, and the docs
  do not say whether a start-up probe reaches a port bound to `127.0.0.1`. If the sidecar never turns
  healthy: first a `tcpSocket` probe on 3456; then `MERIDIAN_HOST` `0.0.0.0`, which stays unreachable from
  outside because only the ingress container takes traffic.
- **`gcloud run services replace` rejects a sidecar without a launch stage.** Add
  `run.googleapis.com/launch-stage: BETA` to the service annotations only if the dry run demands it
  (RESEARCH A2).
- **`run.developer` cannot set `invoker-iam-disabled`.** Grant the deployer the role the error names
  (RESEARCH A9), not a wider one.

## Design notes

- **No SIGTERM handler.** uvicorn drains in-flight HTTP requests on SIGTERM, and the Pub/Sub intake never
  runs on Cloud Run. The remaining risk is the background-patch case above, measured in 04-13.
- **No age-based delete rule on the index bucket.** A lifecycle rule by age would also delete the build the
  pointer names after a month without a new sync, and the server would refuse to start. Old builds are a
  few MB each; prune them with the sync step, not with a bucket rule.
- **Meridian transcripts.** `MERIDIAN_TRANSCRIPT_RETENTION_DAYS` is `7`: Meridian writes one transcript
  per request, and they hold employee questions (BOT-11). The session store sits on an in-memory volume
  (`MERIDIAN_SESSION_DIR`), and `MERIDIAN_SILENT` is `1`.
- **Single instance.** `maxScale` is `1` on both services: one Meridian is the only writer of the
  credentials file (FUSE has no write locking), and Meridian serves one person's Max login.
- **`DEPLOY_ENV` is explicit on `mcp-server` and unset on `chat-bot`.** Both mean production (fail closed).
  The bot leaves it unset, as 04-03 asked, so the YAML cannot carry a local-only knob by mistake.
