"""Turn fetched ClickUp pages into redacted, citable ``HandbookPage`` rows.

Denylisted pages are dropped before redaction, hashing or logging (D-13). The stored
``content_hash`` covers the redacted title and content only, never raw upstream text.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from buddy_core.models import HandbookPage
from buddy_sync.clickup import FlatPage, page_url
from buddy_sync.redaction import Redactor, RuleHit, log_hits

_MS_THRESHOLD = 1e12


class EmptyDenylistError(Exception):
    """REDACT_PAGE_IDS is empty and the caller did not opt in to that explicitly."""


class EmptyHandbookError(Exception):
    """No page is left after the denylist and archived filters; nothing may be published."""


@dataclass(frozen=True, slots=True)
class HandbookSyncResult:
    pages: tuple[HandbookPage, ...]
    seen: int
    processed: int
    unchanged: int
    removed: int
    denied: int
    skipped_archived: int


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
    fetched: Sequence[FlatPage],
    *,
    previous: Sequence[HandbookPage] | None,
    versions_match: bool,
    denylist: frozenset[str],
    allow_empty_denylist: bool,
    redactor: Redactor,
    workspace_id: int,
    doc_id: str,
    skipped_archived: int,
    logger: logging.Logger,
) -> HandbookSyncResult:
    """Redact every non-denylisted page and return rows in tree order."""
    if not denylist and not allow_empty_denylist:
        raise EmptyDenylistError(
            "REDACT_PAGE_IDS is empty; set it or pass allow_empty_denylist explicitly"
        )

    rows: list[HandbookPage] = []
    denied = 0
    for page in fetched:
        if page.page_id in denylist:
            denied += 1
            continue
        title = redactor.redact(page.name)
        body = redactor.redact(page.content)
        log_hits(logger, page.page_id, _merge_hits(title.hits, body.hits))
        rows.append(
            HandbookPage(
                page_id=page.page_id,
                parent_id=page.parent_id,
                position=len(rows),
                depth=page.depth,
                title=title.text,
                url=page_url(workspace_id, doc_id, page.page_id),
                date_edited_raw=page.date_edited,
                date_created_raw=page.date_created,
                revision_date_iso=revision_date_iso(
                    page.date_edited if page.date_edited is not None else page.date_created
                ),
                content_md=body.text,
                content_hash=_content_hash(title.text, body.text),
            )
        )

    if not rows:
        raise EmptyHandbookError("no handbook page left after denylist and archived filters")

    # First-run path: every page is new. The comparison with `previous` comes in Task 3.
    _ = (previous, versions_match)
    return HandbookSyncResult(
        pages=tuple(rows),
        seen=len(fetched),
        processed=len(rows),
        unchanged=0,
        removed=0,
        denied=denied,
        skipped_archived=skipped_archived,
    )
