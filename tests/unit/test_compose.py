"""Structural guard for docker-compose.yml (offline): profiles, ports, pins, mounts, secrets.

Migrated from the Phase 3 guard of the dev compose file; every assertion that still applies
is kept, and the hermetic-stack and ordering rules of Phase 4 (INFRA-02) are added.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "docker-compose.yml"
SMOKE_SCRIPT = ROOT / "scripts" / "compose-smoke.sh"
MERIDIAN_VERSION_FILE = ROOT / "deploy" / "meridian.version"

# 03-01-SUMMARY.md, decision meridian_credentials, and 04-01 token_chain (b): option "b" is a
# dedicated named volume that stays writable. Under "a" or "c" the host credentials would be
# bound and this constant must change together with the D-16 amendment in 03-CONTEXT.md.
MERIDIAN_CREDENTIALS_OPTION = "b"

HERMETIC_SERVICES = {
    "firestore",
    "pubsub",
    "pubsub-init",
    "sync",
    "mcp-server",
    "stub-llm",
    "chat-bot",
}
LIVE_SERVICES = {"meridian", "chat-bot-live"}
HERMETIC_PROJECT = "demo-ai-buddy"
BOTS = ("chat-bot", "chat-bot-live")
SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN")
BOT_ONLY_SECRETS = ("THREAD_KEY_SECRET", "MERIDIAN_API_KEY", "ANTHROPIC_API_KEY")
MERIDIAN_CONTEXT = re.compile(r"https://github\.com/rynfar/meridian\.git#([0-9a-f]{40})")
INTERPOLATION = re.compile(r"\$\{[^}]+\}")


def _load() -> dict[str, Any]:
    loaded = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _services() -> dict[str, dict[str, Any]]:
    services = _load()["services"]
    assert isinstance(services, dict)
    return services


def _environment(service: dict[str, Any]) -> dict[str, str]:
    environment = service.get("environment", {})
    assert isinstance(environment, dict), "environment blocks are written as mappings"
    return {str(key): str(value) for key, value in environment.items()}


def _profiles(service: dict[str, Any]) -> list[str]:
    return [str(profile) for profile in service.get("profiles", [])]


def _hermetic() -> dict[str, dict[str, Any]]:
    return {name: svc for name, svc in _services().items() if not _profiles(svc)}


def _depends_on(name: str) -> dict[str, str]:
    raw = _services()[name]["depends_on"]
    assert isinstance(raw, dict), "depends_on is written with conditions"
    return {str(dep): str(spec["condition"]) for dep, spec in raw.items()}


def test_default_services_are_exactly_the_seven_hermetic_ones() -> None:
    assert set(_hermetic()) == HERMETIC_SERVICES


def test_profile_live_adds_exactly_meridian_and_the_live_bot() -> None:
    live = {name for name, svc in _services().items() if _profiles(svc)}
    assert live == LIVE_SERVICES
    for name in LIVE_SERVICES:
        assert _profiles(_services()[name]) == ["live"]


def test_no_service_publishes_a_port_or_shares_a_network_namespace() -> None:
    for name, service in _services().items():
        assert "ports" not in service, f"{name} publishes a port to the host (T-04-20)"
        assert "network_mode" not in service, f"{name} shares or bypasses the compose network"


def test_meridian_is_built_from_the_pinned_commit() -> None:
    context = _services()["meridian"]["build"]["context"]
    found = MERIDIAN_CONTEXT.fullmatch(context)
    assert found, "Meridian must build from a 40-hex commit (T-03-36)"
    pinned = MERIDIAN_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert found.group(1) == pinned, "the build SHA must equal deploy/meridian.version"


def test_meridian_request_logging_is_silenced() -> None:
    # BOT-11: no question text in logs. MERIDIAN_SILENT=1 removes every routine [PROXY] request
    # line, so a later Meridian change cannot start printing prompt text unnoticed.
    # MERIDIAN_DEBUG is verbose request/session logging.
    environment = _environment(_services()["meridian"])
    assert environment["MERIDIAN_SILENT"] == "1"
    for debug_flag in ("MERIDIAN_DEBUG", "CLAUDE_PROXY_DEBUG", "OPENCODE_CLAUDE_PROVIDER_DEBUG"):
        assert debug_flag not in environment


def test_meridian_credentials_follow_the_recorded_decision() -> None:
    meridian = _services()["meridian"]
    volumes = meridian["volumes"]
    host_sides = [str(volume).split(":", 1)[0] for volume in volumes]
    if MERIDIAN_CREDENTIALS_OPTION == "b":
        assert not any(".claude" in side for side in host_sides), "host ~/.claude must not be bound"
        assert "meridian-claude:/home/claude/.claude" in volumes, "writable: no :ro (token_chain b)"
        declared = _load()["volumes"]["meridian-claude"]
        assert declared == {"external": True}, "the volume is seeded once, never created empty"
        for name, service in _services().items():
            if name != "meridian":
                assert not any("meridian-claude" in str(v) for v in service.get("volumes", [])), (
                    f"{name} must not mount the credentials volume"
                )
        assert not [key for key in _environment(meridian) if "READ_ONLY" in key.upper()]


def test_hermetic_chat_bot_cannot_reach_a_real_service() -> None:
    # INFRA-02 prohibition: the default stack never touches Chat, Max, a key or a real project.
    bot = _services()["chat-bot"]
    environment = _environment(bot)
    assert "env_file" not in bot
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in environment
    assert environment["CHAT_API"] == "recording"
    assert environment["DEPLOY_ENV"] == "local"
    assert environment["LLM_BASE_URL"] == "http://stub-llm:8090"
    assert environment["GOOGLE_CLOUD_PROJECT"] == HERMETIC_PROJECT
    assert environment["PUBSUB_EMULATOR_HOST"] == "pubsub:8085"
    assert environment["FIRESTORE_EMULATOR_HOST"] == "firestore:8080"
    assert environment["LANGSMITH_TRACING"] == "false"


def test_no_hermetic_service_carries_credentials_or_a_real_project() -> None:
    for name, service in _hermetic().items():
        assert "env_file" not in service, f"{name} would receive host variables"
        environment = _environment(service)
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in environment, name
        assert environment.get("GOOGLE_CLOUD_PROJECT", HERMETIC_PROJECT) == HERMETIC_PROJECT, name
        for volume in service.get("volumes", []):
            assert "secrets" not in str(volume), f"{name} mounts a secret path"
            assert "meridian" not in str(volume), f"{name} mounts Meridian credentials"


def test_live_chat_bot_is_wired_for_real_chat_and_meridian() -> None:
    bot = _services()["chat-bot-live"]
    environment = _environment(bot)
    assert environment["CHAT_API"] == "google"
    assert environment["LLM_BACKEND"] == "meridian"
    assert environment["LLM_BASE_URL"] == "http://meridian:3456"
    assert environment["INTAKE"] == "pubsub"
    assert environment["LANGSMITH_TRACING"] == "false"
    assert environment["DEPLOY_ENV"] == "local"
    assert environment["PORT"] == "8080", "the MCP server's PORT=8000 from .env must not leak in"
    assert "PUBSUB_EMULATOR_HOST" not in environment, "the live bot reads the real subscription"
    assert environment["GOOGLE_APPLICATION_CREDENTIALS"] == "/secrets/bot-sa.json"
    key_mounts = [v for v in bot["volumes"] if str(v).endswith(":/secrets/bot-sa.json:ro")]
    assert len(key_mounts) == 1, "the service-account key is mounted read-only"
    assert str(key_mounts[0]).startswith("${BOT_SA_KEY_FILE:?")
    assert bot["env_file"] == [{"path": ".env", "required": True}]


def test_both_bots_call_the_mcp_server_by_service_name() -> None:
    services = _services()
    for name in BOTS:
        assert _environment(services[name])["MCP_URL"] == "http://mcp-server:8000/mcp", name
    hosts = _environment(services["mcp-server"])["MCP_ALLOWED_HOSTS"].split(",")
    assert "mcp-server" in hosts


def test_start_order_is_fixed_by_depends_on_conditions() -> None:
    assert _depends_on("pubsub-init") == {"pubsub": "service_healthy"}
    mcp = _depends_on("mcp-server")
    assert mcp["sync"] == "service_completed_successfully"
    assert mcp["firestore"] == "service_healthy"
    bot = _depends_on("chat-bot")
    assert bot["pubsub-init"] == "service_completed_successfully"
    assert bot["sync"] == "service_completed_successfully"
    assert bot["mcp-server"] == "service_healthy"
    assert bot["firestore"] == "service_healthy"
    assert bot["stub-llm"] == "service_started"
    live = _depends_on("chat-bot-live")
    assert live["meridian"] == "service_started"
    assert live["mcp-server"] == "service_healthy"
    assert live["firestore"] == "service_healthy"


def test_one_shot_services_never_restart() -> None:
    for name in ("sync", "pubsub-init"):
        assert str(_services()[name]["restart"]) == "no", name


def test_mcp_server_artifacts_are_read_only_and_sync_writes_the_same_volume() -> None:
    services = _services()
    served = [v for v in services["mcp-server"]["volumes"] if ":/artifacts" in str(v)]
    assert served == ["artifacts:/artifacts:ro"]
    written = [v for v in services["sync"]["volumes"] if str(v) == "artifacts:/artifacts"]
    assert len(written) == 1, "the sync one-shot writes the named volume the server reads"
    assert "artifacts" in _load()["volumes"]


def test_sync_reads_its_sources_read_only() -> None:
    mounts = {
        str(v["target"]): v
        for v in _services()["sync"]["volumes"]
        if isinstance(v, dict)  # long syntax: a relative host path is never read as a volume name
    }
    assert set(mounts) == {"/handbook", "/guides-src"}
    for target, mount in mounts.items():
        assert mount["type"] == "bind" and mount["read_only"] is True, target
    assert mounts["/handbook"]["source"].startswith("${HANDBOOK_SRC_DIR:?")
    assert mounts["/guides-src"]["source"].startswith("${GUIDES_SRC_DIR:?")
    environment = _environment(_services()["sync"])
    assert environment["ARTIFACT_DIR"] == "/artifacts"
    assert environment["GUIDES_REPO_URL"] == "/guides-src"


def test_mcp_server_serves_a_local_store_without_auth_or_bot_secrets() -> None:
    # IN-03: env_file would hand every .env variable, bot secrets included, to the server.
    server = _services()["mcp-server"]
    assert "env_file" not in server
    environment = _environment(server)
    for secret in BOT_ONLY_SECRETS:
        assert secret not in environment
    assert not [key for key in environment if key.endswith(SECRET_SUFFIXES)]
    assert environment["ARTIFACT_STORE"] == "local"
    assert environment["ARTIFACT_DIR"] == "/artifacts"
    assert environment["AUTH_MODE"] == "off"
    assert environment["DEPLOY_ENV"] == "local"
    assert environment["GOOGLE_CLOUD_PROJECT"] == HERMETIC_PROJECT
    assert "/healthz" in " ".join(str(part) for part in server["healthcheck"]["test"])


def test_emulator_wiring_is_consistent() -> None:
    services = _services()
    for name in ("mcp-server", "chat-bot", "chat-bot-live"):
        assert _environment(services[name])["FIRESTORE_EMULATOR_HOST"] == "firestore:8080", name
    for emulator in ("firestore", "pubsub"):
        assert services[emulator]["image"].startswith("google/cloud-sdk:")
        assert services[emulator]["image"].endswith("-emulators")
    assert f"--project={HERMETIC_PROJECT}" in services["pubsub"]["command"]


def test_pubsub_init_creates_the_subscription_the_bot_pulls() -> None:
    script = "\n".join(str(part) for part in _services()["pubsub-init"]["command"])
    subscription = _environment(_services()["chat-bot"])["PUBSUB_SUBSCRIPTION"]
    assert subscription == f"projects/{HERMETIC_PROJECT}/subscriptions/chat-events"
    assert f"projects/{HERMETIC_PROJECT}" in script
    assert "put topics/chat-events" in script
    assert "put subscriptions/chat-events" in script
    assert f'"topic":"projects/{HERMETIC_PROJECT}/topics/chat-events"' in script
    assert "200|409" in script


def test_stub_llm_runs_the_mounted_stub_read_only() -> None:
    stub = _services()["stub-llm"]
    assert stub["build"]["target"] == "chat_bot"
    assert stub["command"] == ["python", "/stub/stub_llm.py"]
    assert stub["volumes"] == ["./deploy/compose:/stub:ro"]
    assert (ROOT / "deploy" / "compose" / "stub_llm.py").is_file()


def test_secret_looking_environment_values_are_interpolations() -> None:
    checked = 0
    for name, service in _services().items():
        for key, value in _environment(service).items():
            if key.endswith(SECRET_SUFFIXES):
                checked += 1
                assert INTERPOLATION.fullmatch(value), f"{name}.{key} must be a ${{...}} reference"
    assert checked >= 3, "meridian, the hermetic bot and the live bot each receive a secret"


def test_required_variables_have_no_default() -> None:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    for variable in (
        "BOT_SA_KEY_FILE",
        "MERIDIAN_API_KEY",
        "THREAD_KEY_SECRET",
        "HANDBOOK_SRC_DIR",
        "GUIDES_SRC_DIR",
        "REDACT_PAGE_FILES",
    ):
        assert f"${{{variable}:?" in text, variable


def test_env_example_mcp_url_matches_the_live_wiring() -> None:
    # IN-02: compose and kind call the Service name; the server admits it via MCP_ALLOWED_HOSTS.
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))
    assert values["MCP_URL"] == _environment(_services()["chat-bot-live"])["MCP_URL"]


def test_smoke_script_is_executable_and_bounded() -> None:
    text = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert os.access(SMOKE_SCRIPT, os.X_OK)
    assert "set -euo pipefail" in text
    assert 'SMOKE_TIMEOUT_SECONDS="${SMOKE_TIMEOUT_SECONDS:-120}"' in text
    assert "timeout after" in text
    assert text.count("round trip ok") == 1
    assert "handbook://02-ferie" in text and "Fonte: Manuale" in text
    assert "down -v" in text, "the trap removes the stack and its volume"
