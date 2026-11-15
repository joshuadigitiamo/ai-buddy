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


# --- cache, attestations and scan (INFRA-05/06, 04-23) ----------------------------------------

TRIVY_ACTION = "aquasecurity/trivy-action"
TRIVY_COMMIT = "ed142fd0673e97e23eac54620cfb913e5ce36c25"
# The malicious binary of GHSA-69fq-xp46-6x23 (March 2026) and the DockerHub images that followed.
COMPROMISED_TRIVY = {"v0.69.4", "v0.69.5", "v0.69.6"}


def _scan_step() -> dict[str, Any]:
    return _uses_step(_load_workflow("_deploy.yml"), TRIVY_ACTION)


def test_builds_use_a_per_image_gha_cache() -> None:
    deploy = _uses_step(_load_workflow("_deploy.yml"), "docker/build-push-action")["with"]
    assert deploy["cache-from"] == "type=gha,scope=${{ inputs.service }}"
    assert deploy["cache-to"] == "type=gha,scope=${{ inputs.service }},mode=max"
    meridian = _uses_step(_load_workflow("meridian.yml"), "docker/build-push-action")["with"]
    assert meridian["cache-from"] == "type=gha,scope=meridian"
    assert meridian["cache-to"] == "type=gha,scope=meridian,mode=max"


def test_service_images_carry_sbom_and_provenance() -> None:
    build = _uses_step(_load_workflow("_deploy.yml"), "docker/build-push-action")["with"]
    assert build["sbom"] is True
    assert build["provenance"] == "mode=max"


def test_the_pushed_digest_is_scanned_before_render() -> None:
    deploy = _load_workflow("_deploy.yml")
    scan = _scan_step()
    assert scan["name"] == "Scan the pushed image"
    assert scan["uses"] == f"{TRIVY_ACTION}@{TRIVY_COMMIT}"
    options = scan["with"]
    assert options["image-ref"] == (
        "europe-west8-docker.pkg.dev/${{ vars.GCP_PROJECT_ID }}/ai-buddy/${{ inputs.service }}"
        "@${{ steps.build.outputs.digest }}"
    ), "the scanned digest is the digest the render step deploys"
    assert options["severity"] == "CRITICAL,HIGH"
    assert options["exit-code"] == "1"
    assert options["format"] == "table"
    version = str(options["version"])
    assert re.fullmatch(r"v\d+\.\d+\.\d+", version), "the Trivy binary is set explicitly"
    assert version not in COMPROMISED_TRIVY
    assert scan["env"] == {
        "TRIVY_USERNAME": "oauth2accesstoken",
        "TRIVY_PASSWORD": "${{ steps.auth.outputs.access_token }}",
    }

    steps = [step for _, step in _steps(deploy)]
    build_at = steps.index(_uses_step(deploy, "docker/build-push-action"))
    assert steps.index(scan) == build_at + 1, "the scan follows the push at once"
    assert steps.index(scan) < steps.index(_step_named("Find the serving revision"))
    assert steps.index(scan) < steps.index(_render_step())
    assert _render_step()["env"]["IMAGE_DIGEST"] == "${{ steps.build.outputs.digest }}"


SCAN_SUMMARY = ROOT / ".planning" / "phases" / "04-infrastructure-and-ci-cd" / "04-23-SUMMARY.md"
TRIVY_IGNORE_FILE = ROOT / ".trivyignore.yaml"


def test_scan_policy_matches_the_recorded_decision() -> None:
    # Joshua's choice is recorded once in the plan summary; the gate has to enforce exactly that option.
    recorded = re.findall(
        r"^scan-policy: (strict|fixable|strict-with-ignores)$",
        SCAN_SUMMARY.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert len(recorded) == 1, "the summary records exactly one scan-policy line"
    options = _scan_step()["with"]
    assert options["severity"] == "CRITICAL,HIGH"
    assert options["exit-code"] == "1"
    if recorded[0] == "fixable":
        assert options["ignore-unfixed"] is True
        assert "trivyignores" not in options
        assert not TRIVY_IGNORE_FILE.exists()
    elif recorded[0] == "strict":
        assert options["ignore-unfixed"] is False
        assert "trivyignores" not in options
        assert not TRIVY_IGNORE_FILE.exists()
    else:
        assert options["ignore-unfixed"] is False
        assert options["trivyignores"] == ".trivyignore.yaml"
        assert TRIVY_IGNORE_FILE.exists()
