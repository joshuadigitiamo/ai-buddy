# buddy_mcp: MCP server

Remote MCP server (FastMCP, stateless streamable HTTP with plain JSON replies) that serves the published `index.db` to claude.ai, Claude Code and the chat bot. It only reads the artifact that `jobs/sync` publishes: the handbook pages and the Guides sections.

Everything runs in Docker. Do not run it with the host Python.

## Tools and resource

| Name | Purpose |
|------|---------|
| `handbook_search` | Keyword search over whole handbook pages (Italian stemming). |
| `handbook_get` | One handbook page selected by the `section` argument, or the table of contents when it is omitted. |
| `guides_search` | Keyword search over the Guides sections. |
| `guides_get_section` | One Guides section by its `id`. |
| `buddy_report_gap` | Records a question the sources could not answer. The only tool that writes, and it only appends. |
| resource `handbook://{pagina}` | A handbook page as Markdown. |

Every result carries `source_url`, `revision_date`, `revision_kind` and, for Guides sections with a video, `video_url`. Every reply carries `status` (`ok` or `no_results`). The contract (D-06) is in `buddy_mcp/models.py`; the chat bot and the Skill parse it, so rename a field only together with both.

## Run it locally

Build the test image and run the whole offline gate or the Firestore emulator tests:

```bash
./run-unit-tests.sh --all
./run-unit-tests.sh --emulator
```

`--emulator` starts the Firestore emulator in a private compose network and runs the tests marked `firestore`, among them the real-process test that starts `python -m buddy_mcp` and calls it over HTTP.

Run the process from the test image. This is `AUTH_MODE=off` with `DEPLOY_ENV=local`, so it is for your machine only. It needs a published `index.db` in `./artifacts` (see `jobs/sync/README.md`) and a Firestore to write gaps to: either the emulator, or a real project reached with credentials you mount yourself.

```bash
docker build --target test -t ai-buddy-test .
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --env-file .env \
  -e DEPLOY_ENV=local -e AUTH_MODE=off -e MCP_HOST=0.0.0.0 -p 127.0.0.1:8000:8000 \
  -v "$PWD:/app" -w /app ai-buddy-test python -m buddy_mcp
```

The server answers at `http://localhost:8000/mcp`. With a local Claude Code:

```bash
claude mcp add --transport http digitiamo-buddy http://localhost:8000/mcp
```

Build the runtime image (only `buddy_core` and `buddy_mcp` code, runs as uid 10001, no index baked in) and mount the artifacts read-only:

```bash
docker build --target mcp_server -t ai-buddy-mcp .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 \
  -v "$PWD/artifacts:/app/artifacts:ro" ai-buddy-mcp
```

The index is read once, at cold start. After a new sync, restart the server.

## Environment variables

Every setting comes from the environment (`--env-file .env`; no env file is read by the code). `.env.example` lists the non-secret variables; `.env` is gitignored.

| Variable | Default | Meaning |
|----------|---------|---------|
| `ARTIFACT_DIR` | none, required | Directory holding the published `index.db`. It is never created or written by the server. |
| `GUIDES_WEB_BASE` | none, required | `https://` base URL of the Guides repository, used to build Guides `source_url` links. |
| `GOOGLE_CLOUD_PROJECT` | none, required | Project of the Firestore that stores gaps and, with `OAUTH_STORAGE=firestore`, OAuth state. |
| `MCP_HOST` | `0.0.0.0` | Interface to bind. |
| `PORT` | `8000` | Port to bind. |
| `DEPLOY_ENV` | `production` | `local` or `production`. `local` is for a developer machine, compose and kind; it is refused when `K_SERVICE` is set. See "Local vs deployed". |
| `AUTH_MODE` | `on` | `on` or `off`; `off` needs `DEPLOY_ENV=local`. See "Authentication". |
| `MCP_PUBLIC_BASE_URL` | none | Public `https://` URL of the server, equal to the URL users type into the connector without `/mcp` (`http://localhost` is allowed for local runs). Required when `AUTH_MODE=on`. |
| `MCP_ALLOWED_HOSTS` | empty | Comma-separated extra bare hostnames the server answers on plain http, for example the Service name `mcp-server` in compose and kind. Lowercase DNS names only: no scheme, port, path, wildcard or underscore. The Host guard stays on; `localhost`, `127.0.0.1` and the `MCP_PUBLIC_BASE_URL` host are always allowed. |
| `GOOGLE_CLIENT_ID` | none | Google OAuth client id. Required when `AUTH_MODE=on`. |
| `GOOGLE_CLIENT_SECRET` | none | **Secret, never commit.** Google OAuth client secret. Required when `AUTH_MODE=on`. |
| `OAUTH_JWT_SIGNING_KEY` | none | **Secret, never commit.** Random value of at least 32 characters that signs the server's own access tokens. Required when `AUTH_MODE=on`. |
| `ALLOWED_EMAIL_DOMAIN` | `digitiamo.com` | Only verified e-mail addresses of this domain may log in. |
| `BOT_SA_EMAILS` | empty | Comma-separated service-account e-mails allowed to call the server as the bot. |
| `OAUTH_STORAGE` | `memory` | `memory` or `firestore`; where the OAuth proxy keeps its state. |
| `OAUTH_STORAGE_ENCRYPTION_KEY` | none | **Secret, never commit.** Fernet key; required when `OAUTH_STORAGE=firestore`. |
| `OAUTH_COLLECTION` | `oauth_state` | Firestore collection for OAuth state. |
| `RATE_LIMIT_RPS` | `5` | Sustained requests per second per caller. |
| `RATE_LIMIT_BURST` | `30` | Burst size per caller. |
| `GAP_TTL_DAYS` | `90` | Days a gap document lives before `expire_at`. |
| `GAP_COLLECTION` | `gaps` | Firestore collection for gaps. |

The three secrets are not in `.env.example`. Set them only in `.env` or a secret manager. Generate the signing key with `openssl rand -hex 32`. Generate the Fernet key inside the container, so no host Python is needed:

```bash
docker run --rm ai-buddy-mcp python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If a variable is missing or invalid, the process exits with code 1 and one `ERROR` line that names the variables, never their values.

## Authentication

### AUTH_MODE rules (D-13)

- `AUTH_MODE=off` disables authentication. The server accepts it only with `DEPLOY_ENV=local`, set explicitly; a missing or empty `DEPLOY_ENV` means production on every host.
- `DEPLOY_ENV=local` is refused whenever `K_SERVICE` is set, which is how Cloud Run marks a deployed service.
- With `AUTH_MODE=on`, `MCP_PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `OAUTH_JWT_SIGNING_KEY` are all required, and the signing key must be at least 32 characters.
- A plain `http://` `MCP_PUBLIC_BASE_URL` is accepted only when its hostname is exactly `localhost` or `127.0.0.1`.

### Local vs deployed

`DEPLOY_ENV` defaults to `production`. Set `DEPLOY_ENV=local` only on a developer machine, in compose and in kind. `K_SERVICE` forces production: the server refuses `DEPLOY_ENV=local` on Cloud Run even with authentication on. One image serves every target; the environment variables decide the behaviour.

### Health route

`GET /healthz` answers `200` with the constant body `{"status": "ok"}`. It needs no token, even with `AUTH_MODE=on`, and reads neither Firestore nor any bucket, so a slow dependency never fails liveness. The Host guard applies to it as to `/mcp`: a probe must send a `Host` header the server allows (for Kubernetes `httpGet` probes, set `Host: mcp-server` and list `mcp-server` in `MCP_ALLOWED_HOSTS`).

### Google OAuth client

People log in with their Google account through the server's OAuth proxy. Set it up once in Google Cloud Console:

1. Google Auth Platform, Audience: set the user type to **Internal**, so only the Workspace organisation can sign in. The server also checks the domain itself; the consent-screen setting is the second layer, not the only one.
2. APIs and Services, Credentials: create an OAuth client of type **Web application**.
3. Add this authorized redirect URI: `<MCP_PUBLIC_BASE_URL>/auth/callback`. The path `/auth/callback` is the fastmcp OAuth proxy default and is confirmed from the installed source.
4. Scopes requested: `openid` and `https://www.googleapis.com/auth/userinfo.email`.
5. Put the client id in `GOOGLE_CLIENT_ID` and the client secret in `GOOGLE_CLIENT_SECRET`.

claude.ai cannot reach `localhost`. A live login needs a public HTTPS URL (a tunnel to a local run, or the Phase 4 host), and `MCP_PUBLIC_BASE_URL` must equal the URL users paste into the connector, without `/mcp`.

### Domain check

A token is accepted only when its e-mail is verified and its domain is exactly `ALLOWED_EMAIL_DOMAIN`. The `hd` authorize parameter is a UI hint only, so the server verifies the claim itself. An account of another domain can finish the Google login but never reaches the tools.

### OAuth state storage

The OAuth proxy keeps client registrations and token mappings in a store. There is no file-backed option.

- `memory` (default): the state is lost on every restart, so everyone logs in again. Good for local runs and tests.
- `firestore`: the state is stored in `OAUTH_COLLECTION`, encrypted with the Fernet key in `OAUTH_STORAGE_ENCRYPTION_KEY`. It survives restarts and scale-to-zero. A value that cannot be decrypted (rotated key) reads as missing, so clients register again instead of the server failing. Use this for any deployed run.

### Bot contract (D-12)

The chat bot has no shared secret. Its service account mints a Google ID token with `audience` equal to `MCP_PUBLIC_BASE_URL` and sends it as a bearer token. List the service account's e-mail in `BOT_SA_EMAILS`. The server checks the Google signature, issuer, audience, expiry, a verified e-mail and the allowlist. With `BOT_SA_EMAILS` empty, no bot token is accepted.

## Rate limiting

Each caller has a token bucket (`RATE_LIMIT_RPS`, `RATE_LIMIT_BURST`), kept in memory, per instance. The caller is the authenticated client, or `anonymous` when `AUTH_MODE=off`. Every request counts, including `initialize` and `tools/list`, which is why the default burst is generous. Over the limit the reply is HTTP 200 with a JSON-RPC error, not HTTP 429.

## Gap log

`buddy_report_gap` writes one document per unanswered question to `GAP_COLLECTION`, with these six fields and nothing that identifies the asker: `question`, `marker` (`nessuna fonte trovata`), `created_at`, `expire_at`, `build_id`, `tried`. The Firestore client is created when the first gap is written, so startup makes no network call; a failed write becomes a tool error.

Expiry is a Firestore TTL policy on `expire_at`. Apply it once, when the hosting is set up in Phase 4:

```bash
gcloud firestore fields ttls update expire_at --collection-group=gaps --enable-ttl
```

Firestore deletes expired documents within about a day. The emulator does not enforce TTL.

## Logging policy

The process logs counts, ids and modes only: at startup one INFO line with the number of handbook pages and Guides sections, the build id and the auth mode. Question text, search queries and caller identity never appear in logs, and a startup error names variables, never values.

## Never commit these

`.env`, any file holding a value of the three secrets, and the `ARTIFACT_DIR` contents. The repository is public: `.env.example` holds placeholders only and never `FIRESTORE_EMULATOR_HOST`.
