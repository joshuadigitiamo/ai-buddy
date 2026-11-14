"""D-09: the Chat API adapter posts the placeholder in the thread and patches it in place."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import google.auth
import pytest
from google.api_core import exceptions as api_exceptions
from google.apps import chat_v1
from google.auth.credentials import AnonymousCredentials
from google.protobuf import field_mask_pb2
from tests.unit.chat_bot.conftest import (
    GOOD_DRAFT,
    REFORMULATION,
    FakeLlm,
    ServiceFactory,
    load_event,
)

from buddy_bot.chat_api import (
    CHAT_BOT_SCOPE,
    ChatApiError,
    GoogleChatApi,
    RecordingChatApi,
    build_chat_client,
)
from buddy_bot.render import render_reply
from buddy_bot.schemas import AnswerDraft, BotReply, Evidence, Reformulation

pytestmark = pytest.mark.anyio

REPLY_OPTION = chat_v1.CreateMessageRequest.MessageReplyOption
PERMALINK = "https://github.example.invalid/blob/abc/guide.md#L10-L14"
VIDEO = "https://videos.example.invalid/demo.mp4#t=12"
THUMBNAIL = "https://example.invalid/thumb.png"


class FakeChatClient:
    """Stands in for ChatServiceAsyncClient; records the requests it receives."""

    def __init__(self, error: Exception | None = None) -> None:
        self.created: list[chat_v1.CreateMessageRequest] = []
        self.updated: list[tuple[chat_v1.Message, field_mask_pb2.FieldMask]] = []
        self._error = error

    async def create_message(self, *, request: chat_v1.CreateMessageRequest) -> chat_v1.Message:
        if self._error:
            raise self._error
        self.created.append(request)
        return chat_v1.Message(name=f"{request.parent}/messages/M{len(self.created)}")

    async def update_message(
        self, *, message: chat_v1.Message, update_mask: field_mask_pb2.FieldMask
    ) -> chat_v1.Message:
        if self._error:
            raise self._error
        self.updated.append((message, update_mask))
        return message


def _video_cards() -> Sequence[Mapping[str, Any]]:
    source = Evidence(
        source_url=PERMALINK,
        kind="guides",
        title="Guida demo",
        text="testo",
        revision_date="2026-11-03T10:00:00+00:00",
        revision_kind="indexed_on",
        video_url=VIDEO,
    )
    reply = BotReply(kind="answer", answer="Risposta.", sources=[source])
    return render_reply(reply, video_thumbnail_url=THUMBNAIL).cards_v2


async def test_client_is_built_lazily_and_only_once() -> None:
    client = FakeChatClient()
    built: list[int] = []

    def factory() -> FakeChatClient:
        built.append(1)
        return client

    api = GoogleChatApi(factory)
    assert built == []
    await api.create_message(space="spaces/S", thread=None, text="a")
    await api.create_message(space="spaces/S", thread=None, text="b")
    assert built == [1]


async def test_create_message_replies_in_the_event_thread() -> None:
    client = FakeChatClient()
    api = GoogleChatApi(lambda: client)

    name = await api.create_message(space="spaces/S", thread="spaces/S/threads/T", text="x")

    assert name == "spaces/S/messages/M1"
    request = client.created[0]
    assert request.parent == "spaces/S"
    assert request.message.text == "x"
    assert request.message.thread.name == "spaces/S/threads/T"
    assert request.message_reply_option == REPLY_OPTION.REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD


async def test_create_message_without_thread_sends_no_thread_and_no_reply_option() -> None:
    client = FakeChatClient()
    api = GoogleChatApi(lambda: client)

    await api.create_message(space="spaces/S", thread=None, text="x")

    request = client.created[0]
    assert not chat_v1.Message.pb(request.message).HasField("thread")
    assert request.message_reply_option == REPLY_OPTION.MESSAGE_REPLY_OPTION_UNSPECIFIED


async def test_update_message_sends_text_and_the_video_card_with_the_field_mask() -> None:
    client = FakeChatClient()
    api = GoogleChatApi(lambda: client)

    await api.update_message(name="spaces/S/messages/M1", text="Risposta.", cards_v2=_video_cards())

    message, mask = client.updated[0]
    assert message.name == "spaces/S/messages/M1"
    assert message.text == "Risposta."
    assert list(mask.paths) == ["text", "cards_v2"]
    card = message.cards_v2[0]
    assert card.card_id == "video-sources"
    section = card.card.sections[0]
    assert section.widgets[0].image.image_url == THUMBNAIL
    buttons = section.widgets[2].button_list.buttons
    assert [button.text for button in buttons] == ["Fonte", "Guarda"]
    assert buttons[0].on_click.open_link.url == PERMALINK
    assert buttons[1].on_click.open_link.url == VIDEO


async def test_update_message_without_cards_clears_the_card_field() -> None:
    client = FakeChatClient()
    api = GoogleChatApi(lambda: client)

    await api.update_message(name="spaces/S/messages/M1", text="Solo testo.", cards_v2=[])

    message, mask = client.updated[0]
    assert list(message.cards_v2) == []
    assert list(mask.paths) == ["text", "cards_v2"]


@pytest.mark.parametrize("operation", ["create", "update"])
async def test_google_api_errors_become_chat_api_error_naming_only_the_type(
    operation: str,
) -> None:
    secret = "token ya29.SECRET in the message"
    failure = api_exceptions.PermissionDenied(secret)  # type: ignore[no-untyped-call]
    api = GoogleChatApi(lambda: FakeChatClient(error=failure))

    with pytest.raises(ChatApiError) as raised:
        if operation == "create":
            await api.create_message(space="spaces/S", thread=None, text="x")
        else:
            await api.update_message(name="spaces/S/messages/M1", text="x", cards_v2=[])

    assert str(raised.value) == "PermissionDenied"
    assert secret not in repr(raised.value)


async def test_a_card_the_api_cannot_parse_becomes_chat_api_error() -> None:
    api = GoogleChatApi(lambda: FakeChatClient())
    bad_card = [{"cardId": "x", "card": {"notAField": 1}}]

    with pytest.raises(ChatApiError) as raised:
        await api.update_message(name="spaces/S/messages/M1", text="x", cards_v2=bad_card)

    assert str(raised.value) == "ParseError"


async def test_build_chat_client_uses_app_credentials_with_the_chat_bot_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_default(*, scopes: list[str]) -> tuple[AnonymousCredentials, str]:
        seen["scopes"] = scopes
        return AnonymousCredentials(), "demo-project"  # type: ignore[no-untyped-call]

    monkeypatch.setattr(google.auth, "default", fake_default)

    client = build_chat_client()

    assert seen["scopes"] == [CHAT_BOT_SCOPE]
    assert CHAT_BOT_SCOPE == "https://www.googleapis.com/auth/chat.bot"
    assert isinstance(client, chat_v1.ChatServiceAsyncClient)


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def test_recording_create_message_returns_a_name_under_the_space_and_records_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "chat.jsonl"
    api = RecordingChatApi(path)

    first = await api.create_message(space="spaces/S", thread="spaces/S/threads/T", text="wait")
    second = await api.create_message(space="spaces/S", thread=None, text="again")

    assert first == "spaces/S/messages/rec-1"
    assert second == "spaces/S/messages/rec-2"
    records = _records(path)
    assert [r["op"] for r in records] == ["create", "create"]
    assert records[0]["name"] == first
    assert records[0]["space"] == "spaces/S"
    assert records[0]["thread"] == "spaces/S/threads/T"
    assert records[0]["text"] == "wait"
    assert records[1]["thread"] is None


async def test_recording_update_message_records_name_text_and_cards(tmp_path: Path) -> None:
    path = tmp_path / "chat.jsonl"
    api = RecordingChatApi(path)

    await api.update_message(
        name="spaces/S/messages/rec-1", text="Risposta con è e Fonte.", cards_v2=_video_cards()
    )

    (record,) = _records(path)
    assert record["op"] == "update"
    assert record["name"] == "spaces/S/messages/rec-1"
    assert record["text"] == "Risposta con è e Fonte."
    assert record["cards_v2"][0]["cardId"] == "video-sources"
    assert "è" in path.read_text(encoding="utf-8")  # ensure_ascii=False, UTF-8


async def test_recording_appends_to_an_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "chat.jsonl"
    path.write_text('{"op": "create"}\n', encoding="utf-8")

    await RecordingChatApi(path).create_message(space="spaces/S", thread=None, text="x")

    assert len(_records(path)) == 2


async def test_recording_missing_parent_directory_is_a_chat_api_error_naming_the_type(
    tmp_path: Path,
) -> None:
    api = RecordingChatApi(tmp_path / "missing" / "chat.jsonl")

    with pytest.raises(ChatApiError) as raised:
        await api.create_message(space="spaces/S", thread=None, text="x")
    assert str(raised.value) == "FileNotFoundError"
    assert not (tmp_path / "missing").exists()

    with pytest.raises(ChatApiError) as raised_update:
        await api.update_message(name="spaces/S/messages/rec-1", text="x", cards_v2=[])
    assert str(raised_update.value) == "FileNotFoundError"


async def test_recording_round_trip_of_the_dm_fixture_through_bot_service(
    tmp_path: Path, make_service: ServiceFactory
) -> None:
    path = tmp_path / "chat.jsonl"
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    service = make_service(llm, chat=RecordingChatApi(path))

    await service.handle(load_event("legacy_dm_message"))

    created, updated = _records(path)
    assert created["op"] == "create"
    assert created["space"] == "spaces/AAAAsyntheticDM"
    assert updated["op"] == "update"
    assert updated["name"] == created["name"]
    assert GOOD_DRAFT.answer in updated["text"]
    assert "Fonte: Manuale" in updated["text"]
