"""Repository layout, dependency pinning and public-repo hygiene assertions."""

import importlib.metadata
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
        "services/chat_bot/requirements.txt",
    ):
        for line in _lines(name):
            if not line or line.startswith(("#", "-r")):
                continue
            if "==" not in line:
                unpinned.append(f"{name}:{line.split('=')[0]}")
    assert unpinned == []


def _pins(name: str) -> dict[str, str]:
    """name==version pairs of one requirements file; trailing comments stripped."""
    pins: dict[str, str] = {}
    for line in _lines(name):
        spec = line.split("#", 1)[0].strip()
        if "==" in spec:
            package, version = spec.split("==", 1)
            pins[package.strip().lower()] = version.strip()
    return pins


def test_shared_pins_agree() -> None:
    seen: dict[str, dict[str, str]] = {}
    for name in (
        "requirements.txt",
        "requirements-dev.txt",
        "services/mcp_server/requirements.txt",
        "services/chat_bot/requirements.txt",
    ):
        for package, version in _pins(name).items():
            seen.setdefault(package, {})[name] = version
    disagreeing = {p: v for p, v in seen.items() if len(set(v.values())) > 1}
    assert disagreeing == {}


def test_chat_bot_pins_installed() -> None:
    import buddy_bot

    assert buddy_bot.__version__ == "0.1.0"
    mismatched = {
        package: (version, importlib.metadata.version(package))
        for package, version in _pins("services/chat_bot/requirements.txt").items()
        if importlib.metadata.version(package) != version
    }
    assert mismatched == {}


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
