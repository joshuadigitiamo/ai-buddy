#!/usr/bin/env bash
# Hermetic round trip over docker-compose.yml (INFRA-02, ROADMAP criterion 1).
#
# Builds a throwaway fixture Guides git repo, brings the default compose services up from the
# per-service images (emulators, sync, mcp-server, stub LLM, chat-bot), publishes the legacy DM
# fixture event to the Pub/Sub emulator topic and waits until the recording Chat adapter holds a
# final message that carries "Fonte: Manuale" and "handbook://02-ferie". No real service, key or
# project is touched; no secret value is printed.
#
# Usage:
#   scripts/compose-smoke.sh
#   SMOKE_TIMEOUT_SECONDS=300 scripts/compose-smoke.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SMOKE_TIMEOUT_SECONDS="${SMOKE_TIMEOUT_SECONDS:-120}"
POLL_SECONDS=2
PROJECT_NAME="ai-buddy-smoke"
EVENT_FILE="${ROOT_DIR}/tests/fixtures/chat_events/legacy_dm_message.json"
TOPIC_URL="http://localhost:8085/v1/projects/demo-ai-buddy/topics/chat-events:publish"

log() { echo "[compose-smoke] $*"; }

WORK_DIR="$(mktemp -d)"
compose=(docker compose -p "${PROJECT_NAME}" -f "${ROOT_DIR}/docker-compose.yml")

cleanup() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

log "Creating a fixture Guides git repository ..."
GUIDES_DIR="${WORK_DIR}/guides"
mkdir -p "${GUIDES_DIR}"
cp -R "${ROOT_DIR}/tests/fixtures/guides_repo/." "${GUIDES_DIR}/"
git -C "${GUIDES_DIR}" init -q -b master
git -C "${GUIDES_DIR}" add -A
git -C "${GUIDES_DIR}" \
  -c user.name=smoke -c user.email=smoke@example.invalid \
  commit -q -m "fixture guides"

export HANDBOOK_SRC_DIR="${ROOT_DIR}/tests/fixtures/handbook"
export GUIDES_SRC_DIR="${GUIDES_DIR}"
export REDACT_PAGE_FILES="04-rete-ospiti.md"
# Random per run and never printed (at least 32 characters).
if [[ -z "${THREAD_KEY_SECRET:-}" ]]; then
  THREAD_KEY_SECRET="$(head -c 48 /dev/urandom | base64 -w0 | tr -d '/+=')"
  export THREAD_KEY_SECRET
fi

show_logs() {
  log "Recent logs (counts and modes only by design):"
  for service in chat-bot mcp-server; do
    log "--- ${service}"
    "${compose[@]}" logs --no-color --tail 50 "${service}" || true
  done
}

fail() {
  log "ERROR: $*" >&2
  show_logs >&2
  exit 1
}

log "Starting the default compose services (build, then wait until healthy) ..."
"${compose[@]}" up -d --build --wait || fail "compose up failed"

log "Publishing the legacy DM fixture event to the Pub/Sub emulator topic ..."
DATA_B64="$(base64 -w0 "${EVENT_FILE}")"
PUBLISH_BODY="{\"messages\":[{\"data\":\"${DATA_B64}\"}]}"
RESPONSE="$("${compose[@]}" exec -T pubsub curl -s -X POST -H 'Content-Type: application/json' \
  -d "${PUBLISH_BODY}" "${TOPIC_URL}")" || fail "publish request failed"
[[ "${RESPONSE}" == *messageIds* ]] || fail "publish was not accepted by the emulator"

log "Waiting up to ${SMOKE_TIMEOUT_SECONDS} s for the final answer ..."
deadline=$((SECONDS + SMOKE_TIMEOUT_SECONDS))
while ((SECONDS < deadline)); do
  recorded="$("${compose[@]}" exec -T chat-bot cat /tmp/chat.jsonl 2>/dev/null || true)"
  if grep -F '"op": "update"' <<<"${recorded}" | grep -F 'Fonte: Manuale' | grep -qF 'handbook://02-ferie'; then
    log "round trip ok"
    exit 0
  fi
  sleep "${POLL_SECONDS}"
done

fail "timeout after ${SMOKE_TIMEOUT_SECONDS} s: no final answer with a handbook citation was recorded"
