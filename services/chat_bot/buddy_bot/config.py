"""Environment-driven settings for the chat bot.

Every value comes from the process environment (Docker ``--env-file`` or the host
environment); no env file is read here. Errors name variables, never values.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    @field_validator("allowed_users", mode="before")
    @classmethod
    def _parse_allowed_users(cls, value: Any) -> Any:
        return _split_csv(value)

    @model_validator(mode="after")
    def _check_backend(self) -> BotSettings:
        # Names only: no value of a secret may reach the error text.
        if self.llm_backend == "api" and self.anthropic_api_key is None:
            raise ValueError("LLM_BACKEND=api requires: ANTHROPIC_API_KEY")
        return self
