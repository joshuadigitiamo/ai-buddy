"""Incremental handbook sync (SYNC-02, D-10) on the synthetic ClickUp fixture."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from buddy_core.models import HandbookPage
from buddy_sync.clickup import ClickUpClient, FlatPage, flatten_pages
from buddy_sync.handbook import (
    EmptyDenylistError,
    EmptyHandbookError,
    HandbookSyncResult,
    revision_date_iso,
    sync_handbook,
)
from buddy_sync.redaction import Redactor

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "clickup" / "pages.json"
WORKSPACE_ID = 123
DOC_ID = "demo-doc"
WIFI_ID = "demo-page-wifi"
DENYLIST = frozenset({WIFI_ID})
EXPECTED_PROCESSED = 5  # 6 non-archived pages minus the denylisted Wi-Fi page
LOGGER = logging.getLogger("buddy_sync.test")


def _flat(raw_pages: object = None) -> tuple[list[FlatPage], int]:
    payload = json.dumps(raw_pages).encode() if raw_pages is not None else FIXTURE.read_bytes()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    client = ClickUpClient(
        token=SecretStr("pk_SYNTHETIC_TOKEN_DO_NOT_USE_0000000000"),
        base_url="https://api.clickup.com",
        timeout_s=5.0,
        transport=httpx.MockTransport(handler),
    )
    try:
        return flatten_pages(client.fetch_pages(WORKSPACE_ID, DOC_ID))
    finally:
        client.close()


def _run(
    fetched: list[FlatPage],
    *,
    previous: tuple[HandbookPage, ...] | None = None,
    versions_match: bool = True,
    denylist: frozenset[str] = DENYLIST,
    allow_empty_denylist: bool = False,
    skipped_archived: int = 2,
) -> HandbookSyncResult:
    return sync_handbook(
        fetched,
        previous=previous,
        versions_match=versions_match,
        denylist=denylist,
        allow_empty_denylist=allow_empty_denylist,
        redactor=Redactor(email_allow_domains=frozenset({"digitiamo.com"})),
        workspace_id=WORKSPACE_ID,
        doc_id=DOC_ID,
        skipped_archived=skipped_archived,
        logger=LOGGER,
    )


def _edit(fetched: list[FlatPage], page_id: str, **changes: Any) -> list[FlatPage]:
    return [replace(p, **changes) if p.page_id == page_id else p for p in fetched]


def test_first_run_processes_all() -> None:
    fetched, skipped = _flat()

    result = _run(fetched, skipped_archived=skipped)

    assert result.seen == 6
    assert result.processed == EXPECTED_PROCESSED
    assert result.unchanged == 0
    assert result.removed == 0
    assert result.denied == 1
    assert result.skipped_archived == 2
    assert len(result.pages) == EXPECTED_PROCESSED
    assert [p.position for p in result.pages] == list(range(EXPECTED_PROCESSED))


def test_rerun_processes_zero() -> None:
    fetched, _ = _flat()
    first = _run(fetched)

    second = _run(fetched, previous=first.pages)

    assert second.processed == 0
    assert second.unchanged == EXPECTED_PROCESSED
    assert second.pages == first.pages


def test_single_edit_reprocesses_one() -> None:
    fetched, _ = _flat()
    first = _run(fetched)
    edited = _edit(fetched, "demo-page-0003", date_edited=1_740_000_000_000, content="Nuovo testo.")

    second = _run(edited, previous=first.pages)

    assert second.processed == 1
    assert second.unchanged == EXPECTED_PROCESSED - 1
    row = next(p for p in second.pages if p.page_id == "demo-page-0003")
    assert row.content_md == "Nuovo testo."
    assert row.date_edited_raw == 1_740_000_000_000
    assert row.revision_date_iso == revision_date_iso(1_740_000_000_000)


def test_date_updated_only_ignored() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def bump(pages: list[dict[str, object]]) -> None:
        for page in pages:
            page["date_updated"] = 1_999_999_999_999
            children = page["pages"]
            assert isinstance(children, list)
            bump(children)

    first = _run(_flat()[0])
    bump(raw)
    bumped, _ = _flat(raw)

    second = _run(bumped, previous=first.pages)

    assert second.processed == 0
    assert second.pages == first.pages


def test_content_change_same_date_edited() -> None:
    fetched, _ = _flat()
    first = _run(fetched)
    edited = _edit(fetched, "demo-page-0002", content="Testo cambiato senza nuova data.")

    second = _run(edited, previous=first.pages)

    assert second.processed == 1
    row = next(p for p in second.pages if p.page_id == "demo-page-0002")
    assert row.content_md == "Testo cambiato senza nuova data."
    assert (
        row.content_hash
        != next(p for p in first.pages if p.page_id == "demo-page-0002").content_hash
    )


def test_removed_page_dropped() -> None:
    fetched, _ = _flat()
    first = _run(fetched)
    fewer = [p for p in fetched if p.page_id != "demo-page-0007"]

    second = _run(fewer, previous=first.pages)

    assert second.removed == 1
    assert second.processed == 0
    assert "demo-page-0007" not in {p.page_id for p in second.pages}
    assert len(second.pages) == EXPECTED_PROCESSED - 1
    assert [p.position for p in second.pages] == list(range(EXPECTED_PROCESSED - 1))


def test_version_change_reprocesses_all() -> None:
    fetched, _ = _flat()
    first = _run(fetched)

    second = _run(fetched, previous=first.pages, versions_match=False)

    assert second.processed == EXPECTED_PROCESSED
    assert second.unchanged == 0


def test_moved_page_is_unchanged_but_takes_current_position_and_parent() -> None:
    fetched, _ = _flat()
    first = _run(fetched)
    moved = _edit(fetched, "demo-page-0004", parent_id="demo-page-0001", depth=1)

    second = _run(moved, previous=first.pages)

    assert second.processed == 0
    row = next(p for p in second.pages if p.page_id == "demo-page-0004")
    assert row.parent_id == "demo-page-0001"
    assert row.depth == 1


def test_empty_denylist_refused() -> None:
    fetched, _ = _flat()

    with pytest.raises(EmptyDenylistError):
        _run(fetched, denylist=frozenset())


def test_empty_denylist_allowed() -> None:
    fetched, _ = _flat()

    result = _run(fetched, denylist=frozenset(), allow_empty_denylist=True)

    assert result.denied == 0
    assert result.processed == EXPECTED_PROCESSED + 1


def test_empty_denylist_refused_before_any_page_is_touched(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fetched, _ = _flat()

    with caplog.at_level(logging.DEBUG), pytest.raises(EmptyDenylistError):
        _run(fetched, denylist=frozenset())

    assert caplog.records == []


def test_zero_pages_raises() -> None:
    only_wifi = [p for p in _flat()[0] if p.page_id == WIFI_ID]

    with pytest.raises(EmptyHandbookError):
        _run(only_wifi)


def test_empty_content_stored() -> None:
    fetched, _ = _flat()
    blank = _edit(fetched, "demo-page-0002", content="")

    result = _run(blank)

    row = next(p for p in result.pages if p.page_id == "demo-page-0002")
    assert row.content_md == ""


@pytest.mark.parametrize("raw", [1_735_689_600_000, 1_735_689_600])
def test_revision_date_units(raw: int) -> None:
    assert revision_date_iso(raw) == "2025-01-01T00:00:00+00:00"


def test_revision_date_falls_back_to_created_then_none() -> None:
    fetched, _ = _flat()
    no_dates = _edit(fetched, "demo-page-0002", date_edited=None, date_created=None)
    created_only = _edit(
        fetched, "demo-page-0002", date_edited=None, date_created=1_735_689_600_000
    )

    row_none = next(p for p in _run(no_dates).pages if p.page_id == "demo-page-0002")
    row_created = next(p for p in _run(created_only).pages if p.page_id == "demo-page-0002")

    assert revision_date_iso(None) is None
    assert row_none.revision_date_iso is None
    assert row_created.revision_date_iso == "2025-01-01T00:00:00+00:00"


def test_content_hash_covers_redacted_text_only() -> None:
    fetched, _ = _flat()
    raw_page = next(p for p in fetched if p.page_id == "demo-page-0003")

    row = next(p for p in _run(fetched).pages if p.page_id == "demo-page-0003")

    stored = hashlib.sha256(f"{row.title}\x00{row.content_md}".encode()).hexdigest()
    raw = hashlib.sha256(f"{raw_page.name}\x00{raw_page.content}".encode()).hexdigest()
    assert row.content_hash == stored
    assert row.content_hash != raw
    assert ("Zq9-synthetic-not-real" in row.content_md) is False


def test_redaction_hits_are_logged_for_processed_pages_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fetched, _ = _flat()
    with caplog.at_level(logging.INFO, logger="buddy_sync.test"):
        first = _run(fetched)
    logged = caplog.text
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="buddy_sync.test"):
        _run(fetched, previous=first.pages)

    assert "source=demo-page-0003" in logged
    assert ("Zq9-synthetic-not-real" in logged) is False
    assert ("Wf9-synthetic-wifi-value" in logged) is False
    assert (WIFI_ID in logged) is False
    assert caplog.records == []
