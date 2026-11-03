"""Tracer: synthetic ClickUp doc -> redaction -> index.db; denylisted page leaves no trace."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import HandbookPage, IndexContent
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.clickup import ClickUpClient, FlatPage, flatten_pages
from buddy_sync.handbook import sync_handbook
from buddy_sync.redaction import REDACTION_VERSION, Redactor

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "clickup" / "pages.json"
WORKSPACE_ID = 123
DOC_ID = "demo-doc"
WIFI_ID = "demo-page-wifi"


def _fetch_flat() -> tuple[list[FlatPage], int]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=FIXTURE.read_bytes())

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


def _sync(denylist: frozenset[str]) -> tuple[HandbookPage, ...]:
    flat, skipped = _fetch_flat()
    result = sync_handbook(
        flat,
        previous=None,
        versions_match=True,
        denylist=denylist,
        allow_empty_denylist=False,
        redactor=Redactor(email_allow_domains=frozenset({"digitiamo.com"})),
        workspace_id=WORKSPACE_ID,
        doc_id=DOC_ID,
        skipped_archived=skipped,
        logger=logging.getLogger("buddy_sync.test"),
    )
    return result.pages


@pytest.fixture
def published_dir(tmp_path: Path) -> Path:
    pages = _sync(frozenset({WIFI_ID}))
    content = IndexContent(
        handbook=pages,
        chunks=(),
        videos={},
        source_doc_id=DOC_ID,
        guides_commit_sha="none",
        pipeline_version="1",
        redaction_version=REDACTION_VERSION,
    )
    store = LocalDirArtifactStore(tmp_path)
    staged = store.staging_path()
    meta = build_index(content, staged, now=datetime(2026, 11, 3, tzinfo=UTC))
    store.publish(staged, meta)
    return tmp_path


def test_denylisted_page_absent(published_dir: Path) -> None:
    blob = (published_dir / "index.db").read_bytes() + (
        published_dir / "index.manifest.json"
    ).read_bytes()

    assert (WIFI_ID.encode() in blob) is False
    assert (b"Rete ospiti" in blob) is False
    assert (b"Wf9-synthetic-wifi-value" in blob) is False
    assert (b"Zq9-synthetic-not-real" in blob) is False
    assert (b"[REDATTO]" in blob) is True


def test_pages_carry_source(published_dir: Path) -> None:
    with open_index(published_dir / "index.db") as index:
        pages = index.load_handbook()

    assert pages, "no pages stored"
    for page in pages:
        assert page.url.startswith("https://app.clickup.com/")
        assert page.title
        assert page.revision_date_iso
    titles = [p.title for p in pages]
    ids = {p.page_id for p in pages}
    assert titles.count("Benvenuto") == 2
    assert len({p.page_id for p in pages if p.title == "Benvenuto"}) == 2
    assert "demo-page-0005" not in ids
    assert "demo-page-0006" not in ids
    assert [p.position for p in pages] == list(range(len(pages)))
    assert [p.page_id for p in pages] == [
        "demo-page-0001",
        "demo-page-0002",
        "demo-page-0004",
        "demo-page-0003",
        "demo-page-0007",
    ]
