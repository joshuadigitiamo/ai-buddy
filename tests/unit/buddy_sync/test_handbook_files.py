"""Loader contract for the local handbook folder (D-25, D-26, SYNC-01, SYNC-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from buddy_sync.handbook_files import (
    HandbookFilesError,
    SourcePage,
    citation_uri,
    read_handbook_dir,
)

MARKER = "MARKER-synthetic-7f3a"
NO_DENY: frozenset[str] = frozenset()


def _ms(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=UTC).timestamp() * 1000)


def _write(root: Path, name: str, front: str, body: str = "Corpo.\n") -> Path:
    path = root / name
    path.write_text(f"---\n{front}---\n{body}", encoding="utf-8")
    return path


def _page(root: Path, name: str = "01-a.md", front: str | None = None) -> SourcePage:
    if front is not None:
        _write(root, name, front)
    return read_handbook_dir(root, denylist=NO_DENY).pages[0]


def _error(root: Path, denylist: frozenset[str] = NO_DENY) -> str:
    with pytest.raises(HandbookFilesError) as info:
        read_handbook_dir(root, denylist=denylist)
    return str(info.value)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "handbook"
    folder.mkdir()
    return folder


def test_pages_in_file_name_order_with_stem_title_and_content(root: Path) -> None:
    _write(root, "02-b.md", "title: Secondo\nlast_updated: 2026-10-02\n", "Testo due.\n")
    _write(root, "01-a.md", "title: Primo\nlast_updated: 2026-10-01\n", "Testo uno.\n")
    _write(root, "03-c.md", "title: Terzo\nlast_updated: 2026-10-03\n")

    files = read_handbook_dir(root, denylist=NO_DENY)

    assert [p.page_id for p in files.pages] == ["01-a", "02-b", "03-c"]
    assert [p.position for p in files.pages] == [0, 1, 2]
    assert [p.title for p in files.pages] == ["Primo", "Secondo", "Terzo"]
    assert files.pages[0].content == "Testo uno.\n"
    assert files.seen == 3
    assert files.denied == 0


def test_last_updated_date_is_the_edit_date(root: Path) -> None:
    page = _page(root, front="title: T\nlast_updated: 2026-10-01\ndate_created: 2026-09-01\n")

    assert page.date_edited == _ms(2026, 10, 1)
    assert page.date_created == _ms(2026, 9, 1)


def test_export_string_form_gives_the_date_edited_value(root: Path) -> None:
    page = _page(root, front="title: T\nlast_updated: 2026-10-03 (date_edited 2026-09-20)\n")

    assert page.date_edited == _ms(2026, 9, 20)


def test_missing_date_created_is_none(root: Path) -> None:
    page = _page(root, front="title: T\nlast_updated: 2026-10-01\n")

    assert page.date_created is None


@pytest.mark.parametrize(
    "last_updated",
    [
        None,
        "last_updated: 2026-10-01 10:30:00\n",
        "last_updated: yesterday\n",
        "last_updated: 2026-10-03 (edited 2026-09-20)\n",
    ],
)
def test_bad_or_missing_last_updated_names_file_and_key(
    root: Path, last_updated: str | None
) -> None:
    _write(root, "01-a.md", "title: T\n" + (last_updated or ""))

    message = _error(root)

    assert "01-a.md" in message
    assert "last_updated" in message


@pytest.mark.parametrize(
    "front", ["last_updated: 2026-10-01\n", "title: ''\nlast_updated: 2026-10-01\n"]
)
def test_missing_or_empty_title_names_file(root: Path, front: str) -> None:
    _write(root, "01-a.md", front)

    message = _error(root)

    assert "01-a.md" in message
    assert "title" in message


def test_file_without_opening_fence_names_file(root: Path) -> None:
    (root / "01-a.md").write_text("title: T\nlast_updated: 2026-10-01\n", encoding="utf-8")

    assert "01-a.md" in _error(root)


def test_unclosed_block_names_file(root: Path) -> None:
    (root / "01-a.md").write_text("---\ntitle: T\nlast_updated: 2026-10-01\n", encoding="utf-8")

    assert "01-a.md" in _error(root)


def test_invalid_yaml_names_file_and_class_but_not_the_line(root: Path) -> None:
    _write(root, "01-a.md", f"title: [{MARKER}\n")

    message = _error(root)

    assert "01-a.md" in message
    assert ("ParserError" in message or "ScannerError" in message) is True
    assert (MARKER in message) is False


def test_yaml_that_is_not_a_mapping_names_file(root: Path) -> None:
    _write(root, "01-a.md", f"- {MARKER}\n")

    message = _error(root)

    assert "01-a.md" in message
    assert (MARKER in message) is False


def test_file_that_is_not_utf8_names_file(root: Path) -> None:
    (root / "01-a.md").write_bytes(b"---\ntitle: \xff\xfe\n---\n")

    assert "01-a.md" in _error(root)


def test_unknown_front_matter_keys_are_ignored(root: Path) -> None:
    page = _page(
        root,
        front=(
            "title: T\nlast_updated: 2026-10-01\n"
            f"page_id: {MARKER}\nsource: https://legacy.example.invalid/{MARKER}\n"
            f"creator_id: {MARKER}\n"
        ),
    )

    held = [str(getattr(page, field)) for field in page.__slots__]
    assert any(MARKER in value for value in held) is False


def test_denylisted_file_is_never_opened(root: Path) -> None:
    _write(root, "01-a.md", "title: A\nlast_updated: 2026-10-01\n")
    (root / "07-wi-fi.md").write_bytes(b"\xff\xfe\x00 no front matter, not utf-8")

    files = read_handbook_dir(root, denylist=frozenset({"07-wi-fi.md"}))

    assert [p.page_id for p in files.pages] == ["01-a"]
    assert files.denied == 1
    assert files.seen == 2


def test_positions_skip_denied_files(root: Path) -> None:
    _write(root, "01-a.md", "title: A\nlast_updated: 2026-10-01\n")
    _write(root, "02-b.md", "title: B\nlast_updated: 2026-10-01\n")
    _write(root, "03-c.md", "title: C\nlast_updated: 2026-10-01\n")

    files = read_handbook_dir(root, denylist=frozenset({"02-b.md"}))

    assert [(p.page_id, p.position) for p in files.pages] == [("01-a", 0), ("03-c", 1)]


def test_denylist_entry_naming_no_file_fails_closed(root: Path) -> None:
    _write(root, "01-a.md", "title: A\nlast_updated: 2026-10-01\n")

    message = _error(root, frozenset({"07-wi-fi.md"}))

    assert "07-wi-fi.md" in message


def test_md_name_outside_the_pattern_is_rejected(root: Path) -> None:
    _write(root, "01-a.md", "title: A\nlast_updated: 2026-10-01\n")
    _write(root, "02 spazio.md", "title: B\nlast_updated: 2026-10-01\n")

    assert "02 spazio.md" in _error(root)


def test_other_files_and_subdirectories_are_ignored(root: Path) -> None:
    _write(root, "01-a.md", "title: A\nlast_updated: 2026-10-01\n")
    (root / "notes.txt").write_text("x", encoding="utf-8")
    (root / "nested").mkdir()
    _write(root / "nested", "02-b.md", "title: B\nlast_updated: 2026-10-01\n")
    (root / "folder.md").mkdir()

    files = read_handbook_dir(root, denylist=NO_DENY)

    assert [p.page_id for p in files.pages] == ["01-a"]
    assert files.seen == 1


def test_symlink_resolving_outside_the_folder_is_rejected(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    target = _write(outside, "secret.md", "title: S\nlast_updated: 2026-10-01\n")
    (root / "01-leak.md").symlink_to(target)

    assert "01-leak.md" in _error(root)


def test_missing_root_names_the_variable(tmp_path: Path) -> None:
    assert "HANDBOOK_DIR" in _error(tmp_path / "absent")


def test_root_that_is_a_file_names_the_variable(tmp_path: Path) -> None:
    afile = tmp_path / "afile"
    afile.write_text("x", encoding="utf-8")

    assert "HANDBOOK_DIR" in _error(afile)


def test_citation_uri() -> None:
    assert citation_uri("03-x") == "handbook://03-x"
