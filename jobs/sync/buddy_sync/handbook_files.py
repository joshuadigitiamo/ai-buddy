"""Read a local folder of Markdown handbook pages (D-25, D-26).

The folder is mounted read-only and never committed. Each ``*.md`` file starts with a YAML
front matter block; only ``title``, ``last_updated`` and ``date_created`` are read, every
other key (legacy export ids, source URLs, person ids) is dropped here and never copied on.
A file named in the denylist is counted but never opened (D-13 as amended by D-25).
Error messages name files and keys, never file content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import yaml

SOURCE_ID: Final = "local-handbook"
CITATION_PREFIX: Final = "handbook://"
PAGE_FILE_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.md$")

_EDIT_DATE_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2} \(date_edited (\d{4}-\d{2}-\d{2})\)$")
_FENCE: Final = "---"


class HandbookFilesError(Exception):
    """A handbook folder or file broke a rule. The message never carries file content."""


@dataclass(frozen=True, slots=True)
class SourcePage:
    page_id: str
    position: int
    title: str
    content: str
    date_created: int | None
    date_edited: int | None


@dataclass(frozen=True, slots=True)
class HandbookFiles:
    pages: tuple[SourcePage, ...]
    seen: int
    denied: int


def citation_uri(page_id: str) -> str:
    """The stable citation for a page: ``handbook://<page_id>``."""
    return CITATION_PREFIX + page_id


def _epoch_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def _split_front_matter(name: str, text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        raise HandbookFilesError(f"{name}: front matter must start with a '---' line")
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == _FENCE:
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    raise HandbookFilesError(f"{name}: front matter block is not closed by a '---' line")


def _parse_meta(name: str, block: str) -> dict[str, object]:
    try:
        meta = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        # The YAML error text quotes the offending line: keep only its class (T-01-42).
        raise HandbookFilesError(
            f"{name}: front matter is not valid YAML ({type(exc).__name__})"
        ) from None
    if not isinstance(meta, dict):
        raise HandbookFilesError(f"{name}: front matter is not a mapping")
    return {str(key): value for key, value in meta.items()}


def _plain_date(value: object) -> date | None:
    """A YAML date (not a timestamp with a time part), else None."""
    return value if type(value) is date else None


def _date_edited(name: str, meta: dict[str, object]) -> int:
    value = meta.get("last_updated")
    day = _plain_date(value)
    if day is not None:
        return _epoch_ms(day)
    if isinstance(value, str):
        match = _EDIT_DATE_RE.fullmatch(value)
        if match is not None:
            try:
                return _epoch_ms(date.fromisoformat(match.group(1)))
            except ValueError:
                pass
    raise HandbookFilesError(f"{name}: last_updated must be a date or 'DATE (date_edited DATE)'")


def _date_created(name: str, meta: dict[str, object]) -> int | None:
    if "date_created" not in meta or meta["date_created"] is None:
        return None
    day = _plain_date(meta["date_created"])
    if day is None:
        raise HandbookFilesError(f"{name}: date_created must be a date")
    return _epoch_ms(day)


def _read_page(path: Path, position: int) -> SourcePage:
    name = path.name
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HandbookFilesError(f"{name}: file is not valid UTF-8") from exc
    block, content = _split_front_matter(name, text)
    meta = _parse_meta(name, block)
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        raise HandbookFilesError(f"{name}: title must be a non-empty string")
    return SourcePage(
        page_id=path.stem,
        position=position,
        title=title.strip(),
        content=content,
        date_created=_date_created(name, meta),
        date_edited=_date_edited(name, meta),
    )


def _list_page_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise HandbookFilesError("HANDBOOK_DIR is not a directory")
    files = sorted(
        (path for path in root.iterdir() if path.suffix == ".md" and path.is_file()),
        key=lambda path: path.name,
    )
    for path in files:
        if PAGE_FILE_RE.fullmatch(path.name) is None:
            raise HandbookFilesError(
                f"{path.name}: page file name must match {PAGE_FILE_RE.pattern}"
            )
    return files


def _check_inside(root: Path, path: Path) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise HandbookFilesError(f"{path.name}: file resolves outside HANDBOOK_DIR")


def read_handbook_dir(root: Path, *, denylist: frozenset[str]) -> HandbookFiles:
    """Read every non-denylisted ``*.md`` page directly inside ``root``, in file-name order.

    Every denylist entry must name a page file in the folder, so a typo or a stale entry
    cannot let a page through. A denylisted file is never opened.
    """
    files = _list_page_files(root)
    unknown = sorted(denylist - {path.name for path in files})
    if unknown:
        raise HandbookFilesError(
            "REDACT_PAGE_FILES names no file in HANDBOOK_DIR: " + ", ".join(unknown)
        )
    pages: list[SourcePage] = []
    denied = 0
    for path in files:
        if path.name in denylist:
            denied += 1
            continue
        _check_inside(root, path)
        pages.append(_read_page(path, len(pages)))
    return HandbookFiles(pages=tuple(pages), seen=len(files), denied=denied)
