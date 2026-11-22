#!/usr/bin/env bash
# Bring the dev overlay up on a local kind cluster (INFRA-03, ROADMAP criterion 2).
#
# Downloads kind (pinned, sha256-verified) into .cache/bin, creates the cluster, builds and loads
# the images, creates the credentials Secrets imperatively and applies deploy/k8s/overlays/dev.
# No secret value is printed or written to a file in the repository.
#
# Needs: MERIDIAN_OAUTH_TOKEN, the one-year `claude setup-token` token that Compose also uses
# (services/chat_bot/README.md). It is taken from the environment, or else from the
# MERIDIAN_OAUTH_TOKEN= line of .env (ENV_FILE overrides the path; the file is not sourced).
# It reaches the cluster only as the MERIDIAN_PROFILES oauthToken profile in a Secret.
#
# Usage:
#   scripts/kind-up.sh
#   ARTIFACTS_DIR=/path/with/index.db KIND_CLUSTER=ai-buddy scripts/kind-up.sh
#   ENV_FILE=/path/to/.env scripts/kind-up.sh
#
# The cluster uses its own kubeconfig (.cache/kubeconfig-<cluster>), so ~/.kube/config is not
# touched. scripts/kind-smoke.sh reads the same file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

KIND_VERSION="v0.33.0"
NODE_IMAGE="kindest/node:v1.37.0"
KIND_CLUSTER="${KIND_CLUSTER:-ai-buddy}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${ROOT_DIR}/artifacts}"
NAMESPACE="ai-buddy"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-300s}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

BIN_DIR="${ROOT_DIR}/.cache/bin"
KIND_BIN="${BIN_DIR}/kind"
KIND_URL="https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}"
export KUBECONFIG="${ROOT_DIR}/.cache/kubeconfig-${KIND_CLUSTER}"

log() { echo "[kind-up] $*"; }
die() { echo "[kind-up] ERROR: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is required"
command -v kubectl >/dev/null 2>&1 || die "kubectl is required"

# ---- Meridian login: checked before any download or cluster work, value never printed
read_env_file_token() {
  [[ -f "${ENV_FILE}" ]] || return 0
  local line
  line="$(grep -E '^[[:space:]]*(export[[:space:]]+)?MERIDIAN_OAUTH_TOKEN=' "${ENV_FILE}" | tail -n 1 || true)"
  line="${line#*=}"
  line="${line%$'\r'}"
  line="${line#[\"\']}"
  line="${line%[\"\']}"
  printf '%s' "${line}"
}
MERIDIAN_OAUTH_TOKEN="${MERIDIAN_OAUTH_TOKEN:-$(read_env_file_token)}"
[[ -n "${MERIDIAN_OAUTH_TOKEN}" ]] \
  || die "MERIDIAN_OAUTH_TOKEN is not set (environment or ${ENV_FILE#"${ROOT_DIR}"/}); mint it with claude setup-token as services/chat_bot/README.md describes"
# The token goes into a JSON string unescaped, so only token characters are accepted.
[[ "${MERIDIAN_OAUTH_TOKEN}" =~ ^[A-Za-z0-9._~+/=-]+$ ]] \
  || die "MERIDIAN_OAUTH_TOKEN holds characters a claude setup-token token does not (quotes, spaces or backslashes); value not printed"

# ---- kind binary: pinned release, published sha256 checked before the file is made executable
install_kind() {
  if [[ -x "${KIND_BIN}" ]] && "${KIND_BIN}" version 2>/dev/null | grep -q "${KIND_VERSION}"; then
    return
  fi
  log "Downloading kind ${KIND_VERSION} into ${BIN_DIR} ..."
  mkdir -p "${BIN_DIR}"
  rm -f "${BIN_DIR}/kind-linux-amd64" "${BIN_DIR}/kind-linux-amd64.sha256sum"
  curl -fsSL -o "${BIN_DIR}/kind-linux-amd64" "${KIND_URL}/kind-linux-amd64"
  curl -fsSL -o "${BIN_DIR}/kind-linux-amd64.sha256sum" "${KIND_URL}/kind-linux-amd64.sha256sum"
  if ! (cd "${BIN_DIR}" && sha256sum --check --strict kind-linux-amd64.sha256sum); then
    rm -f "${BIN_DIR}/kind-linux-amd64"
    die "sha256 of the kind download does not match the published checksum; file removed"
  fi
  chmod +x "${BIN_DIR}/kind-linux-amd64"
  mv -f "${BIN_DIR}/kind-linux-amd64" "${KIND_BIN}"
}
install_kind

# ---- inputs: the index the server will read (D-10)
[[ -d "${ARTIFACTS_DIR}" ]] || die "ARTIFACTS_DIR ${ARTIFACTS_DIR} is not a directory"
ARTIFACTS_DIR="$(cd "${ARTIFACTS_DIR}" && pwd)"
[[ -f "${ARTIFACTS_DIR}/index.db" ]] \
  || die "no index.db in ${ARTIFACTS_DIR}; run the sync once (laptop sync or the compose sync volume) or set ARTIFACTS_DIR"

# ---- cluster
if "${KIND_BIN}" get clusters 2>/dev/null | grep -qx "${KIND_CLUSTER}"; then
  log "Cluster ${KIND_CLUSTER} already exists"
  "${KIND_BIN}" export kubeconfig --name "${KIND_CLUSTER}" --kubeconfig "${KUBECONFIG}"
else
  log "Creating cluster ${KIND_CLUSTER} (${NODE_IMAGE}) with ${ARTIFACTS_DIR} mounted read-only ..."
  RENDERED="$(mktemp)"
  trap 'rm -f "${RENDERED}"' EXIT
  template="$(cat "${ROOT_DIR}/deploy/k8s/kind-config.yaml")"
  printf '%s\n' "${template//__ARTIFACTS_DIR__/${ARTIFACTS_DIR}}" > "${RENDERED}"
  "${KIND_BIN}" create cluster --name "${KIND_CLUSTER}" --image "${NODE_IMAGE}" \
    --config "${RENDERED}" --kubeconfig "${KUBECONFIG}" --wait 120s
fi

# ---- images: built locally, loaded into the node, never pushed
MERIDIAN_SHA="$(tr -d '[:space:]' < "${ROOT_DIR}/deploy/meridian.version")"
[[ "${MERIDIAN_SHA}" =~ ^[0-9a-f]{40}$ ]] || die "deploy/meridian.version does not hold a 40-character commit"
MERIDIAN_IMAGE="ai-buddy/meridian:${MERIDIAN_SHA}"

log "Building ai-buddy/mcp-server:dev and ai-buddy/chat-bot:dev ..."
docker build --target mcp_server -t ai-buddy/mcp-server:dev "${ROOT_DIR}"
docker build --target chat_bot -t ai-buddy/chat-bot:dev "${ROOT_DIR}"
log "Building ${MERIDIAN_IMAGE} from the pinned commit ..."
docker build -t "${MERIDIAN_IMAGE}" "https://github.com/rynfar/meridian.git#${MERIDIAN_SHA}"
log "Loading images into the cluster ..."
for image in ai-buddy/mcp-server:dev ai-buddy/chat-bot:dev "${MERIDIAN_IMAGE}"; do
  "${KIND_BIN}" load docker-image "${image}" --name "${KIND_CLUSTER}"
done

# ---- namespace and Secrets: created here, never written to a manifest (D-15)
kubectl apply -f "${ROOT_DIR}/deploy/k8s/overlays/dev/namespace.yaml"

# Meridian login, built as in Compose: a MERIDIAN_PROFILES oauthToken profile. The JSON is written
# by the printf builtin into a pipe read by kubectl, so the token is in no argv, log or file.
log "Creating Secret meridian-credentials from MERIDIAN_OAUTH_TOKEN (value not printed) ..."
kubectl create secret generic meridian-credentials -n "${NAMESPACE}" \
    --from-file=MERIDIAN_PROFILES=<(printf '[{"id":"local","oauthToken":"%s"}]' "${MERIDIAN_OAUTH_TOKEN}") \
    --dry-run=client -o yaml \
  | kubectl apply --server-side --force-conflicts -f - >/dev/null

# Bot secrets: random per cluster, kept across re-runs, never printed.
random_secret() { printf '%s' "$(head -c 96 /dev/urandom | base64 -w0 | tr -d '/+=' | cut -c1-48)"; }
if kubectl -n "${NAMESPACE}" get secret bot-secrets >/dev/null 2>&1; then
  log "Secret bot-secrets already exists"
else
  log "Creating Secret bot-secrets (values not printed) ..."
  kubectl create secret generic bot-secrets -n "${NAMESPACE}" \
    --from-file=THREAD_KEY_SECRET=<(random_secret) \
    --from-file=MERIDIAN_API_KEY=<(random_secret) >/dev/null
fi

# ---- workloads
# A Job's pod template is immutable, so a re-run recreates it.
kubectl -n "${NAMESPACE}" delete job pubsub-init --ignore-not-found >/dev/null
log "Applying deploy/k8s/overlays/dev ..."
kubectl apply -k "${ROOT_DIR}/deploy/k8s/overlays/dev"

log "Waiting for rollouts and the pubsub-init Job ..."
for deployment in firestore-emulator pubsub-emulator mcp-server chat-bot; do
  kubectl -n "${NAMESPACE}" rollout status "deployment/${deployment}" --timeout="${ROLLOUT_TIMEOUT}"
done
kubectl -n "${NAMESPACE}" wait --for=condition=complete job/pubsub-init --timeout="${ROLLOUT_TIMEOUT}"

log "kind up ok (cluster ${KIND_CLUSTER}, kubeconfig ${KUBECONFIG#"${ROOT_DIR}"/})"
