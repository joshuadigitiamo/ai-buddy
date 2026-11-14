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
scripts/kind-smoke.sh   # in-cluster /healthz plus one cited guides_search call; last line: kind smoke ok
scripts/validate-infra.sh   # kubectl kustomize + kubeconform -strict for base and every overlay
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `KIND_CLUSTER` | `ai-buddy` | cluster name; the kubeconfig is `.cache/kubeconfig-<name>` (`~/.kube/config` is not touched) |
| `ARTIFACTS_DIR` | `./artifacts` | host directory holding `index.db`; mounted read-only at `/artifacts` |
| `SMOKE_QUERY` | `MCP` | query for the `guides_search` call in the smoke |

`kind-up.sh` fails with a clear message when `ARTIFACTS_DIR/index.db` is missing (run the sync
once, from the laptop or from the Compose `sync` service) or when the Docker volume
`meridian-claude` does not exist. Tear down with `.cache/bin/kind delete cluster --name ai-buddy`.

## Environment contract per target

The same images run on three hosts; only the environment differs.

| Variable | Compose | kind dev overlay | Cloud Run |
|----------|---------|------------------|-----------|
| `ARTIFACT_STORE` | local | local (hostPath `/artifacts`) | gcs |
| `DEPLOY_ENV` | local | local | production |
| `AUTH_MODE` (server) / `MCP_AUTH` (bot) | off / none | off / none | on / google_id_token |
| `INTAKE` | pubsub | pubsub | http |
| `CHAT_API` | recording | recording | google |
| `LLM_BACKEND` / `LLM_BASE_URL` | stub LLM (profile `live`: Meridian) | meridian, `http://localhost:3456` (read-only credentials) | meridian, `http://localhost:3456` |
| `MCP_URL` | `http://mcp-server:8000/mcp` | `http://mcp-server:8000/mcp` | public https URL |
| `MCP_ALLOWED_HOSTS` | mcp-server | mcp-server | unset |

`base` sets none of the local-only knobs (`DEPLOY_ENV=local`, `AUTH_MODE=off`, `MCP_AUTH=none`):
the server and the bot refuse to start without an overlay that supplies them. The dev overlay sets
them in the ConfigMaps `mcp-server-local` and `chat-bot-local`.

## Credentials

- No Secret object is stored in git, and no manifest holds a secret value; only the Secret names
  appear (`meridian-credentials`, `bot-secrets`). A unit test enforces this.
- `kind-up.sh` creates `meridian-credentials` by streaming `.credentials.json` out of the local
  Docker volume `meridian-claude` straight into `kubectl`, so the value is never printed and
  never written to disk. The pod copies it into an `emptyDir` with an init container.
- Meridian in kind runs with `MERIDIAN_CREDENTIALS_READONLY=1`. It never refreshes or writes the
  login, so it cannot invalidate the token chain used by the Compose live profile or Cloud Run
  (04-01 `token_chain`). The access token is only as fresh as the volume: if it has expired, run
  the Compose `live` profile once so its writable Meridian refreshes it, then re-run `kind-up.sh`
  and `kubectl -n ai-buddy rollout restart deployment/chat-bot`.
- `bot-secrets` (`THREAD_KEY_SECRET`, `MERIDIAN_API_KEY`) holds random values generated on first
  run and kept on re-runs. It is created without printing the values.

## Probes and sidecar

- `mcp-server` readiness and liveness call `/healthz` with `Host: mcp-server`. kubelet would send
  the pod IP, which the server's Host guard rejects; the dev overlay lists `mcp-server` in the
  server's allow-list.
- The chat bot has no HTTP port in Pub/Sub intake mode, so it has no HTTP probe.
- Meridian is an init container with `restartPolicy: Always` (native sidecar) and a startup
  probe, so the bot starts only after Meridian answers. It listens on `127.0.0.1` only; kubelet
  httpGet probes target the pod IP, so its probes run inside the container with `node` against
  `/health` (start-up, readiness) and `/livez` (liveness). `/readyz` is not used: it also needs a
  Meridian profile and answers 503 for the single credentials file seeded here.

## Pod Security exception

The `ai-buddy` namespace is labelled `warn` and `audit` at the `restricted` Pod Security level and
does not enforce one. Two things would be rejected by enforcement and are accepted for local
use: the artifacts `hostPath` volume (baseline and restricted both forbid it; D-10 asks for it in
kind) and the emulator containers, which run as root. The app containers (`mcp-server`,
`chat-bot`) and the Job still run with restricted-style settings: uid 10001, `runAsNonRoot`, no
privilege escalation, all capabilities dropped, a read-only root filesystem and the default
seccomp profile. `base` has no Ingress; access is in-cluster only.
