"""BOT-02: the HTTP intake accepts only Chat requests signed by Google for this endpoint.

Tokens are signed with a local RSA key; google-auth's real `verify_oauth2_token` runs against a
fake Request that serves that key as Google's certificate map, so signature, issuer and expiry
checks are not mocked.
"""

import asyncio
import json
import logging
import socket
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

import httpx2
import pytest
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from google.auth.transport import Request, Response
from starlette.applications import Starlette
from tests.unit.chat_bot.conftest import load_event

from buddy_bot.intake.http import (
    ACK_SECONDS,
    CERT_FETCH_TIMEOUT,
    CERT_TTL_SECONDS,
    MAX_BODY_BYTES,
    ChatTokenVerifier,
    HttpIntake,
    build_http_app,
)

pytestmark = pytest.mark.anyio

AUDIENCE = "https://bot.example.invalid/chat"
CHAT_EMAIL = "service-123@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"
OTHER_EMAIL = "attacker@example.invalid"
GOOGLE_ISSUER = "https://accounts.google.com"
KEY_ID = "test-key-1"


class _CertsResponse(Response):
    def __init__(self, payload: Mapping[str, str]) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    @property
    def status(self) -> int:
        return 200

    @property
    def headers(self) -> Mapping[str, str]:
        return {}

    @property
    def data(self) -> bytes:
        return self._data


class _CertsRequest(Request):
    """Answers every certificate fetch with the test public key."""

    def __init__(self, key: RSAKeyPair) -> None:
        self._certs = {KEY_ID: key.public_key}
        self.urls: list[str] = []
        self.timeouts: list[float | None] = []
        self.fail = False

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Response:
        self.urls.append(url)
        self.timeouts.append(timeout)
        if self.fail:
            raise OSError("certs unreachable")
        return _CertsResponse(self._certs)


class _Handler:
    """Records events; optionally sleeps to model a slow run."""

    def __init__(self, delay: float = 0.0, fail: bool = False) -> None:
        self.events: list[Mapping[str, Any]] = []
        self.finished = 0
        self._delay = delay
        self._fail = fail

    async def __call__(self, event: Mapping[str, Any]) -> None:
        self.events.append(event)
        if self._delay:
            await asyncio.sleep(self._delay)
        self.finished += 1
        if self._fail:
            raise RuntimeError("boom")


@pytest.fixture
def key() -> RSAKeyPair:
    return RSAKeyPair.generate()


@pytest.fixture
def certs(key: RSAKeyPair) -> _CertsRequest:
    return _CertsRequest(key)


@pytest.fixture
def verifier(certs: _CertsRequest) -> ChatTokenVerifier:
    return ChatTokenVerifier(AUDIENCE, CHAT_EMAIL, request=certs)


@pytest.fixture
def sign(key: RSAKeyPair) -> Callable[..., str]:
    def build(
        *,
        aud: str = AUDIENCE,
        email: str = CHAT_EMAIL,
        verified: bool | str = True,
        expires_in: int = 300,
        issuer: str = GOOGLE_ISSUER,
        signer: RSAKeyPair | None = None,
    ) -> str:
        pair = signer or key
        return pair.create_token(
            subject="1234567890",
            issuer=issuer,
            audience=aud,
            expires_in_seconds=expires_in,
            additional_claims={"email": email, "email_verified": verified},
            kid=KEY_ID,
        )

    return build


def _client(app: Starlette) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://bot")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_valid_token_returns_empty_object_and_hands_the_event_over(
    verifier: ChatTokenVerifier, sign: Callable[..., str], certs: _CertsRequest
) -> None:
    handler = _Handler()
    event = load_event("legacy_dm_message")
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.post("/", content=json.dumps(event), headers=_auth(sign()))
    assert response.status_code == 200
    assert response.json() == {}
    assert handler.events == [event]
    assert certs.urls, "google-auth fetched the certificate map through the injected Request"


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer "}, {"Authorization": "Bearer"}],
    ids=["missing", "basic-scheme", "empty-token", "no-token"],
)
async def test_missing_or_malformed_authorization_is_401_with_empty_body(
    verifier: ChatTokenVerifier, headers: dict[str, str]
) -> None:
    handler = _Handler()
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.post("/", content="{}", headers=headers)
    assert response.status_code == 401
    assert response.content == b""
    assert handler.events == []


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": AUDIENCE + "/"},
        {"aud": "https://other.example.invalid/"},
        {"email": OTHER_EMAIL},
        {"verified": False},
        {"verified": "false"},
        {"expires_in": -5},
        {"issuer": "https://evil.example.invalid"},
    ],
    ids=[
        "audience-trailing-slash",
        "audience-other",
        "other-service-account",
        "email-not-verified",
        "email-not-verified-string",
        "expired",
        "wrong-issuer",
    ],
)
async def test_token_failing_a_check_is_401(
    verifier: ChatTokenVerifier, sign: Callable[..., str], claims: dict[str, Any]
) -> None:
    handler = _Handler()
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.post("/", content="{}", headers=_auth(sign(**claims)))
    assert response.status_code == 401
    assert response.content == b""
    assert handler.events == []


async def test_token_signed_by_another_key_is_401(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler()
    token = sign(signer=RSAKeyPair.generate())
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.post("/", content="{}", headers=_auth(token))
    assert response.status_code == 401
    assert handler.events == []


async def test_issuer_email_match_ignores_case(
    certs: _CertsRequest, sign: Callable[..., str]
) -> None:
    verifier = ChatTokenVerifier(AUDIENCE, CHAT_EMAIL.upper(), request=certs)
    assert await verifier.verify(sign()) is True


async def test_verifier_without_audience_is_refused() -> None:
    with pytest.raises(ValueError, match="audience"):
        ChatTokenVerifier("", CHAT_EMAIL)


@pytest.mark.parametrize("body", ["", "not json", "[1,2]", '"text"'])
async def test_verified_request_with_unusable_body_is_400(
    verifier: ChatTokenVerifier, sign: Callable[..., str], body: str
) -> None:
    handler = _Handler()
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.post("/", content=body, headers=_auth(sign()))
    assert response.status_code == 400
    assert handler.events == []


async def test_declared_oversized_body_is_413(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler()
    body = b" " * (MAX_BODY_BYTES + 1)
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.post("/", content=body, headers=_auth(sign()))
    assert response.status_code == 413
    assert handler.events == []


async def test_streamed_oversized_body_is_413(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler()

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(5):
            yield b" " * 300

    async with _client(build_http_app(handler, verifier, max_body_bytes=1000)) as http:
        response = await http.post("/", content=chunks(), headers=_auth(sign()))
    assert response.status_code == 413
    assert handler.events == []


async def test_body_at_the_limit_is_accepted(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler()
    payload = json.dumps({"k": "v"}).encode()
    async with _client(build_http_app(handler, verifier, max_body_bytes=len(payload))) as http:
        response = await http.post("/", content=payload, headers=_auth(sign()))
    assert response.status_code == 200
    assert handler.events == [{"k": "v"}]


async def test_get_is_405(verifier: ChatTokenVerifier) -> None:
    handler = _Handler()
    async with _client(build_http_app(handler, verifier)) as http:
        response = await http.get("/")
    assert response.status_code == 405
    assert handler.events == []


async def test_slow_run_is_acked_after_the_window_and_still_completes(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler(delay=0.2)
    app = build_http_app(handler, verifier, ack_seconds=0.05)
    async with _client(app) as http:
        response = await http.post("/", content="{}", headers=_auth(sign()))
        assert response.status_code == 200
        assert response.json() == {}
        assert handler.finished == 0, "the response left before the run finished"
        await asyncio.sleep(0.4)
    assert handler.finished == 1


async def test_ack_window_zero_returns_at_once(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler(delay=0.2)
    async with _client(build_http_app(handler, verifier, ack_seconds=0.0)) as http:
        response = await http.post("/", content="{}", headers=_auth(sign()))
        assert response.status_code == 200
        assert handler.finished == 0
        await asyncio.sleep(0.4)
    assert handler.finished == 1


async def test_fast_run_finishes_before_the_response(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler(delay=0.05)
    async with _client(build_http_app(handler, verifier, ack_seconds=5.0)) as http:
        response = await http.post("/", content="{}", headers=_auth(sign()))
    assert response.status_code == 200
    assert handler.finished == 1


async def test_failing_handler_still_answers_empty_object_without_detail(
    verifier: ChatTokenVerifier, sign: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    handler = _Handler(fail=True)
    with caplog.at_level(logging.DEBUG):
        async with _client(build_http_app(handler, verifier)) as http:
            response = await http.post("/", content="{}", headers=_auth(sign()))
    assert response.status_code == 200
    assert response.json() == {}
    assert "boom" not in caplog.text


async def test_logs_never_carry_the_token(
    verifier: ChatTokenVerifier, sign: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    token = sign(email=OTHER_EMAIL)
    with caplog.at_level(logging.DEBUG):
        async with _client(build_http_app(_Handler(), verifier)) as http:
            await http.post("/", content="{}", headers=_auth(token))
    assert token not in caplog.text
    assert OTHER_EMAIL not in caplog.text


async def test_concurrent_events_are_handled_independently(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler(delay=0.05)
    async with _client(build_http_app(handler, verifier)) as http:
        first, second = await asyncio.gather(
            http.post("/", content='{"n": 1}', headers=_auth(sign())),
            http.post("/", content='{"n": 2}', headers=_auth(sign())),
        )
    assert first.status_code == second.status_code == 200
    assert sorted(e["n"] for e in handler.events) == [1, 2]
    assert handler.finished == 2


def test_constants_follow_the_http_ack_decision() -> None:
    assert ACK_SECONDS == 25.0
    assert MAX_BODY_BYTES == 1_048_576


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def test_http_intake_serves_over_a_real_socket_and_stops_on_cancel(
    verifier: ChatTokenVerifier, sign: Callable[..., str]
) -> None:
    handler = _Handler()
    port = _free_port()
    intake = HttpIntake(verifier, host="127.0.0.1", port=port, ack_seconds=1.0)
    task = asyncio.create_task(intake.run(handler))
    try:
        async with httpx2.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            for _ in range(100):
                try:
                    response = await http.post("/", content='{"a": 1}', headers=_auth(sign()))
                    break
                except httpx2.TransportError:
                    await asyncio.sleep(0.05)
            else:
                raise AssertionError("server did not start")
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert response.status_code == 200
    assert handler.events == [{"a": 1}]
    with socket.socket() as probe:
        probe.settimeout(0.5)
        assert probe.connect_ex(("127.0.0.1", port)) != 0, "the port is released after cancel"


def test_http_intake_turns_access_logging_off(verifier: ChatTokenVerifier) -> None:
    config = HttpIntake(verifier, host="127.0.0.1", port=8080, ack_seconds=1.0).uvicorn_config(
        _Handler()
    )
    assert config.access_log is False
    assert config.port == 8080


async def test_certificates_are_fetched_once_and_cached(
    verifier: ChatTokenVerifier, sign: Callable[..., str], certs: _CertsRequest
) -> None:
    results = [await verifier.verify(sign()) for _ in range(5)]

    assert results == [True] * 5
    assert len(certs.urls) == 1


async def test_certificate_fetch_is_bounded_by_a_short_timeout(
    verifier: ChatTokenVerifier, sign: Callable[..., str], certs: _CertsRequest
) -> None:
    await verifier.verify(sign())

    assert certs.timeouts == [CERT_FETCH_TIMEOUT]
    assert CERT_FETCH_TIMEOUT <= 10


async def test_cached_certificates_expire_after_the_ttl(
    key: RSAKeyPair, certs: _CertsRequest, sign: Callable[..., str]
) -> None:
    now = [1000.0]
    verifier = ChatTokenVerifier(AUDIENCE, CHAT_EMAIL, request=certs, clock=lambda: now[0])

    await verifier.verify(sign())
    now[0] += CERT_TTL_SECONDS - 1
    await verifier.verify(sign())
    assert len(certs.urls) == 1
    now[0] += 2
    await verifier.verify(sign())
    assert len(certs.urls) == 2


async def test_a_failed_certificate_fetch_is_not_cached(
    verifier: ChatTokenVerifier, sign: Callable[..., str], certs: _CertsRequest
) -> None:
    certs.fail = True
    assert await verifier.verify(sign()) is False
    certs.fail = False

    assert await verifier.verify(sign()) is True
    assert len(certs.urls) == 2


@pytest.mark.parametrize(
    "token",
    ["x", "a.b", "a.b.c.d", "a..c", "a b.c.d", "a.b.c\n", "é.b.c", "a." + "b" * 9000 + ".c"],
    ids=["one", "two", "four", "empty-part", "space", "newline", "non-ascii", "huge"],
)
async def test_a_token_that_is_not_jwt_shaped_never_reaches_the_network(
    verifier: ChatTokenVerifier, certs: _CertsRequest, token: str
) -> None:
    assert await verifier.verify(token) is False
    assert certs.urls == []
