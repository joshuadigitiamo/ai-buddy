# Kubernetes (kind) deployment

Kustomize manifests that run the whole system on a local [kind](https://kind.sigs.k8s.io/)
cluster from the same images as Docker Compose: the MCP server, the chat bot with Meridian as a
native sidecar, the Firestore and Pub/Sub emulators and a `pubsub-init` Job. kind is a local
developer target only; it does not run in CI. CI and `scripts/validate-infra.sh` check the
manifests with `kubeconform`, which needs no cluster.

```
deploy/k8s/
  kind-config.yaml             cluster template (read-only artifact mount)
  base/                        Deployments, Services, Job; fail closed on their own
  overlays/dev/                namespace, local environment, hostPath artifacts, image tags
```

## Run it

```bash
scripts/kind-up.sh      # kind v0.33.0 into .cache/bin (sha256 checked), cluster, images, Secrets, overlay
scripts/kind-smoke.sh   # in-cluster /health plus one cited guides_search call; last line: kind smoke ok
scripts/validate-infra.sh   # kubectl kustomize + kubeconform -strict for base and every overlay
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `KIND_CLUSTER` | `ai-buddy` | cluster name; the kubeconfig is `.cache/kubeconfig-<name>` (`~/.kube/config` is not touched) |
| `ARTIFACTS_DIR` | `./artifacts` | host directory holding `index.db`; mounted read-only at `/artifacts` |
| `MERIDIAN_OAUTH_TOKEN` | from `.env` | **Secret.** Meridian's `claude setup-token` token, the same one Compose uses; read from the environment, else from the `MERIDIAN_OAUTH_TOKEN=` line of `.env` |
| `ENV_FILE` | `./.env` | file read for `MERIDIAN_OAUTH_TOKEN` when the environment does not set it (not sourced) |
| `SMOKE_QUERY` | `MCP` | query for the `guides_search` call in the smoke |

`kind-up.sh` fails with a clear message when `MERIDIAN_OAUTH_TOKEN` is missing (checked first,
before any download or cluster work; the message names the variable, never its value) or when
`ARTIFACTS_DIR/index.db` is missing (run the sync once, from the laptop or from the Compose `sync`
service). Tear down with `.cache/bin/kind delete cluster --name ai-buddy`.

## Environment contract per target

The same images run on three hosts; only the environment differs.

| Variable | Compose | kind dev overlay | Cloud Run |
|----------|---------|------------------|-----------|
| `ARTIFACT_STORE` | local | local (hostPath `/artifacts`) | gcs |
| `DEPLOY_ENV` | local | local | production |
| `AUTH_MODE` (server) / `MCP_AUTH` (bot) | off / none | off / none | on / google_id_token |
| `INTAKE` | pubsub | pubsub | http |
| `CHAT_API` | recording | recording | google |
| `LLM_BACKEND` / `LLM_BASE_URL` | stub LLM (profiles `live` and `eval`: Meridian) | meridian, `http://localhost:3456` (oauthToken profile) | meridian, `http://localhost:3456` |
| `MCP_URL` | `http://mcp-server:8000/mcp` | `http://mcp-server:8000/mcp` | public https URL |
| `MCP_ALLOWED_HOSTS` | mcp-server | mcp-server | unset |

`base` sets none of the local-only knobs (`DEPLOY_ENV=local`, `AUTH_MODE=off`, `MCP_AUTH=none`):
the server and the bot refuse to start without an overlay that supplies them. The dev overlay sets
them in the ConfigMaps `mcp-server-local` and `chat-bot-local`.

## Credentials

- No Secret object is stored in git, and no manifest holds a secret value; only the Secret names
  appear (`meridian-credentials`, `bot-secrets`). A unit test enforces this.
- Meridian logs in the same way as in Compose: `kind-up.sh` turns `MERIDIAN_OAUTH_TOKEN` into
  the `MERIDIAN_PROFILES` value `[{"id":"local","oauthToken":"…"}]` and stores it in the Secret
  `meridian-credentials`; the Meridian sidecar reads that key as an environment variable, with
  `MERIDIAN_DEFAULT_PROFILE=local`. The JSON is piped into `kubectl`, so the token is never
  printed, never on a command line and never written to disk. The Docker volume
  `meridian-claude` is not used by kind: in Compose it holds only Meridian's SDK session state,
  and in kind an `emptyDir` plays that role.
- The token comes from `claude setup-token` and has no refresh token, so nothing rotates and
  the kind copy cannot log out the host Claude Code CLI or Compose. Meridian in kind also runs
  with `MERIDIAN_CREDENTIALS_READONLY=1`, so it writes no login state. To mint or renew the
  token (once a year), follow "Give Meridian its own token" in `services/chat_bot/README.md`:
  run `claude setup-token` on the host, put the token in `.env` as `MERIDIAN_OAUTH_TOKEN=<token>`,
  then re-run `kind-up.sh` and `kubectl -n ai-buddy rollout restart deployment/chat-bot`.
- `bot-secrets` (`THREAD_KEY_SECRET`, `MERIDIAN_API_KEY`) holds random values generated on first
  run and kept on re-runs. It is created without printing the values.

## Probes and sidecar

- `mcp-server` readiness and liveness call `/health` with `Host: mcp-server`. kubelet would send
  the pod IP, which the server's Host guard rejects; the dev overlay lists `mcp-server` in the
  server's allow-list.
- The chat bot has no HTTP port in Pub/Sub intake mode, so it has no HTTP probe.
- Meridian is an init container with `restartPolicy: Always` (native sidecar) and a startup
  probe, so the bot starts only after Meridian answers. It listens on `127.0.0.1` only; kubelet
  httpGet probes target the pod IP, so its probes run inside the container with `node` against
  `/health` (start-up, readiness) and `/livez` (liveness).

## Pod Security exception

The `ai-buddy` namespace is labelled `warn` and `audit` at the `restricted` Pod Security level and
does not enforce one. Two things would be rejected by enforcement and are accepted for local
use: the artifacts `hostPath` volume (baseline and restricted both forbid it; D-10 asks for it in
kind) and the emulator containers, which run as root. The app containers (`mcp-server`,
`chat-bot`) and the Job still run with restricted-style settings: uid 10001, `runAsNonRoot`, no
privilege escalation, all capabilities dropped, a read-only root filesystem and the default
seccomp profile. `base` has no Ingress; access is in-cluster only.
