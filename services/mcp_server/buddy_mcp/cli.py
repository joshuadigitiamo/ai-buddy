"""Command line for the MCP server: ``python -m buddy_mcp``.

This is the only place real adapters (Firestore gap log, OAuth state store, Google auth) are
built; everything else takes them as arguments. Output is limited to counts, ids and modes,
never question text, page content or secrets (MCP-01, ASVS V13).
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from collections.abc import Callable, Sequence
from typing import Any, Final

from fastmcp import FastMCP
from google.cloud import firestore
from pydantic import ValidationError

from buddy_core.gcs_bucket import BucketError, GcsBucket
from buddy_core.index_reader import IndexFormatError
from buddy_mcp.auth import build_auth
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import FirestoreGapLog
from buddy_mcp.oauth_storage import OAuthStorageError, build_oauth_storage
from buddy_mcp.server import build_server, host_kwargs
from buddy_mcp.snapshot import (
    BucketFactory,
    SnapshotError,
    artifact_store_from_settings,
    load_snapshot,
    resolve_index_path,
)

LOGGER_NAME: Final = "buddy_mcp"
LOG_FORMAT: Final = "%(levelname)s %(name)s %(message)s"

# Failures that end startup with one ERROR line and exit code 1.
_EXPECTED_ERRORS: Final = (
    SnapshotError,
    BucketError,
    IndexFormatError,
    OAuthStorageError,
    OSError,
    sqlite3.Error,
)

ServeFn = Callable[[FastMCP, McpSettings], None]


def _describe_validation_error(exc: ValidationError) -> str:
    """Name the offending variables only; error inputs could carry secret values.

    Cross-field validators carry no field location: their message names variables, not values.
    """
    names = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err["loc"]})
    notes = sorted(
        {err["msg"].removeprefix("Value error, ") for err in exc.errors() if not err["loc"]}
    )
    return "invalid or missing configuration: " + "; ".join([*names, *notes] or ["(unknown)"])


def _serve_http(mcp: FastMCP, settings: McpSettings) -> None:
    """Run the stateless JSON HTTP server with the same Host/Origin guard as build_app."""
    options: dict[str, Any] = dict(stateless_http=True, json_response=True, **host_kwargs(settings))
    mcp.run(transport="http", host=settings.mcp_host, port=settings.port, **options)


def _configure_logging(logger: logging.Logger) -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return handler


def main(
    argv: Sequence[str] | None = None,
    *,
    serve: ServeFn | None = None,
    bucket_factory: BucketFactory | None = None,
) -> int:
    """Build every adapter from the environment and serve; return 0 or 1 on a reported failure."""
    del argv  # no command-line options: every setting comes from the environment
    logger = logging.getLogger(LOGGER_NAME)
    handler = _configure_logging(logger)
    try:
        return _run(logger, serve or _serve_http, bucket_factory or GcsBucket)
    except ValidationError as exc:
        logger.error("%s", _describe_validation_error(exc))
        return 1
    except _EXPECTED_ERRORS as exc:
        logger.error("%s: %s", type(exc).__name__, exc)
        return 1
    finally:
        logger.removeHandler(handler)


def _run(logger: logging.Logger, serve: ServeFn, bucket_factory: BucketFactory) -> int:
    settings = McpSettings()
    project = settings.google_cloud_project
    if not project:
        logger.error("missing environment variable: GOOGLE_CLOUD_PROJECT")
        return 1

    # GcsBucket builds its client on first use, so a local run makes no network call.
    store = artifact_store_from_settings(settings, bucket_factory=bucket_factory)
    snapshot = load_snapshot(resolve_index_path(store))
    try:
        # The Firestore client is built on the first gap write, inside the server's event loop,
        # so startup makes no network call.
        gaplog = FirestoreGapLog(
            lambda: firestore.AsyncClient(project=project), collection=settings.gap_collection
        )
        # With auth off the proxy is never built, so no Firestore OAuth store is either.
        storage_kind = settings.oauth_storage if settings.auth_mode == "on" else "memory"
        encryption_key = settings.oauth_storage_encryption_key
        storage = build_oauth_storage(
            storage_kind,
            project=project,
            encryption_key=encryption_key.get_secret_value() if encryption_key else None,
            collection=settings.oauth_collection,
        )
        auth = build_auth(settings, storage=storage)
        mcp = build_server(settings, snapshot=snapshot, gaplog=gaplog, auth=auth)
        logger.info(
            "serving %d handbook pages, %d guides sections, build %s, auth %s",
            len(snapshot.pages),
            len(snapshot.chunks),
            snapshot.meta.build_id,
            settings.auth_mode,
        )
        serve(mcp, settings)
    finally:
        snapshot.reader.close()
        snapshot.handbook_index.close()
    return 0
