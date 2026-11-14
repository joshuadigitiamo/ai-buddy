#!/usr/bin/env bash
# The one laptop command that refreshes the hosted index (D-06, D-07, D-08).
#
#   1. build the sync image
#   2. run: handbook and Guides in, index.db out, no network, read-only sources
#   3. publish: upload the index to the private bucket (db object first, pointer last)
#   4. only after a new publish: force a new mcp-server revision so the next request
#      cold-starts on the new index
#
# Nothing here prints file contents, credentials or the credentials path: only step names, build
# ids and the sync report (counts and ids).
#
# Usage:
#   HANDBOOK_SRC_DIR=... GUIDES_SRC_DIR=... REDACT_PAGE_FILES=... PROJECT_ID=... \
#     scripts/sync-and-publish.sh [--local-only]
#
# Environment:
#   HANDBOOK_SRC_DIR   handbook folder (required, mounted read-only)
#   GUIDES_SRC_DIR     local Guides git checkout (required, mounted read-only)
#   REDACT_PAGE_FILES  comma-separated handbook page files to drop (required, as for `run`)
#   ARTIFACTS_DIR      where index.db is written (default ./artifacts)
#   PROJECT_ID         GCP project id; unset means stop after the local sync
#   ARTIFACT_BUCKET    index bucket (default <PROJECT_ID>-ai-buddy-index)
#   ARTIFACT_PREFIX    object prefix (default index/)
#   ADC_FILE           user credentials file (default ~/.config/gcloud/application_default_credentials.json)
#
# --local-only stops after the local sync: no bucket call, no gcloud call.

set -euo pipefail

IMAGE_NAME="ai-buddy-sync:laptop"
GCLOUD_IMAGE="google/cloud-sdk:592.0.0-emulators"
REGION="europe-west8"
SERVICE="mcp-server"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { echo "[sync-and-publish] $*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

usage() {
  echo "Usage: $0 [--local-only]" >&2
  exit 2
}

LOCAL_ONLY=false
for arg in "$@"; do
  case "${arg}" in
    --local-only) LOCAL_ONLY=true ;;
    *) usage ;;
  esac
done

for name in HANDBOOK_SRC_DIR GUIDES_SRC_DIR REDACT_PAGE_FILES; do
  [[ -n "${!name:-}" ]] || fail "${name} is not set"
done
[[ -d "${HANDBOOK_SRC_DIR}" ]] || fail "HANDBOOK_SRC_DIR is not a directory"
[[ -d "${GUIDES_SRC_DIR}" ]] || fail "GUIDES_SRC_DIR is not a directory"

ARTIFACTS_DIR="${ARTIFACTS_DIR:-${ROOT_DIR}/artifacts}"
PROJECT_ID="${PROJECT_ID:-}"
ARTIFACT_PREFIX="${ARTIFACT_PREFIX-index/}"
ADC_FILE="${ADC_FILE:-${HOME}/.config/gcloud/application_default_credentials.json}"

# Docker bind mounts need absolute paths.
HANDBOOK_SRC_DIR="$(cd "${HANDBOOK_SRC_DIR}" && pwd)"
GUIDES_SRC_DIR="$(cd "${GUIDES_SRC_DIR}" && pwd)"
mkdir -p "${ARTIFACTS_DIR}" "${ROOT_DIR}/.cache"
ARTIFACTS_DIR="$(cd "${ARTIFACTS_DIR}" && pwd)"

# The container runs as the host user with HOME=/tmp, so the artifact and cache directories stay
# owned by the host user and writable.
HOST_USER=(--user "$(id -u):$(id -g)" -e HOME=/tmp)

log "Building sync image: ${IMAGE_NAME} ..."
docker build --target sync -t "${IMAGE_NAME}" "${ROOT_DIR}"

log "Syncing handbook and Guides with no network ..."
docker run --rm \
  --network none \
  "${HOST_USER[@]}" \
  -v "${HANDBOOK_SRC_DIR}:/handbook:ro" \
  -v "${GUIDES_SRC_DIR}:/guides-src:ro" \
  -v "${ARTIFACTS_DIR}:/artifacts" \
  -v "${ROOT_DIR}/.cache:/app/.cache" \
  -e HANDBOOK_DIR=/handbook \
  -e GUIDES_REPO_URL=/guides-src \
  -e GUIDES_CHECKOUT_DIR=/app/.cache/guides \
  -e ARTIFACT_DIR=/artifacts \
  -e REDACT_PAGE_FILES \
  "${IMAGE_NAME}" run

for name in index.db index.manifest.json; do
  [[ -s "${ARTIFACTS_DIR}/${name}" ]] || fail "${name} is missing or empty after the sync"
done

if [[ "${LOCAL_ONLY}" == "true" ]]; then
  log "--local-only: stopping after the local sync; nothing was published"
  exit 0
fi
if [[ -z "${PROJECT_ID}" ]]; then
  log "PROJECT_ID is not set: stopping after the local sync; nothing was published"
  exit 0
fi
[[ "${PROJECT_ID}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || fail "PROJECT_ID is not a GCP project id"
ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-${PROJECT_ID}-ai-buddy-index}"
[[ -r "${ADC_FILE}" ]] || fail "ADC_FILE is not a readable file; run gcloud auth application-default login"

log "Publishing the index to the private bucket ..."
# The credentials file is mounted read-only into this container only, never into the sync run.
if ! PUBLISH_OUT="$(docker run --rm \
  "${HOST_USER[@]}" \
  -v "${ARTIFACTS_DIR}:/artifacts:ro" \
  -v "${ADC_FILE}:/adc.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc.json \
  -e GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" \
  -e ARTIFACT_DIR=/artifacts \
  -e ARTIFACT_BUCKET="${ARTIFACT_BUCKET}" \
  -e ARTIFACT_PREFIX="${ARTIFACT_PREFIX}" \
  "${IMAGE_NAME}" publish)"; then
  fail "publish failed; the bucket pointer was not changed by this run"
fi

PUBLISH_STATUS="${PUBLISH_OUT%% *}"
BUILD_ID="${PUBLISH_OUT##*build_id=}"
[[ "${PUBLISH_OUT}" == "${PUBLISH_STATUS} build_id=${BUILD_ID}" ]] || fail "publish printed an unexpected line"
[[ "${BUILD_ID}" =~ ^[A-Za-z0-9_-]{1,128}$ ]] || fail "publish returned an invalid build id"

case "${PUBLISH_STATUS}" in
  unchanged)
    log "unchanged build_id=${BUILD_ID}: the bucket already holds this index; no new revision"
    exit 0
    ;;
  published) log "published build_id=${BUILD_ID}" ;;
  *) fail "publish returned an unknown status" ;;
esac

[[ -d "${HOME}/.config/gcloud" ]] || fail "no gcloud configuration for this user; run gcloud auth login"
GCLOUD=(docker run --rm "${HOST_USER[@]}" -e CLOUDSDK_CONFIG=/gcloud -v "${HOME}/.config/gcloud:/gcloud" "${GCLOUD_IMAGE}" gcloud)

# The first publish happens before the first deploy: with no service there is nothing to refresh.
if ! DESCRIBE_ERR="$("${GCLOUD[@]}" run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(metadata.name)' 2>&1 >/dev/null)"; then
  if grep -qiE 'not.?found|cannot find service' <<<"${DESCRIBE_ERR}"; then
    log "${SERVICE} not deployed yet; the first CI deploy will load this index"
    exit 0
  fi
  echo "${DESCRIBE_ERR}" >&2
  fail "could not look up ${SERVICE}; the index is published but no new revision was created"
fi

log "Forcing a new ${SERVICE} revision so the next request loads build ${BUILD_ID} ..."
if ! "${GCLOUD[@]}" run services update "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --update-env-vars INDEX_BUILD_ID="${BUILD_ID}" --quiet >/dev/null; then
  fail "the revision update failed; the index is published, rerun after fixing the error above"
fi
log "${SERVICE} now serves build_id=${BUILD_ID} from its next cold start"
