"""Refusal path end to end: one retry, a referente quoted from the handbook, one gap logged.

Runs through run_workflow and render_reply over the real in-memory MCP server (BOT-05, D-03,
D-04, D-07).
"""

import pytest
from tests.unit.chat_bot.conftest import FakeLlm, RecordingConnector

from buddy_bot.render import render_reply
from buddy_bot.schemas import (
    AnswerDraft,
    ContactExtraction,
    Reformulation,
    RetryPlan,
)
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow
from buddy_mcp.gaplog import InMemoryGapLog

pytestmark = pytest.mark.anyio

STANDALONE = "Come richiedo le ferie?"
REFORMULATION = Reformulation(
    standalone_question=STANDALONE,
    keywords_it=["ferie"],
    keywords_en=["holidays"],
    intent="question",
    sensitive_topic=None,
)
RETRY = RetryPlan(keywords_it=["permessi"], keywords_en=["leave"])


def _forged(page_id: str) -> AnswerDraft:
    return AnswerDraft(
        answer="Risposta inventata.",
        citations=[f"handbook://{page_id}"],
        grounded=True,
        confidence=0.9,
    )


def _llm(contact: ContactExtraction) -> FakeLlm:
    return FakeLlm(
        {
            Reformulation: [REFORMULATION],
            AnswerDraft: [_forged("99-inventata"), _forged("98-inventata")],
            RetryPlan: [RETRY],
            ContactExtraction: [contact],
        }
    )


async def test_unsupported_question_is_retried_once_then_refused_with_quoted_contact(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = _llm(ContactExtraction(contact="hr@example.invalid", source_url="handbook://05-contatti"))

    reply = await run_workflow("ferie?", [], WorkflowDeps(llm, connector, workflow_config))

    schemas = [call.schema for call in llm.calls]
    assert schemas.count(AnswerDraft) == 2
    assert schemas.count(RetryPlan) == 1
    assert reply.kind == "refusal"
    assert reply.referente is not None
    assert reply.referente.role == "HR"
    assert reply.referente.contact == "hr@example.invalid"
    assert reply.referente.contact_source is not None
    assert reply.referente.contact_source.source_url == "handbook://05-contatti"
    assert reply.gap_reported is True
    rendered = render_reply(reply, video_thumbnail_url=None)
    assert rendered.text.startswith("Non lo so, chiedi a HR (hr@example.invalid).")

    assert len(gaplog.records) == 1
    record = gaplog.records[0]
    assert record.question == STANDALONE
    assert record.tried == (
        "handbook_search: ferie",
        "guides_search: holidays",
        "handbook_search: permessi",
        "guides_search: leave",
    )
    assert set(connector.calls) == {"handbook_search", "guides_search", "buddy_report_gap"}
    assert connector.calls.count("buddy_report_gap") == 1


async def test_contact_not_in_the_handbook_page_is_dropped(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = _llm(
        ContactExtraction(contact="hr-finto@example.invalid", source_url="handbook://05-contatti")
    )

    reply = await run_workflow("ferie?", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.kind == "refusal"
    assert reply.referente is not None
    assert reply.referente.role == "HR"
    assert reply.referente.contact is None
    assert reply.referente.contact_source is None
    assert render_reply(reply, video_thumbnail_url=None).text.startswith("Non lo so, chiedi a HR.")
    assert len(gaplog.records) == 1


async def test_contact_cited_from_a_page_the_run_did_not_return_is_dropped(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = _llm(ContactExtraction(contact="hr@example.invalid", source_url="handbook://77-altra"))

    reply = await run_workflow("ferie?", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.referente is not None
    assert reply.referente.contact is None
