"""The scene offset of a Guides section survives index -> MCP tool -> bot -> Chat card (SC5).

Gap 1 of the Phase 4 verification: a live click on Guarda did not seek. This module pins every hop
that lives in our own code, so a live failure can be placed outside it. The index uses the
`storage.cloud.google.com` URL form written by the video mapping and a placeholder bucket.

`chat_api._to_message` is a function, so the third test calls it on the card the bot actually sent
and asserts on the converted GAPIC object; no network is involved.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastmcp import FastMCP
from tests.unit.chat_bot.conftest import (
    ALLOWED,
    REFORMULATION,
    DictThreadMemory,
    FakeChatApi,
    FakeLlm,
    UpdatedMessage,
    load_event,
)
from tests.unit.mcp_server.conftest import (
    FILE,
    NOW,
    SHA,
    WEB_BASE,
    make_chunk,
    make_content,
    write_index,
)

from buddy_bot.chat_api import _to_message
from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.schemas import AnswerDraft, Reformulation
from buddy_bot.service import BotService
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps
from buddy_core.models import IndexContent, VideoLink
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import IndexSnapshot, load_snapshot

pytestmark = pytest.mark.anyio

OBJECT_URL = "https://storage.cloud.google.com/demo-videos/videos/demo.mp4"
SECTION = make_chunk(
    "Retrieval", "Chunking", 10, 14, "Chunking splits documents into heading sections."
)
SECTION_PERMALINK = f"{WEB_BASE}/blob/{SHA}/{FILE}#L10-L14"
DRAFT = AnswerDraft(
    answer="Il chunking divide i documenti in sezioni.",
    citations=[SECTION_PERMALINK],
    grounded=True,
    confidence=0.9,
)


@pytest.fixture
def server_for(tmp_path: Path) -> Iterator[Callable[[IndexContent], FastMCP]]:
    """Factory: a real MCP server over a fresh tmp index built from `content`."""
    opened: list[IndexSnapshot] = []

    def factory(content: IndexContent) -> FastMCP:
        directory = tmp_path / "artifacts"
        write_index(directory, content)
        snapshot = load_snapshot(directory / "index.db")
        opened.append(snapshot)
        settings = McpSettings(
            artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
        )
        return build_server(settings, snapshot=snapshot, gaplog=InMemoryGapLog(), now=lambda: NOW)

    yield factory
    for snapshot in opened:
        snapshot.reader.close()
        snapshot.handbook_index.close()


def _content(video: VideoLink) -> IndexContent:
    return make_content(chunks=(SECTION,), videos={SECTION.chunk_key: video})


async def _send_dm_and_get_update(server: FastMCP) -> UpdatedMessage:
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [DRAFT]})
    chat = FakeChatApi()
    service = BotService(
        allowed_users=ALLOWED,
        chat=chat,
        deps=WorkflowDeps(
            llm=llm,
            mcp=FastMcpConnector(server),
            config=WorkflowConfig(
                reformulate_model="test-haiku", answer_model="test-sonnet", confidence_threshold=0.7
            ),
        ),
        memory=DictThreadMemory(),
        memory_turns=3,
        video_thumbnail_url="https://example.invalid/thumb.png",
    )
    await service.handle(load_event("legacy_dm_message"))
    assert len(chat.updated) == 1
    return chat.updated[0]


def _guarda_urls(update: UpdatedMessage) -> list[str]:
    urls: list[str] = []
    for card in update.cards_v2:
        for section in card["card"]["sections"]:
            for widget in section["widgets"]:
                for button in widget.get("buttonList", {}).get("buttons", []):
                    if button["text"] == "Guarda":
                        urls.append(button["onClick"]["openLink"]["url"])
    return urls


async def test_scene_offset_reaches_the_guarda_button(
    server_for: Callable[[IndexContent], FastMCP],
) -> None:
    server = server_for(_content(VideoLink(OBJECT_URL, 1, 125.0, "scene")))

    update = await _send_dm_and_get_update(server)

    assert _guarda_urls(update) == [f"{OBJECT_URL}#t=125"]


async def test_fallback_row_has_no_offset_in_the_guarda_button(
    server_for: Callable[[IndexContent], FastMCP],
) -> None:
    server = server_for(_content(VideoLink(OBJECT_URL, 1, None, "readme_fallback")))

    update = await _send_dm_and_get_update(server)

    assert _guarda_urls(update) == [OBJECT_URL]


async def test_converted_chat_message_keeps_the_offset(
    server_for: Callable[[IndexContent], FastMCP],
) -> None:
    server = server_for(_content(VideoLink(OBJECT_URL, 1, 125.0, "scene")))
    update = await _send_dm_and_get_update(server)

    message = _to_message(update.name, update.text, update.cards_v2)

    urls = [
        button.on_click.open_link.url
        for card in message.cards_v2
        for section in card.card.sections
        for widget in section.widgets
        for button in widget.button_list.buttons
        if button.text == "Guarda"
    ]
    assert urls == [f"{OBJECT_URL}#t=125"]
