"""GUIDES_INDEX.md generation and drift check (D-23). RED skeleton: behaviour follows."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from buddy_sync.chunker import Heading

GUIDES_INDEX_NAME: Final = "GUIDES_INDEX.md"


@dataclass(frozen=True, slots=True)
class IndexEntry:
    file: str
    level: int
    title: str
    line: int


@dataclass(frozen=True, slots=True)
class Drift:
    kind: Literal["missing", "extra", "moved", "absent_file"]
    file: str
    title: str
    declared_line: int | None
    actual_line: int | None


class GuidesIndexDriftError(Exception):
    """GUIDES_INDEX.md disagrees with the headings of the Guides."""


def render_guides_index(outline: Mapping[str, Sequence[Heading]]) -> str:
    return ""


def parse_guides_index(text: str) -> list[IndexEntry]:
    return []


def compare_guides_index(
    declared: Sequence[IndexEntry], actual_outline: Mapping[str, Sequence[Heading]]
) -> list[Drift]:
    return []


def check_guides_index(
    root: Path,
    outline: Mapping[str, Sequence[Heading]],
    *,
    strict: bool,
    logger: logging.Logger,
) -> list[Drift]:
    return []


def write_guides_index(root: Path, outline: Mapping[str, Sequence[Heading]]) -> Path:
    return root / GUIDES_INDEX_NAME
