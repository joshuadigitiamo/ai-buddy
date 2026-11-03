"""Command line for the sync job: ``python -m buddy_sync <run|guides-index|search>``.

This is the only place real adapters (git, the local artifact directory) are built. Output
is limited to counts, ids, redacted titles and source locations; page content and matched
secrets are never printed (SYNC-03).
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from buddy_core.index_reader import IndexFormatError, open_index
from buddy_core.models import video_link
from buddy_core.store import INDEX_NAME, LocalDirArtifactStore
from buddy_sync.chunker import heading_outline
from buddy_sync.config import SyncSettings
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_git import GitGuidesSource, GuidesGitError
from buddy_sync.guides_index import GuidesIndexDriftError, write_guides_index
from buddy_sync.handbook import EmptyDenylistError, EmptyHandbookError
from buddy_sync.handbook_files import HandbookFilesError
from buddy_sync.pipeline import run_sync
from buddy_sync.redaction import Redactor
from buddy_sync.video_map import VideoMapError

LOGGER_NAME: Final = "buddy_sync"
LOG_FORMAT: Final = "%(levelname)s %(name)s %(message)s"
DEFAULT_ARTIFACT_DIR: Final = "artifacts"
DEFAULT_SEARCH_LIMIT: Final = 5

# Failures that end a command with one ERROR line and exit code 1.
_EXPECTED_ERRORS: Final = (
    EmptyDenylistError,
    EmptyHandbookError,
    HandbookFilesError,
    GuidesGitError,
    VideoMapError,
    GuidesIndexDriftError,
    IndexFormatError,
    OSError,
    sqlite3.Error,
)

NowFn = Callable[[], datetime]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddy_sync", description="AI Buddy content sync job")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run", help="sync the local handbook folder and the Guides repo, publish index.db"
    )
    run.add_argument("--strict", action="store_true", help="fail when GUIDES_INDEX.md drifts")
    run.add_argument(
        "--allow-empty-denylist",
        action="store_true",
        help="run although REDACT_PAGE_FILES is empty",
    )

    index = sub.add_parser("guides-index", help="write GUIDES_INDEX.md into a Guides checkout")
    index.add_argument("--checkout", required=True, type=Path, help="Guides checkout directory")

    search = sub.add_parser("search", help="keyword search over the published Guides chunks")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=DEFAULT_SEARCH_LIMIT)
    search.add_argument("--artifact-dir", type=Path, default=None)
    return parser


def _describe_validation_error(exc: ValidationError) -> str:
    """Name the offending variables only; error inputs could carry secret values."""
    names = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err["loc"]})
    return "invalid or missing environment variables: " + ", ".join(names or ["(unknown)"])


def _run(args: argparse.Namespace, logger: logging.Logger, now: NowFn) -> int:
    settings = SyncSettings()
    guides = GitGuidesSource(
        url=settings.guides_repo_url,
        branch=settings.guides_branch,
        checkout_dir=settings.guides_checkout_dir,
        token=None,
    )
    report = run_sync(
        settings,
        guides=guides,
        store=LocalDirArtifactStore(settings.artifact_dir),
        redactor=Redactor.from_settings(settings),
        now=now(),
        allow_empty_denylist=args.allow_empty_denylist,
        strict=args.strict,
        logger=logger,
    )
    print(report.to_json())
    return 0


def _guides_index(checkout: Path) -> int:
    outline = {
        relpath: heading_outline((checkout / relpath).read_text(encoding="utf-8"))
        for relpath in select_guide_files(checkout)
    }
    print(write_guides_index(checkout, outline))
    return 0


def _search(query: str, limit: int, artifact_dir: Path | None) -> int:
    root = artifact_dir or Path(os.environ.get("ARTIFACT_DIR") or DEFAULT_ARTIFACT_DIR)
    with open_index(root / INDEX_NAME) as reader:
        for hit in reader.search_guides(query, limit):
            chunk = hit.chunk
            link = video_link(hit.video) if hit.video is not None else "-"
            print(
                f"{chunk.file}:{chunk.line_start}-{chunk.line_end}  "
                f"{chunk.h2} > {chunk.h3 or '(intro)'}  {link}"
            )
    return 0


def _configure_logging(logger: logging.Logger) -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return handler


def main(
    argv: Sequence[str] | None = None,
    *,
    now: NowFn | None = None,
) -> int:
    """Run one subcommand; return 0 on success, 1 on a reported failure, 2 on bad arguments."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    logger = logging.getLogger(LOGGER_NAME)
    handler = _configure_logging(logger)
    clock: NowFn = now or (lambda: datetime.now(UTC))
    try:
        match args.command:
            case "run":
                return _run(args, logger, clock)
            case "guides-index":
                return _guides_index(args.checkout)
            case _:
                return _search(args.query, args.limit, args.artifact_dir)
    except ValidationError as exc:
        logger.error("%s", _describe_validation_error(exc))
        return 1
    except _EXPECTED_ERRORS as exc:
        logger.error("%s: %s", type(exc).__name__, exc)
        return 1
    finally:
        logger.removeHandler(handler)
