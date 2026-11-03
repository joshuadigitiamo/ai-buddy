"""Tracer: a local fixture Guides repo is cloned, chunked, redacted, indexed and searched."""

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from buddy_core.index_reader import IndexReader, open_index
from buddy_core.index_writer import build_index
from buddy_core.models import IndexContent
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.chunker import PIPELINE_VERSION
from buddy_sync.guides import sync_guides
from buddy_sync.guides_git import GitGuidesSource
from buddy_sync.redaction import REDACTION_VERSION, Redactor

FIXTURE_TREE = Path(__file__).resolve().parents[2] / "fixtures" / "guides_repo"
DEMO = "AI-Engineering/DEMO_GUIDE.md"
LOGGER = logging.getLogger("buddy_sync.test")
RepoFactory = Callable[[Mapping[str, str] | Path], Path]


def _published_reader(tmp_path: Path, repo: Path) -> tuple[IndexReader, str]:
    source = GitGuidesSource(
        url=str(repo), branch="master", checkout_dir=tmp_path / "checkout", token=None
    )
    checkout = source.sync()
    redactor = Redactor(email_allow_domains=frozenset({"digitiamo.com"}))
    result = sync_guides(
        checkout, previous=None, versions_match=False, redactor=redactor, logger=LOGGER
    )
    content = IndexContent(
        handbook=(),
        chunks=result.chunks,
        videos={},
        source_doc_id="doc-synthetic",
        guides_commit_sha=result.commit_sha,
        pipeline_version=PIPELINE_VERSION,
        redaction_version=REDACTION_VERSION,
    )
    store = LocalDirArtifactStore(tmp_path / "artifacts")
    staged = store.staging_path()
    meta = build_index(content, staged, now=datetime.now(UTC))
    published = store.publish(staged, meta)
    return open_index(published), checkout.commit_sha


def test_fixture_guide_becomes_searchable_chunks_with_exact_lines(
    tmp_path: Path, git_repo_factory: RepoFactory
) -> None:
    repo = git_repo_factory(FIXTURE_TREE)
    reader, sha = _published_reader(tmp_path, repo)
    with reader:
        hits = reader.search_guides("chunking")
        assert hits
        first = hits[0].chunk
        assert (first.file, first.h2, first.h3) == (DEMO, "1. Basics", "Chunking")
        # "### Chunking" is on line 10 of the fixture; its paragraph ends on line 12.
        assert (first.line_start, first.line_end) == (10, 12)
        assert reader.meta.guides_commit_sha == sha


def test_checkout_reports_the_repo_head_commit(
    tmp_path: Path, git_repo_factory: RepoFactory
) -> None:
    repo = git_repo_factory(FIXTURE_TREE)
    source = GitGuidesSource(
        url=str(repo), branch="master", checkout_dir=tmp_path / "checkout", token=None
    )
    expected = (repo / ".git" / "refs" / "heads" / "master").read_text(encoding="utf-8").strip()
    assert source.sync().commit_sha == expected


def test_fenced_pseudo_heading_is_body_text_of_the_code_chunk(
    tmp_path: Path, git_repo_factory: RepoFactory
) -> None:
    repo = git_repo_factory(FIXTURE_TREE)
    reader, _ = _published_reader(tmp_path, repo)
    with reader:
        hits = reader.search_guides("fake heading inside fence")
        assert hits
        code = hits[0].chunk
        assert (code.h2, code.h3) == ("1. Basics", "Code")
        assert "## fake heading inside fence" in code.text
        assert not any(c.h2 == "fake heading inside fence" for c in reader.guide_chunks())
