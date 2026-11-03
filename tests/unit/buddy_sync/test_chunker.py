"""Chunker rules (D-20): one chunk per ###, preamble, fences, oversize splitting, keys."""

from buddy_sync.chunker import MAX_CHUNK_CHARS, chunk_markdown, heading_outline

FILE = "Demo/DEMO_GUIDE.md"


def _chunks(text: str, **kwargs: int) -> list[tuple[str, str | None, str]]:
    return [(c.h2, c.h3, c.text) for c in chunk_markdown(text, file=FILE, **kwargs)]


def test_one_chunk_per_h3_carries_parent_h2() -> None:
    text = "## A\n\n### B\n\nbody b\n\n### C\n\nbody c\n"
    assert _chunks(text) == [("A", "B", "body b"), ("A", "C", "body c")]


def test_h2_without_h3_is_one_chunk_with_no_h3() -> None:
    chunks = chunk_markdown("## Only\n\nfirst\n\nsecond\n", file=FILE)
    assert [(c.h2, c.h3, c.heading, c.text) for c in chunks] == [
        ("Only", None, "Only", "first\n\nsecond")
    ]


def test_preamble_chunk_exists_when_h2_has_prose_before_first_h3() -> None:
    chunks = chunk_markdown("## A\n\nintro\n\n### B\n\nbody\n", file=FILE)
    assert [(c.h3, c.heading, c.text) for c in chunks] == [(None, "A", "intro"), ("B", "B", "body")]


def test_h2_immediately_followed_by_h3_has_no_preamble() -> None:
    chunks = chunk_markdown("## A\n### B\n\nbody\n", file=FILE)
    assert [c.h3 for c in chunks] == ["B"]


def test_h3_with_empty_body_yields_no_chunk() -> None:
    assert _chunks("## A\n\n### Empty\n\n### Full\n\nbody\n") == [("A", "Full", "body")]


def test_backtick_fence_hides_heading_like_lines() -> None:
    text = "## A\n\n### B\n\n```\n## x\n### y\n```\n"
    chunks = chunk_markdown(text, file=FILE)
    assert [(c.h2, c.h3) for c in chunks] == [("A", "B")]
    assert "## x" in chunks[0].text


def test_tilde_fence_hides_heading_like_lines() -> None:
    text = "## A\n\n### B\n\n~~~\n## x\n~~~\n"
    chunks = chunk_markdown(text, file=FILE)
    assert [(c.h2, c.h3) for c in chunks] == [("A", "B")]
    assert "## x" in chunks[0].text


def test_h4_and_deeper_stay_inside_their_h3_chunk() -> None:
    chunks = chunk_markdown("## A\n\n### B\n\nlead\n\n#### D\n\ndeep\n", file=FILE)
    assert len(chunks) == 1
    assert "#### D" in chunks[0].text
    assert chunks[0].text.endswith("deep")


def test_text_above_first_h2_is_not_indexed() -> None:
    chunks = chunk_markdown("# Title\n\ntoc line\n\n## A\n\nbody\n", file=FILE)
    assert [c.text for c in chunks] == ["body"]


def test_empty_text_and_title_only_yield_no_chunks() -> None:
    assert chunk_markdown("", file=FILE) == []
    assert chunk_markdown("# Title\n", file=FILE) == []
    assert chunk_markdown("# Title\n\nsome prose, no section\n", file=FILE) == []


def test_line_numbers_are_one_based_and_match_the_source() -> None:
    text = "# T\n\n## A\n\n### B\n\nline one\nline two\n\n### C\n\nlast\n"
    lines = text.split("\n")
    by_h3 = {c.h3: c for c in chunk_markdown(text, file=FILE)}
    assert (by_h3["B"].line_start, by_h3["B"].line_end) == (5, 8)
    assert (by_h3["C"].line_start, by_h3["C"].line_end) == (10, 12)
    assert lines[by_h3["B"].line_start - 1] == "### B"
    assert lines[by_h3["C"].line_end - 1] == "last"


def test_oversized_h3_splits_at_paragraph_boundaries_and_tiles_the_section() -> None:
    paras = ["a" * 100, "b" * 100, "c" * 100]
    text = "## A\n\n### B\n\n" + "\n\n".join(paras) + "\n"
    chunks = chunk_markdown(text, file=FILE, max_chars=200)
    assert [c.part_index for c in chunks] == [0, 1, 2]
    assert {(c.h2, c.h3, c.heading) for c in chunks} == {("A", "B", "B")}
    assert [c.text for c in chunks] == paras
    lines = text.split("\n")
    assert chunks[0].line_start == 3  # part 0 starts at the heading line
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert all(not ln.strip() for ln in lines[previous.line_end : current.line_start - 1])
    assert chunks[-1].line_end == 9  # last paragraph line


def test_fenced_block_longer_than_the_limit_stays_whole() -> None:
    fence = "```\n" + "\n".join("x" * 50 for _ in range(6)) + "\n```"
    text = f"## A\n\n### B\n\nintro\n\n{fence}\n\noutro\n"
    chunks = chunk_markdown(text, file=FILE, max_chars=200)
    holders = [c for c in chunks if fence in c.text]
    assert len(holders) == 1
    assert len(chunks) == 3


def test_table_is_never_split() -> None:
    rows = "\n".join(f"| row {n:02d} | {'v' * 20} |" for n in range(12))
    table = f"| name | value |\n| --- | --- |\n{rows}"
    text = f"## A\n\n### B\n\nintro\n\n{table}\n"
    chunks = chunk_markdown(text, file=FILE, max_chars=200)
    holders = [c for c in chunks if "| row 11 |" in c.text]
    assert len(holders) == 1
    assert "| name | value |" in holders[0].text


def test_default_limit_keeps_ordinary_sections_in_one_part() -> None:
    body = "word " * 100
    chunks = chunk_markdown(f"## A\n\n### B\n\n{body}\n", file=FILE)
    assert len(chunks) == 1
    assert len(chunks[0].text) < MAX_CHUNK_CHARS


def test_output_is_ordered_by_line_then_part_index() -> None:
    text = "## A\n\n### B\n\n" + "\n\n".join("p" * 100 for _ in range(3)) + "\n\n### C\n\nend\n"
    chunks = chunk_markdown(text, file=FILE, max_chars=200)
    order = [(c.line_start, c.part_index) for c in chunks]
    assert order == sorted(order)
    assert [c.h3 for c in chunks] == ["B", "B", "B", "C"]


def test_duplicate_headings_get_distinct_keys_with_occurrence_suffix() -> None:
    text = "## A\n\n### Examples\n\nfirst\n\n### Examples\n\nsecond\n"
    first, second = chunk_markdown(text, file=FILE)
    assert "~" not in first.chunk_key
    assert second.chunk_key.endswith("~2")
    assert second.chunk_key.removesuffix("~2") == first.chunk_key


def test_heading_outline_lists_h2_and_h3_with_lines_and_skips_fences() -> None:
    text = "# T\n\n## A\n\n### B\n\n```\n## no\n```\n\n#### deep\n\n## C\n"
    assert [(h.level, h.title, h.line) for h in heading_outline(text)] == [
        (2, "A", 3),
        (3, "B", 5),
        (2, "C", 13),
    ]
