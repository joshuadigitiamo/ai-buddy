"""Turn local handbook pages into redacted, citable ``HandbookPage`` rows.

Pages come from the local handbook folder; denylisted files are skipped by the reader
before they are opened (D-13 as amended by D-25). The stored ``content_hash`` covers the
redacted title and content only, never raw source text.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from buddy_core.models import HandbookPage
from buddy_sync.handbook_files import SourcePage, citation_uri
from buddy_sync.redaction import Redactor, RuleHit, log_hits

_MS_THRESHOLD = 1e12


class EmptyDenylistError(Exception):
    """REDACT_PAGE_FILES is empty and the caller did not opt in to that explicitly."""


class EmptyHandbookError(Exception):
    """No page is left after the denylist; nothing may be published."""


@dataclass(frozen=True, slots=True)
class HandbookSyncResult:
    pages: tuple[HandbookPage, ...]
    processed: int
    unchanged: int
    removed: int


def revision_date_iso(raw: int | None) -> str | None:
    """UTC ISO-8601 from an epoch value: >= 1e12 is milliseconds, smaller is seconds."""
    if raw is None:
        return None
    seconds = raw / 1000 if raw >= _MS_THRESHOLD else raw
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat()


def _content_hash(title: str, content: str) -> str:
    return hashlib.sha256(f"{title}\x00{content}".encode()).hexdigest()


def _merge_hits(*groups: Sequence[RuleHit]) -> tuple[RuleHit, ...]:
    totals: dict[str, int] = {}
    for group in groups:
        for hit in group:
            totals[hit.rule] = totals.get(hit.rule, 0) + hit.count
    return tuple(RuleHit(rule, count) for rule, count in totals.items())


def sync_handbook(
    pages: Sequence[SourcePage],
    *,
    previous: Sequence[HandbookPage] | None,
    versions_match: bool,
    redactor: Redactor,
    logger: logging.Logger,
) -> HandbookSyncResult:
    """Redact every page and return rows in file-name order.

    A page is *processed* when it is new, when ``versions_match`` is False, when its
    ``date_edited`` differs from the previous row, or when the hash of its redacted text
    differs. Otherwise the previous row is kept, with the current position.
    """
    before = {row.page_id: row for row in previous or ()}
    rows: list[HandbookPage] = []
    processed = 0
    for page in pages:
        title = redactor.redact(page.title)
        body = redactor.redact(page.content)
        content_hash = _content_hash(title.text, body.text)
        old = before.get(page.page_id)
        if (
            old is not None
            and versions_match
            and old.date_edited_raw == page.date_edited
            and old.content_hash == content_hash
        ):
            rows.append(replace(old, parent_id=None, position=len(rows), depth=0))
            continue
        processed += 1
        log_hits(logger, page.page_id, _merge_hits(title.hits, body.hits))
        rows.append(
            HandbookPage(
                page_id=page.page_id,
                parent_id=None,
                position=len(rows),
                depth=0,
                title=title.text,
                url=citation_uri(page.page_id),
                date_edited_raw=page.date_edited,
                date_created_raw=page.date_created,
                revision_date_iso=revision_date_iso(
                    page.date_edited if page.date_edited is not None else page.date_created
                ),
                content_md=body.text,
                content_hash=content_hash,
            )
        )

    if not rows:
        raise EmptyHandbookError("no handbook page left after the denylist")

    return HandbookSyncResult(
        pages=tuple(rows),
        processed=processed,
        unchanged=len(rows) - processed,
        removed=len(before.keys() - {row.page_id for row in rows}),
    )
