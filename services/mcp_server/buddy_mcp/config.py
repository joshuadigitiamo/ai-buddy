"""Environment-driven settings for the MCP server.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. Errors name variables, never values.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_COLLECTION_NAME = re.compile(r"[A-Za-z0-9_-]+")


class McpSettings(BaseSettings):
    """MCP server configuration, keyed by upper-case env vars (ARTIFACT_DIR, GAP_TTL_DAYS, ...)."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    artifact_dir: Path
    guides_web_base: str
    mcp_host: str = "0.0.0.0"
    port: int = 8000
    gap_ttl_days: int = 90
    gap_collection: str = "gaps"

    @field_validator("guides_web_base")
    @classmethod
    def _check_guides_web_base(cls, value: str) -> str:
        # The value is not echoed: hide_input_in_errors keeps it out of the error.
        if not value.startswith("https://"):
            raise ValueError("guides_web_base must start with https://")
        return value.rstrip("/")

    @field_validator("gap_ttl_days")
    @classmethod
    def _check_gap_ttl_days(cls, value: int) -> int:
        if value < 1:
            raise ValueError("gap_ttl_days must be at least 1")
        return value

    @field_validator("gap_collection")
    @classmethod
    def _check_gap_collection(cls, value: str) -> str:
        if not _COLLECTION_NAME.fullmatch(value):
            raise ValueError("gap_collection must match [A-Za-z0-9_-]+")
        return value
