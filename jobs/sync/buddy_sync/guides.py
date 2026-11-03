"""Turn a Guides checkout into redacted heading chunks (SYNC-04, D-18, D-19)."""

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from buddy_core.index_reader import IndexReader
from buddy_core.models import GuideChunk
from buddy_sync.chunker import Heading, assign_chunk_keys, chunk_markdown, heading_outline
from buddy_sync.guides_git import GuidesCheckout
from buddy_sync.redaction import Redactor, RuleHit, log_hits


@dataclass(frozen=True, slots=True)
class GuidesSyncResult:
    """Chunks and heading outline of one Guides sync."""

    chunks: tuple[GuideChunk, ...]
    commit_sha: str
    rebuilt: bool
    outline: dict[str, list[Heading]]


def select_guide_files(root: Path) -> list[str]:
    """Indexed files as sorted posix paths relative to ``root``."""
    return sorted(path.relative_to(root).as_posix() for path in root.glob("**/*_GUIDE.md"))


def _read(root: Path, relpath: str) -> str:
    return (root / relpath).read_text(encoding="utf-8")


def _merge(hits: Sequence[RuleHit]) -> list[RuleHit]:
    totals: Counter[str] = Counter()
    for hit in hits:
        totals[hit.rule] += hit.count
    return [RuleHit(rule, count) for rule, count in totals.items()]


def _redact_chunk(chunk: GuideChunk, redactor: Redactor) -> tuple[GuideChunk, list[RuleHit]]:
    hits: list[RuleHit] = []

    def clean(value: str) -> str:
        result = redactor.redact(value)
        hits.extend(result.hits)
        return result.text

    redacted = replace(
        chunk,
        h2=clean(chunk.h2),
        h3=clean(chunk.h3) if chunk.h3 is not None else None,
        heading=clean(chunk.heading),
        text=clean(chunk.text),
    )
    return redacted, _merge(hits)


def build_guide_chunks(
    root: Path,
    files: Sequence[str],
    *,
    redactor: Redactor,
    logger: logging.Logger,
) -> list[GuideChunk]:
    """Chunk and redact each file; chunk keys are derived from the redacted headings."""
    out: list[GuideChunk] = []
    for relpath in files:
        redacted: list[GuideChunk] = []
        for chunk in chunk_markdown(_read(root, relpath), file=relpath):
            clean, hits = _redact_chunk(chunk, redactor)
            log_hits(logger, f"{relpath}#L{chunk.line_start}", hits)
            redacted.append(clean)
        out.extend(assign_chunk_keys(relpath, redacted))
    return out


def sync_guides(
    checkout: GuidesCheckout,
    *,
    previous: IndexReader | None,
    versions_match: bool,
    redactor: Redactor,
    logger: logging.Logger,
) -> GuidesSyncResult:
    """Build the Guides chunks for a checkout."""
    files = select_guide_files(checkout.path)
    chunks = build_guide_chunks(checkout.path, files, redactor=redactor, logger=logger)
    outline = {relpath: heading_outline(_read(checkout.path, relpath)) for relpath in files}
    return GuidesSyncResult(
        chunks=tuple(chunks), commit_sha=checkout.commit_sha, rebuilt=True, outline=outline
    )
