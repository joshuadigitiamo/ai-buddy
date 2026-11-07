"""GoogleIdTokenAuth: bearer header, 50-minute cache, worker-thread fetch, no token in logs."""

import logging
import threading

import httpx2
import pytest
from google.auth.transport.requests import Request

from buddy_bot.mcp_client import FastMcpConnector, GoogleIdTokenAuth

pytestmark = pytest.mark.anyio

AUDIENCE = "https://mcp.example.invalid"
URL = "http://mcp.example.invalid/mcp"


class FakeFetch:
    """A fetch hook that returns tok-1, tok-2, ... and records audiences and calling threads."""

    def __init__(self) -> None:
        self.audiences: list[str] = []
        self.threads: list[int] = []

    def __call__(self, request: Request, audience: str) -> str:
        assert isinstance(request, Request)
        self.audiences.append(audience)
        self.threads.append(threading.get_ident())
        return f"tok-{len(self.audiences)}"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _recording_transport(seen: list[str | None]) -> httpx2.MockTransport:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx2.Response(200, json={})

    return httpx2.MockTransport(handler)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_sync_request_carries_the_bearer_token_for_the_audience() -> None:
    fetch, seen = FakeFetch(), list[str | None]()
    auth = GoogleIdTokenAuth(AUDIENCE, fetch=fetch)

    with httpx2.Client(transport=_recording_transport(seen), auth=auth) as client:
        client.get(URL)

    assert seen == ["Bearer tok-1"]
    assert fetch.audiences == [AUDIENCE]


def test_token_is_cached_until_the_lifetime_passes() -> None:
    fetch, clock, seen = FakeFetch(), FakeClock(), list[str | None]()
    auth = GoogleIdTokenAuth(AUDIENCE, fetch=fetch, lifetime_seconds=3000.0, clock=clock)

    with httpx2.Client(transport=_recording_transport(seen), auth=auth) as client:
        client.get(URL)
        clock.now += 2999.0
        client.get(URL)
        assert len(fetch.audiences) == 1
        clock.now += 2.0
        client.get(URL)

    assert seen == ["Bearer tok-1", "Bearer tok-1", "Bearer tok-2"]


def test_nothing_is_fetched_until_the_first_request() -> None:
    fetch = FakeFetch()

    GoogleIdTokenAuth(AUDIENCE, fetch=fetch)

    assert fetch.audiences == []


async def test_async_request_fetches_on_a_worker_thread() -> None:
    fetch, clock, seen = FakeFetch(), FakeClock(), list[str | None]()
    auth = GoogleIdTokenAuth(AUDIENCE, fetch=fetch, clock=clock)

    async with httpx2.AsyncClient(transport=_recording_transport(seen), auth=auth) as client:
        await client.get(URL)
        await client.get(URL)

    assert seen == ["Bearer tok-1", "Bearer tok-1"]
    assert fetch.audiences == [AUDIENCE]
    assert fetch.threads[0] != threading.get_ident()


async def test_a_fetch_error_keeps_its_type_and_no_request_is_sent() -> None:
    class FetchFailed(Exception):
        pass

    def failing(request: Request, audience: str) -> str:
        raise FetchFailed("no credentials")

    auth = GoogleIdTokenAuth(AUDIENCE, fetch=failing)
    seen: list[str | None] = []

    async with httpx2.AsyncClient(transport=_recording_transport(seen), auth=auth) as client:
        with pytest.raises(FetchFailed):
            await client.get(URL)

    assert seen == []


def _chain_text(error: BaseException | None) -> str:
    """str and repr of an exception and everything it was raised from or during."""
    parts: list[str] = []
    while error is not None:
        parts.append(f"{error!s} {error!r}")
        error = error.__cause__ or error.__context__
    return " ".join(parts)


@pytest.fixture
def unauthorized_mcp(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """Every HTTP request of any httpx2 async client is answered 401; sent headers are recorded."""
    seen: list[str | None] = []

    async def answer_unauthorized(
        self: httpx2.AsyncHTTPTransport, request: httpx2.Request
    ) -> httpx2.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx2.Response(401, json={"error": "unauthorized"}, request=request)

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", answer_unauthorized)
    return seen


async def test_an_unauthorized_mcp_call_surfaces_an_error_without_the_token(
    unauthorized_mcp: list[str | None], caplog: pytest.LogCaptureFixture
) -> None:
    token = "tok-sentinella-segreto"

    def fetch(request: Request, audience: str) -> str:
        return token

    connector = FastMcpConnector(URL, auth=GoogleIdTokenAuth(AUDIENCE, fetch=fetch))
    problems: list[BaseException] = []

    with caplog.at_level(logging.DEBUG):
        try:
            async with connector.session() as tools:
                await tools.handbook_search("ferie")
        except Exception as exc:
            problems.append(exc)

    assert len(problems) == 1
    assert f"Bearer {token}" in unauthorized_mcp
    assert token not in _chain_text(problems[0])
    assert token not in caplog.text
