"""Environment-driven settings for the chat bot.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. Errors name variables, never values.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_COLLECTION_NAME = re.compile(r"[A-Za-z0-9_-]+")
_TRUE_VALUES = frozenset({"1", "true", "yes"})
_TRACING_VARIABLES = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")
_MIN_THREAD_KEY_SECRET_LENGTH = 32


def _require(mode: str, *, applies: bool, needs: Sequence[tuple[str, object | None]]) -> None:
    """Raise naming every variable ``mode`` needs that is unset; values are never read out."""
    missing = [name for name, value in needs if applies and value is None]
    if missing:
        raise ValueError(f"{mode} requires: {', '.join(missing)}")


def _split_csv(value: Any) -> Any:
    """Split a comma-separated string into stripped, lowercased, non-blank items."""
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    return value


class BotSettings(BaseSettings):
    """Bot configuration, keyed by upper-case env vars (ALLOWED_USERS, LLM_BACKEND, ...)."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    allowed_users: Annotated[frozenset[str], NoDecode]
    llm_backend: Literal["meridian", "api", "vertex"]
    llm_base_url: str | None = None
    anthropic_api_key: SecretStr | None = None
    meridian_api_key: SecretStr | None = None
    vertex_project: str | None = None
    vertex_region: str | None = None
    reformulate_model: str = "claude-haiku-5-5"
    answer_model: str = "claude-sonnet-5-5"
    llm_timeout_seconds: float = Field(default=60, gt=0)
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    memory_turns: int = Field(default=3, ge=1, le=10)
    thread_key_secret: SecretStr
    memory_collection: str = "thread_memory"
    google_cloud_project: str | None = None
    mcp_url: str
    deploy_env: Literal["local", "production"] = "production"
    mcp_auth: Literal["google_id_token", "none"] = "google_id_token"
    mcp_audience: str | None = None
    intake: Literal["pubsub", "http"]
    pubsub_subscription: str | None = None
    chat_jwt_audience: str | None = None
    chat_jwt_issuer_email: str | None = None
    bot_host: str = "0.0.0.0"
    port: int = 8080
    video_thumbnail_url: str
    help_command_id: str | None = None
    run_deadline_seconds: float = Field(default=120, gt=0)
    chat_api: Literal["google", "recording"] = "google"
    chat_record_path: Path | None = None

    @field_validator("allowed_users", mode="before")
    @classmethod
    def _parse_allowed_users(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("thread_key_secret")
    @classmethod
    def _check_thread_key_secret(cls, value: SecretStr) -> SecretStr:
        # The value is not echoed: SecretStr and hide_input_in_errors keep it out of the error.
        if len(value.get_secret_value()) < _MIN_THREAD_KEY_SECRET_LENGTH:
            raise ValueError(
                f"THREAD_KEY_SECRET must be at least {_MIN_THREAD_KEY_SECRET_LENGTH} characters"
            )
        return value

    @field_validator("video_thumbnail_url")
    @classmethod
    def _check_video_thumbnail_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("VIDEO_THUMBNAIL_URL must start with https://")
        return value

    @field_validator("memory_collection")
    @classmethod
    def _check_memory_collection(cls, value: str) -> str:
        if not _COLLECTION_NAME.fullmatch(value):
            raise ValueError("MEMORY_COLLECTION must match [A-Za-z0-9_-]+")
        return value

    @model_validator(mode="after")
    def _check_startup_guards(self) -> BotSettings:
        # Names only: no value of a secret may reach the error text.
        if self.llm_backend == "vertex":
            raise ValueError("LLM_BACKEND=vertex is not enabled")
        if not self.allowed_users:
            raise ValueError("ALLOWED_USERS must list at least one user")
        # BOT-08 / D1a: Meridian runs on Joshua's Claude Max credentials, so one person only.
        if self.llm_backend == "meridian" and len(self.allowed_users) > 1:
            raise ValueError("LLM_BACKEND=meridian requires exactly one ALLOWED_USERS entry (D1a)")
        _require(
            "LLM_BACKEND=meridian",
            applies=self.llm_backend == "meridian",
            needs=(("LLM_BASE_URL", self.llm_base_url),),
        )
        _require(
            "LLM_BACKEND=api",
            applies=self.llm_backend == "api",
            needs=(("ANTHROPIC_API_KEY", self.anthropic_api_key),),
        )
        # Mirror of the MCP server rule (Phase 4, D-13): DEPLOY_ENV defaults to production and
        # only an explicit local unlocks the local-only knobs; K_SERVICE (Cloud Run) forces
        # production, so no host can run them by accident.
        if self.deploy_env == "local" and "K_SERVICE" in os.environ:
            raise ValueError(
                "DEPLOY_ENV=local is refused when K_SERVICE is set (deployed on Cloud Run)"
            )
        if self.mcp_auth == "none" and self.deploy_env != "local":
            raise ValueError("MCP_AUTH=none requires DEPLOY_ENV=local")
        if self.chat_api == "recording" and self.deploy_env != "local":
            raise ValueError("CHAT_API=recording requires DEPLOY_ENV=local")
        _require(
            "CHAT_API=recording",
            applies=self.chat_api == "recording",
            needs=(("CHAT_RECORD_PATH", self.chat_record_path),),
        )
        _require(
            "MCP_AUTH=google_id_token",
            applies=self.mcp_auth == "google_id_token",
            needs=(("MCP_AUDIENCE", self.mcp_audience),),
        )
        _require(
            "INTAKE=pubsub",
            applies=self.intake == "pubsub",
            needs=(("PUBSUB_SUBSCRIPTION", self.pubsub_subscription),),
        )
        _require(
            "INTAKE=http",
            applies=self.intake == "http",
            needs=(
                ("CHAT_JWT_AUDIENCE", self.chat_jwt_audience),
                ("CHAT_JWT_ISSUER_EMAIL", self.chat_jwt_issuer_email),
            ),
        )
        if any(
            os.environ.get(name, "").strip().lower() in _TRUE_VALUES for name in _TRACING_VARIABLES
        ):
            raise ValueError("LANGSMITH_TRACING must be false: prompts must not leave the host")
        return self
