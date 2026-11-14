"""BOT-01 and BOT-02 end to end: ``python -m buddy_bot`` as a real process on the emulators."""

import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx2
import pytest
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from tests.unit.chat_bot.conftest import EVENTS_DIR

from buddy_bot.config import BotSettings

pytestmark = [
    pytest.mark.firestore,
    pytest.mark.pubsub,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not (os.environ.get("FIRESTORE_EMULATOR_HOST") and os.environ.get("PUBSUB_EMULATOR_HOST")),
        reason="needs both emulators: run ./run-unit-tests.sh --emulator",
    ),
]

PROJECT = "demo-ai-buddy"
STARTUP_TIMEOUT_SECONDS = 30
EVENT_WAIT_SECONDS = 20
ALLOWED_USER = "users/111111111111111111111"
STRANGER = "users/2222222222222222222"
STARTED_LINE = "starting: intake pubsub"
DROPPED_LINE = "event dropped: sender not allowed"

# The caller's environment (an env file is loaded into the container) must not leak settings in.
_BOT_VARIABLES = frozenset(
    {name.upper() for name in BotSettings.model_fields} | {"K_SERVICE", "LANGCHAIN_TRACING_V2"}
)
_BASE_ENV = {
    "ALLOWED_USERS": ALLOWED_USER,
    "LLM_BACKEND": "api",
    "ANTHROPIC_API_KEY": "sentinella-chiave-api-finta",
    "THREAD_KEY_SECRET": "t" * 40,
    "GOOGLE_CLOUD_PROJECT": PROJECT,
    "MCP_URL": "http://127.0.0.1:9/mcp",
    "MCP_AUTH": "none",
    "DEPLOY_ENV": "local",
    "VIDEO_THUMBNAIL_URL": "https://example.invalid/video-thumbnail.png",
    "LANGSMITH_TRACING": "false",
}


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _stranger_event() -> bytes:
    """The recorded DM event with its sender (and user) replaced by a non-allowlisted id."""
    text = (EVENTS_DIR / "legacy_dm_message.json").read_text(encoding="utf-8")
    return text.replace(ALLOWED_USER, STRANGER).encode()


def _bot_env(**settings: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _BOT_VARIABLES}
    env.update(_BASE_ENV)
    env.update(settings)
    return env


@contextmanager
def _bot_process(env: dict[str, str], stderr_path: Path) -> Iterator[subprocess.Popen[bytes]]:
    with stderr_path.open("wb") as stderr_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "buddy_bot"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
        try:
            yield process
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def _wait_for_port(port: int, process: subprocess.Popen[bytes], stderr_path: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"bot exited with {process.returncode}: {stderr_path.read_text()[-2000:]}"
            )
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise AssertionError(f"bot did not listen within {STARTUP_TIMEOUT_SECONDS} s")


def _wait_for_text(
    text: str, process: subprocess.Popen[bytes], stderr_path: Path, seconds: float
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if text in stderr_path.read_text():
            return
        if process.poll() is not None:
            raise AssertionError(
                f"bot exited with {process.returncode}: {stderr_path.read_text()[-2000:]}"
            )
        time.sleep(0.2)
    raise AssertionError(f"{text!r} not seen on stderr within {seconds} s")


class _Channel:
    """A fresh topic and subscription on the emulator, removed afterwards."""

    def __init__(self) -> None:
        suffix = uuid.uuid4().hex
        self.publisher = PublisherClient()
        self.subscriber = SubscriberClient()
        self.topic = f"projects/{PROJECT}/topics/bot-{suffix}"
        self.subscription = f"projects/{PROJECT}/subscriptions/bot-{suffix}"
        self.publisher.create_topic(name=self.topic)
        self.subscriber.create_subscription(name=self.subscription, topic=self.topic)

    def publish(self, data: bytes) -> None:
        self.publisher.publish(self.topic, data).result(timeout=10)

    def close(self) -> None:
        self.subscriber.delete_subscription(request={"subscription": self.subscription})
        self.publisher.delete_topic(request={"topic": self.topic})
        self.subscriber.close()


@pytest.fixture
def channel() -> Iterator[_Channel]:
    created = _Channel()
    yield created
    created.close()


@pytest.fixture
def stderr_path(tmp_path: Path) -> Path:
    return tmp_path / "bot.stderr"


async def test_http_intake_rejects_a_request_without_a_token(stderr_path: Path) -> None:
    port = _free_port()
    env = _bot_env(
        INTAKE="http",
        BOT_HOST="127.0.0.1",
        PORT=str(port),
        CHAT_JWT_AUDIENCE="https://bot.example.invalid",
        CHAT_JWT_ISSUER_EMAIL="chat@system.gserviceaccount.example.invalid",
    )
    with _bot_process(env, stderr_path) as process:
        _wait_for_port(port, process, stderr_path)
        async with httpx2.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            unauthenticated = await http.post("/", json={"type": "MESSAGE"})
            wrong_method = await http.get("/")
            malformed = await http.post(
                "/", json={"type": "MESSAGE"}, headers={"Authorization": "Bearer not-a-jwt"}
            )
    assert unauthenticated.status_code == 401
    assert wrong_method.status_code == 405
    assert malformed.status_code == 401
    assert "starting: intake http" in stderr_path.read_text()


def test_missing_allowed_users_exits_one_naming_the_variable(stderr_path: Path) -> None:
    env = _bot_env(INTAKE="pubsub", PUBSUB_SUBSCRIPTION=f"projects/{PROJECT}/subscriptions/unused")
    del env["ALLOWED_USERS"]
    with _bot_process(env, stderr_path) as process:
        assert process.wait(timeout=STARTUP_TIMEOUT_SECONDS) == 1
    captured = stderr_path.read_text()
    assert "ALLOWED_USERS" in captured
    assert "Traceback" not in captured
    assert _BASE_ENV["THREAD_KEY_SECRET"] not in captured


async def test_pubsub_intake_drops_a_stranger_and_keeps_running(
    channel: _Channel, stderr_path: Path
) -> None:
    env = _bot_env(INTAKE="pubsub", PUBSUB_SUBSCRIPTION=channel.subscription)
    with _bot_process(env, stderr_path) as process:
        _wait_for_text(STARTED_LINE, process, stderr_path, STARTUP_TIMEOUT_SECONDS)
        channel.publish(_stranger_event())
        _wait_for_text(DROPPED_LINE, process, stderr_path, EVENT_WAIT_SECONDS)
        assert process.poll() is None
    captured = stderr_path.read_text()
    assert "users/" not in captured
    assert "@example.invalid" not in captured
