#!/usr/bin/env bash
# Render a Cloud Run service template into a deployable file (INFRA-04).
#
# The templates under deploy/cloudrun carry ${PLACEHOLDER} markers instead of project identifiers, so
# the public repository holds no project id, project number or personal id. This script fills them
# from environment variables, for CI (GitHub repository variables) and for a laptop alike.
#
# Usage:
#   PROJECT_ID=... PROJECT_NUMBER=... IMAGE_TAG=... GOOGLE_CLIENT_ID=... GUIDES_WEB_BASE=... \
#   CHAT_JWT_ISSUER_EMAIL=... VIDEO_THUMBNAIL_URL=... HELP_COMMAND_ID=... \
#     scripts/render-cloudrun.sh <mcp-server|chat-bot> <output-file>
#
# MERIDIAN_TAG defaults to the commit in deploy/meridian.version (D-14). Only variable names are
# printed, never values, and the rendered file is never printed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { echo "[render-cloudrun] $*"; }
die() { echo "[render-cloudrun] ERROR: $*" >&2; exit 1; }

usage() {
  echo "Usage: $0 <mcp-server|chat-bot> <output-file>" >&2
  exit 1
}

[[ $# -eq 2 ]] || usage
SERVICE="$1"
OUTPUT="$2"

case "${SERVICE}" in
  mcp-server | chat-bot) ;;
  *) usage ;;
esac

TEMPLATE="${ROOT_DIR}/deploy/cloudrun/${SERVICE}.yaml"
[[ -f "${TEMPLATE}" ]] || die "template not found: deploy/cloudrun/${SERVICE}.yaml"

command -v envsubst >/dev/null 2>&1 || die "envsubst is required (package gettext-base)"

if [[ -z "${MERIDIAN_TAG:-}" ]]; then
  [[ -f "${ROOT_DIR}/deploy/meridian.version" ]] || die "deploy/meridian.version is missing"
  MERIDIAN_TAG="$(tr -d '[:space:]' < "${ROOT_DIR}/deploy/meridian.version")"
fi
export MERIDIAN_TAG

# The fixed list: every variable must be set and non-empty for every service, and only these are
# substituted, so a stray ${...} in a template is never silently replaced by an empty string.
VARIABLES=(
  PROJECT_ID
  PROJECT_NUMBER
  IMAGE_TAG
  MERIDIAN_TAG
  GOOGLE_CLIENT_ID
  GUIDES_WEB_BASE
  CHAT_JWT_ISSUER_EMAIL
  VIDEO_THUMBNAIL_URL
  HELP_COMMAND_ID
)

missing=()
for name in "${VARIABLES[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("${name}")
  fi
done
if ((${#missing[@]} > 0)); then
  die "missing environment variables: ${missing[*]}"
fi

# The values land inside double-quoted YAML scalars: refuse anything that could end the scalar or
# start another substitution. The value is never printed; only the variable name is.
for name in "${VARIABLES[@]}"; do
  value="${!name}"
  case "${value}" in
    *'"'* | *'\'* | *'$'* | *$'\n'* | *$'\r'*)
      die "${name} contains a character that is not allowed in a rendered value"
      ;;
  esac
done

SUBSTITUTIONS=""
for name in "${VARIABLES[@]}"; do
  SUBSTITUTIONS+="\${${name}} "
  export "${name}"
done

RENDERED="$(mktemp)"
trap 'rm -f "${RENDERED}"' EXIT

envsubst "${SUBSTITUTIONS}" < "${TEMPLATE}" > "${RENDERED}"

if grep -q '\${' "${RENDERED}"; then
  leftover="$(grep -o '\${[A-Za-z_][A-Za-z0-9_]*}' "${RENDERED}" | sort -u | tr '\n' ' ')"
  die "unrendered placeholder left in ${SERVICE}: ${leftover:-unknown}"
fi

mkdir -p "$(dirname "${OUTPUT}")"
mv "${RENDERED}" "${OUTPUT}"
trap - EXIT
log "rendered ${SERVICE} to ${OUTPUT}"
