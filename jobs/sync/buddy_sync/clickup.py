"""ClickUp v3 REST adapter: the only module that knows ClickUp field names.

``ClickUpClient.fetch_pages`` validates the external payload at the boundary (pydantic,
unknown keys ignored) and ``flatten_pages`` turns the page tree into ordered ``FlatPage`` rows.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

MAX_RESPONSE_BYTES: Final = 50_000_000
_MIN_DELAY_S: Final = 1.0
_MAX_DELAY_S: Final = 30.0


class ClickUpError(Exception):
    """A ClickUp request failed. Messages carry status and doc id only, never token or body."""


class ClickUpPage(BaseModel):
    """One page of the ``/pages`` response; fields not listed here are dropped."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str = ""
    content: str = ""
    parent_page_id: str | None = None
    date_created: int | None = None
    date_edited: int | None = None
    archived: bool = False
    deleted: bool = False
    pages: list[ClickUpPage] = Field(default_factory=list)

    @field_validator("name", "content", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> Any:
        return "" if value is None else value

    @field_validator("pages", mode="before")
    @classmethod
    def _none_to_no_pages(cls, value: Any) -> Any:
        return [] if value is None else value


@dataclass(frozen=True, slots=True)
class FlatPage:
    """A page with its tree position: depth-first pre-order, ``position`` 0..n-1."""

    page_id: str
    parent_id: str | None
    position: int
    depth: int
    name: str
    content: str
    date_created: int | None
    date_edited: int | None


def page_url(workspace_id: int, doc_id: str, page_id: str) -> str:
    """ClickUp deep link to one page of a doc."""
    return f"https://app.clickup.com/{workspace_id}/v/dc/{doc_id}/{page_id}"


def flatten_pages(pages: list[ClickUpPage]) -> tuple[list[FlatPage], int]:
    """Walk the tree depth-first pre-order; archived or deleted pages drop with their subtree.

    Returns the flat rows and the number of pages skipped (a skipped subtree counts fully).
    """
    flat: list[FlatPage] = []
    skipped = 0

    def count(page: ClickUpPage) -> int:
        return 1 + sum(count(child) for child in page.pages)

    def walk(items: list[ClickUpPage], parent_id: str | None, depth: int) -> None:
        nonlocal skipped
        for page in items:
            if page.archived or page.deleted:
                skipped += count(page)
                continue
            flat.append(
                FlatPage(
                    page_id=page.id,
                    parent_id=parent_id if parent_id is not None else page.parent_page_id,
                    position=len(flat),
                    depth=depth,
                    name=page.name,
                    content=page.content,
                    date_created=page.date_created,
                    date_edited=page.date_edited,
                )
            )
            walk(page.pages, page.id, depth + 1)

    walk(pages, None, 0)
    return flat, skipped


class ClickUpClient:
    """Thin httpx wrapper for ``GET /api/v3/workspaces/{ws}/docs/{doc}/pages``."""

    def __init__(
        self,
        *,
        token: SecretStr,
        base_url: str,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        if transport is None and not base_url.startswith("https://"):
            raise ClickUpError("clickup_base_url must use https")
        self._sleep = sleep
        self._max_retries = max_retries
        # ClickUp personal tokens go in the header as-is, with no auth-scheme prefix.
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": token.get_secret_value()},
            timeout=timeout_s,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _delay(self, response: httpx.Response, attempt: int) -> float:
        """Seconds to wait before the next try: Retry-After, else rate-limit reset, else 2**n."""
        delay = float(2**attempt)
        retry_after = response.headers.get("Retry-After")
        reset = response.headers.get("X-RateLimit-Reset")
        try:
            if retry_after is not None:
                delay = float(retry_after)
            elif reset is not None:
                delay = float(reset) - time.time()
        except ValueError:
            pass
        return min(max(delay, _MIN_DELAY_S), _MAX_DELAY_S)

    def _get_body(self, workspace_id: int, doc_id: str) -> bytes:
        """GET with bounded retries on 429 and 5xx; return the size-checked 200 body."""
        path = f"/api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages"
        params: dict[str, str | int] = {"max_page_depth": -1, "content_format": "text/md"}
        attempt = 0
        while True:
            try:
                with self._client.stream("GET", path, params=params) as response:
                    status = response.status_code
                    if status == 200:
                        return self._read_capped(response, doc_id)
                    retryable = status == 429 or status >= 500
                    delay = self._delay(response, attempt) if retryable else 0.0
            except httpx.HTTPError as exc:
                # The exception text can echo request details; report its type only.
                raise ClickUpError(
                    f"ClickUp request failed ({type(exc).__name__}) for doc {doc_id}"
                ) from None
            if not retryable or attempt >= self._max_retries:
                raise ClickUpError(f"ClickUp returned HTTP {status} for doc {doc_id}")
            self._sleep(delay)
            attempt += 1

    @staticmethod
    def _read_capped(response: httpx.Response, doc_id: str) -> bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ClickUpError(f"ClickUp response too large for doc {doc_id}")
            chunks.append(chunk)
        return b"".join(chunks)

    def fetch_pages(self, workspace_id: int, doc_id: str) -> list[ClickUpPage]:
        """One request returns the whole page tree with content and dates."""
        raw = self._get_body(workspace_id, doc_id)
        try:
            body = json.loads(raw)
        except ValueError:
            raise ClickUpError(f"ClickUp returned invalid JSON for doc {doc_id}") from None
        items = body.get("pages") if isinstance(body, dict) else body
        if not isinstance(items, list):
            raise ClickUpError(f"ClickUp returned an unexpected payload shape for doc {doc_id}")
        pages: list[ClickUpPage] = []
        for index, item in enumerate(items):
            try:
                pages.append(ClickUpPage.model_validate(item))
            except ValidationError as exc:
                # Locations only: error input values would carry page content.
                paths = sorted(
                    ".".join(str(part) for part in (index, *err["loc"])) for err in exc.errors()
                )
                raise ClickUpError(
                    f"ClickUp page failed validation for doc {doc_id} at: " + ", ".join(paths)
                ) from None
        return pages
