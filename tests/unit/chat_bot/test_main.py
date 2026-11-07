"""Composition root: startup failures are loud and safe, a valid config wires the right intake."""

import socket
from collections.abc import Callable
from typing import Any

import pytest
from google.cloud import firestore
from google.oauth2 import id_token

from buddy_bot import cli
from buddy_bot.cli import main
from buddy_bot.config import BotSettings
from buddy_bot.intake.http import HttpIntake
from buddy_bot.intake.pubsub import PubSubIntake
from buddy_bot.ports import EventHandler, IntakePort
from buddy_bot.service import BotService

SECRET_SENTINEL = "sentinella-segreto-thread-" + "x" * 14
SHORT_SECRET_SENTINEL = "sentinella-corto"
USER_ONE = "users/111111111111111111111"
USER_TWO = "users/222222222222222222222"

_SETTING_VARIABLES = tuple(name.upper() for name in BotSettings.model_fields) + (
    "K_SERVICE",
    "LANGCHAIN_TRACING_V2",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """run-unit-tests.sh loads an env file into the container; start from an empty environment."""
    for name in _SETTING_VARIABLES:
        monkeypatch.delenv(name, raising=False)


class RunStub:
    """Records what the composition root hands to the runner."""

    def __init__(self) -> None:
        self.calls = 0
        self.intake: IntakePort | None = None
        self.handler: EventHandler | None = None

    def __call__(self, intake: IntakePort, handler: EventHandler) -> None:
        self.calls += 1
        self.intake = intake
        self.handler = handler


@pytest.fixture
def run_stub() -> RunStub:
    return RunStub()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Set a valid offline configuration; an override of None removes the variable."""

    def apply(**overrides: str | None) -> None:
        values: dict[str, str | None] = {
            "ALLOWED_USERS": USER_ONE,
            "LLM_BACKEND": "api",
            "ANTHROPIC_API_KEY": "sentinella-chiave-api",
            "THREAD_KEY_SECRET": SECRET_SENTINEL,
            "GOOGLE_CLOUD_PROJECT": "demo-ai-buddy",
            "MCP_URL": "http://localhost:8000/mcp",
            "MCP_AUTH": "none",
            "INTAKE": "pubsub",
            "PUBSUB_SUBSCRIPTION": "projects/demo-ai-buddy/subscriptions/chat-events",
            "VIDEO_THUMBNAIL_URL": "https://example.invalid/video-thumbnail.png",
        }
        values.update(overrides)
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)

    return apply


def _error_lines(captured: str) -> list[str]:
    return [line for line in captured.splitlines() if line.startswith("ERROR")]


def test_pubsub_intake_receives_the_service_handler(
    valid_env: Callable[..., None], run_stub: RunStub, capsys: pytest.CaptureFixture[str]
) -> None:
    valid_env(ALLOWED_USERS=f"{USER_ONE}, {USER_TWO}", LLM_BACKEND="api")

    assert main([], run=run_stub) == 0

    assert run_stub.calls == 1
    assert isinstance(run_stub.intake, PubSubIntake)
    handler: Any = run_stub.handler
    assert isinstance(handler.__self__, BotService)
    assert handler.__name__ == "handle"
    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("INFO")]
    assert lines == [
        "INFO buddy_bot starting: intake pubsub, llm backend api, 2 allowed user(s), memory turns 3"
    ]


def test_startup_output_names_no_identity_or_secret(
    valid_env: Callable[..., None], run_stub: RunStub, capsys: pytest.CaptureFixture[str]
) -> None:
    valid_env()

    assert main([], run=run_stub) == 0

    captured = capsys.readouterr()
    for text in (captured.err, captured.out):
        assert "users/" not in text
        assert SECRET_SENTINEL not in text
        assert "sentinella-chiave-api" not in text


def test_http_intake_is_selected_by_configuration(
    valid_env: Callable[..., None], run_stub: RunStub
) -> None:
    valid_env(
        INTAKE="http",
        PUBSUB_SUBSCRIPTION=None,
        CHAT_JWT_AUDIENCE="https://bot.example.invalid",
        CHAT_JWT_ISSUER_EMAIL="chat@system.gserviceaccount.example.invalid",
    )

    assert main([], run=run_stub) == 0

    assert isinstance(run_stub.intake, HttpIntake)


def test_google_id_token_auth_is_wired_without_fetching_a_token(
    valid_env: Callable[..., None], run_stub: RunStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid_env(MCP_AUTH="google_id_token", MCP_AUDIENCE="https://mcp.example.invalid")
    fetched: list[str] = []

    def refuse(*args: Any, **kwargs: Any) -> str:
        fetched.append("fetch_id_token")
        raise AssertionError("an ID token must not be fetched at startup")

    monkeypatch.setattr(id_token, "fetch_id_token", refuse)

    assert main([], run=run_stub) == 0

    assert fetched == []


def test_startup_makes_no_network_call(
    valid_env: Callable[..., None], run_stub: RunStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid_env(MCP_AUTH="google_id_token", MCP_AUDIENCE="https://mcp.example.invalid")
    attempted: list[str] = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        attempted.append("call")
        raise AssertionError("no client may be built or connected at startup")

    monkeypatch.setattr(firestore, "AsyncClient", refuse)
    monkeypatch.setattr(cli, "build_chat_client", refuse)
    monkeypatch.setattr(id_token, "fetch_id_token", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)

    assert main([], run=run_stub) == 0

    assert attempted == []
    assert run_stub.calls == 1


def test_missing_variables_are_named_without_a_traceback(
    valid_env: Callable[..., None], run_stub: RunStub, capsys: pytest.CaptureFixture[str]
) -> None:
    valid_env(ALLOWED_USERS=None, MCP_URL=None)

    assert main([], run=run_stub) == 1

    captured = capsys.readouterr().err
    errors = _error_lines(captured)
    assert len(errors) == 1
    assert "ALLOWED_USERS" in errors[0]
    assert "MCP_URL" in errors[0]
    assert "Traceback" not in captured
    assert run_stub.calls == 0


def test_missing_google_cloud_project_is_named(
    valid_env: Callable[..., None], run_stub: RunStub, capsys: pytest.CaptureFixture[str]
) -> None:
    valid_env(GOOGLE_CLOUD_PROJECT=None)

    assert main([], run=run_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "GOOGLE_CLOUD_PROJECT" in errors[0]
    assert run_stub.calls == 0


@pytest.mark.parametrize(
    ("overrides", "named"),
    [
        pytest.param(
            {
                "LLM_BACKEND": "meridian",
                "LLM_BASE_URL": "http://meridian:3456",
                "ANTHROPIC_API_KEY": None,
                "ALLOWED_USERS": f"{USER_ONE},{USER_TWO}",
            },
            "ALLOWED_USERS",
            id="meridian-with-two-users",
        ),
        pytest.param({"LLM_BACKEND": "vertex"}, "LLM_BACKEND", id="vertex"),
        pytest.param({"LANGSMITH_TRACING": "true"}, "LANGSMITH_TRACING", id="tracing"),
        pytest.param({"LANGCHAIN_TRACING_V2": "true"}, "LANGSMITH_TRACING", id="legacy-tracing"),
        pytest.param(
            {"MCP_AUTH": "none", "K_SERVICE": "buddy-bot"}, "MCP_AUTH", id="auth-none-on-cloud-run"
        ),
        pytest.param(
            {"THREAD_KEY_SECRET": SHORT_SECRET_SENTINEL}, "THREAD_KEY_SECRET", id="short-secret"
        ),
    ],
)
def test_refused_configurations_exit_one_with_one_safe_line(
    valid_env: Callable[..., None],
    run_stub: RunStub,
    capsys: pytest.CaptureFixture[str],
    overrides: dict[str, str | None],
    named: str,
) -> None:
    valid_env(**overrides)

    assert main([], run=run_stub) == 1

    captured = capsys.readouterr().err
    errors = _error_lines(captured)
    assert len(errors) == 1
    assert named in errors[0]
    assert "Traceback" not in captured
    for secret in (SECRET_SENTINEL, SHORT_SECRET_SENTINEL, "sentinella-chiave-api"):
        assert secret not in captured
    assert run_stub.calls == 0
