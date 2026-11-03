"""ClickUpClient robustness: request shape, retries, error hygiene, response-shape tolerance."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from buddy_sync import clickup
from buddy_sync.clickup import ClickUpClient, ClickUpError, flatten_pages

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "clickup" / "pages.json"
TOKEN = "pk_SYNTHETIC_TOKEN_DO_NOT_USE_0000000000"
PAGES_PATH = "/api/v3/workspaces/123/docs/demo-doc/pages"

Handler = Callable[[httpx.Request], httpx.Response]


def _client(
    handler: Handler, sleeps: list[float] | None = None, base_url: str = "https://api.clickup.com"
) -> ClickUpClient:
    recorded = sleeps if sleeps is not None else []
    return ClickUpClient(
        token=SecretStr(TOKEN),
        base_url=base_url,
        timeout_s=5.0,
        transport=httpx.MockTransport(handler),
        sleep=recorded.append,
        max_retries=3,
    )


def _ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=FIXTURE.read_bytes())


def test_request_shape_and_token_header_without_scheme() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok(request)

    _client(handler).fetch_pages(123, "demo-doc")

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == PAGES_PATH
    assert request.url.params["max_page_depth"] == "-1"
    assert request.url.params["content_format"] == "text/md"
    assert request.headers["Authorization"] == TOKEN


def test_nested_pages_flatten_depth_first_and_skip_archived_subtree() -> None:
    flat, skipped = flatten_pages(_client(_ok).fetch_pages(123, "demo-doc"))

    assert [(p.page_id, p.depth, p.position) for p in flat] == [
        ("demo-page-0001", 0, 0),
        ("demo-page-0002", 1, 1),
        ("demo-page-0004", 2, 2),
        ("demo-page-0003", 1, 3),
        ("demo-page-0007", 2, 4),
        ("demo-page-wifi", 1, 5),
    ]
    assert skipped == 2
    assert flat[2].parent_id == "demo-page-0002"
    assert flat[0].parent_id is None


def test_object_body_with_pages_key_parses_like_array_body() -> None:
    array = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pages": array})

    from_object = _client(handler).fetch_pages(123, "demo-doc")
    from_array = _client(_ok).fetch_pages(123, "demo-doc")

    assert from_object == from_array


def test_429_with_retry_after_then_success_sleeps_once() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return _ok(request)

    pages = _client(handler, sleeps).fetch_pages(123, "demo-doc")

    assert calls == 2
    assert sleeps == [1.0]
    assert pages[0].id == "demo-page-0001"


def test_persistent_500_raises_after_max_retries_with_backoff() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, text="upstream exploded")

    with pytest.raises(ClickUpError) as info:
        _client(handler, sleeps).fetch_pages(123, "demo-doc")

    assert calls == 4
    assert sleeps == [1.0, 2.0, 4.0]
    assert "500" in str(info.value)
    assert "demo-doc" in str(info.value)
    assert ("upstream exploded" in str(info.value)) is False


def test_401_fails_at_once_without_retry() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="token rejected")

    with pytest.raises(ClickUpError, match="401"):
        _client(handler, sleeps).fetch_pages(123, "demo-doc")

    assert calls == 1
    assert sleeps == []


def test_retry_after_is_clamped_to_30_seconds_and_at_least_one() -> None:
    sleeps: list[float] = []
    codes = iter([429, 429, 200])
    retry_after = iter(["999", "0"])

    def handler(request: httpx.Request) -> httpx.Response:
        code = next(codes)
        if code == 200:
            return _ok(request)
        return httpx.Response(code, headers={"Retry-After": next(retry_after)})

    _client(handler, sleeps).fetch_pages(123, "demo-doc")

    assert sleeps == [30.0, 1.0]


def test_rate_limit_reset_header_is_used_when_retry_after_is_absent() -> None:
    sleeps: list[float] = []
    codes = iter([429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        if next(codes) == 200:
            return _ok(request)
        return httpx.Response(429, headers={"X-RateLimit-Reset": str(int(time.time()) + 5)})

    _client(handler, sleeps).fetch_pages(123, "demo-doc")

    assert len(sleeps) == 1
    assert 3.0 <= sleeps[0] <= 6.0


def test_oversized_body_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clickup, "MAX_RESPONSE_BYTES", 100)

    with pytest.raises(ClickUpError, match="too large"):
        _client(_ok).fetch_pages(123, "demo-doc")


def test_page_missing_id_names_field_path_but_not_content() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        page = {"name": "TOP-SECRET-TITLE", "content": "TOP-SECRET-BODY"}
        return httpx.Response(200, json=[page])

    with pytest.raises(ClickUpError) as info:
        _client(handler).fetch_pages(123, "demo-doc")

    message = str(info.value)
    assert "0.id" in message
    assert ("TOP-SECRET-TITLE" in message) is False
    assert ("TOP-SECRET-BODY" in message) is False


@pytest.mark.parametrize("body", [b"not json at all", b'"a string"', b"42"])
def test_non_page_payload_raises_without_echoing_body(body: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(ClickUpError) as info:
        _client(handler).fetch_pages(123, "demo-doc")

    assert (body.decode() in str(info.value)) is False


def test_transport_error_becomes_clickup_error_without_details() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom with pk_SYNTHETIC_TOKEN_DO_NOT_USE_0000000000 inside")

    with pytest.raises(ClickUpError) as info:
        _client(handler).fetch_pages(123, "demo-doc")

    assert (TOKEN in str(info.value)) is False
    assert "demo-doc" in str(info.value)


def test_token_never_in_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=f"echo {TOKEN}")

    with caplog.at_level(logging.DEBUG), pytest.raises(ClickUpError) as info:
        _client(handler).fetch_pages(123, "demo-doc")

    assert (TOKEN in str(info.value)) is False
    assert (TOKEN in repr(info.value)) is False
    assert (TOKEN in caplog.text) is False


def test_plain_http_base_url_is_refused_without_injected_transport() -> None:
    with pytest.raises(ClickUpError, match="https"):
        ClickUpClient(token=SecretStr(TOKEN), base_url="http://api.clickup.com", timeout_s=5.0)


def test_https_base_url_is_accepted_without_transport() -> None:
    client = ClickUpClient(
        token=SecretStr(TOKEN), base_url="https://api.clickup.com", timeout_s=5.0
    )
    client.close()


def test_context_manager_closes_the_client() -> None:
    with _client(_ok) as client:
        assert client.fetch_pages(123, "demo-doc")
