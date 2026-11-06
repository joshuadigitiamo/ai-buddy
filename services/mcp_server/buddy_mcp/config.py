"""Environment-driven settings for the MCP server.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. Errors name variables, never values.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    """MCP server configuration, keyed by ARTIFACT_DIR, GUIDES_WEB_BASE, MCP_HOST and PORT."""

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

    @field_validator("guides_web_base")
    @classmethod
    def _check_guides_web_base(cls, value: str) -> str:
        # The value is not echoed: hide_input_in_errors keeps it out of the error.
        if not value.startswith("https://"):
            raise ValueError("guides_web_base must start with https://")
        return value.rstrip("/")
