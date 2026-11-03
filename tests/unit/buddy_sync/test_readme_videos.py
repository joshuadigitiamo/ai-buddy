"""README video table parser: formats it accepts and the drift guard (synthetic text only)."""

from pathlib import Path

import pytest

from buddy_sync.video_map import VideoMapError, VideoPart, parse_readme_videos

HEADER = "| Guide | Topic | Video |\n|---|---|---|\n"
URL = "https://videos.example.invalid"


def table(*rows: str) -> str:
    return HEADER + "\n".join(rows) + "\n"


def test_single_link_row_is_part_one() -> None:
    text = table(f"| [Demo](A/DEMO_GUIDE.md) | Topic | [02:00]({URL}/demo.mp4) |")
    assert parse_readme_videos(text) == {"A/DEMO_GUIDE.md": [VideoPart(1, f"{URL}/demo.mp4")]}


def test_multi_part_row_gives_ordered_parts() -> None:
    cell = f"[Part 1 · 01:00]({URL}/m_part1.mp4)<br>[Part 2 · 01:30]({URL}/m_part2.mp4)"
    parts = parse_readme_videos(table(f"| [Multi](A/M_GUIDE.md) | Topic | {cell} |"))
    assert parts == {
        "A/M_GUIDE.md": [VideoPart(1, f"{URL}/m_part1.mp4"), VideoPart(2, f"{URL}/m_part2.mp4")]
    }


def test_parts_are_sorted_by_part_number_not_by_position() -> None:
    cell = f"[Part 2 · 01:30]({URL}/b.mp4)<br>[Part 1 · 01:00]({URL}/a.mp4)"
    parts = parse_readme_videos(table(f"| [Multi](A/M_GUIDE.md) | T | {cell} |"))
    assert [p.part for p in parts["A/M_GUIDE.md"]] == [1, 2]


@pytest.mark.parametrize("dash", ["—", "–", "-"])
def test_dash_row_has_no_key(dash: str) -> None:
    assert parse_readme_videos(table(f"| [No](F/NO_GUIDE.md) | Topic | {dash} |")) == {}


def test_rows_outside_the_table_and_separator_rows_are_ignored() -> None:
    text = (
        "Intro with a [link](A/OUTSIDE_GUIDE.md) in prose.\n\n"
        + table(f"| [Demo](./A/DEMO_GUIDE.md) | Topic | [02:00]({URL}/demo.mp4) |")
        + "\n| Other | Table | Without guide links |\n|:---|---:|---|\n"
    )
    assert list(parse_readme_videos(text)) == ["A/DEMO_GUIDE.md"]


def test_topic_cell_with_escaped_pipe_does_not_shift_columns() -> None:
    text = table(f"| [Demo](A/DEMO_GUIDE.md) | a \\| b | [02:00]({URL}/demo.mp4) |")
    assert parse_readme_videos(text)["A/DEMO_GUIDE.md"][0].url == f"{URL}/demo.mp4"


@pytest.mark.parametrize(
    "cell",
    [
        "coming soon",
        "",
        f"[02:00]({URL}/demo.webm)",
        "[02:00](http://videos.example.invalid/demo.mp4)",
        f"[01:00]({URL}/a.mp4)<br>[01:30]({URL}/b.mp4)",
        f"[Part 1 · 01:00]({URL}/a.mp4)<br>[Part 1 · 01:30]({URL}/b.mp4)",
    ],
    ids=["text", "empty", "not_mp4", "not_https", "unlabelled_multi", "repeated_part"],
)
def test_drifted_video_cell_raises(cell: str) -> None:
    with pytest.raises(VideoMapError, match="D_GUIDE"):
        parse_readme_videos(table(f"| [D](A/D_GUIDE.md) | Topic | {cell} |"))


def test_guide_listed_twice_raises() -> None:
    row = f"| [D](A/D_GUIDE.md) | Topic | [02:00]({URL}/d.mp4) |"
    with pytest.raises(VideoMapError, match="more than once"):
        parse_readme_videos(table(row, row))


def test_fixture_readme_parses_to_the_three_guides_with_a_video() -> None:
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "guides_videos" / "README.md"
    parts = parse_readme_videos(fixture.read_text(encoding="utf-8"))
    assert sorted(parts) == [
        "AI-Engineering/DEMO_GUIDE.md",
        "AI-Engineering/FALLBACK_GUIDE.md",
        "AI-Engineering/MULTI_GUIDE.md",
    ]
    assert [p.part for p in parts["AI-Engineering/MULTI_GUIDE.md"]] == [1, 2]
