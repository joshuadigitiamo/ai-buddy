"""Index identity, permalink resolution and expected-source matching. Synthetic data only."""

from pathlib import Path

import pytest
from tests.unit.mcp_server.conftest import (
    FILE,
    MAPPED,
    PLAIN,
    SHA,
    SINGLE,
    WEB_BASE,
    make_chunk,
    make_content,
    write_index,
)

from buddy_bot.schemas import BotReply, Evidence
from buddy_core.index_reader import open_index
from buddy_eval.golden import GoldenItem
from buddy_eval.runner import ItemOutcome
from buddy_eval.scoring import score_item
from buddy_eval.sources import IndexIdentity, SourceIndex, matches
from buddy_mcp.guides_tools import guides_permalink

MAPPED_SECTION = MAPPED.chunk_key.rsplit("/", 1)[0]
MAPPED_PERMALINK = f"{WEB_BASE}/blob/{SHA}/{FILE}#L10-L14"
SPACE_FILE = "AI-Engineering/WITH SPACE.md"
SPACED = make_chunk("Intro", None, 3, 9, "A section in a file with a space.", file=SPACE_FILE)


@pytest.fixture
def source_index(tmp_path: Path) -> SourceIndex:
    write_index(tmp_path, make_content(chunks=(MAPPED, PLAIN, SINGLE, SPACED)))
    return SourceIndex.open(tmp_path)


class TestResolve:
    def test_a_range_permalink_resolves_to_the_mapped_chunk_key(
        self, source_index: SourceIndex
    ) -> None:
        assert source_index.resolve(MAPPED_PERMALINK) == MAPPED.chunk_key

    def test_a_single_line_permalink_resolves_to_the_single_line_chunk(
        self, source_index: SourceIndex
    ) -> None:
        assert source_index.resolve(f"{WEB_BASE}/blob/{SHA}/{FILE}#L40") == SINGLE.chunk_key

    def test_the_permalink_the_server_builds_resolves_back_to_its_chunk(
        self, source_index: SourceIndex
    ) -> None:
        for chunk in (MAPPED, PLAIN, SINGLE, SPACED):
            assert source_index.resolve(guides_permalink(WEB_BASE, SHA, chunk)) == chunk.chunk_key

    def test_a_quoted_path_with_a_space_resolves_after_unquoting(
        self, source_index: SourceIndex
    ) -> None:
        url = f"{WEB_BASE}/blob/{SHA}/AI-Engineering/WITH%20SPACE.md#L3-L9"

        assert source_index.resolve(url) == SPACED.chunk_key

    @pytest.mark.parametrize(
        "url",
        [
            f"{WEB_BASE}/blob/{'2' * 40}/{FILE}#L10-L14",
            f"{WEB_BASE}/blob/{SHA}/{FILE}#L10-L15",
            f"{WEB_BASE}/blob/{SHA}/{FILE}#L11-L14",
            f"{WEB_BASE}/blob/{SHA}/Other/FILE.md#L10-L14",
            f"{WEB_BASE}/blob/{SHA}/{FILE}",
            f"{WEB_BASE}/blob/{SHA}/{FILE}#L10-L14/extra",
            f"{WEB_BASE}/tree/main/{FILE}#L10-L14",
            "ftp://example.invalid/blob/" + SHA + f"/{FILE}#L10-L14",
            "not a url",
            "",
        ],
    )
    def test_anything_else_resolves_to_nothing(self, source_index: SourceIndex, url: str) -> None:
        assert source_index.resolve(url) is None

    def test_a_handbook_citation_resolves_to_itself_only_when_the_page_exists(
        self, source_index: SourceIndex
    ) -> None:
        assert source_index.resolve("handbook://02-ferie") == "handbook://02-ferie"
        assert source_index.resolve("handbook://99-missing") is None


class TestMatches:
    @pytest.mark.parametrize(
        ("key", "expected", "outcome"),
        [
            ("file#h2/h3/0", "file#h2/h3/0", True),
            ("file#h2/h3/0", "file#h2/h3", True),
            ("file#h2/h3/1~2", "file#h2/h3", True),
            ("file#h2/h3x/0", "file#h2/h3", False),
            ("file#h2/h3", "file#h2/h3/0", False),
            ("file#h2/_/0", "file#h2/_", True),
            ("handbook://02-ferie", "handbook://02-ferie", True),
            ("handbook://02-ferie-old", "handbook://02-ferie", False),
            ("handbook://02-ferie/0", "handbook://02-ferie", False),
            ("handbook://02-ferie", "file#h2/h3", False),
        ],
    )
    def test_prefix_at_a_segment_boundary_and_exact_handbook_ids(
        self, key: str, expected: str, outcome: bool
    ) -> None:
        assert matches(key, expected) is outcome


class TestHasExpected:
    def test_an_existing_page_id_and_a_section_prefix_with_a_chunk_are_present(
        self, source_index: SourceIndex
    ) -> None:
        assert source_index.has_expected("handbook://02-ferie") is True
        assert source_index.has_expected(MAPPED_SECTION) is True
        assert source_index.has_expected(MAPPED.chunk_key) is True

    @pytest.mark.parametrize(
        "entry",
        ["handbook://99-missing", f"{FILE}#retrieval/chunk", f"{FILE}#nothing/_", "handbook://"],
    )
    def test_anything_without_a_page_or_chunk_is_absent(
        self, source_index: SourceIndex, entry: str
    ) -> None:
        assert source_index.has_expected(entry) is False


class TestIdentity:
    def test_identity_equals_the_index_meta(self, tmp_path: Path) -> None:
        write_index(tmp_path, make_content())

        identity = SourceIndex.open(tmp_path).identity

        with open_index(tmp_path / "index.db") as reader:
            meta = reader.meta
        assert identity == IndexIdentity(meta.content_hash, meta.guides_commit_sha, meta.build_id)
        assert identity.guides_commit_sha == SHA

    def test_a_missing_index_names_artifact_dir(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="ARTIFACT_DIR"):
            SourceIndex.open(tmp_path)


def _guides_item(*expected: str) -> GoldenItem:
    return GoldenItem(
        id="item-gd-01",
        kind="guides",
        question="synthetic question",
        expected_answer="synthetic expected answer",
        key_facts=["synthetic fact"],
        expected_sources=list(expected),
        expected_referente_role=None,
        review="approved",
        review_note="",
    )


def _evidence(url: str) -> Evidence:
    return Evidence(
        source_url=url,
        kind="guides",
        title="t",
        text="x",
        revision_date="2026-11-03",
        revision_kind="indexed_on",
    )


def _outcome(*urls: str) -> ItemOutcome:
    reply = BotReply(kind="answer", answer="a", sources=[_evidence(u) for u in urls])
    return ItemOutcome("item-gd-01", "completed", reply, "tr-1", None)


class TestScoringWithTheIndexResolver:
    def test_a_mapped_permalink_cites_the_expected_section(self, source_index: SourceIndex) -> None:
        verdict = score_item(
            _guides_item(MAPPED_SECTION), _outcome(MAPPED_PERMALINK), resolve=source_index.resolve
        )

        assert verdict.checks["citation"] is True

    def test_the_handbook_only_default_cannot_resolve_a_permalink(self) -> None:
        verdict = score_item(_guides_item(MAPPED_SECTION), _outcome(MAPPED_PERMALINK))

        assert verdict.checks["citation"] is False

    def test_a_permalink_of_another_section_does_not_cite_the_expected_one(
        self, source_index: SourceIndex
    ) -> None:
        other = f"{WEB_BASE}/blob/{SHA}/{FILE}#L30-L34"

        verdict = score_item(
            _guides_item(MAPPED_SECTION), _outcome(other), resolve=source_index.resolve
        )

        assert verdict.checks["citation"] is False
        assert verdict.status == "wrong"

    def test_two_parts_of_one_section_fill_the_same_expected_entry_once(
        self, tmp_path: Path
    ) -> None:
        part0 = make_chunk("Retrieval", "Chunking", 10, 14, "first", part_index=0)
        part1 = make_chunk("Retrieval", "Chunking", 15, 20, "second", part_index=1)
        write_index(tmp_path, make_content(chunks=(part0, part1)))
        index = SourceIndex.open(tmp_path)
        urls = [guides_permalink(WEB_BASE, SHA, c) for c in (part0, part1)]

        item = _guides_item(MAPPED_SECTION, f"{FILE}#serving/_")

        verdict = score_item(item, _outcome(*urls), resolve=index.resolve)

        assert verdict.checks["citation"] is True
