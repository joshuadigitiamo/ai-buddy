"""Structural guard for docker-compose.dev.yml (offline): ports, pins, mounts, secrets."""

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "docker-compose.dev.yml"

# 03-01-SUMMARY.md, decision meridian_credentials: option "b" is a dedicated named volume.
# Under "a" or "c" the host credentials would be bound and this constant must change together
# with the D-16 amendment in 03-CONTEXT.md.
MERIDIAN_CREDENTIALS_OPTION = "b"

SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN")
MERIDIAN_CONTEXT = re.compile(r"https://github\.com/rynfar/meridian\.git#[0-9a-f]{40}")
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


def test_has_the_four_dev_services() -> None:
    assert set(_services()) == {"meridian", "firestore", "mcp_server", "chat_bot"}


def test_no_service_publishes_a_port() -> None:
    for name, service in _services().items():
        assert "ports" not in service, f"{name} publishes a port to the host (T-03-35)"


def test_meridian_is_built_from_the_approved_commit() -> None:
    context = _services()["meridian"]["build"]["context"]
    assert MERIDIAN_CONTEXT.fullmatch(context), "Meridian must build from a 40-hex commit (T-03-36)"
    assert context.endswith("cafdcf780f1b40c8f0dee17481132f47b4cbb353"), "03-01 approved SHA"


def test_meridian_request_logging_is_silenced() -> None:
    # BOT-11: no question text in logs. At the approved SHA the per-request `[PROXY] ... msgs=`
    # line carries only roles and content types, but MERIDIAN_SILENT=1 (src/proxy/types.ts)
    # removes every routine [PROXY] request line, so a later Meridian change cannot start
    # printing prompt text unnoticed. MERIDIAN_DEBUG is verbose request/session logging.
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
        assert "meridian-claude:/home/claude/.claude" in volumes
        declared = _load()["volumes"]["meridian-claude"]
        assert declared == {"external": True}, "the volume is seeded once, never created empty"
        for name, service in _services().items():
            if name != "meridian":
                assert not any("meridian-claude" in str(v) for v in service.get("volumes", [])), (
                    f"{name} must not mount the credentials volume"
                )


def test_chat_bot_is_wired_for_live_meridian_and_pubsub() -> None:
    bot = _services()["chat_bot"]
    environment = _environment(bot)
    assert environment["LLM_BACKEND"] == "meridian"
    assert environment["INTAKE"] == "pubsub"
    assert environment["LANGSMITH_TRACING"] == "false"
    assert environment["LLM_BASE_URL"] == "http://meridian:3456"
    assert environment["PORT"] == "8080", "the MCP server's PORT=8000 from .env must not leak in"
    key_mounts = [v for v in bot["volumes"] if str(v).endswith("/secrets/bot-sa.json:ro")]
    assert len(key_mounts) == 1, "the service-account key is mounted read-only"
    assert environment["GOOGLE_APPLICATION_CREDENTIALS"] == "/secrets/bot-sa.json"


def test_chat_bot_waits_for_its_dependencies() -> None:
    depends_on = _services()["chat_bot"]["depends_on"]
    assert set(depends_on) == {"meridian", "mcp_server", "firestore"}
    assert depends_on["firestore"]["condition"] == "service_healthy"


def test_mcp_server_artifacts_are_read_only() -> None:
    volumes = _services()["mcp_server"]["volumes"]
    artifacts = [v for v in volumes if ":/artifacts" in str(v)]
    assert len(artifacts) == 1
    assert str(artifacts[0]).endswith(":/artifacts:ro")


def test_mcp_server_admits_the_bot_host() -> None:
    # Live check 2026-11-07: without this the Host guard answered every bot call with 421.
    # The server admits plain http only for loopback hosts, so the bot must share its network
    # namespace and call it on localhost.
    bot = _services()["chat_bot"]
    assert bot["network_mode"] == "service:mcp_server"
    assert _environment(bot)["MCP_URL"] == "http://localhost:8000/mcp"


def test_emulator_wiring_is_consistent() -> None:
    services = _services()
    for name in ("mcp_server", "chat_bot"):
        assert _environment(services[name])["FIRESTORE_EMULATOR_HOST"] == "firestore:8080"
    assert services["firestore"]["image"].startswith("google/cloud-sdk:")
    assert services["firestore"]["image"].endswith("-emulators")


def test_secret_looking_environment_values_are_interpolations() -> None:
    checked = 0
    for name, service in _services().items():
        for key, value in _environment(service).items():
            if key.endswith(SECRET_SUFFIXES):
                checked += 1
                assert INTERPOLATION.fullmatch(value), f"{name}.{key} must be a ${{...}} reference"
    assert checked >= 2, "meridian and chat_bot both receive MERIDIAN_API_KEY"


def test_key_file_and_required_variables_have_no_default() -> None:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "${BOT_SA_KEY_FILE:?" in text
    assert "${MERIDIAN_API_KEY:?" in text
    assert "${GOOGLE_CLOUD_PROJECT:?" in text


def test_env_example_mcp_url_matches_the_dev_wiring() -> None:
    # IN-02: the compose-style host name got 421 Misdirected Request in the live check.
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))
    assert values["MCP_URL"] == _environment(_services()["chat_bot"])["MCP_URL"]


BOT_ONLY_SECRETS = ("THREAD_KEY_SECRET", "MERIDIAN_API_KEY", "ANTHROPIC_API_KEY")


def test_mcp_server_does_not_receive_the_bots_env_file_or_secrets() -> None:
    # IN-03: env_file would hand every .env variable, bot secrets included, to the server.
    server = _services()["mcp_server"]
    assert "env_file" not in server
    environment = _environment(server)
    for secret in BOT_ONLY_SECRETS:
        assert secret not in environment
    assert not [key for key in environment if key.endswith(SECRET_SUFFIXES)]


def test_mcp_server_still_gets_the_variables_it_requires() -> None:
    environment = _environment(_services()["mcp_server"])
    assert INTERPOLATION.fullmatch(environment["GUIDES_WEB_BASE"]), "required by McpSettings"
    assert environment["ARTIFACT_DIR"] == "/artifacts"
    assert environment["AUTH_MODE"] == "off"
