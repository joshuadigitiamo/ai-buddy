#!/usr/bin/env bash
# Hermetic eval smoke over docker-compose.yml, profile eval (EVAL-05, D-21).
#
# Brings up mcp-server (over the fixture handbook and a throwaway fixture Guides git repo), the
# stub LLM and the real MLflow container; no Meridian and no Max session are involved. Runs
# `eval run` over three synthetic golden items, then reads the traces back through the MLflow
# client and checks that every item produced exactly one trace with a bot_run root, LLM-call
# spans, its expectations and a correctness feedback, and that the answered handbook item shows
# the workflow node spans. Then it starts mcp-server-empty and runs `eval gate`, asserting one
# `GATE: ` line, the recall and empty_context lines, and that the container exit code is 0 exactly
# when the line is `GATE: PASS` (RESEARCH A5). The verdict itself is not asserted: with the stub
# LLM the empty-context outcome depends on stub keyword overlap with the fixture (Pitfall 10).
# No real service or key is touched; no secret value and no golden question text is printed.
#
# Usage:
#   scripts/eval-smoke.sh
#   EVAL_SMOKE_TIMEOUT_SECONDS=600 scripts/eval-smoke.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVAL_SMOKE_TIMEOUT_SECONDS="${EVAL_SMOKE_TIMEOUT_SECONDS:-300}"
POLL_SECONDS=2
PROJECT_NAME="ai-buddy-eval-smoke"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures/eval"
EXPECTED_TRACES=3

log() { echo "[eval-smoke] $*"; }

WORK_DIR="$(mktemp -d)"
compose=(docker compose -p "${PROJECT_NAME}" -f "${ROOT_DIR}/docker-compose.yml" --profile eval)

cleanup() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

show_logs() {
  log "Recent logs (counts and modes only by design):"
  for service in mcp-server mcp-server-empty mlflow stub-llm; do
    log "--- ${service}"
    "${compose[@]}" logs --no-color --tail 30 "${service}" || true
  done
}

fail() {
  log "ERROR: $*" >&2
  show_logs >&2
  exit 1
}

deadline=$((SECONDS + EVAL_SMOKE_TIMEOUT_SECONDS))

# Runs a command inside what is left of the overall budget; exit status 124 means the budget ran out.
bounded() {
  local left=$((deadline - SECONDS))
  if ((left <= 0)); then
    return 124
  fi
  timeout "${left}" "$@"
}

timed_out() {
  log "ERROR: timeout after ${EVAL_SMOKE_TIMEOUT_SECONDS} s: $*" >&2
  show_logs >&2
  exit 1
}

# Runs a bounded command; a timeout and any other failure each end the smoke with their own message.
step() {
  local description="$1"
  shift
  local status=0
  bounded "$@" || status=$?
  if ((status == 124)); then
    timed_out "${description}"
  elif ((status != 0)); then
    fail "${description} failed (exit ${status})"
  fi
}

log "Creating a fixture Guides git repository ..."
GUIDES_DIR="${WORK_DIR}/guides"
mkdir -p "${GUIDES_DIR}"
cp -R "${ROOT_DIR}/tests/fixtures/guides_repo/." "${GUIDES_DIR}/"
git -C "${GUIDES_DIR}" init -q -b master
git -C "${GUIDES_DIR}" add -A
git -C "${GUIDES_DIR}" \
  -c user.name=smoke -c user.email=smoke@example.invalid \
  commit -q -m "fixture guides"

# The private directory is mounted at /private and is written by the eval container, which runs
# as the host user: it must belong to that user.
PRIVATE_DIR="${WORK_DIR}/private"
mkdir -p "${PRIVATE_DIR}"
cp "${FIXTURE_DIR}/golden-public.yaml" "${FIXTURE_DIR}/golden-handbook.yaml" "${PRIVATE_DIR}/"

export HANDBOOK_SRC_DIR="${ROOT_DIR}/tests/fixtures/handbook"
export GUIDES_SRC_DIR="${GUIDES_DIR}"
export REDACT_PAGE_FILES="04-rete-ospiti.md"
export HOST_UID="$(id -u)"
export HOST_GID="$(id -g)"
export EVAL_PRIVATE_DIR="${PRIVATE_DIR}"
export EVAL_GOLDEN_PUBLIC_PATH="/private/golden-public.yaml"
export EVAL_GOLDEN_PRIVATE_PATH="/private/golden-handbook.yaml"
export EVAL_LLM_BASE_URL="http://stub-llm:8090"
# Random per run and never printed (at least 32 characters).
if [[ -z "${THREAD_KEY_SECRET:-}" ]]; then
  THREAD_KEY_SECRET="$(head -c 48 /dev/urandom | base64 -w0 | tr -d '/+=')"
  export THREAD_KEY_SECRET
fi

log "Building the eval and service images ..."
step "image build" "${compose[@]}" build eval mcp-server mcp-server-empty stub-llm sync

log "Starting mcp-server, mlflow and the stub LLM (wait until healthy) ..."
step "compose up" "${compose[@]}" up -d --wait mcp-server mlflow stub-llm

log "Waiting for the stub LLM to listen ..."
while true; do
  if bounded "${compose[@]}" exec -T stub-llm python -c \
    "import socket; socket.create_connection(('localhost', 8090), timeout=2)" >/dev/null 2>&1; then
    break
  fi
  if ((SECONDS >= deadline)); then
    timed_out "the stub LLM never listened"
  fi
  sleep "${POLL_SECONDS}"
done

log "Running the eval over the synthetic golden items ..."
RUN_OUTPUT="${WORK_DIR}/eval-run.out"
status=0
bounded "${compose[@]}" run --rm --no-deps eval run >"${RUN_OUTPUT}" 2>&1 || status=$?
if ((status == 124)); then
  timed_out "the eval run did not finish"
elif ((status != 0)); then
  # Item ids and statuses only; the eval job never prints question or answer text.
  cat "${RUN_OUTPUT}" >&2
  fail "eval run exited ${status}"
fi
cat "${RUN_OUTPUT}"
grep -q '^correctness_with_citation:' "${RUN_OUTPUT}" || fail "no correctness_with_citation line in the eval output"

read -r -d '' CHECK_PY <<'PY' || true
import os
import sys

import mlflow

EXPECTED = int(sys.argv[1])
NODES = {"reformulate", "retrieve", "answer", "gate"}
HANDBOOK_ITEM = "smoke-handbook-ferie"

mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
experiment = mlflow.get_experiment_by_name(os.environ.get("MLFLOW_EXPERIMENT", "ai-buddy-eval"))
assert experiment is not None, "experiment ai-buddy-eval is missing"
traces = mlflow.search_traces(experiment_ids=[experiment.experiment_id], return_type="list")
problems = []
if len(traces) != EXPECTED:
    problems.append(f"expected {EXPECTED} traces, found {len(traces)}")
seen_items = set()
for trace in traces:
    item = trace.info.tags.get("item_id", "?")
    seen_items.add(item)
    names = [span.name for span in trace.data.spans]
    if "bot_run" not in names:
        problems.append(f"{item}: no bot_run root span")
    if not any("Messages" in name for name in names):
        problems.append(f"{item}: no LLM-call span")
    if item == HANDBOOK_ITEM:
        missing = sorted(NODES - set(names))
        if missing:
            problems.append(f"{item}: missing node spans {missing}")
    assessments = {a.name for a in (trace.info.assessments or [])}
    for needed in ("expected_sources", "correctness"):
        if needed not in assessments:
            problems.append(f"{item}: no {needed} assessment")
if len(seen_items) != len(traces):
    problems.append("an item produced more than one trace")
if HANDBOOK_ITEM not in seen_items:
    problems.append(f"no trace tagged {HANDBOOK_ITEM}")
if problems:
    for problem in problems:
        print("trace check failed:", problem)
    sys.exit(1)
print(f"trace check ok ({len(traces)} traces)")
PY

log "Checking the traces in the MLflow server ..."
status=0
bounded "${compose[@]}" run --rm --no-deps --entrypoint python eval -c "${CHECK_PY}" "${EXPECTED_TRACES}" || status=$?
if ((status == 124)); then
  timed_out "the trace check did not finish"
elif ((status != 0)); then
  fail "trace check failed (exit ${status})"
fi

log "Starting mcp-server-empty for the gate's empty-context test ..."
step "mcp-server-empty up" "${compose[@]}" up -d --wait mcp-server-empty

log "Running the gate (recall, scoring, empty-context, verdict) ..."
GATE_OUTPUT="${WORK_DIR}/eval-gate.out"
status=0
bounded "${compose[@]}" run --rm --no-deps eval gate >"${GATE_OUTPUT}" 2>&1 || status=$?
if ((status == 124)); then
  timed_out "the gate did not finish"
fi
# Item ids, numbers and trace links only; the eval job never prints question or answer text.
cat "${GATE_OUTPUT}"
gate_lines="$(grep -c '^GATE: ' "${GATE_OUTPUT}" || true)"
[[ "${gate_lines}" == "1" ]] || fail "expected exactly one 'GATE: ' line, found ${gate_lines} (exit ${status})"
grep -q '^recall@5 guides:' "${GATE_OUTPUT}" || fail "no 'recall@5 guides:' line in the gate output"
grep -q '^empty_context:' "${GATE_OUTPUT}" || fail "no 'empty_context:' line in the gate output"
gate_verdict="$(grep '^GATE: ' "${GATE_OUTPUT}")"
if [[ "${gate_verdict}" == "GATE: PASS" ]]; then
  expected_status=0
else
  expected_status=1
fi
((status == expected_status)) || fail "gate exit code ${status} does not match '${gate_verdict}' (expected ${expected_status})"
log "gate exit code consistent (${status})"

log "eval smoke ok"
