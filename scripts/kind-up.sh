#!/usr/bin/env bash
# Bring the dev overlay up on a local kind cluster (INFRA-03, ROADMAP criterion 2).
#
# Downloads kind (pinned, sha256-verified) into .cache/bin, creates the cluster, builds and loads
# the images, creates the credentials Secrets imperatively and applies deploy/k8s/overlays/dev.
# No secret value is printed or written to a file in the repository.
#
# Usage:
#   scripts/kind-up.sh
#   ARTIFACTS_DIR=/path/with/index.db KIND_CLUSTER=ai-buddy scripts/kind-up.sh
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

BIN_DIR="${ROOT_DIR}/.cache/bin"
KIND_BIN="${BIN_DIR}/kind"
KIND_URL="https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}"
export KUBECONFIG="${ROOT_DIR}/.cache/kubeconfig-${KIND_CLUSTER}"

log() { echo "[kind-up] $*"; }
die() { echo "[kind-up] ERROR: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is required"
command -v kubectl >/dev/null 2>&1 || die "kubectl is required"

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
log "Building ai-buddy/mcp-server:dev ..."
docker build --target mcp_server -t ai-buddy/mcp-server:dev "${ROOT_DIR}"
log "Loading images into the cluster ..."
"${KIND_BIN}" load docker-image ai-buddy/mcp-server:dev --name "${KIND_CLUSTER}"

# ---- workloads
log "Applying deploy/k8s/overlays/dev ..."
kubectl apply -k "${ROOT_DIR}/deploy/k8s/overlays/dev"

log "Waiting for rollouts ..."
kubectl -n "${NAMESPACE}" rollout status deployment/mcp-server --timeout="${ROLLOUT_TIMEOUT}"

log "kind up ok (cluster ${KIND_CLUSTER}, kubeconfig ${KUBECONFIG#"${ROOT_DIR}"/})"
