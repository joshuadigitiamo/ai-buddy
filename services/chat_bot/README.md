# buddy_bot: Google Chat bot

Google Chat app "AI Buddy". It answers employee questions only from the official sources behind the MCP server (handbook pages and Guides sections), cites the source, or says it does not know and logs the gap. It never invents a policy.

Everything runs in Docker. Do not run it with the host Python.

## What it does

1. **Intake.** Chat events arrive from a Pub/Sub pull subscription (`INTAKE=pubsub`, development) or an HTTP endpoint that verifies Google's JWT on every request (`INTAKE=http`, Cloud Run). Both feed the same service. Both Chat event formats (add-on and legacy) are accepted.
2. **Allowlist.** The sender must be in `ALLOWED_USERS`. Anyone else is dropped silently: no reply, no MCP call, no LLM call, no memory write.
3. **Placeholder.** The bot posts "Sto cercando nelle fonti…" at once, then updates that same message.
4. **Answer.** A LangGraph two-step RAG: reformulate the question (with the last turns of the thread as context), search through the MCP tools, answer from the evidence only. Confidence below `CONFIDENCE_THRESHOLD` becomes a refusal ("Non lo so, chiedi a ...") and a gap record.
5. **Rendering.** Handbook sources are a text citation (`Manuale – <title> (handbook://<page_id>), revisione <date>`). A Guides source with a video adds a card with the thumbnail and a "Guarda" button. Sensitive topics (pay, illness, harassment, ...) get only the general written rule with its source and a referral to the role named in the shared escalation table.
6. **Canned replies, no LLM:** being added to a space, and the `/aiuto` slash command.

The bot is a client of the MCP server (`MCP_URL`); it contains no search code and no index.

## Run it locally

The live development stack is `docker-compose.dev.yml` at the repository root: Meridian, the MCP server, the bot and the Firestore emulator. No service publishes a port to the host. Phase 4 replaces this file with the real deployment definitions.

### Prerequisites

- A Google Cloud project with the Chat API and the Pub/Sub API enabled, the Chat app configured as described below, and a pull subscription on the Chat topic.
- A service-account key file for the bot, kept **outside** the repository.
- A published index in `./artifacts` (see `jobs/sync/README.md`), or any directory set in `ARTIFACTS_DIR`.
- Joshua's Claude login on the host (`~/.claude/.credentials.json`), used once to seed Meridian.

### Seed the Meridian credentials (once)

Meridian refreshes its OAuth tokens, so it needs a directory it can write. The credentials therefore live in a dedicated Docker named volume, `meridian-claude`, that only the Meridian container mounts. The host `~/.claude` is never mounted and nothing is baked into an image. Seed the volume once by copying the single credentials file into it:

```bash
docker volume create meridian-claude
docker run --rm \
  -v meridian-claude:/dest \
  -v "$HOME/.claude/.credentials.json:/src/.credentials.json:ro" \
  alpine:3 sh -c 'cp /src/.credentials.json /dest/.credentials.json \
    && chown -R 1000:1000 /dest && chmod 600 /dest/.credentials.json'
```

The compose file declares the volume `external: true`, so `docker compose up` refuses to start until it exists. Uid 1000 is the user Meridian runs as. If the login expires or is revoked, repeat the seeding with a fresh login.

### Start

Put the variables below in `.env` (gitignored), export the key file path, then start the stack:

```bash
export BOT_SA_KEY_FILE=/path/outside/the/repo/bot-sa-key.json
docker compose -f docker-compose.dev.yml up --build
```

Compose reads `MERIDIAN_API_KEY` and `GOOGLE_CLOUD_PROJECT` from `.env` and refuses to start without them. Compose-only host variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `BOT_SA_KEY_FILE` | none, required | Host path of the bot service-account key. Mounted read-only at `/secrets/bot-sa.json`. |
| `ARTIFACTS_DIR` | `./artifacts` | Host directory with the published index. Mounted read-only into the MCP server. |
| `BOT_UID`, `BOT_GID` | `1000`, `1000` | User the bot container runs as in dev. The image's own user (10001) cannot read a key file kept at mode 600, so dev uses the host user instead. |

The compose file sets these for the bot itself: `INTAKE=pubsub`, `LLM_BACKEND=meridian`, `LLM_BASE_URL=http://meridian:3456`, `MCP_URL=http://localhost:8000/mcp` (the bot shares the MCP server's network namespace, because the server admits plain http only for loopback hosts), `DEPLOY_ENV=local`, `MCP_AUTH=none`, `PORT=8080`, `FIRESTORE_EMULATOR_HOST=firestore:8080`, `LANGSMITH_TRACING=false`.

`PORT` matters: `.env.example` has `PORT=8000`, which is the MCP server's port. The compose file sets the bot's `PORT` explicitly so that value does not leak in.

The Firestore emulator holds the thread memory and the gap log in dev. It is lost on restart, which is fine for development. Read the gap log from the emulator:

```bash
docker compose -f docker-compose.dev.yml exec firestore curl -s \
  "http://localhost:8080/v1/projects/$GOOGLE_CLOUD_PROJECT/databases/(default)/documents/gaps"
```

## Environment variables

Every setting comes from the process environment (`--env-file .env`; no env file is read by the code). `.env.example` lists the non-secret variables; `.env` is gitignored. If a variable is missing or invalid, the process exits with code 1 and one `ERROR` line that names the variables, never their values.

| Variable | Default | Meaning |
|----------|---------|---------|
| `ALLOWED_USERS` | none, required | Comma-separated Chat user ids (`users/<id>`) and/or lowercase e-mails. See "ALLOWED_USERS". |
| `LLM_BACKEND` | none, required | `meridian` or `api`. `vertex` is refused ("not enabled"). |
| `LLM_BASE_URL` | none | Anthropic-compatible base URL. Required with `LLM_BACKEND=meridian` (`http://meridian:3456` in dev). |
| `ANTHROPIC_API_KEY` | none | **Secret.** Required with `LLM_BACKEND=api`. |
| `MERIDIAN_API_KEY` | none | **Secret.** Shared secret that gates Meridian; the bot sends it as the Anthropic key. |
| `VERTEX_PROJECT` | none | Reserved for the Vertex backend, which is not enabled. |
| `VERTEX_REGION` | none | Reserved for the Vertex backend, which is not enabled. |
| `REFORMULATE_MODEL` | `claude-haiku-5-5` | Model for the reformulation step. |
| `ANSWER_MODEL` | `claude-sonnet-5-5` | Model for the answer step. |
| `LLM_TIMEOUT_SECONDS` | `60` | Client timeout per LLM call. Meridian spawns a CLI turn per request, so keep it generous. |
| `CONFIDENCE_THRESHOLD` | `0.7` | Below this the bot refuses and logs a gap. |
| `MEMORY_TURNS` | `3` | Last Q/A turns kept per thread (1 to 10). |
| `THREAD_KEY_SECRET` | none, required | **Secret.** At least 32 characters. HMAC key for the thread-memory document ids. Generate with `openssl rand -hex 32`. |
| `MEMORY_COLLECTION` | `thread_memory` | Firestore collection for thread memory (`[A-Za-z0-9_-]+`). |
| `GOOGLE_CLOUD_PROJECT` | none | Project of the Firestore that holds thread memory and the gap log. |
| `MCP_URL` | none, required | URL of the MCP server, including `/mcp`. |
| `DEPLOY_ENV` | `production` | `local` or `production`. `local` only on a developer machine, compose and kind: it unlocks `MCP_AUTH=none` and `CHAT_API=recording`, and is refused when `K_SERVICE` is set (Cloud Run). Leave it unset on every deployed host. |
| `MCP_AUTH` | `google_id_token` | `google_id_token` or `none`. `none` is accepted only with `DEPLOY_ENV=local`. |
| `MCP_AUDIENCE` | none | Required with `MCP_AUTH=google_id_token`. Must equal the MCP server's `MCP_PUBLIC_BASE_URL`, without `/mcp`. |
| `INTAKE` | none, required | `pubsub` or `http`. |
| `PUBSUB_SUBSCRIPTION` | none | Required with `INTAKE=pubsub`: `projects/<id>/subscriptions/<name>`. |
| `CHAT_JWT_AUDIENCE` | none | Required with `INTAKE=http`: the HTTP endpoint URL configured in the Chat app. |
| `CHAT_JWT_ISSUER_EMAIL` | none | Required with `INTAKE=http`: the service account that signs Chat's requests (see below). |
| `BOT_HOST` | `0.0.0.0` | Interface the HTTP intake binds. |
| `PORT` | `8080` | Port the HTTP intake binds. |
| `VIDEO_THUMBNAIL_URL` | none, required | Real `https://` image shown on video cards. Startup fails without it. There is no default: supply your own image in `.env`. |
| `HELP_COMMAND_ID` | none | Command id of the `/aiuto` slash command, as shown in the Chat app configuration. Without it `/aiuto` is matched by its text prefix only. |
| `RUN_DEADLINE_SECONDS` | `120` | Whole-run deadline; on expiry an error text replaces the placeholder. |
| `CHAT_API` | `google` | `google` or `recording`. `recording` is for local smoke runs only (needs `DEPLOY_ENV=local`): the bot writes each placeholder and answer as a JSON line to `CHAT_RECORD_PATH` instead of calling Google Chat. |
| `CHAT_RECORD_PATH` | none | Path of the recording file, required with `CHAT_API=recording`. The file is appended to; its parent directory must exist. |

Also read from the environment: `LANGSMITH_TRACING` and `LANGCHAIN_TRACING_V2`. The bot refuses to start if either is `true`.

## Google Chat app settings (manual)

These cannot be set from code. Configure them in Google Cloud Console, Google Chat API, Configuration.

- **Name:** AI Buddy.
- **Visibility: Joshua only.** Share the app with the one person who may use it, and nobody else. This is part of BOT-03; the allowlist is the second layer, not the first.
- **Connection, development:** Cloud Pub/Sub, with the topic. The bot pulls from a subscription on that topic.
- **Connection, Cloud Run (Phase 4):** HTTP endpoint URL, with **Authentication Audience = HTTP endpoint URL**. Set `CHAT_JWT_AUDIENCE` to that same URL. Set `CHAT_JWT_ISSUER_EMAIL` to the service account that signs the requests, which depends on the app format: `chat@system.gserviceaccount.com` for the legacy format, the add-on service account `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com` for the add-on format. Only the endpoint-URL audience mode is supported; the project-number mode is not.
- **Markup syntax: MARKDOWN** (the default). Chat then renders standard Markdown, where a lone newline is a soft break, so the bot puts a blank line between every Fonte line, the contact line and the referral sentence. Do not switch the app to another syntax without changing `render.py`.
- **Slash command:** `/aiuto`. Note the command id Chat shows and put it in `HELP_COMMAND_ID`.
- **Event formats:** apps created after July 2025 default to the add-on format (the "Build this Chat app as a Google Workspace add-on" checkbox, which cannot be undone), older ones to the legacy format. The bot accepts both.

## Pub/Sub and IAM

- Grant `roles/pubsub.publisher` on the topic **only** to the identity Chat publishes as, which depends on the app format. Nobody else may publish: anything on the topic is treated as a Chat event (the allowlist still applies, but publishing rights are the first line).
  - **Add-on format** (the default for new apps, and what this project uses): `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`, where `<project-number>` is the numeric project number, not the project id. Granting `chat-api-push` here does not work: the live check got `PERMISSION_DENIED` on publish until the add-on service account was the publisher.
  - **Legacy format** (non-add-on apps only): `chat-api-push@system.gserviceaccount.com`.
  - The grant is on the topic itself, not on the project, and that single service account is the only publisher. Remove the grant of the format you do not use.
- Grant `roles/pubsub.subscriber` on the subscription to the bot service account.
- The bot service-account key stays outside the repository. Its path goes in the `BOT_SA_KEY_FILE` environment variable of your shell and the compose file mounts it read-only. It is never in `.env.example`, this README or the repository.

## ALLOWED_USERS

`ALLOWED_USERS` accepts `users/<id>` and lowercase e-mail addresses, comma-separated. A sender matches when their `user.name` (`users/<id>`) or, if the event carries one, their `user.email` is listed.

With `LLM_BACKEND=meridian` the list must contain exactly one person (D1a), counted after normalisation: an id and an e-mail of the same person count as two entries and startup refuses. Pick one form.

Chat events do not always carry `user.email`. If yours do not, use the id. To learn your numeric id once, call the People API `people/me` (scope `profile`) while signed in as yourself: the `resourceName` is `people/<id>`, and the Chat user name is `users/<id>` with the same id. [Medium: documented as the same canonical id, to be confirmed at the live check.] Do not add a code path that logs ids; the bot logs none.

## Meridian

Meridian is a third-party proxy that lets the bot use Joshua's Claude Max login through the Anthropic Messages API (D1a). It is for one person only, and only while Joshua is the sole user.

- It is built only from the source commit approved at 03-01 (pinned in `docker-compose.dev.yml` as a 40-character SHA), with the repository's own Dockerfile.
- It publishes no port. It is reachable only on the compose network, at `http://meridian:3456`, and every API route requires `MERIDIAN_API_KEY`.
- Its credentials are the `meridian-claude` volume described above, never an image layer and never the host `~/.claude`.
- Auth header: the Anthropic SDK sends the key as `Authorization: Bearer`, and Meridian accepted it at the live check (2026-11-07). No `x-api-key` override is needed.
- Logging: the compose file sets `MERIDIAN_SILENT=1`, which drops Meridian's routine per-request `[PROXY]` stderr lines. At the pinned commit the `msgs=` field of that line holds only roles and content types (for example `user[string]`), never question text, but the flag keeps a later change from printing prompts unnoticed (BOT-11). Meridian has no other logging option, and `MERIDIAN_DEBUG` must stay unset: it turns on verbose request and session logging.
- Meridian honours neither sampling controls nor exact output-token caps; structured output is JSON in the prompt.

## Thread memory and privacy

Follow-ups ("E per i permessi?") need the previous turns, so the bot keeps a small memory per thread (D-11):

- The Firestore document id is an HMAC-SHA256 of the DM space name, or of the thread name in a room, keyed with `THREAD_KEY_SECRET`. The raw space, thread and user ids are never stored, and no sender field is stored.
- Only the last `MEMORY_TURNS` turns are kept, and they expire after 24 hours. Expiry is enforced when reading (an expired document reads as empty).
- The history goes only to the reformulation step. The answer step sees only this run's retrieval, never earlier answers.
- Firestore deletes expired documents through a TTL policy on `expire_at`. Apply it once when the hosting is set up in Phase 4:

```bash
gcloud firestore fields ttls update expire_at --collection-group=thread_memory --enable-ttl
```

The emulator does not enforce TTL.

## Logging policy

The bot logs counters, node names, durations, tool names, modes and exception types only. It never logs event bodies, question text, history, evidence text, sender fields, space or thread names, or any secret. LangSmith export is off in the image (`LANGSMITH_TRACING=false`) and the bot refuses to start if tracing is enabled, because prompts carry employee questions and may only reach the LLM backend and the MCP server. The `fastmcp` and `anthropic` loggers are held at INFO so a debug environment variable cannot log prompts.

## Open items to confirm at the live check (D-18)

These are covered by synthetic fixtures and unit tests only. The first live run settles them:

- Which event format arrives (add-on or legacy), and whether `user.email` is present. Settled at the live check: add-on format, `user.email` present.
- That the message update works with the field mask `text` and `cards_v2`, and that the card and the "Guarda" button render and open the video at the scene offset.
- That a bare `@AI Buddy` mention in a room, with blank `argumentText`, is handled (it may normalise to the text "Buddy").
- That a DM follow-up uses the thread memory.
- That the Meridian auth header is accepted. Settled: it is.
- That the Pub/Sub topic accepts publishes only from the Chat service account. For an add-on app that account is `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`.
- With `MCP_AUTH=google_id_token`: a live ID-token call to the MCP server (`MCP_AUDIENCE` equal to the server's `MCP_PUBLIC_BASE_URL`). Not run so far; it is tracked in `.planning/WINDOWS.md`.

## Prima di un secondo utente

Do all of these before anyone other than Joshua uses the bot:

- [ ] **Switch `LLM_BACKEND`** from `meridian` to `api` (an Anthropic API key) or to Vertex in the EU region (D1a). Meridian runs on one person's Claude Max login and must not serve anyone else. Then remove the Meridian service and its credentials volume.
- [ ] **Re-check the thread-memory posture (D-11):** HMAC key, last N turns, 24 h TTL, no sender fields. Decide again whether keeping conversation turns is acceptable for the new users, and apply the Firestore TTL policy.
- [ ] **Move the videos to Google Drive** (D15). GitHub release assets are for development only.
- [ ] **Worker notice and AI disclosure** before employees use it, as the project's out-of-scope note requires.
- [ ] Widen the Chat app visibility and `ALLOWED_USERS` deliberately, never by default.

## Never commit these

- `.env` and any file holding a secret value (`THREAD_KEY_SECRET`, `MERIDIAN_API_KEY`, `ANTHROPIC_API_KEY`).
- The bot service-account key file.
- The Meridian credentials file or anything copied from `~/.claude`.
- Real user ids, names or e-mail addresses, in code, tests, fixtures or documentation. Use `example.invalid` addresses.
