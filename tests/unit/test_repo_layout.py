"""Repository layout, dependency pinning and public-repo hygiene assertions."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

D11_PATHS = {
    "packages/buddy_core",
    "services/mcp_server",
    "services/chat_bot",
    "jobs/sync",
    "deploy/k8s",
    "deploy/cloudrun",
    ".github/workflows",
    "tests",
}

CONTRACT_KEYS = {
    "HANDBOOK_DIR",
    "REDACT_PAGE_FILES",
    "REDACT_EMAIL_ALLOW_DOMAINS",
    "GUIDES_REPO_URL",
    "GUIDES_BRANCH",
    "GUIDES_CHECKOUT_DIR",
    "ARTIFACT_DIR",
    "GUIDES_WEB_BASE",
    "MCP_HOST",
    "PORT",
    "AUTH_MODE",
    "MCP_PUBLIC_BASE_URL",
    "GOOGLE_CLIENT_ID",
    "ALLOWED_EMAIL_DOMAIN",
    "BOT_SA_EMAILS",
    "OAUTH_STORAGE",
    "OAUTH_COLLECTION",
    "RATE_LIMIT_RPS",
    "RATE_LIMIT_BURST",
    "GAP_TTL_DAYS",
    "GAP_COLLECTION",
    "GOOGLE_CLOUD_PROJECT",
}

SECRET_SUFFIXES = ("_SECRET", "_SIGNING_KEY", "_ENCRYPTION_KEY", "_PASSWORD", "_TOKEN")

GITIGNORE_REQUIRED = {
    ".env",
    "*.db",
    "artifacts/",
    "docs/research/handbook-raw/",
    "docs/internal/",
}


def _lines(name: str) -> list[str]:
    return [ln.strip() for ln in (ROOT / name).read_text().splitlines()]


def _env_example() -> dict[str, str]:
    pairs = (ln.split("=", 1) for ln in _lines(".env.example") if ln and not ln.startswith("#"))
    return {key: value for key, value in pairs}


def test_d11_layout_exists() -> None:
    missing = {p for p in D11_PATHS if not (ROOT / p).is_dir()}
    assert missing == set()


def test_requires_python_312() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == ">=3.12"


def test_requirements_are_pinned() -> None:
    unpinned: list[str] = []
    for name in (
        "requirements.txt",
        "requirements-dev.txt",
        "services/mcp_server/requirements.txt",
    ):
        for line in _lines(name):
            if not line or line.startswith(("#", "-r")):
                continue
            if "==" not in line:
                unpinned.append(f"{name}:{line.split('=')[0]}")
    assert unpinned == []


def test_gitignore_protects_public_repo() -> None:
    present = set(_lines(".gitignore"))
    assert GITIGNORE_REQUIRED - present == set()


def test_env_example_holds_exactly_the_contract_keys() -> None:
    assert set(_env_example()) == CONTRACT_KEYS


def test_env_example_has_no_token_variable() -> None:
    assert {key for key in _env_example() if key.endswith("_TOKEN")} == set()


def test_env_example_has_no_secret_variable() -> None:
    assert {key for key in _env_example() if key.endswith(SECRET_SUFFIXES)} == set()


def test_env_example_never_targets_the_emulator() -> None:
    assert "FIRESTORE_EMULATOR_HOST" not in _env_example()
