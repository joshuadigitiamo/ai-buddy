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
from tests.unit.test_dockerfile_stages import RUNTIME_STAGES, _copy_sources
from tests.unit.test_repo_layout import ROOT

WORKFLOW_DIR = ROOT / ".github" / "workflows"
CALLERS = sorted(p.name for p in WORKFLOW_DIR.glob("*.yml") if not p.name.startswith("_"))
ALL_WORKFLOWS = sorted(p.name for p in WORKFLOW_DIR.glob("*.yml"))
STAGE_WORKFLOWS = {"mcp_server": "mcp-server.yml", "chat_bot": "chat-bot.yml", "sync": "sync.yml"}
SERVICE_WORKFLOWS = tuple(STAGE_WORKFLOWS.values())
DEPLOYING = ["mcp-server.yml", "chat-bot.yml"]
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


@pytest.mark.parametrize("name", DEPLOYING)
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


@pytest.mark.parametrize("name", [*DEPLOYING, "meridian.yml"])
def test_deploy_concurrency_group_never_cancels(name: str) -> None:
    concurrency = _load(name)["concurrency"]
    assert concurrency["group"] == f"deploy-{name.removesuffix('.yml')}"
    assert concurrency["cancel-in-progress"] is False


def _push_paths(name: str) -> list[str]:
    paths = _triggers(_load(name))["push"]["paths"]
    assert isinstance(paths, list) and paths, f"{name}: no push paths"
    return paths


def _matches(path: str, patterns: list[str]) -> bool:
    """GitHub path filter, restricted to the forms used here: `dir/**` prefix, exact, and a `*`
    inside the last segment (which never crosses a `/`)."""
    for pattern in patterns:
        if pattern.endswith("/**"):
            if path == pattern.removesuffix("/**") or path.startswith(pattern.removesuffix("**")):
                return True
        elif "*" in pattern:
            if re.fullmatch(re.escape(pattern).replace(r"\*", "[^/]*"), path):
                return True
        elif path == pattern:
            return True
    return False


def test_matcher_handles_prefix_and_exact_paths() -> None:
    assert _matches("a/b/c.py", ["a/**"])
    assert _matches("a", ["a/**"])
    assert not _matches("ab/c.py", ["a/**"])
    assert _matches("Dockerfile", ["Dockerfile"])
    assert not _matches("Dockerfile.dev", ["Dockerfile"])
    assert _matches("docker-compose.test.yml", ["docker-compose*.yml"])
    assert not _matches("deploy/docker-compose.yml", ["docker-compose*.yml"])


@pytest.mark.parametrize("name", [*SERVICE_WORKFLOWS, "meridian.yml", "tests.yml"])
def test_push_paths_use_only_prefix_and_exact_patterns(name: str) -> None:
    for pattern in _push_paths(name):
        head, _, last = pattern.removesuffix("/**").rpartition("/")
        assert "*" not in head, f"{name}: unsupported pattern {pattern}"
        assert "**" not in last, f"{name}: unsupported pattern {pattern}"
        assert not pattern.startswith("/"), f"{name}: absolute pattern {pattern}"


@pytest.mark.parametrize("stage", RUNTIME_STAGES)
def test_workflow_paths_do_not_drift_from_dockerfile_copy_sources(stage: str) -> None:
    patterns = _push_paths(STAGE_WORKFLOWS[stage])
    uncovered = [s for s in _copy_sources(stage) if not _matches(s, patterns)]
    assert uncovered == [], f"{STAGE_WORKFLOWS[stage]} would not rebuild {stage} on {uncovered}"


@pytest.mark.parametrize("name", SERVICE_WORKFLOWS)
def test_service_workflow_paths_name_their_own_files_and_the_dockerfile(name: str) -> None:
    patterns = _push_paths(name)
    assert _matches("Dockerfile", patterns)
    assert _matches(f".github/workflows/{name}", patterns)
    assert _matches(".github/workflows/_test.yml", patterns)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("services/mcp_server/buddy_mcp/server.py", {"mcp-server.yml"}),
        ("services/mcp_server/buddy_mcp/models.py", {"mcp-server.yml", "chat-bot.yml"}),
        ("services/mcp_server/buddy_mcp/__init__.py", {"mcp-server.yml", "chat-bot.yml"}),
        ("services/chat_bot/buddy_bot/service.py", {"chat-bot.yml"}),
        ("jobs/sync/buddy_sync/cli.py", {"sync.yml"}),
        ("packages/buddy_core/buddy_core/models.py", set(SERVICE_WORKFLOWS)),
    ],
)
def test_a_changed_file_triggers_only_the_workflows_that_copy_it(
    path: str, expected: set[str]
) -> None:
    assert (ROOT / path).is_file(), f"{path} no longer exists, update the example"
    triggered = {name for name in SERVICE_WORKFLOWS if _matches(path, _push_paths(name))}
    assert triggered == expected


def test_chat_bot_deploy_fails_early_when_the_meridian_image_is_missing() -> None:
    deploy = _load("_deploy.yml")
    steps = [step for _, step in _steps(deploy)]
    check = next(s for s in steps if "meridian.version" in s.get("run", ""))
    assert check["if"] == "inputs.service == 'chat-bot'"
    assert "gcloud artifacts docker images describe" in check["run"]
    assert "Meridian image ${MERIDIAN_TAG} missing: run the meridian workflow" in check["run"]
    build = _step_index(deploy, lambda s: s.get("uses", "").startswith("docker/build-push-action@"))
    assert steps.index(check) < build, "the Meridian check must run before the build and push"


def test_sync_workflow_tests_and_builds_the_image_without_push_or_deploy() -> None:
    workflow = _load("sync.yml")
    jobs = workflow["jobs"]
    assert set(jobs) == {"test", "build"}
    assert jobs["test"]["uses"] == "./.github/workflows/_test.yml"
    assert jobs["build"]["needs"] == "test"
    build = _uses_step(workflow, "docker/build-push-action")
    assert build["with"]["target"] == "sync"
    assert build["with"]["push"] is False
    text = (WORKFLOW_DIR / "sync.yml").read_text()
    assert "services replace" not in text
    assert "_deploy.yml" not in text
    assert "id-token" not in text


def test_meridian_workflow_triggers_on_the_version_file_and_on_dispatch() -> None:
    triggers = _triggers(_load("meridian.yml"))
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["push"]["paths"] == [
        "deploy/meridian.version",
        ".github/workflows/meridian.yml",
    ]
    assert "workflow_dispatch" in triggers


def test_meridian_workflow_builds_only_the_reviewed_commit_after_the_test_gate() -> None:
    workflow = _load("meridian.yml")
    jobs = workflow["jobs"]
    assert jobs["test"]["uses"] == "./.github/workflows/_test.yml"
    assert jobs["push"]["needs"] == "test"
    assert jobs["push"]["if"] == "vars.GCP_PROJECT_ID != ''"
    read = next(s for _, s in _steps(workflow) if "meridian.version" in s.get("run", ""))
    assert read["id"] == "version"
    assert "[0-9a-f]{40}" in read["run"], "the version file must be validated as a full commit"
    build = _uses_step(workflow, "docker/build-push-action")
    assert build["with"]["context"] == (
        "https://github.com/rynfar/meridian.git#${{ steps.version.outputs.sha }}"
    )
    assert build["with"]["push"] is True
    assert build["with"]["tags"].endswith("/ai-buddy/meridian:${{ steps.version.outputs.sha }}")
    assert "target" not in build["with"]


def test_test_only_workflow_covers_the_files_no_service_image_copies() -> None:
    workflow = _load("tests.yml")
    assert set(workflow["jobs"]) == {"test"}
    assert workflow["jobs"]["test"]["uses"] == "./.github/workflows/_test.yml"
    patterns = _push_paths("tests.yml")
    for path in (
        "tests/unit/test_workflows.py",
        "pyproject.toml",
        "requirements-dev.txt",
        "run-unit-tests.sh",
        "docker-compose.yml",
        "docker-compose.test.yml",
        "deploy/k8s/base/kustomization.yaml",
        "deploy/compose/__init__.py",
        "scripts/validate-infra.sh",
    ):
        assert _matches(path, patterns), f"tests.yml would miss a change to {path}"


def test_dependabot_bumps_the_pinned_actions_weekly() -> None:
    data = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    assert data["version"] == 2
    [update] = data["updates"]
    assert update["package-ecosystem"] == "github-actions"
    assert update["directory"] == "/"
    assert update["schedule"]["interval"] == "weekly"
