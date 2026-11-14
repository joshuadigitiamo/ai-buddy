"""BotSettings guards: Meridian single user, vertex off, conditional needs, tracing, secrets."""

import pytest
from pydantic import ValidationError

from buddy_bot.config import BotSettings

_ENV_VARIABLES = (
    "ALLOWED_USERS",
    "LLM_BACKEND",
    "LLM_BASE_URL",
    "ANTHROPIC_API_KEY",
    "MERIDIAN_API_KEY",
    "VERTEX_PROJECT",
    "VERTEX_REGION",
    "REFORMULATE_MODEL",
    "ANSWER_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "CONFIDENCE_THRESHOLD",
    "MEMORY_TURNS",
    "THREAD_KEY_SECRET",
    "MEMORY_COLLECTION",
    "GOOGLE_CLOUD_PROJECT",
    "MCP_URL",
    "MCP_AUTH",
    "MCP_AUDIENCE",
    "INTAKE",
    "PUBSUB_SUBSCRIPTION",
    "CHAT_JWT_AUDIENCE",
    "CHAT_JWT_ISSUER_EMAIL",
    "BOT_HOST",
    "PORT",
    "VIDEO_THUMBNAIL_URL",
    "HELP_COMMAND_ID",
    "RUN_DEADLINE_SECONDS",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING_V2",
    "K_SERVICE",
    "DEPLOY_ENV",
    "CHAT_API",
    "CHAT_RECORD_PATH",
)

SENTINEL_ANTHROPIC = "sentinella-segreto-anthropic"
SENTINEL_MERIDIAN = "sentinella-segreto-meridian"
SENTINEL_THREAD = "sentinella-segreto-thread-" + "x" * 14
SENTINEL_THREAD_SHORT = "sentinella-segreto-" + "x" * 12


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """run-unit-tests.sh loads an env file into the container; start from nothing."""
    for name in _ENV_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def settings_env(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    """Set a valid api-backend environment; an override of None removes the variable."""
    values: dict[str, str | None] = {
        "ALLOWED_USERS": "users/111111111111111111111",
        "LLM_BACKEND": "api",
        "ANTHROPIC_API_KEY": SENTINEL_ANTHROPIC,
        "MERIDIAN_API_KEY": SENTINEL_MERIDIAN,
        "THREAD_KEY_SECRET": SENTINEL_THREAD,
        "MCP_URL": "http://mcp.invalid/mcp",
        "MCP_AUTH": "none",
        "DEPLOY_ENV": "local",
        "INTAKE": "pubsub",
        "PUBSUB_SUBSCRIPTION": "projects/demo-ai-buddy/subscriptions/chat",
        "VIDEO_THUMBNAIL_URL": "https://example.invalid/thumb.png",
    }
    values.update(overrides)
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def load(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> BotSettings:
    settings_env(monkeypatch, **overrides)
    return BotSettings()


def refusal(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> str:
    """The text of the error BotSettings raises for this environment."""
    settings_env(monkeypatch, **overrides)
    with pytest.raises(ValidationError) as caught:
        BotSettings()
    return str(caught.value)


MERIDIAN = {"LLM_BACKEND": "meridian", "LLM_BASE_URL": "http://meridian:3456"}


# --- BOT-08: one person on Meridian -------------------------------------------------------


def test_meridian_with_two_users_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    text = refusal(monkeypatch, ALLOWED_USERS="users/1,users/2", **MERIDIAN)

    assert "ALLOWED_USERS" in text
    assert "LLM_BACKEND=meridian requires exactly one ALLOWED_USERS entry" in text


def test_duplicate_entries_count_once(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, ALLOWED_USERS="users/1, USERS/1 ,users/1", **MERIDIAN)

    assert settings.allowed_users == frozenset({"users/1"})


def test_api_backend_allows_two_users(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, ALLOWED_USERS="users/1,users/2")

    assert settings.allowed_users == frozenset({"users/1", "users/2"})


def test_blank_allowlist_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "ALLOWED_USERS must list at least one user" in refusal(monkeypatch, ALLOWED_USERS=" , ")


def test_missing_allowlist_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "allowed_users" in refusal(monkeypatch, ALLOWED_USERS=None)


# --- BOT-07: vertex configured, not enabled ------------------------------------------------


def test_vertex_is_not_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    text = refusal(
        monkeypatch,
        LLM_BACKEND="vertex",
        VERTEX_PROJECT="demo-ai-buddy",
        VERTEX_REGION="europe-west1",
    )

    assert "not enabled" in text


# --- requirements that depend on the chosen mode -------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "names"),
    [
        ({"LLM_BACKEND": "meridian"}, ["LLM_BASE_URL"]),
        ({"ANTHROPIC_API_KEY": None}, ["ANTHROPIC_API_KEY"]),
        ({"MCP_AUTH": "google_id_token"}, ["MCP_AUDIENCE"]),
        ({"PUBSUB_SUBSCRIPTION": None}, ["PUBSUB_SUBSCRIPTION"]),
        (
            {"INTAKE": "http", "PUBSUB_SUBSCRIPTION": None},
            ["CHAT_JWT_AUDIENCE", "CHAT_JWT_ISSUER_EMAIL"],
        ),
    ],
)
def test_missing_mode_requirements_are_named(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str | None], names: list[str]
) -> None:
    text = refusal(monkeypatch, **overrides)

    for name in names:
        assert name in text


def test_complete_meridian_and_http_environment_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(
        monkeypatch,
        MCP_AUTH="google_id_token",
        MCP_AUDIENCE="https://mcp.invalid",
        INTAKE="http",
        CHAT_JWT_AUDIENCE="https://bot.invalid/chat",
        CHAT_JWT_ISSUER_EMAIL="chat@system.gserviceaccount.com",
        **MERIDIAN,
    )

    assert settings.llm_backend == "meridian"
    assert settings.intake == "http"
    assert settings.mcp_audience == "https://mcp.invalid"


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch)

    assert (settings.reformulate_model, settings.answer_model) == (
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
    )
    assert settings.memory_turns == 3
    assert settings.confidence_threshold == 0.7
    assert settings.run_deadline_seconds == 120
    assert settings.llm_timeout_seconds == 60
    assert settings.memory_collection == "thread_memory"
    assert settings.port == 8080


# --- T-03-18, T-04-09, T-04-10: local-only knobs need an explicit DEPLOY_ENV=local ---------


def test_deploy_env_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, DEPLOY_ENV=None, MCP_AUTH="google_id_token", MCP_AUDIENCE="x")

    assert settings.deploy_env == "production"
    assert settings.chat_api == "google"
    assert settings.chat_record_path is None


def test_deploy_env_refuses_an_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "deploy_env" in refusal(monkeypatch, DEPLOY_ENV="staging")


def test_mcp_auth_none_without_deploy_env_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    text = refusal(monkeypatch, DEPLOY_ENV=None, MCP_AUTH="none")

    assert "MCP_AUTH" in text
    assert "DEPLOY_ENV" in text


def test_mcp_auth_none_with_deploy_env_production_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = refusal(monkeypatch, DEPLOY_ENV="production", MCP_AUTH="none")

    assert "MCP_AUTH" in text
    assert "DEPLOY_ENV" in text


def test_mcp_auth_none_with_deploy_env_local_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, DEPLOY_ENV="local", MCP_AUTH="none")

    assert settings.deploy_env == "local"
    assert settings.mcp_auth == "none"


def test_deploy_env_local_is_refused_when_k_service_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("K_SERVICE", "ai-buddy-bot")

    text = refusal(monkeypatch, DEPLOY_ENV="local", MCP_AUTH="google_id_token", MCP_AUDIENCE="x")

    assert "DEPLOY_ENV" in text
    assert "K_SERVICE" in text


def test_no_mcp_auth_on_cloud_run_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "ai-buddy-bot")

    assert "K_SERVICE" in refusal(monkeypatch, MCP_AUTH="none")
    assert "MCP_AUTH" in refusal(monkeypatch, DEPLOY_ENV=None, MCP_AUTH="none")


def test_id_token_auth_on_cloud_run_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "ai-buddy-bot")

    settings = load(
        monkeypatch,
        DEPLOY_ENV=None,
        MCP_AUTH="google_id_token",
        MCP_AUDIENCE="https://mcp.invalid",
    )

    assert settings.mcp_auth == "google_id_token"
    assert settings.deploy_env == "production"


@pytest.mark.parametrize("deploy_env", [None, "production"])
@pytest.mark.parametrize("k_service", [False, True])
def test_every_value_but_local_refuses_the_local_only_knobs(
    monkeypatch: pytest.MonkeyPatch, deploy_env: str | None, k_service: bool
) -> None:
    if k_service:
        monkeypatch.setenv("K_SERVICE", "ai-buddy-bot")

    assert "MCP_AUTH" in refusal(monkeypatch, DEPLOY_ENV=deploy_env, MCP_AUTH="none")
    text = refusal(
        monkeypatch,
        DEPLOY_ENV=deploy_env,
        MCP_AUTH="google_id_token",
        MCP_AUDIENCE="x",
        CHAT_API="recording",
        CHAT_RECORD_PATH="/tmp/chat.jsonl",
    )
    assert "CHAT_API" in text
    assert "DEPLOY_ENV" in text


def test_chat_api_recording_with_deploy_env_local_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, CHAT_API="recording", CHAT_RECORD_PATH="/tmp/chat.jsonl")

    assert settings.chat_api == "recording"
    assert str(settings.chat_record_path) == "/tmp/chat.jsonl"


def test_chat_api_recording_without_a_record_path_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = refusal(monkeypatch, CHAT_API="recording", CHAT_RECORD_PATH=None)

    assert "CHAT_RECORD_PATH" in text


def test_chat_api_refuses_an_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "chat_api" in refusal(monkeypatch, CHAT_API="fake")


@pytest.mark.parametrize(
    ("variable", "value"),
    [("LANGSMITH_TRACING", "true"), ("LANGSMITH_TRACING", "YES"), ("LANGCHAIN_TRACING_V2", "1")],
)
def test_true_tracing_is_refused(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    assert "LANGSMITH_TRACING must be false: prompts must not leave the host" in refusal(
        monkeypatch
    )


def test_false_tracing_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    assert load(monkeypatch).llm_backend == "api"


# --- field rules ---------------------------------------------------------------------------


def test_short_thread_key_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "THREAD_KEY_SECRET" in refusal(monkeypatch, THREAD_KEY_SECRET=SENTINEL_THREAD_SHORT)


def test_thread_key_secret_of_32_characters_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, THREAD_KEY_SECRET="k" * 32)

    assert settings.thread_key_secret.get_secret_value() == "k" * 32


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CONFIDENCE_THRESHOLD", "1.5"),
        ("MEMORY_TURNS", "0"),
        ("MEMORY_TURNS", "11"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("MEMORY_COLLECTION", "nome non valido!"),
    ],
)
def test_out_of_range_values_are_refused(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    assert variable.lower() in refusal(monkeypatch, **{variable: value}).lower()


def test_http_thumbnail_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    text = refusal(monkeypatch, VIDEO_THUMBNAIL_URL="http://x.invalid/a.png")

    assert "VIDEO_THUMBNAIL_URL must start with https://" in text


def test_missing_thumbnail_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # 03-01 bot09_rendering (2c): VIDEO_THUMBNAIL_URL is a required HTTPS setting.
    assert "video_thumbnail_url" in refusal(monkeypatch, VIDEO_THUMBNAIL_URL=None)


# --- T-03-14: no secret value in any refusal -----------------------------------------------

REFUSALS: list[dict[str, str | None]] = [
    {"ALLOWED_USERS": "users/1,users/2", **MERIDIAN},
    {"ALLOWED_USERS": " , "},
    {"LLM_BACKEND": "vertex", "VERTEX_PROJECT": "demo-ai-buddy", "VERTEX_REGION": "europe-west1"},
    {"LLM_BACKEND": "meridian"},
    {"ANTHROPIC_API_KEY": None},
    {"MCP_AUTH": "google_id_token"},
    {"DEPLOY_ENV": None},
    {"CHAT_API": "recording", "CHAT_RECORD_PATH": None},
    {"INTAKE": "http", "PUBSUB_SUBSCRIPTION": None},
    {"THREAD_KEY_SECRET": SENTINEL_THREAD_SHORT},
    {"THREAD_KEY_SECRET": None},
    {"CONFIDENCE_THRESHOLD": "1.5"},
    {"VIDEO_THUMBNAIL_URL": "http://x.invalid/a.png"},
    {"LLM_BACKEND": "inesistente"},
]


@pytest.mark.parametrize("overrides", REFUSALS)
def test_no_refusal_echoes_a_secret(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str | None]
) -> None:
    text = refusal(monkeypatch, **overrides)

    for sentinel in (SENTINEL_ANTHROPIC, SENTINEL_MERIDIAN, SENTINEL_THREAD, SENTINEL_THREAD_SHORT):
        assert sentinel not in text


@pytest.mark.parametrize("variable", ["LANGSMITH_TRACING", "K_SERVICE"])
def test_environment_refusals_echo_no_secret(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "true")
    overrides: dict[str, str | None] = {"MCP_AUTH": "none"} if variable == "K_SERVICE" else {}

    text = refusal(monkeypatch, **overrides)

    for sentinel in (SENTINEL_ANTHROPIC, SENTINEL_MERIDIAN, SENTINEL_THREAD):
        assert sentinel not in text
