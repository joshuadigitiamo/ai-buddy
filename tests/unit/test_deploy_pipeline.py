"""Deploy identity contract across _deploy.yml and both Cloud Run templates (INFRA-05, 04-20).

Every deploy references the image by the digest its own build step produced and names its revision
after the run id and attempt, so a re-run of the same commit still creates a revision of the exact
image it built. The pushed `:<sha>` tag stays as a human lookup alias.
"""

import json
import re
import subprocess
import sys
from typing import Any

import pytest
from tests.unit.test_cloudrun_yaml import BOT_FILE, MCP_FILE, _containers, _env, _load
from tests.unit.test_repo_layout import ROOT
from tests.unit.test_workflows import _load as _load_workflow
from tests.unit.test_workflows import _steps, _uses_step

from buddy_mcp.config import _HOSTNAME

SERVICES = {"mcp-server": MCP_FILE, "chat-bot": BOT_FILE}
SERVING_HELPER = ROOT / "scripts" / "serving_revision.py"
MARKER = "marker-that-must-never-be-echoed"


def _render_step() -> dict[str, Any]:
    matches = [
        step
        for _, step in _steps(_load_workflow("_deploy.yml"))
        if "render-cloudrun.sh" in step.get("run", "")
    ]
    assert len(matches) == 1
    return matches[0]


def test_deploy_renders_the_digest_of_the_image_it_built() -> None:
    deploy = _load_workflow("_deploy.yml")
    build = _uses_step(deploy, "docker/build-push-action")
    assert build["id"] == "build"
    env = _render_step()["env"]
    assert env["IMAGE_DIGEST"] == "${{ steps.build.outputs.digest }}"
    assert "IMAGE_TAG" not in env, "the commit tag is a lookup alias, not a deploy identity"
    assert build["with"]["tags"].endswith("/ai-buddy/${{ inputs.service }}:${{ github.sha }}")


def test_deploy_names_the_revision_after_the_run_and_attempt() -> None:
    env = _render_step()["env"]
    assert env["DEPLOY_ID"] == "r${{ github.run_id }}-${{ github.run_attempt }}"
    assert "${{" not in _render_step()["run"], "expressions stay in env, never in run text"


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_templates_deploy_by_digest_and_name_their_revision(service: str) -> None:
    document = _load(SERVICES[service])
    template = document["spec"]["template"]
    assert template["metadata"]["name"] == f"{service}-${{DEPLOY_ID}}"
    image = str(_containers(document)[service]["image"])
    assert re.fullmatch(
        rf"europe-west8-docker\.pkg\.dev/\$\{{PROJECT_ID\}}/ai-buddy/{service}@\$\{{IMAGE_DIGEST\}}",
        image,
    ), image
    assert ":latest" not in image
    text = SERVICES[service].read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "IMAGE_TAG" not in code


# --- staged deploys (INFRA-05, 04-22) ---------------------------------------------------------


def _step_named(name: str) -> dict[str, Any]:
    steps = _steps(_load_workflow("_deploy.yml"))
    matches = [step for _, step in steps if step.get("name") == name]
    assert len(matches) == 1, f"expected one step named {name!r}"
    return matches[0]


def _step_with_run(text: str) -> dict[str, Any]:
    matches = [
        step for _, step in _steps(_load_workflow("_deploy.yml")) if text in step.get("run", "")
    ]
    assert len(matches) == 1, f"expected one step whose run text holds {text!r}"
    return matches[0]


def _lookup(stdin: str, service: str = "mcp-server") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SERVING_HELPER), service],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def _describe(status_traffic: list[dict[str, Any]] | None, spec_traffic: Any = None) -> str:
    """The shape `gcloud run services describe --format=json` returns (Knative v1 Service)."""
    document: dict[str, Any] = {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {"name": "mcp-server", "annotations": {"note": MARKER}},
        "spec": {"traffic": spec_traffic or [{"latestRevision": True, "percent": 100}]},
    }
    if status_traffic is not None:
        document["status"] = {"traffic": status_traffic}
    return json.dumps(document)


def test_serving_lookup_reads_the_resolved_status_traffic() -> None:
    latest_mode = _describe(
        [{"latestRevision": True, "percent": 100, "revisionName": "mcp-server-00012-abc"}]
    )
    result = _lookup(latest_mode)
    assert (result.returncode, result.stdout, result.stderr) == (0, "mcp-server-00012-abc\n", "")

    pinned = _describe(
        [
            {"revisionName": "mcp-server-r1-1", "percent": 100},
            {"revisionName": "mcp-server-r2-1", "tag": "candidate"},
        ],
        spec_traffic=[
            {"revisionName": "mcp-server-r1-1", "percent": 100},
            {"revisionName": "mcp-server-r2-1", "percent": 0, "tag": "candidate"},
        ],
    )
    result = _lookup(pinned)
    assert (result.returncode, result.stdout) == (0, "mcp-server-r1-1\n")

    published = "mcp-server-p20261115-1763000000"
    forced = _describe([{"latestRevision": True, "percent": 100, "revisionName": published}])
    assert _lookup(forced).stdout == f"{published}\n"


@pytest.mark.parametrize(
    "stdin",
    [
        pytest.param(_describe(None), id="no-status-never-falls-back-to-spec"),
        pytest.param(
            json.dumps({"spec": {"traffic": [{"latestRevision": True, "percent": 100}]}}),
            id="status-key-absent",
        ),
        pytest.param(json.dumps({"status": {}, "note": MARKER}), id="no-status-traffic"),
        pytest.param(
            _describe(
                [
                    {"revisionName": "mcp-server-r1-1", "percent": 50},
                    {"revisionName": "mcp-server-r2-1", "percent": 50},
                ]
            ),
            id="split-50-50",
        ),
        pytest.param(
            _describe([{"revisionName": "chat-bot-r1-1", "percent": 100}]), id="foreign-service"
        ),
        pytest.param(_describe([{"latestRevision": True, "percent": 100}]), id="no-revision-name"),
        pytest.param(_describe([{"revisionName": "mcp-server-r1-1"}]), id="nobody-holds-traffic"),
        pytest.param("{ not json " + MARKER, id="invalid-json"),
        pytest.param("", id="empty-input"),
    ],
)
def test_serving_lookup_refuses_split_or_unresolved_traffic(stdin: str) -> None:
    result = _lookup(stdin)
    assert result.returncode == 2
    assert result.stdout == "", "an empty answer would read as a first deploy"
    assert result.stderr.startswith("::error::"), result.stderr
    assert "mcp-server" in result.stderr
    assert MARKER not in result.stderr, "the describe output is never echoed"


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_templates_stage_the_new_revision_behind_the_candidate_tag(service: str) -> None:
    document = _load(SERVICES[service])
    assert document["spec"]["traffic"] == [
        {"revisionName": "${SERVING_REVISION}", "percent": 100},
        {"revisionName": f"{service}-${{DEPLOY_ID}}", "percent": 0, "tag": "candidate"},
    ]


def test_deploy_checks_the_candidate_before_moving_traffic() -> None:
    steps = [step for _, step in _steps(_load_workflow("_deploy.yml"))]
    names = [step.get("name") for step in steps]

    serving = _step_named("Find the serving revision")
    assert serving["id"] == "serving"
    assert names.index(serving["name"]) < steps.index(_render_step())
    assert "serving_revision.py" in serving["run"]
    assert "services describe" in serving["run"]
    assert _render_step()["env"]["SERVING_REVISION"] == "${{ steps.serving.outputs.revision }}"

    candidate = _step_with_run("candidate---")
    text = candidate["run"]
    assert "https://candidate---${SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app" in text
    assert "add-mask" in text
    assert set(candidate["env"]) >= {"SERVICE", "PROJECT_NUMBER", "SERVING_REVISION", "DEPLOY_ID"}
    assert "services describe" in text
    assert text.index("serving_revision.py") < text.index("curl"), "the traffic check comes first"
    assert "the new revision took traffic before its checks" in text
    assert "${{" not in text

    live = _step_named("Check the live service")["run"]
    calls = re.compile(r"^\s*(expect (?:GET|POST) \S+ \d+)$", re.MULTILINE)
    assert calls.findall(text) == calls.findall(live), "same expectations on both URLs"
    assert calls.findall(text).count("expect POST / 401") == 1, (
        "the chat-bot candidate receives one unauthenticated POST, never a model call"
    )
    assert text.count("curl") == live.count("curl") == 1, "requests go through expect only"

    switch = _step_with_run("--to-latest")
    assert "update-traffic" in switch["run"]
    assert switch["run"].index("--to-latest") < switch["run"].index("--remove-tags candidate")
    assert names.index(candidate["name"]) < names.index(switch["name"])
    assert names.index(switch["name"]) < names.index("Check the live service")


def test_server_allows_the_candidate_host() -> None:
    environment = _env(_containers(_load(MCP_FILE))["mcp-server"])
    value = str(environment["MCP_ALLOWED_HOSTS"]["value"])
    assert value == "candidate---mcp-server-${PROJECT_NUMBER}.europe-west8.run.app"
    host = value.replace("${PROJECT_NUMBER}", "123456789012")
    assert _HOSTNAME.fullmatch(host), "the Host guard setting accepts the rendered name"
