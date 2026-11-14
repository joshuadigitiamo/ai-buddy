#!/usr/bin/env bash
# Offline end-to-end run of the sync image over the repository fixtures.
#
# Builds the `sync` stage, then runs it with no network, the fixture handbook and a throwaway
# git copy of the fixture Guides mounted read-only, and a temporary artifact directory. Fails
# unless index.db and index.manifest.json appear there. No private data is read or written.
#
# Usage:
#   scripts/sync-image-smoke.sh

set -euo pipefail

IMAGE_NAME="ai-buddy-sync:smoke"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { echo "[sync-image-smoke] $*"; }

WORK_DIR="$(mktemp -d)"
cleanup() {
  # The container writes the artifact directory as uid 10001, so remove it from a container
  # that runs as that uid's owner (root) instead of failing on host permissions.
  docker run --rm --network none -v "${WORK_DIR}:/work" --entrypoint rm "${IMAGE_NAME}" -rf /work/artifacts \
    >/dev/null 2>&1 || true
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

log "Building sync image: ${IMAGE_NAME} ..."
docker build --target sync -t "${IMAGE_NAME}" "${ROOT_DIR}"

log "Creating a fixture Guides git repository ..."
GUIDES_DIR="${WORK_DIR}/guides"
mkdir -p "${GUIDES_DIR}"
cp -R "${ROOT_DIR}/tests/fixtures/guides_repo/." "${GUIDES_DIR}/"
git -C "${GUIDES_DIR}" init -q -b master
git -C "${GUIDES_DIR}" add -A
git -C "${GUIDES_DIR}" \
  -c user.name=smoke -c user.email=smoke@example.invalid \
  commit -q -m "fixture guides"

ARTIFACT_DIR="${WORK_DIR}/artifacts"
mkdir -p "${ARTIFACT_DIR}"
chmod 777 "${ARTIFACT_DIR}"

log "Running sync with no network ..."
docker run --rm \
  --network none \
  -v "${ROOT_DIR}/tests/fixtures/handbook:/handbook:ro" \
  -v "${GUIDES_DIR}:/guides-src:ro" \
  -v "${ARTIFACT_DIR}:/artifacts" \
  -e HANDBOOK_DIR=/handbook \
  -e GUIDES_REPO_URL=/guides-src \
  -e GUIDES_CHECKOUT_DIR=/app/.cache/guides \
  -e ARTIFACT_DIR=/artifacts \
  -e REDACT_PAGE_FILES=04-rete-ospiti.md \
  "${IMAGE_NAME}" run

for name in index.db index.manifest.json; do
  [[ -s "${ARTIFACT_DIR}/${name}" ]] || { log "ERROR: ${name} missing or empty in the artifact directory" >&2; exit 1; }
done
log "index.db written"
