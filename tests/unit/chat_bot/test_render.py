"""Chat rendering: the Guides video card (BOT-09, D15) and bot-built sources only (D-02)."""

import pytest
from tests.unit.chat_bot.conftest import FakeLlm, RecordingConnector
from tests.unit.mcp_server.conftest import FILE, SHA, WEB_BASE

from buddy_bot.render import render_reply
from buddy_bot.schemas import AnswerDraft, Reformulation
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow

pytestmark = pytest.mark.anyio

THUMBNAIL = "https://example.invalid/thumb.png"
MAPPED_PERMALINK = f"{WEB_BASE}/blob/{SHA}/{FILE}#L10-L14"
MAPPED_VIDEO = "https://videos.example.invalid/demo.mp4#t=12"


async def test_guides_answer_with_mapped_video_renders_card_with_fonte_and_guarda(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                Reformulation(
                    standalone_question="Cos'e il chunking?",
                    keywords_it=["suddivisione"],
                    keywords_en=["chunking"],
                    intent="question",
                )
            ],
            AnswerDraft: [
                AnswerDraft(
                    answer="Il chunking divide i documenti in sezioni.",
                    citations=[MAPPED_PERMALINK],
                    grounded=True,
                    confidence=0.9,
                )
            ],
        }
    )

    reply = await run_workflow("chunking?", [], WorkflowDeps(llm, connector, workflow_config))
    rendered = render_reply(reply, video_thumbnail_url=THUMBNAIL)

    assert reply.kind == "answer"
    assert "Il chunking divide i documenti in sezioni." in rendered.text
    assert "Fonte: Guida" in rendered.text
    assert len(rendered.cards_v2) == 1
    sections = rendered.cards_v2[0]["card"]["sections"]
    assert len(sections) == 1
    widgets = sections[0]["widgets"]
    assert [next(iter(widget)) for widget in widgets] == ["image", "textParagraph", "buttonList"]
    assert widgets[0]["image"]["imageUrl"] == THUMBNAIL
    buttons = widgets[2]["buttonList"]["buttons"]
    assert [button["text"] for button in buttons] == ["Fonte", "Guarda"]
    assert [button["onClick"]["openLink"]["url"] for button in buttons] == [
        MAPPED_PERMALINK,
        MAPPED_VIDEO,
    ]
