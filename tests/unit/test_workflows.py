"""Structural guard over the GitHub Actions workflows (INFRA-05, INFRA-06).

The repository is public, so its Actions logs are public: the workflows must stay keyless, pin
every third-party action by commit, keep GitHub expressions out of shell text, and put the test job
in front of every image push. PyYAML reads the key `on` as the boolean True, so triggers are read
with both keys.
"""

import re
from collections.abc import Iterator
from typing import Any

import pytest
import yaml
from tests.unit.test_repo_layout import ROOT

WORKFLOW_DIR = ROOT / ".github" / "workflows"
CALLERS = sorted(p.name for p in WORKFLOW_DIR.glob("*.yml") if not p.name.startswith("_"))
ALL_WORKFLOWS = sorted(p.name for p in WORKFLOW_DIR.glob("*.yml"))
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
TRACING = re.compile(
    r"\bset\s+-[a-z]*x|xtrace|\bbash\s+-[a-z]*x|ACTIONS_STEP_DEBUG|ACTIONS_RUNNER_DEBUG"
)


def _load(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((WORKFLOW_DIR / name).read_text())
    assert isinstance(data, dict), f"{name}: not a mapping"
    return data


def _triggers(workflow: dict[Any, Any]) -> dict[Any, Any]:
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), "workflow has no `on` mapping"
    return triggers


def _steps(workflow: dict[Any, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            yield job_name, step


def _run_texts(workflow: dict[Any, Any]) -> list[str]:
    return [step["run"] for _, step in _steps(workflow) if "run" in step]


def _step_index(workflow: dict[Any, Any], predicate: Any) -> int:
    steps = [step for _, step in _steps(workflow)]
    matches = [i for i, step in enumerate(steps) if predicate(step)]
    assert len(matches) == 1, f"expected exactly one matching step, found {len(matches)}"
    return matches[0]


def _uses_step(workflow: dict[Any, Any], action: str) -> dict[str, Any]:
    """The one step that runs `action` (owner/repo, any pinned ref)."""
    matches = [s for _, s in _steps(workflow) if s.get("uses", "").startswith(f"{action}@")]
    assert len(matches) == 1, f"expected one {action} step, found {len(matches)}"
    return matches[0]


def _uses_values(workflow: dict[Any, Any]) -> list[str]:
    values = [job["uses"] for job in workflow.get("jobs", {}).values() if "uses" in job]
    values += [step["uses"] for _, step in _steps(workflow) if "uses" in step]
    return values


def test_workflow_directory_holds_only_workflows() -> None:
    assert ALL_WORKFLOWS, "no workflow found"
    assert not (WORKFLOW_DIR / ".gitkeep").exists()


@pytest.mark.parametrize("name", ALL_WORKFLOWS)
def test_every_uses_is_local_or_pinned_by_commit(name: str) -> None:
    for value in _uses_values(_load(name)):
        local = value.startswith("./.github/workflows/") and "@" not in value
        assert local or PINNED.match(value), (
            f"{name}: `{value}` is not a local path or owner/repo@<40 hex>"
        )


@pytest.mark.parametrize("name", ALL_WORKFLOWS)
def test_workflow_drops_default_token_permissions(name: str) -> None:
    assert _load(name).get("permissions") == {}, f"{name}: top-level permissions must be {{}}"


@pytest.mark.parametrize("name", ALL_WORKFLOWS)
def test_every_job_grants_permissions_explicitly(name: str) -> None:
    for job_name, job in _load(name)["jobs"].items():
        permissions = job.get("permissions")
        assert isinstance(permissions, dict) and permissions, (
            f"{name}/{job_name}: no job permissions"
        )
        assert permissions.get("contents") == "read"
        extra = set(permissions) - {"contents", "id-token"}
        assert extra == set(), f"{name}/{job_name}: unexpected grants {extra}"


def test_only_deploy_jobs_may_write_id_tokens() -> None:
    for name in ALL_WORKFLOWS:
        for job_name, job in _load(name)["jobs"].items():
            if job.get("permissions", {}).get("id-token") == "write":
                assert job_name in {"deploy", "push"}, (
                    f"{name}/{job_name} may not mint an OIDC token"
                )


@pytest.mark.parametrize("name", ["mcp-server.yml"])
def test_deploy_job_needs_the_test_job(name: str) -> None:
    jobs = _load(name)["jobs"]
    assert jobs["test"]["uses"] == "./.github/workflows/_test.yml"
    assert jobs["deploy"]["needs"] == "test"
    assert jobs["deploy"]["uses"] == "./.github/workflows/_deploy.yml"


def test_test_workflow_runs_the_full_script_exactly() -> None:
    unit = _load("_test.yml")["jobs"]["unit"]
    runs = [step["run"] for step in unit["steps"] if "run-unit-tests" in step.get("run", "")]
    assert runs == ["./run-unit-tests.sh --all"]


def test_deploy_steps_run_in_the_required_order() -> None:
    deploy = _load("_deploy.yml")
    build = _step_index(deploy, lambda s: s.get("uses", "").startswith("docker/build-push-action@"))
    render = _step_index(deploy, lambda s: "render-cloudrun.sh" in s.get("run", ""))
    dry = _step_index(deploy, lambda s: "--dry-run" in s.get("run", ""))
    replace = _step_index(
        deploy,
        lambda s: "services replace" in s.get("run", "") and "--dry-run" not in s.get("run", ""),
    )
    check = _step_index(deploy, lambda s: "curl" in s.get("run", ""))
    assert build < render < dry < replace < check


def test_deploy_authenticates_keyless_and_pushes_with_the_access_token() -> None:
    deploy = _load("_deploy.yml")
    auth = _uses_step(deploy, "google-github-actions/auth")
    assert auth["with"]["token_format"] == "access_token"
    assert auth["with"]["workload_identity_provider"] == "${{ vars.GCP_WIF_PROVIDER }}"
    assert auth["with"]["service_account"] == "${{ vars.GCP_DEPLOYER_SA }}"
    login = _uses_step(deploy, "docker/login-action")
    assert login["with"]["registry"] == "europe-west8-docker.pkg.dev"
    assert login["with"]["username"] == "oauth2accesstoken"
    assert login["with"]["password"] == "${{ steps.auth.outputs.access_token }}"
    push = _uses_step(deploy, "docker/build-push-action")
    assert push["with"]["push"] is True
    assert push["with"]["target"] == "${{ inputs.target }}"
    assert push["with"]["tags"].endswith("/ai-buddy/${{ inputs.service }}:${{ github.sha }}")


def test_deploy_job_runs_only_when_the_project_is_configured() -> None:
    assert _load("_deploy.yml")["jobs"]["deploy"]["if"] == "vars.GCP_PROJECT_ID != ''"


def test_no_github_secrets_context_and_no_key_file_anywhere() -> None:
    for path in sorted(WORKFLOW_DIR.parent.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text()
        assert re.search(r"\bsecrets\s*[.\[]", text) is None, f"{path.name}: reads secrets"
        assert "credentials_json" not in text, f"{path.name}: uses a JSON key"
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in text, f"{path.name}: sets a key file path"


@pytest.mark.parametrize("name", ALL_WORKFLOWS)
def test_run_steps_hold_no_github_expression(name: str) -> None:
    for text in _run_texts(_load(name)):
        assert "${{" not in text, f"{name}: an expression inside a run step: {text[:60]!r}"


@pytest.mark.parametrize("name", ALL_WORKFLOWS)
def test_no_pull_request_target_trigger(name: str) -> None:
    assert "pull_request_target" not in _triggers(_load(name))
    assert "pull_request_target" not in (WORKFLOW_DIR / name).read_text()


@pytest.mark.parametrize("name", ALL_WORKFLOWS)
def test_no_shell_tracing_in_any_run_step(name: str) -> None:
    workflow = _load(name)
    for text in _run_texts(workflow):
        assert TRACING.search(text) is None, f"{name}: shell tracing in a run step"
    assert TRACING.search((WORKFLOW_DIR / name).read_text()) is None


def test_deploy_workflow_never_prints_a_rendered_file() -> None:
    for text in _run_texts(_load("_deploy.yml")):
        printing = r"\b(cat|less|head|tail|sed|awk|echo|printf)\b[^\n]*service\.yaml"
        assert not re.search(printing, text)


@pytest.mark.parametrize("name", ["mcp-server.yml"])
def test_deploy_concurrency_group_never_cancels(name: str) -> None:
    concurrency = _load(name)["concurrency"]
    assert concurrency["group"] == f"deploy-{name.removesuffix('.yml')}"
    assert concurrency["cancel-in-progress"] is False
