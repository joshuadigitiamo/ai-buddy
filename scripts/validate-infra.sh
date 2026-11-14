#!/usr/bin/env bash
# Offline-from-the-cluster validation of the infrastructure files (INFRA-03) and of the CI files.
#
# For deploy/k8s/base and every directory under deploy/k8s/overlays: `kubectl kustomize` builds the
# manifests and kubeconform (pinned image) validates them against the Kubernetes 1.37.0 schemas in
# strict mode (unknown fields fail). Then actionlint (pinned image) lints .github/workflows and the
# sync image stage is built. Needs kubectl and Docker; needs no cluster and no secret. Fetching the
# schemas and the base images needs network access. CI runs this script in the validate job.
#
# Usage:
#   scripts/validate-infra.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
KUBECONFORM_IMAGE="ghcr.io/yannh/kubeconform:v0.8.0"
ACTIONLINT_IMAGE="rhysd/actionlint:1.7.12"

log() { echo "[validate-infra] $*"; }
die() { echo "[validate-infra] ERROR: $*" >&2; exit 1; }

command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
command -v docker >/dev/null 2>&1 || die "docker is required"

cd "${ROOT_DIR}"
BUILD_FILE="$(mktemp)"
trap 'rm -f "${BUILD_FILE}"' EXIT

failed=0

# Build one kustomization and validate the result. kubeconform reads the manifests from stdin.
validate_kustomization() {
  local directory="$1"
  log "kubectl kustomize ${directory} | kubeconform -strict (Kubernetes 1.37.0)"
  if ! kubectl kustomize "${directory}" > "${BUILD_FILE}"; then
    echo "[validate-infra] kustomize build failed for ${directory}" >&2
    failed=1
    return
  fi
  if ! docker run --rm -i "${KUBECONFORM_IMAGE}" -strict -summary \
      -kubernetes-version 1.37.0 - < "${BUILD_FILE}"; then
    echo "[validate-infra] kubeconform rejected ${directory}" >&2
    failed=1
  fi
}

validate_kustomization deploy/k8s/base
for overlay in deploy/k8s/overlays/*/; do
  validate_kustomization "${overlay%/}"
done

# ---- Workflow lint and the sync image build (04-09, D-02).

# actionlint reads .github/workflows (and the expressions and shell inside them) and fails on any finding.
log "actionlint over .github/workflows"
if ! docker run --rm -v "${ROOT_DIR}:/repo" -w /repo "${ACTIONLINT_IMAGE}"; then
  echo "[validate-infra] actionlint reported findings" >&2
  failed=1
fi

# The sync image is only ever built on a laptop and in CI (D-09); building it here keeps its stage honest.
log "docker build --target sync"
if ! docker build --target sync -t ai-buddy-sync:validate .; then
  echo "[validate-infra] the sync image failed to build" >&2
  failed=1
fi

[[ "${failed}" -eq 0 ]] || die "validation failed"
log "infra validation ok"
