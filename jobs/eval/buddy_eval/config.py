"""Environment-driven settings for the evaluation job.

Every value comes from the process environment (Docker ``--env-file`` or the host environment);
no env file is read here. Errors name variables, never values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TRUE_VALUES: Final = frozenset({"1", "true", "yes"})
_TRACING_VARIABLES: Final = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")
_LOCAL_MLFLOW_HOSTS: Final = frozenset({"mlflow", "localhost", "127.0.0.1"})


class EvalSettings(BaseSettings):
    """Evaluation configuration, keyed by upper-case env vars (LLM_BACKEND, JUDGE_MODEL, ...)."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    llm_backend: Literal["meridian", "api", "vertex"] = "meridian"
    llm_base_url: str = "http://meridian:3456"
    anthropic_api_key: SecretStr | None = None
    meridian_api_key: SecretStr | None = None
    llm_timeout_seconds: float = Field(default=60, gt=0)
    reformulate_model: str = "claude-haiku-5-5"
    answer_model: str = "claude-sonnet-5-5"
    judge_model: str = "claude-opus-5-5"
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    mcp_url: str = "http://mcp-server:8000/mcp"
    golden_public_path: Path = Path("/app/jobs/eval/golden/guides.yaml")
    golden_private_path: Path = Path("/private/golden-handbook.yaml")
    private_dir: Path = Path("/private")
    mlflow_tracking_uri: str | None = None
    mlflow_experiment: str = "ai-buddy-eval"
    mlflow_ui_base_url: str = "http://127.0.0.1:5000"
    max_consecutive_errors: int = Field(default=3, ge=1)
    item_pause_seconds: float = Field(default=0.5, ge=0)

    @field_validator("mlflow_tracking_uri")
    @classmethod
    def _tracking_uri_is_local(cls, value: str | None) -> str | None:
        # D-21: traces hold questions and handbook text, so they stay on the host.
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in _LOCAL_MLFLOW_HOSTS:
            raise ValueError(
                "MLFLOW_TRACKING_URI must point at the local MLflow server "
                "(mlflow, localhost or 127.0.0.1)"
            )
        return value

    @model_validator(mode="after")
    def _check_startup_guards(self) -> EvalSettings:
        # Names only: no value of a secret or of a model setting may reach the error text.
        if self.llm_backend == "vertex":
            raise ValueError("LLM_BACKEND=vertex is not enabled")
        if self.llm_backend == "api" and self.anthropic_api_key is None:
            raise ValueError("LLM_BACKEND=api requires: ANTHROPIC_API_KEY")
        # D-08: a model must not grade its own answers (self-preference bias).
        if self.judge_model == self.answer_model:
            raise ValueError("JUDGE_MODEL must differ from ANSWER_MODEL (D-08)")
        if any(
            os.environ.get(name, "").strip().lower() in _TRUE_VALUES for name in _TRACING_VARIABLES
        ):
            raise ValueError("LANGSMITH_TRACING must be false: prompts must not leave the host")
        return self
