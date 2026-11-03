"""Incremental handbook sync (SYNC-02, D-10) on local handbook pages."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Any

import pytest

from buddy_core.models import HandbookPage
from buddy_sync.handbook import (
    EmptyHandbookError,
    HandbookSyncResult,
    revision_date_iso,
    sync_handbook,
)
from buddy_sync.handbook_files import SourcePage, citation_uri
from buddy_sync.redaction import Redactor

LOGGER = logging.getLogger("buddy_sync.test")
JAN_2025_MS = 1_735_689_600_000
SECRET = "Zq9-synthetic-not-real"


def _pages() -> list[SourcePage]:
    texts = {
        "01-benvenuto": "Benvenuto in azienda.",
        "02-ferie": "Come richiedere le ferie.",
        "03-accesso": f"Istruzioni.\n\nPassword: {SECRET}",
        "04-viaggi": "Rimborsi viaggio.",
        "05-sicurezza": "Norme di sicurezza.",
    }
    return [
        SourcePage(
            page_id=page_id,
            position=index,
            title=f"Titolo {page_id}",
            content=content,
            date_created=JAN_2025_MS,
            date_edited=JAN_2025_MS + index * 86_400_000,
        )
        for index, (page_id, content) in enumerate(texts.items())
    ]


COUNT = len(_pages())


def _run(
    pages: list[SourcePage],
    *,
    previous: tuple[HandbookPage, ...] | None = None,
    versions_match: bool = True,
) -> HandbookSyncResult:
    return sync_handbook(
        pages,
        previous=previous,
        versions_match=versions_match,
        redactor=Redactor(email_allow_domains=frozenset({"digitiamo.com"})),
        logger=LOGGER,
    )


def _edit(pages: list[SourcePage], page_id: str, **changes: Any) -> list[SourcePage]:
    return [replace(p, **changes) if p.page_id == page_id else p for p in pages]


def _row(result: HandbookSyncResult, page_id: str) -> HandbookPage:
    return next(p for p in result.pages if p.page_id == page_id)


def test_first_run_processes_all_as_flat_pages_with_citation_urls() -> None:
    result = _run(_pages())

    assert result.processed == COUNT
    assert result.unchanged == 0
    assert result.removed == 0
    assert [p.position for p in result.pages] == list(range(COUNT))
    for row in result.pages:
        assert row.url == citation_uri(row.page_id)
        assert row.parent_id is None
        assert row.depth == 0


def test_rerun_processes_zero() -> None:
    first = _run(_pages())

    second = _run(_pages(), previous=first.pages)

    assert second.processed == 0
    assert second.unchanged == COUNT
    assert second.pages == first.pages


def test_single_edit_reprocesses_one() -> None:
    first = _run(_pages())
    edited = _edit(_pages(), "03-accesso", date_edited=1_740_000_000_000, content="Nuovo testo.")

    second = _run(edited, previous=first.pages)

    assert second.processed == 1
    assert second.unchanged == COUNT - 1
    row = _row(second, "03-accesso")
    assert row.content_md == "Nuovo testo."
    assert row.date_edited_raw == 1_740_000_000_000
    assert row.revision_date_iso == revision_date_iso(1_740_000_000_000)


def test_content_change_same_date_edited() -> None:
    first = _run(_pages())
    edited = _edit(_pages(), "02-ferie", content="Testo cambiato senza nuova data.")

    second = _run(edited, previous=first.pages)

    assert second.processed == 1
    row = _row(second, "02-ferie")
    assert row.content_md == "Testo cambiato senza nuova data."
    assert row.content_hash != _row(first, "02-ferie").content_hash


def test_removed_page_dropped() -> None:
    first = _run(_pages())
    fewer = [replace(p, position=i) for i, p in enumerate(_pages()[:-1])]

    second = _run(fewer, previous=first.pages)

    assert second.removed == 1
    assert second.processed == 0
    assert "05-sicurezza" not in {p.page_id for p in second.pages}
    assert [p.position for p in second.pages] == list(range(COUNT - 1))


def test_version_change_reprocesses_all() -> None:
    first = _run(_pages())

    second = _run(_pages(), previous=first.pages, versions_match=False)

    assert second.processed == COUNT
    assert second.unchanged == 0


def test_moved_page_is_unchanged_but_takes_current_position() -> None:
    first = _run(_pages())
    pages = _pages()
    shifted = [replace(p, position=i) for i, p in enumerate([pages[1], pages[0], *pages[2:]])]

    second = _run(shifted, previous=first.pages)

    assert second.processed == 0
    assert _row(second, "01-benvenuto").position == 1
    assert _row(second, "02-ferie").position == 0


def test_zero_pages_raises() -> None:
    with pytest.raises(EmptyHandbookError):
        _run([])


def test_empty_content_stored() -> None:
    result = _run(_edit(_pages(), "02-ferie", content=""))

    assert _row(result, "02-ferie").content_md == ""


@pytest.mark.parametrize("raw", [1_735_689_600_000, 1_735_689_600])
def test_revision_date_units(raw: int) -> None:
    assert revision_date_iso(raw) == "2025-01-01T00:00:00+00:00"


def test_revision_date_falls_back_to_created_then_none() -> None:
    no_dates = _edit(_pages(), "02-ferie", date_edited=None, date_created=None)
    created_only = _edit(_pages(), "02-ferie", date_edited=None, date_created=JAN_2025_MS)

    row_none = _row(_run(no_dates), "02-ferie")
    row_created = _row(_run(created_only), "02-ferie")

    assert revision_date_iso(None) is None
    assert row_none.revision_date_iso is None
    assert row_created.revision_date_iso == "2025-01-01T00:00:00+00:00"


def test_content_hash_covers_redacted_text_only() -> None:
    source = next(p for p in _pages() if p.page_id == "03-accesso")

    row = _row(_run(_pages()), "03-accesso")

    stored = hashlib.sha256(f"{row.title}\x00{row.content_md}".encode()).hexdigest()
    raw = hashlib.sha256(f"{source.title}\x00{source.content}".encode()).hexdigest()
    assert row.content_hash == stored
    assert row.content_hash != raw
    assert (SECRET in row.content_md) is False


def test_redaction_hits_are_logged_for_processed_pages_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="buddy_sync.test"):
        first = _run(_pages())
    logged = caplog.text
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="buddy_sync.test"):
        _run(_pages(), previous=first.pages)

    assert "source=03-accesso" in logged
    assert (SECRET in logged) is False
    assert caplog.records == []
