"""One sync run: ClickUp handbook + Guides repo + video map -> one published artifact.

The run is idempotent (D-09, D-10): the logical content is hashed before anything is built,
and an unchanged hash touches no file. A failed build discards its staged file and leaves the
previous artifact in place, so the job can simply be re-run.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime

from buddy_core.index_reader import IndexReader, IndexVersionError, open_index
from buddy_core.index_writer import build_index, compute_content_hash
from buddy_core.models import IndexContent
from buddy_core.store import ArtifactStore
from buddy_sync.chunker import PIPELINE_VERSION
from buddy_sync.clickup import ClickUpClient, flatten_pages
from buddy_sync.config import SyncSettings
from buddy_sync.guides import sync_guides
from buddy_sync.guides_git import GuidesSource
from buddy_sync.guides_index import check_guides_index
from buddy_sync.handbook import EmptyDenylistError, sync_handbook
from buddy_sync.redaction import REDACTION_VERSION, Redactor
from buddy_sync.video_map import resolve_video_links


@dataclass(frozen=True, slots=True)
class SyncReport:
    """Counts and identifiers of one run. It never holds page or Guides content."""

    pages_seen: int
    pages_processed: int
    pages_unchanged: int
    pages_removed: int
    pages_denied: int
    pages_skipped_archived: int
    guides_rebuilt: bool
    guides_commit_sha: str
    chunks: int
    video_links: int
    guides_index_drift: int
    artifact_written: bool
    content_hash: str
    build_id: str | None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def _open_previous(store: ArtifactStore, logger: logging.Logger) -> IndexReader | None:
    """Open the last published artifact; one from another schema major counts as absent."""
    path = store.latest_path()
    if path is None:
        return None
    try:
        return open_index(path)
    except IndexVersionError as exc:
        logger.warning("previous artifact ignored, full rebuild: %s", exc)
        return None


def run_sync(
    settings: SyncSettings,
    *,
    clickup: ClickUpClient,
    guides: GuidesSource,
    store: ArtifactStore,
    redactor: Redactor,
    now: datetime,
    allow_empty_denylist: bool = False,
    strict: bool = False,
    logger: logging.Logger,
) -> SyncReport:
    """Run the whole sync once and return its report."""
    if not settings.redact_page_ids and not allow_empty_denylist:
        raise EmptyDenylistError(
            "REDACT_PAGE_IDS is empty; set it or pass allow_empty_denylist explicitly"
        )

    previous = _open_previous(store, logger)
    try:
        versions_match = (
            previous is not None
            and previous.meta.pipeline_version == PIPELINE_VERSION
            and previous.meta.redaction_version == REDACTION_VERSION
        )
        _token, workspace_id = settings.require_clickup()
        flat, skipped = flatten_pages(clickup.fetch_pages(workspace_id, settings.clickup_doc_id))
        handbook = sync_handbook(
            flat,
            previous=previous.load_handbook() if previous is not None else None,
            versions_match=versions_match,
            denylist=settings.redact_page_ids,
            allow_empty_denylist=allow_empty_denylist,
            redactor=redactor,
            workspace_id=workspace_id,
            doc_id=settings.clickup_doc_id,
            skipped_archived=skipped,
            logger=logger,
        )

        checkout = guides.sync()
        synced = sync_guides(
            checkout,
            previous=previous,
            versions_match=versions_match,
            redactor=redactor,
            logger=logger,
        )
        drift = 0
        if synced.rebuilt:
            videos = resolve_video_links(checkout.path, synced.chunks, logger=logger)
            drift = len(
                check_guides_index(checkout.path, synced.outline, strict=strict, logger=logger)
            )
        else:
            videos = previous.video_links() if previous is not None else {}

        content = IndexContent(
            handbook=handbook.pages,
            chunks=synced.chunks,
            videos=videos,
            source_doc_id=settings.clickup_doc_id,
            guides_commit_sha=checkout.commit_sha,
            pipeline_version=PIPELINE_VERSION,
            redaction_version=REDACTION_VERSION,
        )
        content_hash = compute_content_hash(content)
        unchanged = previous is not None and previous.meta.content_hash == content_hash
    finally:
        if previous is not None:
            previous.close()

    build_id: str | None = None
    if not unchanged:
        staged = store.staging_path()
        try:
            meta = build_index(content, staged, now=now)
            store.publish(staged, meta)
        except Exception:
            store.discard(staged)
            raise
        build_id = meta.build_id
        logger.info("artifact published build_id=%s", build_id)
    else:
        logger.info("content unchanged; no artifact written")

    return SyncReport(
        pages_seen=handbook.seen,
        pages_processed=handbook.processed,
        pages_unchanged=handbook.unchanged,
        pages_removed=handbook.removed,
        pages_denied=handbook.denied,
        pages_skipped_archived=handbook.skipped_archived,
        guides_rebuilt=synced.rebuilt,
        guides_commit_sha=checkout.commit_sha,
        chunks=len(synced.chunks),
        video_links=len(videos),
        guides_index_drift=drift,
        artifact_written=not unchanged,
        content_hash=content_hash,
        build_id=build_id,
    )
