"""Sensitive topics (BOT-06, D-05, D-06, D-07): the general written rule plus a referral, nothing
about the individual case. The sentence `Per il tuo caso specifico chiedi a ...` is rendered by
render.py and asserted in the render tests, never written by the model.
"""

import pytest
from tests.unit.chat_bot.conftest import FakeLlm, RecordingConnector

from buddy_bot import prompts
from buddy_bot.schemas import AnswerDraft, ContactExtraction, Reformulation
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow
from buddy_core.escalation import EscalationTable, EscalationTopic, load_escalation_table
from buddy_mcp.gaplog import InMemoryGapLog

pytestmark = pytest.mark.anyio

STANDALONE = "Cosa prevede il manuale in caso di malattia?"
HR_CONTACT = ContactExtraction(contact="hr@example.invalid", source_url="handbook://05-contatti")


def _reformulation(topic: str | None) -> Reformulation:
    return Reformulation(
        standalone_question=STANDALONE,
        keywords_it=["malattia"],
        keywords_en=["chunking"],
        intent="question",
        sensitive_topic=topic,
    )


def _draft(citation: str = "handbook://03-malattia", confidence: float = 0.9) -> AnswerDraft:
    return AnswerDraft(
        answer="In caso di malattia si comunica il protocollo del certificato a HR.",
        citations=[citation],
        grounded=True,
        confidence=confidence,
    )


async def test_sensitive_question_answers_with_the_cited_rule_and_a_referente(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation("malattia")],
            AnswerDraft: [_draft()],
            ContactExtraction: [HR_CONTACT],
        }
    )

    reply = await run_workflow("domanda", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.kind == "answer"
    assert [s.source_url for s in reply.sources] == ["handbook://03-malattia"]
    assert reply.referente is not None
    assert reply.referente.role == "HR"
    assert reply.referente.contact == "hr@example.invalid"
    assert "Per il tuo caso specifico" not in reply.answer
    assert gaplog.records == []
    answer_call = next(c for c in llm.calls if c.schema is AnswerDraft)
    assert answer_call.system == prompts.ANSWER_SENSITIVE_SYSTEM


async def test_normal_question_uses_the_plain_answer_prompt_and_has_no_referente(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm({Reformulation: [_reformulation(None)], AnswerDraft: [_draft()]})

    reply = await run_workflow("domanda", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.kind == "answer"
    assert reply.referente is None
    answer_call = next(c for c in llm.calls if c.schema is AnswerDraft)
    assert answer_call.system == prompts.ANSWER_SYSTEM


async def test_personal_leave_topic_points_to_the_direct_manager_role(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm({Reformulation: [_reformulation("ferie_personali")], AnswerDraft: [_draft()]})

    reply = await run_workflow("domanda", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.kind == "answer"
    assert reply.referente is not None
    assert reply.referente.role == "responsabile diretto"


async def test_sensitive_question_without_a_supported_rule_is_a_referral_with_a_gap(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation("malattia")],
            AnswerDraft: [_draft("handbook://99-x"), _draft("handbook://98-x")],
            ContactExtraction: [HR_CONTACT],
        }
    )

    reply = await run_workflow("domanda", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.kind == "referral"
    assert reply.sources == []
    assert reply.referente is not None
    assert reply.referente.role == "HR"
    assert reply.referente.contact == "hr@example.invalid"
    assert reply.gap_reported is True
    assert [r.question for r in gaplog.records] == [STANDALONE]


async def test_unknown_topic_id_is_treated_as_sensitive_with_the_fallback_role(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {Reformulation: [_reformulation("argomento-sconosciuto")], AnswerDraft: [_draft()]}
    )

    reply = await run_workflow("domanda", [], WorkflowDeps(llm, connector, workflow_config))

    assert reply.referente is not None
    assert reply.referente.role == "HR"
    answer_call = next(c for c in llm.calls if c.schema is AnswerDraft)
    assert answer_call.system == prompts.ANSWER_SENSITIVE_SYSTEM


async def test_a_custom_escalation_table_decides_the_role(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    table = EscalationTable(
        version=1,
        fallback_role="Ufficio Persone",
        topics=(EscalationTopic("salute", "Salute", "Ufficio Persone", "Medico competente"),),
    )
    llm = FakeLlm({Reformulation: [_reformulation("salute")], AnswerDraft: [_draft()]})

    reply = await run_workflow(
        "domanda", [], WorkflowDeps(llm, connector, workflow_config, escalation=table)
    )

    assert reply.referente is not None
    assert reply.referente.role == "Medico competente"
    assert "salute: Salute" in llm.calls[0].system


async def test_reformulate_prompt_lists_the_table_topics_and_no_sensitive_word_list(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm({Reformulation: [_reformulation(None)], AnswerDraft: [_draft()]})
    await run_workflow("domanda", [], WorkflowDeps(llm, connector, workflow_config))

    system = llm.calls[0].system
    table = load_escalation_table()
    assert len(table.topics) == 8
    for topic in table.topics:
        assert f"{topic.id}: {topic.tema}" in system
    for word in ("depressione", "licenziamento", "gravidanza", "cancro"):
        assert word not in system.lower()


def test_format_topics_renders_one_line_per_topic() -> None:
    table = load_escalation_table()

    lines = prompts.format_topics(table).splitlines()

    assert lines == [f"{t.id}: {t.tema}" for t in table.topics]
