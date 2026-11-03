"""Environment-driven settings for the sync job.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. Tokens are ``SecretStr`` so they never appear in
``repr``, ``str``, JSON dumps or validation errors.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_DOC_ID_RE = re.compile(r"^[A-Za-z0-9-]+$")


class ConfigError(Exception):
    """Raised when a required setting is missing. The message names variables, never values."""


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

    clickup_token: SecretStr | None = None
    clickup_workspace_id: int | None = None
    clickup_doc_id: str
    clickup_base_url: str = "https://api.clickup.com"
    redact_page_ids: Annotated[frozenset[str], NoDecode] = frozenset()
    redact_email_allow_domains: Annotated[frozenset[str], NoDecode] = frozenset({"digitiamo.com"})
    guides_repo_url: str
    guides_repo_token: SecretStr | None = None
    guides_branch: str = "master"
    guides_checkout_dir: Path
    artifact_dir: Path
    http_timeout_s: float = 30.0

    @field_validator("redact_page_ids", mode="before")
    @classmethod
    def _parse_page_ids(cls, value: Any) -> Any:
        return _split_csv(value)

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

    @field_validator("clickup_doc_id")
    @classmethod
    def _check_doc_id(cls, value: str) -> str:
        if not _DOC_ID_RE.fullmatch(value):
            raise ValueError("clickup_doc_id must match [A-Za-z0-9-]+")
        return value

    def require_clickup(self) -> tuple[SecretStr, int]:
        """Return ``(token, workspace_id)`` or raise ``ConfigError`` naming what is missing."""
        missing: list[str] = []
        if self.clickup_token is None:
            missing.append("CLICKUP_TOKEN")
        if self.clickup_workspace_id is None:
            missing.append("CLICKUP_WORKSPACE_ID")
        if self.clickup_token is None or self.clickup_workspace_id is None:
            raise ConfigError("missing required environment variables: " + ", ".join(missing))
        return self.clickup_token, self.clickup_workspace_id
