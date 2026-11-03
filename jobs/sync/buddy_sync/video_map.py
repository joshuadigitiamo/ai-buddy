"""Resolve each Guides chunk to its video link (D-01 to D-06).

Three inputs from the Guides repo are validated here and turned into ``VideoLink`` rows, so
nothing else in the system parses them (anti-corruption layer):

* ``README.md`` video table: the full-video URL of every part of every guide;
* ``videos/<topic>/sections.yaml``: an explicit map from scene id to guide heading (D-02);
* ``videos/<topic>/out/durations.json``: scene durations in narration order, from which the
  start offset of a scene inside its part is computed.

No heuristic text matching is done: a scene link exists only when a ``sections.yaml`` entry
names the heading. Any contract break raises ``VideoMapError`` so the sync fails loudly.
"""

import json
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from buddy_core.models import GuideChunk, VideoLink

SECTIONS_GLOB: Final = "videos/*/sections.yaml"
DURATIONS_RELPATH: Final = "out/durations.json"
README_NAME: Final = "README.md"
MAX_SECTIONS_BYTES: Final = 262_144

_GUIDE_LINK: Final = re.compile(r"\[[^\]]*\]\(([^)\s]+\.md)\)")
_VIDEO_LINK: Final = re.compile(r"\[([^\]]*)\]\((https://[^)\s]+\.mp4)\)")
_PART_LABEL: Final = re.compile(r"^\s*Part\s+(\d+)\b")
_SEPARATOR_CELL: Final = re.compile(r"^:?-+:?$")
_CELL_SPLIT: Final = re.compile(r"(?<!\\)\|")
_DASHES: Final = frozenset({"-", "–", "—"})
_SCENE_PART: Final = re.compile(r"^P(\d+)S")


@dataclass(frozen=True, slots=True)
class VideoPart:
    """One playable part of a guide's full video."""

    part: int
    url: str


class SectionEntry(BaseModel):
    """One scene mapped to a Guides heading; ``h3`` None maps the whole ``##``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene: str = Field(min_length=1)
    h2: str = Field(min_length=1)
    h3: str | None = Field(default=None, min_length=1)


class SectionsFile(BaseModel):
    """The ``sections.yaml`` contract, versioned by ``schema``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = Field(alias="schema")
    guide: str = Field(min_length=1)
    video: str = Field(min_length=1)
    sections: list[SectionEntry]


class VideoMapError(Exception):
    """The README, a sections.yaml or a durations.json broke its contract."""


def parse_readme_videos(readme_text: str) -> dict[str, list[VideoPart]]:
    """Map guide path to its video parts from the README table; a dash row has no key."""
    result: dict[str, list[VideoPart]] = {}
    for raw in readme_text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in _CELL_SPLIT.split(line.strip("|"))]
        if all(_SEPARATOR_CELL.match(c) for c in cells):
            continue
        guide_match = _GUIDE_LINK.search(cells[0])
        if guide_match is None:
            continue
        guide = guide_match.group(1).removeprefix("./")
        if guide in result:
            raise VideoMapError(f"README lists guide {guide!r} more than once")
        last = cells[-1] if len(cells) > 1 else ""
        if last in _DASHES:
            continue
        links = _VIDEO_LINK.findall(last)
        if not links:
            raise VideoMapError(
                f"README row for guide {guide!r} has neither a dash nor an https .mp4 link"
            )
        result[guide] = _parts_from_links(guide, links)
    return result


def _parts_from_links(guide: str, links: list[tuple[str, str]]) -> list[VideoPart]:
    parts: dict[int, str] = {}
    for label, url in links:
        label_match = _PART_LABEL.match(label)
        if label_match is not None:
            number = int(label_match.group(1))
        elif len(links) == 1:
            number = 1
        else:
            raise VideoMapError(
                f"README row for guide {guide!r} has a link without a 'Part N' label"
            )
        if number in parts:
            raise VideoMapError(f"README row for guide {guide!r} repeats part {number}")
        parts[number] = url
    return [VideoPart(part=n, url=parts[n]) for n in sorted(parts)]


def load_sections_file(path: Path) -> SectionsFile:
    """Parse one sections.yaml with ``yaml.safe_load`` and validate it against the schema."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise VideoMapError(f"{path}: cannot read file ({type(exc).__name__})") from exc
    if size > MAX_SECTIONS_BYTES:
        raise VideoMapError(f"{path}: larger than {MAX_SECTIONS_BYTES} bytes")
    try:
        data: Any = yaml.safe_load(path.read_bytes())
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" at line {mark.line + 1}" if mark is not None else ""
        raise VideoMapError(f"{path}: not valid YAML ({type(exc).__name__}{where})") from exc
    try:
        return SectionsFile.model_validate(data)
    except ValidationError as exc:
        locs = {".".join(str(p) for p in e["loc"]) or "<root>" for e in exc.errors()}
        places = ", ".join(sorted(locs))
        raise VideoMapError(f"{path}: schema violation at {places}") from exc


def scene_offsets(durations: Mapping[str, float]) -> dict[str, tuple[int, float]]:
    """Scene id to (part, start seconds inside that part), following mapping order."""
    elapsed: dict[int, float] = {}
    offsets: dict[str, tuple[int, float]] = {}
    for scene, duration in durations.items():
        match = _SCENE_PART.match(scene)
        part = int(match.group(1)) if match is not None else 1
        start = elapsed.get(part, 0.0)
        offsets[scene] = (part, start)
        elapsed[part] = start + duration
    return offsets


def _load_durations(path: Path) -> dict[str, float]:
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VideoMapError(f"{path}: cannot read durations ({type(exc).__name__})") from exc
    if not isinstance(data, dict):
        raise VideoMapError(f"{path}: durations must be a JSON object of scene id to seconds")
    durations: dict[str, float] = {}
    for key, value in data.items():
        valid = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
        if not valid:
            raise VideoMapError(f"{path}: duration of {key!r} is not a non-negative number")
        durations[str(key)] = float(value)
    return durations


def _check_guide_path(path: Path, guide: str, indexed: set[str]) -> None:
    posix = PurePosixPath(guide)
    unsafe = (
        guide.startswith("/")
        or "\\" in guide
        or PureWindowsPath(guide).is_absolute()
        or ".." in posix.parts
    )
    if unsafe:
        raise VideoMapError(f"{path}: key 'guide' must be a relative path without '..'")
    if guide not in indexed:
        raise VideoMapError(f"{path}: key 'guide' {guide!r} is not an indexed Guides file")


@dataclass(frozen=True, slots=True)
class _Target:
    part: int
    start: float


def _targets_for(
    path: Path,
    sections: SectionsFile,
    guide_chunks: Sequence[GuideChunk],
    parts: Mapping[int, str],
    offsets: Mapping[str, tuple[int, float]],
    logger: logging.Logger,
) -> dict[tuple[str, str | None], _Target]:
    targets: dict[tuple[str, str | None], _Target] = {}
    for entry in sections.sections:
        if entry.scene not in offsets:
            raise VideoMapError(f"{path}: scene {entry.scene!r} is not in durations.json")
        part, start = offsets[entry.scene]
        if part not in parts:
            raise VideoMapError(f"{path}: scene {entry.scene!r} is in part {part}, not in README")
        if not any(c.h2 == entry.h2 for c in guide_chunks):
            raise VideoMapError(f"{path}: scene {entry.scene!r}: h2 {entry.h2!r} has no chunk")
        if entry.h3 is not None and not any(
            c.h2 == entry.h2 and c.h3 == entry.h3 for c in guide_chunks
        ):
            raise VideoMapError(
                f"{path}: scene {entry.scene!r}: h3 {entry.h3!r} has no chunk under {entry.h2!r}"
            )
        key = (entry.h2, entry.h3)
        if key in targets:
            logger.warning("%s: duplicate target %r for scene %r ignored", path, key, entry.scene)
            continue
        targets[key] = _Target(part=part, start=start)
    return targets


def resolve_video_links(
    root: Path, chunks: Sequence[GuideChunk], *, logger: logging.Logger
) -> dict[str, VideoLink]:
    """Map chunk_key to its VideoLink for every chunk of a guide that has a README video."""
    sections_paths = sorted(root.glob(SECTIONS_GLOB))
    readme = root / README_NAME
    if not readme.is_file():
        if sections_paths:
            raise VideoMapError(f"{readme}: missing, but {len(sections_paths)} sections.yaml exist")
        logger.warning("%s not found; no video links resolved", readme)
        return {}
    try:
        readme_parts = parse_readme_videos(readme.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VideoMapError(f"{readme}: cannot read ({type(exc).__name__})") from exc

    by_file: dict[str, list[GuideChunk]] = {}
    for chunk in sorted(chunks, key=lambda c: (c.file, c.line_start, c.part_index)):
        by_file.setdefault(chunk.file, []).append(chunk)
    indexed = set(by_file)

    targets_by_guide: dict[str, dict[tuple[str, str | None], _Target]] = {}
    for path in sections_paths:
        sections = load_sections_file(path)
        if sections.video != path.parent.name:
            raise VideoMapError(
                f"{path}: key 'video' must equal the folder name {path.parent.name!r}"
            )
        _check_guide_path(path, sections.guide, indexed)
        if sections.guide in targets_by_guide:
            raise VideoMapError(f"{path}: guide {sections.guide!r} is mapped by two files")
        parts = {p.part: p.url for p in readme_parts.get(sections.guide, [])}
        if not parts:
            raise VideoMapError(f"{path}: guide {sections.guide!r} has no video in README")
        offsets = scene_offsets(_load_durations(path.parent / DURATIONS_RELPATH))
        targets_by_guide[sections.guide] = _targets_for(
            path, sections, by_file[sections.guide], parts, offsets, logger
        )

    links: dict[str, VideoLink] = {}
    for guide, guide_chunks in by_file.items():
        video_parts = readme_parts.get(guide)
        if not video_parts:
            continue
        urls = {p.part: p.url for p in video_parts}
        targets = targets_by_guide.get(guide, {})
        current = 1 if 1 in urls else min(urls)
        for chunk in guide_chunks:
            target = targets.get((chunk.h2, chunk.h3)) if chunk.h3 is not None else None
            if target is None:
                target = targets.get((chunk.h2, None))
            if target is None:
                links[chunk.chunk_key] = VideoLink(urls[current], current, None, "readme_fallback")
                continue
            current = target.part
            links[chunk.chunk_key] = VideoLink(urls[current], current, target.start, "scene")
    return links
