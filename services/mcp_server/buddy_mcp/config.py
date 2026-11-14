"""Environment-driven settings for the MCP server.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. Errors name variables, never values.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_COLLECTION_NAME = re.compile(r"[A-Za-z0-9_-]+")
_LOOPBACK_PREFIXES = ("http://localhost", "http://127.0.0.1")
# A bare lowercase DNS hostname: labels of 1-63 characters (a-z, 0-9, inner hyphens) joined by
# single dots. No scheme, port, path, wildcard, underscore or empty label.
_HOSTNAME = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
)


def _split_csv(value: Any) -> Any:
    """Split a comma-separated string into stripped, lowercased, non-blank items."""
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    return value


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
    google_cloud_project: str | None = None
    mcp_host: str = "0.0.0.0"
    port: int = 8000
    gap_ttl_days: int = 90
    gap_collection: str = "gaps"
    auth_mode: Literal["on", "off"] = "on"
    mcp_public_base_url: str | None = None
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    oauth_jwt_signing_key: SecretStr | None = None
    allowed_email_domain: str = "digitiamo.com"
    bot_sa_emails: Annotated[frozenset[str], NoDecode] = frozenset()
    mcp_allowed_hosts: Annotated[frozenset[str], NoDecode] = frozenset()
    oauth_storage: Literal["memory", "firestore"] = "memory"
    oauth_storage_encryption_key: SecretStr | None = None
    oauth_collection: str = "oauth_state"
    rate_limit_rps: float = Field(default=5.0, gt=0)
    rate_limit_burst: int = Field(default=30, ge=1)

    @field_validator("bot_sa_emails", mode="before")
    @classmethod
    def _parse_bot_sa_emails(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("mcp_allowed_hosts", mode="before")
    @classmethod
    def _parse_mcp_allowed_hosts(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("mcp_allowed_hosts")
    @classmethod
    def _check_mcp_allowed_hosts(cls, value: frozenset[str]) -> frozenset[str]:
        # The value is not echoed: hide_input_in_errors keeps it out of the error.
        if not all(_HOSTNAME.fullmatch(host) for host in value):
            raise ValueError("MCP_ALLOWED_HOSTS entries must be bare hostnames")
        return value

    @field_validator("mcp_public_base_url")
    @classmethod
    def _check_mcp_public_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # The value is not echoed: hide_input_in_errors keeps it out of the error.
        if not (value.startswith("https://") or value.startswith(_LOOPBACK_PREFIXES)):
            raise ValueError(
                "mcp_public_base_url must start with https:// (http only for localhost)"
            )
        return value.rstrip("/")

    @field_validator("allowed_email_domain")
    @classmethod
    def _normalize_allowed_email_domain(cls, value: str) -> str:
        domain = value.strip().lower()
        if not domain or "@" in domain:
            raise ValueError("allowed_email_domain must be a bare domain name")
        return domain

    @model_validator(mode="after")
    def _check_auth_and_storage(self) -> McpSettings:
        # Names only: no value of a secret may reach the error text.
        # D-13: the guard lives here so every entry point (server process, tests) hits it.
        # K_SERVICE is Cloud Run's marker; a different host in Phase 4 must add its own (A6).
        if self.auth_mode == "off" and "K_SERVICE" in os.environ:
            raise ValueError(
                "AUTH_MODE=off is refused when K_SERVICE is set (deployed on Cloud Run)"
            )
        if self.auth_mode == "on":
            missing = [
                name
                for name, value in (
                    ("MCP_PUBLIC_BASE_URL", self.mcp_public_base_url),
                    ("GOOGLE_CLIENT_ID", self.google_client_id),
                    ("GOOGLE_CLIENT_SECRET", self.google_client_secret),
                    ("OAUTH_JWT_SIGNING_KEY", self.oauth_jwt_signing_key),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"AUTH_MODE=on requires: {', '.join(missing)}")
        if self.oauth_storage == "firestore" and self.oauth_storage_encryption_key is None:
            raise ValueError("OAUTH_STORAGE=firestore requires OAUTH_STORAGE_ENCRYPTION_KEY")
        return self

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
