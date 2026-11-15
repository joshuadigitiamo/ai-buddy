"""Deploy identity contract across _deploy.yml and both Cloud Run templates (INFRA-05, 04-20).

Every deploy references the image by the digest its own build step produced and names its revision
after the run id and attempt, so a re-run of the same commit still creates a revision of the exact
image it built. The pushed `:<sha>` tag stays as a human lookup alias.
"""

import re
from typing import Any

import pytest
from tests.unit.test_cloudrun_yaml import BOT_FILE, MCP_FILE, _containers, _load
from tests.unit.test_workflows import _load as _load_workflow
from tests.unit.test_workflows import _steps, _uses_step

SERVICES = {"mcp-server": MCP_FILE, "chat-bot": BOT_FILE}


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
