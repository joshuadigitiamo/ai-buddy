#!/usr/bin/env bash
# Run lint, type and test gates inside Docker (no Python on the host).
#
# Usage:
#   ./run-unit-tests.sh --all
#   ./run-unit-tests.sh --single      <test_file> <test_name> <test_directory>
#   ./run-unit-tests.sh --single-file <test_file> <test_directory>
#   ./run-unit-tests.sh --emulator   (Firestore emulator via docker compose; tests marked `firestore`)

set -euo pipefail

IMAGE_NAME="ai-buddy-test"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[run-unit-tests] $*"; }

usage() {
  echo "Usage:"
  echo "  $0 --all"
  echo "  $0 --single <test_file> <test_name> <test_directory>"
  echo "  $0 --single-file <test_file> <test_directory>"
  echo "  $0 --emulator"
  exit 1
}

# Prefer .env (real values) over .env.example (placeholders).
pick_env_file() {
  if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    echo "${SCRIPT_DIR}/.env"
  elif [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
    echo "${SCRIPT_DIR}/.env.example"
  else
    log "ERROR: neither .env nor .env.example found in ${SCRIPT_DIR}" >&2
    exit 1
  fi
}

build_image() {
  log "Building test image: ${IMAGE_NAME} ..."
  docker build --target test -t "${IMAGE_NAME}" "${SCRIPT_DIR}"
}

# Containers run as the host uid, with no network; caches live under /tmp so the
# bind-mounted working tree never receives root-owned or container-written files.
run_in_container() {
  local env_file
  env_file="$(pick_env_file)"
  log "Running: $* (env: $(basename "${env_file}"))"
  docker run --rm \
    --network none \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e MYPY_CACHE_DIR=/tmp/.mypy_cache \
    -e COVERAGE_FILE=/tmp/.coverage \
    -e RUFF_CACHE_DIR=/tmp/.ruff_cache \
    --env-file "${env_file}" \
    -v "${SCRIPT_DIR}:/app" \
    -w /app \
    "${IMAGE_NAME}" "$@"
}

[[ $# -lt 1 ]] && usage

case "$1" in
  --all)
    pick_env_file >/dev/null
    build_image
    run_in_container ruff check .
    run_in_container ruff format --check .
    run_in_container mypy
    run_in_container python -m pytest tests/ -v --tb=short -o cache_dir=/tmp/.pytest_cache \
      --cov --cov-report=term-missing --cov-fail-under=80
    ;;
  --single)
    [[ $# -ne 4 ]] && { echo "Error: --single requires <test_file> <test_name> <test_directory>"; usage; }
    pick_env_file >/dev/null
    build_image
    run_in_container python -m pytest "$4/$2::$3" -v --tb=short -o cache_dir=/tmp/.pytest_cache
    ;;
  --single-file)
    [[ $# -ne 3 ]] && { echo "Error: --single-file requires <test_file> <test_directory>"; usage; }
    pick_env_file >/dev/null
    build_image
    run_in_container python -m pytest "$3/$2" -v --tb=short -o cache_dir=/tmp/.pytest_cache
    ;;
  --emulator)
    # Only mode that touches a network: the compose project's private network, emulator only.
    env_file="$(pick_env_file)"
    build_image
    export BUDDY_ENV_FILE="${env_file}" HOST_UID="$(id -u)" HOST_GID="$(id -g)"
    compose=(docker compose -p ai-buddy-test -f "${SCRIPT_DIR}/docker-compose.test.yml")
    trap '"${compose[@]}" down --remove-orphans >/dev/null 2>&1 || true' EXIT
    log "Starting Firestore emulator ..."
    "${compose[@]}" up -d --wait firestore
    log "Running firestore-marked tests (env: $(basename "${env_file}"))"
    "${compose[@]}" run --rm tests python -m pytest -m firestore tests/integration -v --tb=short \
      -o cache_dir=/tmp/.pytest_cache -rs
    ;;
  *)
    echo "Error: unknown option '$1'"
    usage
    ;;
esac
