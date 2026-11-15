#!/usr/bin/env bash
# The one laptop command that refreshes the hosted index (D-06, D-07, D-08).
#
#   1. build the sync image
#   2. upload-videos: the Guides videos to the private video bucket, by content hash (D-16, D-17);
#      skipped with --local-only or without PROJECT_ID
#   3. run: handbook and Guides in, index.db out, no network, read-only sources; with videos
#      uploaded, the video links point at the bucket
#   4. publish: upload the index to the private bucket (db object first, pointer last)
#   5. only after a new publish: force a new mcp-server revision so the next request
#      cold-starts on the new index
#
# Nothing here prints file contents, credentials or the credentials path: only step names, build
# ids and the sync report (counts and ids).
#
# Credentials (WR-03): the owner's gcloud login (long-lived refresh token) is mounted only into
# the digest-pinned google/cloud-sdk containers that mint tokens (one for sa-publisher, one for the
# owner's own Cloud Run steps, which then run on a one-hour token without the login). The sync image, which runs third-party
# Python packages, only ever sees a one-hour access token of the sa-publisher service account
# (write access to the index and videos buckets and nothing else), minted right before the step
# that needs it and mounted read-only as GCS_ACCESS_TOKEN_FILE. The owner needs
# roles/iam.serviceAccountTokenCreator on sa-publisher (deploy/cloudrun/bootstrap.sh grants it).
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
#   VIDEO_BUCKET       private video bucket (default <PROJECT_ID>-ai-buddy-videos)
#   EXTRA_VIDEOS_DIR   second directory searched for the README mp4 files (default ./.cache/videos,
#                      filled with `gh release download videos --repo <owner>/Guides --dir .cache/videos`;
#                      skipped when it does not exist). The Guides tree's own videos/ is always searched.
#
# --local-only stops after the local sync: no bucket call, no gcloud call, no video upload (the
# local index keeps the README video URLs).

set -euo pipefail

IMAGE_NAME="ai-buddy-sync:laptop"
# Pinned by digest (docker buildx imagetools inspect google/cloud-sdk:592.0.0-emulators): this image
# is what sees the owner's gcloud login, and only to mint a token.
GCLOUD_IMAGE="google/cloud-sdk:592.0.0-emulators@sha256:808708b26bdf6705e2b42ed48ab53ad4abe0ce171ec8e78074669d28f5cb8dcc"
REGION="europe-west8"
SERVICE="mcp-server"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { echo "[sync-and-publish] $*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

# Reads "<percent>,<latestRevision>" lines (gcloud's flattened spec.traffic) on stdin and prints
# "latest" when exactly one target serves and it is latestRevision at 100, else "pinned". Fails when
# nothing serves or a percent is not a number, so an unreadable describe never passes as latest.
traffic_mode() {
  local percent latest serving=0 latest_full=0
  while IFS=, read -r percent latest; do
    [[ -n "${percent}${latest}" ]] || continue
    percent="${percent:-0}"
    [[ "${percent}" =~ ^[0-9]+$ ]] || return 1
    ((percent > 0)) || continue
    serving=$((serving + 1))
    if [[ "${percent}" == 100 && "${latest}" == True ]]; then latest_full=1; fi
  done
  ((serving > 0)) || return 1
  if ((serving == 1 && latest_full == 1)); then echo latest; else echo pinned; fi
}

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
EXTRA_VIDEOS_DIR="${EXTRA_VIDEOS_DIR:-${ROOT_DIR}/.cache/videos}"

# Docker bind mounts need absolute paths.
HANDBOOK_SRC_DIR="$(cd "${HANDBOOK_SRC_DIR}" && pwd)"
GUIDES_SRC_DIR="$(cd "${GUIDES_SRC_DIR}" && pwd)"
mkdir -p "${ARTIFACTS_DIR}" "${ROOT_DIR}/.cache"
ARTIFACTS_DIR="$(cd "${ARTIFACTS_DIR}" && pwd)"

# The container runs as the host user with HOME=/tmp, so the artifact and cache directories stay
# owned by the host user and writable.
HOST_USER=(--user "$(id -u):$(id -g)" -e HOME=/tmp)

# Short-lived access tokens live in a private temp directory (mode 700, files mode 600) that is
# removed on every exit path. A token is never printed.
TOKEN_DIR=""
cleanup() { [[ -z "${TOKEN_DIR}" ]] || rm -rf "${TOKEN_DIR}"; }
trap cleanup EXIT

# Mint a one-hour access token of sa-publisher into ${TOKEN_DIR}/publisher. The only container that
# sees the gcloud login is this one, run from the pinned gcloud image; its stdout goes to the file.
mint_publisher_token() {
  local token_file="${TOKEN_DIR}/publisher"
  if ! (umask 077 && docker run --rm "${HOST_USER[@]}" \
    -e CLOUDSDK_CONFIG=/gcloud -v "${HOME}/.config/gcloud:/gcloud" "${GCLOUD_IMAGE}" \
    gcloud auth print-access-token --impersonate-service-account="${PUBLISHER_SA}" \
    >"${token_file}" 2>/dev/null); then
    fail "could not mint a token for the publisher service account; the owner needs roles/iam.serviceAccountTokenCreator on it (rerun deploy/cloudrun/bootstrap.sh once) and a gcloud login"
  fi
  chmod 600 "${token_file}"
  [[ -s "${token_file}" ]] || fail "the minted publisher token is empty"
}

# Mint a one-hour access token of the owner into ${TOKEN_DIR}/owner, for the Cloud Run steps. Same
# rule as above: the gcloud login is mounted into this minting container only.
mint_owner_token() {
  local token_file="${TOKEN_DIR}/owner"
  if ! (umask 077 && docker run --rm "${HOST_USER[@]}" \
    -e CLOUDSDK_CONFIG=/gcloud -v "${HOME}/.config/gcloud:/gcloud" "${GCLOUD_IMAGE}" \
    gcloud auth print-access-token >"${token_file}" 2>/dev/null); then
    fail "could not mint an access token for the owner; run gcloud auth login"
  fi
  chmod 600 "${token_file}"
  [[ -s "${token_file}" ]] || fail "the minted owner token is empty"
}

# Bucket steps (video upload now, publish later) need a project and credentials: check both before
# the first one, so a typo fails before any bucket call.
BUCKET_STEPS=false
VIDEO_BUCKET="${VIDEO_BUCKET:-}"
if [[ "${LOCAL_ONLY}" != "true" && -n "${PROJECT_ID}" ]]; then
  BUCKET_STEPS=true
  [[ "${PROJECT_ID}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || fail "PROJECT_ID is not a GCP project id"
  [[ -d "${HOME}/.config/gcloud" ]] || fail "no gcloud configuration for this user; run gcloud auth login"
  PUBLISHER_SA="sa-publisher@${PROJECT_ID}.iam.gserviceaccount.com"
  TOKEN_DIR="$(mktemp -d)"
  chmod 700 "${TOKEN_DIR}"
  VIDEO_BUCKET="${VIDEO_BUCKET:-${PROJECT_ID}-ai-buddy-videos}"
  [[ "${VIDEO_BUCKET}" =~ ^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]] || fail "VIDEO_BUCKET is not a bucket name"
else
  # No upload step runs, so no index link may point at the video bucket (T-04-44).
  VIDEO_BUCKET=""
fi

log "Building sync image: ${IMAGE_NAME} ..."
docker build --target sync -t "${IMAGE_NAME}" "${ROOT_DIR}"

if [[ -n "${VIDEO_BUCKET}" ]]; then
  # Every mp4 named in the Guides README must exist locally, or this step (and the whole command)
  # fails before the index is built. The token file is mounted into this container only.
  log "Uploading the Guides videos to the video bucket ..."
  VIDEO_MOUNTS=(-v "${GUIDES_SRC_DIR}:/guides-src:ro")
  VIDEO_ARGS=(--guides-dir /guides-src --videos-dir /guides-src/videos)
  if [[ -d "${EXTRA_VIDEOS_DIR}" ]]; then
    EXTRA_VIDEOS_DIR="$(cd "${EXTRA_VIDEOS_DIR}" && pwd)"
    VIDEO_MOUNTS+=(-v "${EXTRA_VIDEOS_DIR}:/videos-extra:ro")
    VIDEO_ARGS+=(--videos-dir /videos-extra)
  else
    log "no extra videos directory; searching the Guides tree only"
  fi
  mint_publisher_token
  if ! UPLOAD_OUT="$(docker run --rm \
    "${HOST_USER[@]}" \
    "${VIDEO_MOUNTS[@]}" \
    -v "${TOKEN_DIR}/publisher:/run/gcs-token:ro" \
    -e GCS_ACCESS_TOKEN_FILE=/run/gcs-token \
    -e GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" \
    -e VIDEO_BUCKET="${VIDEO_BUCKET}" \
    "${IMAGE_NAME}" upload-videos "${VIDEO_ARGS[@]}")"; then
    fail "video upload failed; no index was built or published by this run"
  fi
  [[ "${UPLOAD_OUT}" =~ ^uploaded=[0-9]+\ unchanged=[0-9]+$ ]] || fail "upload-videos printed an unexpected line"
  log "videos ${UPLOAD_OUT}"
fi

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
  -e VIDEO_BUCKET="${VIDEO_BUCKET}" \
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
ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-${PROJECT_ID}-ai-buddy-index}"

log "Publishing the index to the private bucket ..."
# A fresh token (the upload step may have been long), mounted read-only into this container only,
# never into the sync run.
mint_publisher_token
if ! PUBLISH_OUT="$(docker run --rm \
  "${HOST_USER[@]}" \
  -v "${ARTIFACTS_DIR}:/artifacts:ro" \
  -v "${TOKEN_DIR}/publisher:/run/gcs-token:ro" \
  -e GCS_ACCESS_TOKEN_FILE=/run/gcs-token \
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

# The Cloud Run steps run on the owner's one-hour token; the gcloud login itself is not mounted, and
# the throwaway CLOUDSDK_CONFIG inside the container is discarded with it.
mint_owner_token
GCLOUD=(docker run --rm "${HOST_USER[@]}" -e CLOUDSDK_CONFIG=/tmp/gcloud -v "${TOKEN_DIR}/owner:/run/owner-token:ro" "${GCLOUD_IMAGE}" gcloud --access-token-file=/run/owner-token)

# The first publish happens before the first deploy: with no service there is nothing to refresh.
if ! DESCRIBE_ERR="$("${GCLOUD[@]}" run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(metadata.name)' 2>&1 >/dev/null)"; then
  if grep -qiE 'not.?found|cannot find service' <<<"${DESCRIBE_ERR}"; then
    log "${SERVICE} not deployed yet; the first CI deploy will load this index"
    exit 0
  fi
  echo "${DESCRIBE_ERR}" >&2
  fail "could not look up ${SERVICE}; the index is published but no new revision was created"
fi

# Traffic mode guard (04-22): a staged CI deploy pins traffic to a named revision until its checks pass. A
# forced revision created then would take no traffic, so the new index would never load. Only
# latest-revision mode (one target at 100% with latestRevision: true) lets the forced revision serve.
# gcloud flattens spec.traffic into one "<percent>,<latestRevision>" line per target (a 0% tagged
# target has an empty percent); bash reads them, since the cloud-sdk image ships no python3. The
# lines are never printed.
TRAFFIC_UNREADABLE="could not read the traffic of ${SERVICE}; the index is published but no new revision was created"
TRAFFIC_LINES="$("${GCLOUD[@]}" run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --flatten spec.traffic --format 'csv[no-heading](spec.traffic.percent,spec.traffic.latestRevision)' 2>/dev/null)" || fail "${TRAFFIC_UNREADABLE}"
TRAFFIC_MODE="$(traffic_mode <<<"${TRAFFIC_LINES}")" || fail "${TRAFFIC_UNREADABLE}"
if [[ "${TRAFFIC_MODE}" != "latest" ]]; then
  fail "${SERVICE} traffic is pinned to a named revision (a staged deploy that did not finish); the index is already published and the next successful ${SERVICE} deploy will load it"
fi

# The revision name: CI names its revisions <service>-r<run id>-<attempt>, so a publish uses its own
# prefix p, the build part and the epoch seconds of this run. A second publish of the same build id
# (the re-publish after an index-object repair) therefore gets a new name instead of an existing one.
BUILD_PART="$(tr 'A-Z_' 'a-z-' <<<"${BUILD_ID}")"
BUILD_PART="${BUILD_PART:0:32}"
while [[ "${BUILD_PART}" == *- ]]; do BUILD_PART="${BUILD_PART%-}"; done
REVISION_SUFFIX="p${BUILD_PART}-$(date -u +%s)"
[[ "${REVISION_SUFFIX}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || fail "the revision suffix is not a valid name part"
if ((${#REVISION_SUFFIX} > 44)); then fail "the revision suffix is longer than 44 characters"; fi

log "Forcing a new ${SERVICE} revision so the next request loads build ${BUILD_ID} ..."
if ! "${GCLOUD[@]}" run services update "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --revision-suffix "${REVISION_SUFFIX}" --update-env-vars INDEX_BUILD_ID="${BUILD_ID}" --quiet >/dev/null; then
  fail "the revision update failed; the index is published, rerun after fixing the error above"
fi
log "${SERVICE} now serves build_id=${BUILD_ID} from its next cold start"
