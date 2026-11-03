"""Tracer: synthetic handbook folder -> redaction -> index.db; denylisted file leaves no trace."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import IndexContent
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.handbook import sync_handbook
from buddy_sync.handbook_files import SOURCE_ID, read_handbook_dir
from buddy_sync.redaction import REDACTION_VERSION, Redactor

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "handbook"
DENYLIST = frozenset({"04-rete-ospiti.md"})
KEPT_IDS = ["01-benvenuto", "02-ferie", "03-accesso-ufficio"]


@pytest.fixture
def published_dir(tmp_path: Path) -> Path:
    files = read_handbook_dir(FIXTURE_DIR, denylist=DENYLIST)
    result = sync_handbook(
        files.pages,
        previous=None,
        versions_match=True,
        redactor=Redactor(email_allow_domains=frozenset({"digitiamo.com"})),
        logger=logging.getLogger("buddy_sync.test"),
    )
    content = IndexContent(
        handbook=result.pages,
        chunks=(),
        videos={},
        source_doc_id=SOURCE_ID,
        guides_commit_sha="none",
        pipeline_version="1",
        redaction_version=REDACTION_VERSION,
    )
    store = LocalDirArtifactStore(tmp_path)
    staged = store.staging_path()
    meta = build_index(content, staged, now=datetime(2026, 11, 3, tzinfo=UTC))
    store.publish(staged, meta)
    return tmp_path


def test_denylisted_file_absent(published_dir: Path) -> None:
    blob = (published_dir / "index.db").read_bytes() + (
        published_dir / "index.manifest.json"
    ).read_bytes()

    assert (b"04-rete-ospiti" in blob) is False
    assert (b"Rete ospiti" in blob) is False
    assert (b"Wf9-synthetic-wifi-value" in blob) is False
    assert (b"Zq9-synthetic-not-real" in blob) is False
    assert (b"[REDATTO]" in blob) is True


def test_pages_carry_citation(published_dir: Path) -> None:
    with open_index(published_dir / "index.db") as index:
        pages = index.load_handbook()

    assert [p.page_id for p in pages] == KEPT_IDS
    assert [p.position for p in pages] == list(range(len(KEPT_IDS)))
    for page in pages:
        assert page.url.startswith("handbook://")
        assert page.title
        assert page.revision_date_iso
