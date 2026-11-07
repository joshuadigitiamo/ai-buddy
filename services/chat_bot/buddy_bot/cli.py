"""Command line for the chat bot: ``python -m buddy_bot``.

This is the only place real adapters (LLM client, MCP connector, Firestore thread memory, Chat
API, intake) are built; everything else takes them as arguments. Output is limited to counts and
modes, never question text, identities or secrets (BOT-11, ASVS V13).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable, Sequence
from typing import Final

import httpx2
from google.cloud import firestore
from pydantic import ValidationError

from buddy_bot.chat_api import GoogleChatApi, build_chat_client
from buddy_bot.config import BotSettings
from buddy_bot.intake.http import ACK_SECONDS, ChatTokenVerifier, HttpIntake
from buddy_bot.intake.pubsub import PubSubIntake
from buddy_bot.llm import build_llm_client
from buddy_bot.mcp_client import FastMcpConnector, GoogleIdTokenAuth
from buddy_bot.memory import FirestoreThreadMemory
from buddy_bot.ports import EventHandler, IntakePort
from buddy_bot.service import BotService
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps
from buddy_core.escalation import EscalationTableError, load_escalation_table

LOGGER_NAME: Final = "buddy_bot"
LOG_FORMAT: Final = "%(levelname)s %(name)s %(message)s"

# Failures that end startup with one ERROR line and exit code 1.
_EXPECTED_ERRORS: Final = (EscalationTableError, OSError)

RunFn = Callable[[IntakePort, EventHandler], None]


def _describe_validation_error(exc: ValidationError) -> str:
    """Name the offending variables only; error inputs could carry secret values.

    Cross-field validators carry no field location: their message names variables, not values.
    """
    names = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err["loc"]})
    notes = sorted(
        {err["msg"].removeprefix("Value error, ") for err in exc.errors() if not err["loc"]}
    )
    return "invalid or missing configuration: " + "; ".join([*names, *notes] or ["(unknown)"])


def _run_intake(intake: IntakePort, handler: EventHandler) -> None:
    """Run the intake on a fresh event loop until it ends or the process is interrupted."""
    try:
        asyncio.run(intake.run(handler))
    except KeyboardInterrupt:
        return


def _configure_logging(logger: logging.Logger) -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return handler


def main(argv: Sequence[str] | None = None, *, run: RunFn | None = None) -> int:
    """Build every adapter from the environment and run the intake; 0, or 1 on a startup failure."""
    del argv  # no command-line options: every setting comes from the environment
    logger = logging.getLogger(LOGGER_NAME)
    handler = _configure_logging(logger)
    try:
        return _run(logger, run or _run_intake)
    except ValidationError as exc:
        logger.error("%s", _describe_validation_error(exc))
        return 1
    except _EXPECTED_ERRORS as exc:
        logger.error("%s: %s", type(exc).__name__, exc)
        return 1
    finally:
        logger.removeHandler(handler)


def _build_intake(settings: BotSettings) -> IntakePort:
    if settings.intake == "pubsub":
        assert settings.pubsub_subscription is not None  # BotSettings requires it for pubsub
        return PubSubIntake(settings.pubsub_subscription)
    assert settings.chat_jwt_audience is not None  # BotSettings requires both for http
    assert settings.chat_jwt_issuer_email is not None
    verifier = ChatTokenVerifier(settings.chat_jwt_audience, settings.chat_jwt_issuer_email)
    return HttpIntake(verifier, host=settings.bot_host, port=settings.port, ack_seconds=ACK_SECONDS)


def _run(logger: logging.Logger, run: RunFn) -> int:
    settings = BotSettings()
    project = settings.google_cloud_project
    if not project:
        logger.error("missing environment variable: GOOGLE_CLOUD_PROJECT")
        return 1

    # Nothing below touches the network: the Firestore client, the Chat API client and the ID
    # token are created on first use, inside the intake's event loop.
    llm = build_llm_client(settings)
    auth: httpx2.Auth | None = None
    if settings.mcp_auth == "google_id_token":
        assert settings.mcp_audience is not None  # BotSettings requires it for this mode
        auth = GoogleIdTokenAuth(settings.mcp_audience)
    connector = FastMcpConnector(settings.mcp_url, auth=auth)
    memory = FirestoreThreadMemory(
        lambda: firestore.AsyncClient(project=project),
        secret=settings.thread_key_secret.get_secret_value(),
        collection=settings.memory_collection,
        max_turns=settings.memory_turns,
    )
    config = WorkflowConfig(
        reformulate_model=settings.reformulate_model,
        answer_model=settings.answer_model,
        confidence_threshold=settings.confidence_threshold,
    )
    deps = WorkflowDeps(llm, connector, config, load_escalation_table())
    service = BotService(
        allowed_users=settings.allowed_users,
        chat=GoogleChatApi(build_chat_client),
        deps=deps,
        memory=memory,
        memory_turns=settings.memory_turns,
        video_thumbnail_url=settings.video_thumbnail_url,
        help_command_id=settings.help_command_id,
        run_deadline_seconds=settings.run_deadline_seconds,
    )
    intake = _build_intake(settings)
    logger.info(
        "starting: intake %s, llm backend %s, %d allowed user(s), memory turns %d",
        settings.intake,
        settings.llm_backend,
        len(settings.allowed_users),
        settings.memory_turns,
    )
    run(intake, service.handle)
    return 0
