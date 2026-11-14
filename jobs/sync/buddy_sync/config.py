"""Environment-driven settings for the sync job.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. No variable is a secret (D-25, D-27): the handbook
is a local folder and the Guides repo is read from a local checkout.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from buddy_core.store import check_bucket_name
from buddy_sync.handbook_files import PAGE_FILE_RE

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def _split_csv(value: Any) -> Any:
    """Split a comma-separated string into stripped, non-blank items."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class SyncSettings(BaseSettings):
    """All sync-job configuration, keyed by the variables listed in ``.env.example``."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    handbook_dir: Path
    redact_page_files: Annotated[frozenset[str], NoDecode] = frozenset()
    redact_email_allow_domains: Annotated[frozenset[str], NoDecode] = frozenset({"digitiamo.com"})
    guides_repo_url: str
    guides_branch: str = "master"
    guides_checkout_dir: Path
    artifact_dir: Path
    video_bucket: str | None = None

    @field_validator("video_bucket")
    @classmethod
    def _check_video_bucket(cls, value: str | None) -> str | None:
        return None if value is None else check_bucket_name(value)

    @field_validator("redact_page_files", mode="before")
    @classmethod
    def _parse_page_files(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("redact_page_files")
    @classmethod
    def _check_page_files(cls, value: frozenset[str]) -> frozenset[str]:
        # Entries are bare page-file names, never paths (D-25, T-01-40). The value is not
        # echoed: hide_input_in_errors keeps it out of the error.
        if any(PAGE_FILE_RE.fullmatch(item) is None for item in value):
            raise ValueError("redact_page_files entries must be bare page file names ending .md")
        return value

    @field_validator("redact_email_allow_domains", mode="before")
    @classmethod
    def _parse_domains(cls, value: Any) -> Any:
        items = _split_csv(value)
        if isinstance(items, list):
            return [item.lower() for item in items]
        return items

    @field_validator("guides_branch")
    @classmethod
    def _check_branch(cls, value: str) -> str:
        # The branch reaches git argv: reject anything option-like or exotic (T-01-14).
        if value.startswith("-") or not _BRANCH_RE.fullmatch(value):
            raise ValueError("guides_branch must match [A-Za-z0-9._/-]+ and not start with '-'")
        return value
