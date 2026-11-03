"""ClickUp v3 REST adapter: the only module that knows ClickUp field names.

``ClickUpClient.fetch_pages`` validates the external payload at the boundary (pydantic,
unknown keys ignored) and ``flatten_pages`` turns the page tree into ordered ``FlatPage`` rows.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


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

    def fetch_pages(self, workspace_id: int, doc_id: str) -> list[ClickUpPage]:
        """One request returns the whole page tree with content and dates."""
        response = self._client.get(
            f"/api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages",
            params={"max_page_depth": -1, "content_format": "text/md"},
        )
        if response.status_code != 200:
            raise ClickUpError(f"ClickUp returned HTTP {response.status_code} for doc {doc_id}")
        body = response.json()
        items = body.get("pages", []) if isinstance(body, dict) else body
        return [ClickUpPage.model_validate(item) for item in items]
