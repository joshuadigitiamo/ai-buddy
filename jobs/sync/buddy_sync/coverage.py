"""Measure how many Guides chunks carry a scene timestamp (D-18).

Two views of the same numbers, both built on the ``video_map`` anti-corruption layer and the
index reader, so no second parser of Guides files exists:

* ``coverage_from_index``: what the published index holds now;
* ``coverage_from_tree``: what the index would hold if the given Guides working tree (its
  ``sections.yaml`` and ``out/durations.json`` files) were committed, over the chunks of the
  published index.

A chunk without a scene entry keeps the D-18 fallback (the current part's full video, no
offset), decided at 04-01 ``coverage_inheritance`` (a); there is no ``inherited`` count.
The report holds guide file paths, labels and counts only (T-04-45).
"""

import logging
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from buddy_core.index_reader import open_index
from buddy_core.models import GuideChunk, VideoLink
from buddy_sync.video_map import (
    DURATIONS_RELPATH,
    README_NAME,
    SECTIONS_GLOB,
    VideoMapError,
    load_sections_file,
    parse_readme_videos,
    resolve_video_links,
    video_basename,
)

BASELINE_SCENE_ROWS: Final = 238
BASELINE_TOTAL_ROWS: Final = 2524

LABEL_SECTIONS: Final = "sections.yaml"
LABEL_DURATIONS_ONLY: Final = "durations only"
LABEL_NO_DURATIONS: Final = "no durations"

_LOGGER: Final = logging.getLogger("buddy_sync.coverage")
_PART_SUFFIX: Final = re.compile(r"_part\d+$")


@dataclass(frozen=True, slots=True)
class CoverageRow:
    """Rows of one guide file that have a video link, split by how the link was found."""

    file: str
    rows: int
    scene: int
    fallback: int
    label: str = ""


def _rows_per_guide(
    chunks: Iterable[GuideChunk], links: Mapping[str, VideoLink], labels: Mapping[str, str]
) -> list[CoverageRow]:
    scene: Counter[str] = Counter()
    fallback: Counter[str] = Counter()
    for chunk in chunks:
        link = links.get(chunk.chunk_key)
        if link is None:
            continue
        (scene if link.source == "scene" else fallback)[chunk.file] += 1
    return [
        CoverageRow(
            file=file,
            rows=scene[file] + fallback[file],
            scene=scene[file],
            fallback=fallback[file],
            label=labels.get(file, ""),
        )
        for file in sorted(set(scene) | set(fallback))
    ]


def coverage_from_index(index_path: Path) -> list[CoverageRow]:
    """Per guide file, the chunk rows of the published index that have a video link."""
    with open_index(index_path) as reader:
        return _rows_per_guide(reader.guide_chunks(), reader.video_links(), {})


def _topic_of(parts_urls: Sequence[str]) -> str | None:
    """The video topic folder a README row names: the file stem without a ``_partN`` suffix."""
    try:
        stem = video_basename(parts_urls[0]).removesuffix(".mp4")
    except (VideoMapError, IndexError):
        return None
    return _PART_SUFFIX.sub("", stem)


def _labels(root: Path, guides: Iterable[str]) -> dict[str, str]:
    mapped = {load_sections_file(path).guide for path in sorted(root.glob(SECTIONS_GLOB))}
    readme = parse_readme_videos((root / README_NAME).read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for guide in guides:
        if guide in mapped:
            labels[guide] = LABEL_SECTIONS
            continue
        topic = _topic_of([part.url for part in readme.get(guide, [])])
        durations = None if topic is None else root / "videos" / topic / DURATIONS_RELPATH
        has_durations = durations is not None and durations.is_file()
        labels[guide] = LABEL_DURATIONS_ONLY if has_durations else LABEL_NO_DURATIONS
    return labels


def coverage_from_tree(root: Path, index_path: Path) -> list[CoverageRow]:
    """Project the report from a Guides working tree over the chunks of the published index."""
    with open_index(index_path) as reader:
        chunks = reader.guide_chunks()
    links = resolve_video_links(root, chunks, logger=_LOGGER)
    files = {chunk.file for chunk in chunks if chunk.chunk_key in links}
    return _rows_per_guide(chunks, links, _labels(root, files) if files else {})


def format_report(rows: Sequence[CoverageRow]) -> str:
    """One line per guide, then ``scene=<S> fallback=<F> rows=<T> (baseline 238/2524)``."""
    lines = [
        f"{row.file}  rows={row.rows} scene={row.scene} fallback={row.fallback}"
        + (f"  [{row.label}]" if row.label else "")
        for row in rows
    ]
    scene = sum(row.scene for row in rows)
    fallback = sum(row.fallback for row in rows)
    lines.append(
        f"scene={scene} fallback={fallback} rows={scene + fallback} "
        f"(baseline {BASELINE_SCENE_ROWS}/{BASELINE_TOTAL_ROWS})"
    )
    return "\n".join(lines)
