"""Command line for the sync job: ``python -m buddy_sync <subcommand>``.

Subcommands: ``run``, ``guides-index``, ``search``, ``publish`` and ``upload-videos``.

This is the only place real adapters (git, the local artifact directory, the GCS bucket) are
built. Output is limited to counts, ids, redacted titles and source locations; page content and
matched secrets are never printed (SYNC-03).
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from buddy_core.gcs_bucket import BucketError, GcsBucket
from buddy_core.index_reader import IndexFormatError, open_index
from buddy_core.models import video_link
from buddy_core.store import (
    INDEX_NAME,
    ArtifactIntegrityError,
    BucketPort,
    GcsArtifactStore,
    LocalDirArtifactStore,
    check_bucket_name,
    check_object_prefix,
)
from buddy_sync.chunker import heading_outline
from buddy_sync.config import SyncSettings
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_git import GitGuidesSource, GuidesGitError
from buddy_sync.guides_index import GuidesIndexDriftError, write_guides_index
from buddy_sync.handbook import EmptyDenylistError, EmptyHandbookError
from buddy_sync.handbook_files import HandbookFilesError
from buddy_sync.pipeline import run_sync
from buddy_sync.publish import PublishError, publish_index
from buddy_sync.redaction import Redactor
from buddy_sync.video_map import README_NAME, VideoMapError, parse_readme_videos
from buddy_sync.video_upload import VideoUploadError, upload_videos

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
    VideoUploadError,
    GuidesIndexDriftError,
    IndexFormatError,
    PublishError,
    ArtifactIntegrityError,
    BucketError,
    OSError,
    sqlite3.Error,
)

NowFn = Callable[[], datetime]
BucketFactory = Callable[[str], BucketPort]


class PublishSettings(BaseSettings):
    """Environment of ``publish``: where the local index is and which bucket receives it.

    ADC for the bucket comes from GOOGLE_APPLICATION_CREDENTIALS and is read by the storage
    client, never here. Errors name variables, never values.
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    artifact_dir: Path
    artifact_bucket: str
    artifact_prefix: str = ""

    @field_validator("artifact_bucket")
    @classmethod
    def _check_bucket(cls, value: str) -> str:
        return check_bucket_name(value)

    @field_validator("artifact_prefix")
    @classmethod
    def _check_prefix(cls, value: str) -> str:
        return check_object_prefix(value)


class VideoUploadSettings(BaseSettings):
    """Environment of ``upload-videos``: the private bucket that holds the Guides videos (D-16).

    ADC comes from GOOGLE_APPLICATION_CREDENTIALS, read by the storage client. Errors name
    variables, never values.
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    video_bucket: str

    @field_validator("video_bucket")
    @classmethod
    def _check_bucket(cls, value: str) -> str:
        return check_bucket_name(value)


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

    sub.add_parser("publish", help="publish the local index.db to the private bucket (D-06)")

    videos = sub.add_parser(
        "upload-videos", help="upload the Guides README videos to the private bucket (D-16, D-17)"
    )
    videos.add_argument("--guides-dir", required=True, type=Path, help="Guides tree with README.md")
    videos.add_argument(
        "--videos-dir",
        required=True,
        action="append",
        type=Path,
        help="directory searched recursively for the mp4 files; repeatable",
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


def _publish(bucket_factory: BucketFactory) -> int:
    settings = PublishSettings()
    bucket = bucket_factory(settings.artifact_bucket)
    with tempfile.TemporaryDirectory(prefix="buddy-publish-") as cache:
        store = GcsArtifactStore(bucket, settings.artifact_prefix, Path(cache))
        result = publish_index(settings.artifact_dir, store, bucket)
    print(f"{result.status} build_id={result.build_id}")
    return 0


def _upload_videos(
    guides_dir: Path, video_dirs: Sequence[Path], bucket_factory: BucketFactory
) -> int:
    settings = VideoUploadSettings()
    readme = (guides_dir / README_NAME).read_text(encoding="utf-8")
    report = upload_videos(
        parse_readme_videos(readme), video_dirs, bucket_factory(settings.video_bucket)
    )
    print(f"uploaded={report.uploaded} unchanged={report.unchanged}")
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
    bucket_factory: BucketFactory | None = None,
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
            case "publish":
                return _publish(bucket_factory or GcsBucket)
            case "upload-videos":
                return _upload_videos(args.guides_dir, args.videos_dir, bucket_factory or GcsBucket)
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
