"""Structural guard over every Dockerfile stage (INFRA-01): one runtime image per service,
non-root, nothing private copied in, and the sync pins in agreement with the other files."""

import re

import pytest
from tests.unit.test_repo_layout import ROOT, _dockerfile_stage, _lines, _pins

RUNTIME_STAGES = ("mcp_server", "chat_bot", "sync")
SYNC_COPY_SOURCES = [
    "requirements.txt",
    "jobs/sync/requirements.txt",
    "packages/buddy_core",
    "jobs/sync",
]
PRIVATE_PREFIXES = ("artifacts", "docs", "tests", ".env", ".cache")
CREDENTIAL_NAME = re.compile(r"credential|secret|token|service[-_]?account|api[-_]?key", re.I)
PIN_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
    "services/mcp_server/requirements.txt",
    "services/chat_bot/requirements.txt",
)


def _stage_names() -> list[str]:
    text = (ROOT / "Dockerfile").read_text()
    return re.findall(r"^FROM \S+ AS (\S+)$", text, flags=re.MULTILINE)


def _instructions(stage: str, keyword: str) -> list[str]:
    """Arguments of every `keyword` instruction in a stage, line continuations joined."""
    joined = _dockerfile_stage(stage).replace("\\\n", " ")
    return [
        line.split(None, 1)[1].strip()
        for line in joined.splitlines()
        if line.split(None, 1)[:1] == [keyword]
    ]


def _copy_sources(stage: str) -> list[str]:
    """Every COPY/ADD source in a stage: all tokens but the last, flags dropped."""
    sources: list[str] = []
    for keyword in ("COPY", "ADD"):
        for args in _instructions(stage, keyword):
            tokens = [token for token in args.split() if not token.startswith("--")]
            sources.extend(tokens[:-1])
    return sources


def _is_private(source: str) -> bool:
    path = source.removeprefix("./")
    if path.split("/", 1)[0] in PRIVATE_PREFIXES or path.endswith(".db"):
        return True
    return path.endswith(".json") and CREDENTIAL_NAME.search(path) is not None


def _private_sources(sources: list[str]) -> list[str]:
    """The sources that would put private or generated data into an image layer."""
    return [source for source in sources if _is_private(source)]


def test_every_stage_exists() -> None:
    assert _stage_names() == ["base", "test", "mcp_server", "chat_bot", "sync"]


@pytest.mark.parametrize("stage", RUNTIME_STAGES)
def test_runtime_stage_is_slim_and_ends_non_root(stage: str) -> None:
    text = _dockerfile_stage(stage)
    assert text.startswith(f"FROM python:3.12-slim AS {stage}"), f"{stage}: not python:3.12-slim"
    users = _instructions(stage, "USER")
    assert users and users[-1] == "10001", f"{stage}: last USER is {users[-1:] or 'missing'}"
    assert text.rfind("USER 10001") > text.rfind("\nCOPY "), f"{stage}: USER 10001 before last COPY"


@pytest.mark.parametrize("stage", RUNTIME_STAGES)
def test_runtime_stage_copies_no_private_data(stage: str) -> None:
    sources = _copy_sources(stage)
    assert sources, f"{stage}: no COPY found, the parser is broken"
    assert _private_sources(sources) == [], f"{stage} copies private data"


def test_guard_flags_private_sources() -> None:
    flagged = _private_sources(
        [
            "artifacts/index.db",
            "docs/research",
            "tests/fixtures",
            ".env",
            ".cache/guides",
            "build/index.db",
            "deploy/client-secret.json",
            "packages/buddy_core",
            "jobs/sync",
        ]
    )
    assert flagged == [
        "artifacts/index.db",
        "docs/research",
        "tests/fixtures",
        ".env",
        ".cache/guides",
        "build/index.db",
        "deploy/client-secret.json",
    ]


def test_sync_stage_copies_exactly_its_sources() -> None:
    assert _copy_sources("sync") == SYNC_COPY_SOURCES


def test_sync_stage_has_git_safe_directory_and_entrypoint() -> None:
    stage = _dockerfile_stage("sync")
    assert "install -y --no-install-recommends git" in stage
    assert "safe.directory /guides-src" in stage
    assert _instructions("sync", "ENTRYPOINT") == ['["python", "-m", "buddy_sync"]']
    assert _instructions("sync", "CMD") == ['["run"]']
    assert "PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync" in stage


def test_chat_bot_stage_takes_only_the_model_files_from_the_server() -> None:
    from_server = [s for s in _copy_sources("chat_bot") if s.startswith("services/mcp_server")]
    assert from_server == [
        "services/mcp_server/buddy_mcp/__init__.py",
        "services/mcp_server/buddy_mcp/models.py",
    ]


def test_sync_requirements_are_pinned_and_agree_with_the_other_files() -> None:
    specs = [
        line.split("#", 1)[0].strip()
        for line in _lines("jobs/sync/requirements.txt")
        if line and not line.startswith("#")
    ]
    assert specs, "jobs/sync/requirements.txt has no requirement"
    assert [spec for spec in specs if "==" not in spec] == []
    sync = _pins("jobs/sync/requirements.txt")
    drifted = {
        (name, package): (version, other[package])
        for name in PIN_FILES
        for other in (_pins(name),)
        for package, version in sync.items()
        if package in other and other[package] != version
    }
    assert drifted == {}
    assert (
        sync["google-cloud-storage"]
        == _pins("services/mcp_server/requirements.txt")["google-cloud-storage"]
    )


def test_test_image_installs_the_sync_requirements() -> None:
    assert "-r jobs/sync/requirements.txt" in _lines("requirements-dev.txt")
    assert "COPY jobs/sync/requirements.txt jobs/sync/requirements.txt" in _dockerfile_stage("base")


def test_dockerignore_keeps_private_paths_out_of_the_build_context() -> None:
    entries = set(_lines(".dockerignore"))
    assert {"artifacts/", "docs/", ".env", ".cache/"} - entries == set()
