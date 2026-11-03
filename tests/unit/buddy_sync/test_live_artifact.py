"""Local-only check of the live artifact built from the real local sources (plan 01-11).

Skipped unless ``LIVE_ARTIFACT_DIR`` names a directory holding ``index.db`` and
``HANDBOOK_DIR`` names a directory, so CI and other machines never need the private
handbook snapshot. Privacy (SYNC-03): every assert compares an integer or a boolean that was
computed into a local variable first. No assert expression holds artifact bytes, page text
or a set of text, so a failure cannot print content. The one print line holds integers only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from buddy_core.index_reader import open_index
from buddy_core.models import GuideChunk, HandbookPage, IndexMeta, VideoLink
from buddy_sync.handbook_files import SOURCE_ID, citation_uri
from buddy_sync.redaction import RULE_NAMES, Redactor

_ARTIFACT_ENV = os.environ.get("LIVE_ARTIFACT_DIR", "")
_HANDBOOK_ENV = os.environ.get("HANDBOOK_DIR", "")
ARTIFACT_DIR = Path(_ARTIFACT_ENV) if _ARTIFACT_ENV else None
HANDBOOK_DIR = Path(_HANDBOOK_ENV) if _HANDBOOK_ENV else None

pytestmark = pytest.mark.skipif(
    ARTIFACT_DIR is None
    or HANDBOOK_DIR is None
    or not (ARTIFACT_DIR / "index.db").is_file()
    or not HANDBOOK_DIR.is_dir(),
    reason="local-only: LIVE_ARTIFACT_DIR or HANDBOOK_DIR does not name a live source",
)

MIN_BODY_LINE_CHARS = 16
MIN_GUIDE_CHUNKS = 2000
MIN_SCENE_LINKS = 10
RESIDUAL_RULES = ("labelled_secret", "private_key_block", "token_prefix", "jwt", "iban")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Live:
    meta: IndexMeta
    pages: tuple[HandbookPage, ...]
    chunks: tuple[GuideChunk, ...]
    videos: dict[str, VideoLink]
    raw: bytes


def _dirs() -> tuple[Path, Path]:
    assert ARTIFACT_DIR is not None
    assert HANDBOOK_DIR is not None
    return ARTIFACT_DIR, HANDBOOK_DIR


def _denylist() -> tuple[str, ...]:
    raw = os.environ.get("REDACT_PAGE_FILES", "")
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def _email_domains() -> frozenset[str]:
    raw = os.environ.get("REDACT_EMAIL_ALLOW_DOMAINS", "digitiamo.com")
    return frozenset(item.strip().lower() for item in raw.split(",") if item.strip())


@pytest.fixture(scope="module")
def live() -> Live:
    artifact_dir, _ = _dirs()
    with open_index(artifact_dir / "index.db") as reader:
        pages = tuple(reader.load_handbook())
        chunks = tuple(reader.guide_chunks())
        videos = reader.video_links()
        meta = reader.meta
    raw = (artifact_dir / "index.db").read_bytes()
    manifest = artifact_dir / "index.manifest.json"
    if manifest.is_file():
        raw += manifest.read_bytes()
    return Live(meta=meta, pages=pages, chunks=chunks, videos=videos, raw=raw)


def _body_lines(path: Path) -> list[str]:
    """Body lines of a page file (text after the front matter). Held in memory only."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return lines[index + 1 :]
    return lines


def test_meta_source_doc_id(live: Live) -> None:
    matches = live.meta.source_doc_id == SOURCE_ID
    assert matches


def test_stored_pages_equal_non_denied_files(live: Live) -> None:
    _, handbook = _dirs()
    expected = {p.stem for p in handbook.glob("*.md")} - {Path(n).stem for n in _denylist()}
    stored = {page.page_id for page in live.pages}
    diff_size = len(expected ^ stored)
    stored_count_equals_rows = len(stored) == len(live.pages)
    assert diff_size == 0
    assert stored_count_equals_rows


def test_denied_pages_absent_from_every_byte(live: Live) -> None:
    _, handbook = _dirs()
    denied = _denylist()
    denied_stems = {Path(name).stem for name in denied}
    stored_ids = {page.page_id for page in live.pages}
    # Text of every kept page file, in memory only: a denied-page line that also sits in a
    # kept page (shared footer or boilerplate) is stored through that page, so its presence
    # proves nothing about the denied page. Only lines unique to the denied page are checked.
    kept_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in handbook.glob("*.md")
        if path.stem not in denied_stems
    )
    for name in denied:
        stem = Path(name).stem
        stem_stored = stem in stored_ids
        stem_in_bytes = stem.encode("utf-8") in live.raw
        substantial = [
            line.strip()
            for line in _body_lines(handbook / name)
            if len("".join(line.split())) >= MIN_BODY_LINE_CHARS
        ]
        unique = [line for line in substantial if line not in kept_text]
        checked_lines = len(unique)
        leaked_lines = sum(1 for line in unique if line.encode("utf-8") in live.raw)
        assert not stem_stored
        assert not stem_in_bytes
        assert checked_lines > 0  # the check must bite: some denied-page line is page-specific
        assert leaked_lines == 0


def test_every_page_has_citation_title_and_revision_date(live: Live) -> None:
    bad_url = sum(1 for p in live.pages if p.url != citation_uri(p.page_id))
    empty_title = sum(1 for p in live.pages if not p.title.strip())
    no_revision = sum(1 for p in live.pages if not p.revision_date_iso)
    assert bad_url == 0
    assert empty_title == 0
    assert no_revision == 0


def test_no_residual_secret_or_iban(live: Live) -> None:
    redactor = Redactor(email_allow_domains=_email_domains())
    unknown = [rule for rule in RESIDUAL_RULES if rule not in RULE_NAMES]
    known_rules = len(unknown) == 0
    texts = [p.title for p in live.pages] + [p.content_md for p in live.pages]
    texts += [c.text for c in live.chunks]
    total = 0
    for text in texts:
        for hit in redactor.redact(text).hits:
            if hit.rule in RESIDUAL_RULES:
                total += hit.count
    assert known_rules
    assert total == 0


def test_guides_chunks_and_scene_links(live: Live) -> None:
    scene = sum(1 for v in live.videos.values() if v.source == "scene")
    chunk_count = len(live.chunks)
    sha_ok = _SHA_RE.fullmatch(live.meta.guides_commit_sha) is not None
    assert chunk_count > MIN_GUIDE_CHUNKS
    assert scene >= MIN_SCENE_LINKS
    assert sha_ok


def test_print_counts(live: Live) -> None:
    scene = sum(1 for v in live.videos.values() if v.source == "scene")
    fallback = sum(1 for v in live.videos.values() if v.source == "readme_fallback")
    print(
        f"live counts: pages={len(live.pages)} denied={len(_denylist())}"
        f" chunks={len(live.chunks)} scene_links={scene} readme_fallback_links={fallback}"
    )
