"""No log record pairs a person with a question or an answer, on any reply path (BOT-11, T-03-31).

Every run feeds BotService an event whose identity, space, thread and text carry the marker
"sentinella"; a failure of the assertion means a log call wrote event fields, model output or an
exception message. The wiring probe proves the capture sees every logger it claims to watch.
"""

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from tests.unit.chat_bot.conftest import (
    DictThreadMemory,
    FakeChatApi,
    FakeLlm,
    ServiceFactory,
    connector,  # noqa: F401  (fixtures reused from the unit conftest)
    gaplog,  # noqa: F401
    load_event,
    make_service,  # noqa: F401
    mcp_server,  # noqa: F401
    with_message,
    workflow_config,  # noqa: F401
)

from buddy_bot.cli import floor_content_loggers
from buddy_bot.ports import Turn
from buddy_bot.render import ERROR_TEXT
from buddy_bot.schemas import AnswerDraft, ContactExtraction, Reformulation, RetryPlan

pytestmark = pytest.mark.anyio

SENDER_USER = "users/sentinella-id"
SENDER_MAIL = "sentinella-mail@example.invalid"
SENDER_NAME = "sentinella-nome"
SPACE = "spaces/sentinella-space"
THREAD = "spaces/sentinella-space/threads/sentinella-thread"
QUESTION = "sentinella-domanda ferie?"
MODEL_ANSWER = "sentinella-risposta: invia la richiesta al responsabile."
CONTACT = ContactExtraction(contact="hr@example.invalid", source_url="handbook://05-contatti")

# The fastmcp logger does not propagate to the root logger, so the capture handler is attached to
# every watched logger by hand.
WATCHED_LOGGERS = ("buddy_bot", "fastmcp", "langgraph", "httpx2", "mcp", "anthropic")


CONTENT_LOGGERS = ("fastmcp", "anthropic")


def _sentinel_event() -> dict[str, Any]:
    """The recorded DM event with every identifying field and the text replaced by sentinels."""
    raw = json.dumps(load_event("legacy_dm_message"))
    for original, sentinel in (
        ("users/111111111111111111111", SENDER_USER),
        ("utente@example.invalid", SENDER_MAIL),
        ("Utente Sintetico", SENDER_NAME),
        ("spaces/AAAAsyntheticDM", SPACE),
        ("threads/thr-1", "threads/sentinella-thread"),
    ):
        raw = raw.replace(original, sentinel)
    event: dict[str, Any] = json.loads(raw)
    return with_message(event, text=QUESTION)


def _reformulation(topic: str | None = None) -> Reformulation:
    return Reformulation(
        standalone_question=QUESTION,
        keywords_it=["ferie"],
        keywords_en=["chunking"],
        intent="question",
        sensitive_topic=topic,
    )


def _draft(citation: str) -> AnswerDraft:
    return AnswerDraft(answer=MODEL_ANSWER, citations=[citation], grounded=True, confidence=0.9)


class _FailingAppendMemory(DictThreadMemory):
    async def append(self, key_source: str, turn: Turn) -> None:
        raise ValueError("sentinella-mem")


@dataclass(frozen=True, slots=True)
class Scenario:
    llm: FakeLlm
    allowed: frozenset[str]
    memory: DictThreadMemory
    check: Callable[[FakeChatApi], None]
    logged: str | None = None  # text the run must have logged, proving the capture saw it


def _answered() -> Scenario:
    def check(chat: FakeChatApi) -> None:
        assert "sentinella-risposta" in chat.updated[0].text

    llm = FakeLlm({Reformulation: [_reformulation()], AnswerDraft: [_draft("handbook://02-ferie")]})
    return Scenario(llm, frozenset({SENDER_USER}), DictThreadMemory(), check)


def _refused_with_gap() -> Scenario:
    def check(chat: FakeChatApi) -> None:
        assert chat.updated[0].text.startswith("Non lo so")
        assert "sentinella-risposta" not in chat.updated[0].text

    llm = FakeLlm(
        {
            Reformulation: [_reformulation()],
            AnswerDraft: [_draft("handbook://99-x"), _draft("handbook://98-x")],
            RetryPlan: [RetryPlan(keywords_it=["permessi"], keywords_en=["leave"])],
            ContactExtraction: [CONTACT],
        }
    )
    return Scenario(llm, frozenset({SENDER_USER}), DictThreadMemory(), check)


def _sensitive_referral() -> Scenario:
    def check(chat: FakeChatApi) -> None:
        assert "sentinella-risposta" not in chat.updated[0].text
        assert "hr@example.invalid" in chat.updated[0].text

    llm = FakeLlm(
        {
            Reformulation: [_reformulation("malattia")],
            AnswerDraft: [_draft("handbook://99-x"), _draft("handbook://98-x")],
            ContactExtraction: [CONTACT],
        }
    )
    return Scenario(llm, frozenset({SENDER_USER}), DictThreadMemory(), check)


def _workflow_error() -> Scenario:
    def check(chat: FakeChatApi) -> None:
        assert chat.updated[0].text == ERROR_TEXT

    llm = FakeLlm({Reformulation: [RuntimeError("sentinella-errore")]})
    return Scenario(
        llm, frozenset({SENDER_USER}), DictThreadMemory(), check, logged="run failed: RuntimeError"
    )


def _stranger() -> Scenario:
    def check(chat: FakeChatApi) -> None:
        assert chat.created == []
        assert chat.updated == []

    return Scenario(
        FakeLlm({}),
        frozenset({"users/222222222222222222222"}),
        DictThreadMemory(),
        check,
        logged="event dropped: sender not allowed",
    )


def _memory_write_fails() -> Scenario:
    def check(chat: FakeChatApi) -> None:
        assert "sentinella-risposta" in chat.updated[0].text

    llm = FakeLlm({Reformulation: [_reformulation()], AnswerDraft: [_draft("handbook://02-ferie")]})
    return Scenario(
        llm,
        frozenset({SENDER_USER}),
        _FailingAppendMemory(),
        check,
        logged="memory write failed: ValueError",
    )


SCENARIOS = {
    "answered-and-cited": _answered,
    "refusal-with-gap": _refused_with_gap,
    "sensitive-referral": _sensitive_referral,
    "workflow-error": _workflow_error,
    "dropped-stranger": _stranger,
    "memory-write-failure": _memory_write_fails,
}


@pytest.fixture
def captured(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture DEBUG records of every watched logger and the root logger.

    The libraries start at DEBUG, as with FASTMCP_LOG_LEVEL=DEBUG or ANTHROPIC_LOG=debug; the
    startup floor then applies, as in the process. caplog restores each level afterwards.
    """
    caplog.set_level(logging.DEBUG)
    loggers = [logging.getLogger(name) for name in WATCHED_LOGGERS]
    for logger in loggers:
        caplog.set_level(logging.DEBUG, logger=logger.name)
        logger.addHandler(caplog.handler)
    floor_content_loggers()
    try:
        yield caplog
    finally:
        for logger in loggers:
            logger.removeHandler(caplog.handler)


def _record_text(record: logging.LogRecord) -> str:
    """Everything one record can carry: message, raw arguments, exception, extra attributes."""
    return " ".join(
        (
            record.getMessage(),
            repr(record.msg),
            repr(record.args),
            repr(record.exc_info),
            record.exc_text or "",
            repr(sorted(vars(record).items(), key=lambda item: item[0])),
        )
    )


@pytest.mark.parametrize("name", list(SCENARIOS))
async def test_no_log_record_carries_identity_question_or_answer(
    name: str,
    captured: pytest.LogCaptureFixture,
    make_service: ServiceFactory,  # noqa: F811
) -> None:
    scenario = SCENARIOS[name]()
    chat = FakeChatApi()
    service = make_service(
        scenario.llm, chat=chat, memory=scenario.memory, allowed_users=scenario.allowed
    )

    await service.handle(_sentinel_event())

    scenario.check(chat)
    if scenario.logged is not None:
        assert scenario.logged in captured.text
    assert "sentinella" not in captured.text
    for record in captured.records:
        assert "sentinella" not in _record_text(record)


def test_capture_wiring_sees_every_watched_logger(captured: pytest.LogCaptureFixture) -> None:
    """Guards the hygiene test above against passing because nothing was captured."""
    for name in WATCHED_LOGGERS:
        logging.getLogger(f"{name}.probe").info("probe-line-%s", name)
        logging.getLogger(f"{name}.probe").debug("probe-debug-%s", name)

    for name in WATCHED_LOGGERS:
        assert f"probe-line-{name}" in captured.text
        # The floored libraries drop DEBUG records; the others keep them.
        assert (f"probe-debug-{name}" in captured.text) is (name not in CONTENT_LOGGERS)
    logging.getLogger().debug("probe-root")
    assert "probe-root" in captured.text
