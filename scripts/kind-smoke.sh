#!/usr/bin/env bash
# In-cluster smoke for the kind dev overlay (INFRA-03, ROADMAP criterion 2).
#
# From a one-off pod (the already loaded mcp-server image, no new image) it GETs
# http://mcp-server:8000/healthz and POSTs one tools/call guides_search to the MCP server by its
# Service name. The last line printed is the success marker; any failure exits non-zero.
#
# Usage:
#   scripts/kind-smoke.sh
#   SMOKE_QUERY=chunking KIND_CLUSTER=ai-buddy scripts/kind-smoke.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
KIND_CLUSTER="${KIND_CLUSTER:-ai-buddy}"
SMOKE_QUERY="${SMOKE_QUERY:-MCP}"
NAMESPACE="ai-buddy"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-300s}"
POD_NAME="kind-smoke-probe"
export KUBECONFIG="${ROOT_DIR}/.cache/kubeconfig-${KIND_CLUSTER}"

log() { echo "[kind-smoke] $*"; }
die() { echo "[kind-smoke] ERROR: $*" >&2; exit 1; }

[[ "${SMOKE_QUERY}" =~ ^[^\"\\]+$ ]] || die "SMOKE_QUERY must not contain double quotes or backslashes"
[[ -f "${KUBECONFIG}" ]] || die "no kubeconfig at ${KUBECONFIG}; run scripts/kind-up.sh first"

log "Waiting for the mcp-server rollout ..."
kubectl -n "${NAMESPACE}" rollout status deployment/mcp-server --timeout="${WAIT_TIMEOUT}"

PROBE='
import json, os, sys, urllib.request

base = "http://mcp-server:8000"
with urllib.request.urlopen(base + "/healthz", timeout=10) as health:
    body = json.loads(health.read())
    assert health.status == 200 and body == {"status": "ok"}, (health.status, body)
print("healthz 200")

call = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "guides_search", "arguments": {"query": os.environ["SMOKE_QUERY"]}},
}
request = urllib.request.Request(
    base + "/mcp",
    data=json.dumps(call).encode(),
    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
)
with urllib.request.urlopen(request, timeout=30) as answer:
    assert answer.status == 200, answer.status
    result = json.loads(answer.read())["result"]
assert result["isError"] is False, "tool call reported an error"
hits = result["structuredContent"]["results"]
assert hits and all(hit["source_url"] for hit in hits), "no cited result"
print("guides_search cited results:", len(hits))
print("SMOKE_PROBE_OK")
'

# Same restricted-style securityContext as the workloads, so the probe adds no Pod Security warning.
# kubectl replaces the whole container list when overrides carry one, so the container is given in
# full; the probe script itself arrives on stdin (python -).
OVERRIDES='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":10001,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"'"${POD_NAME}"'","image":"ai-buddy/mcp-server:dev","imagePullPolicy":"IfNotPresent","command":["python","-"],"stdin":true,"stdinOnce":true,"env":[{"name":"SMOKE_QUERY","value":"'"${SMOKE_QUERY}"'"}],"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}}}]}}'

log "Running the probe pod ..."
kubectl -n "${NAMESPACE}" delete pod "${POD_NAME}" --ignore-not-found --wait=true >/dev/null
OUTPUT="$(kubectl -n "${NAMESPACE}" run "${POD_NAME}" --rm -i --restart=Never --quiet \
  --image=ai-buddy/mcp-server:dev --overrides="${OVERRIDES}" <<<"${PROBE}" 2>&1)" || {
  echo "${OUTPUT}" >&2
  die "probe pod failed"
}
echo "${OUTPUT}"
[[ "${OUTPUT}" == *SMOKE_PROBE_OK* ]] || die "probe did not finish"

echo "kind smoke ok"
