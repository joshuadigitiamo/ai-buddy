"""Google Chat API adapter (D-09): the placeholder is created in the event's thread, then patched.

Authentication is the app's own: Application Default Credentials with the chat.bot scope. The
client is built lazily, on first use inside the running loop. Errors surface as ChatApiError
carrying the exception type name only, so no token or response text can reach a log (BOT-11).
render.py emits Chat REST JSON (cardsV2); this adapter converts it to the GAPIC message.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Protocol

import google.auth
from google.api_core.exceptions import GoogleAPIError
from google.apps import chat_v1
from google.protobuf import field_mask_pb2, json_format

CHAT_BOT_SCOPE: Final = "https://www.googleapis.com/auth/chat.bot"
_UPDATE_MASK: Final = ("text", "cards_v2")


class ChatApiError(Exception):
    """A Chat API call failed; the message is the exception type name only."""


class ChatClient(Protocol):
    """The two calls of `chat_v1.ChatServiceAsyncClient` this adapter makes."""

    async def create_message(self, *, request: chat_v1.CreateMessageRequest) -> chat_v1.Message: ...

    async def update_message(
        self, *, message: chat_v1.Message, update_mask: field_mask_pb2.FieldMask
    ) -> chat_v1.Message: ...


def build_chat_client() -> chat_v1.ChatServiceAsyncClient:
    """An async Chat client acting as the app (service account), scope chat.bot."""
    credentials, _ = google.auth.default(scopes=[CHAT_BOT_SCOPE])
    return chat_v1.ChatServiceAsyncClient(credentials=credentials)


def _to_message(name: str, text: str, cards_v2: Sequence[Mapping[str, Any]]) -> chat_v1.Message:
    """Convert the REST JSON of render.py into the GAPIC Message through its protobuf."""
    pb = chat_v1.Message.pb(chat_v1.Message())
    json_format.ParseDict({"name": name, "text": text, "cardsV2": list(cards_v2)}, pb)
    message: chat_v1.Message = chat_v1.Message.wrap(pb)
    return message


class GoogleChatApi:
    """ChatApi port over Google Chat."""

    def __init__(self, client_factory: Callable[[], ChatClient]) -> None:
        self._client_factory = client_factory
        self._client: ChatClient | None = None

    def _chat(self) -> ChatClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    async def create_message(self, *, space: str, thread: str | None, text: str) -> str:
        message = chat_v1.Message(text=text)
        option = chat_v1.CreateMessageRequest.MessageReplyOption.MESSAGE_REPLY_OPTION_UNSPECIFIED
        if thread is not None:
            message.thread = chat_v1.Thread(name=thread)
            option = (
                chat_v1.CreateMessageRequest.MessageReplyOption.REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD
            )
        request = chat_v1.CreateMessageRequest(
            parent=space, message=message, message_reply_option=option
        )
        try:
            created = await self._chat().create_message(request=request)
        except GoogleAPIError as exc:
            raise ChatApiError(type(exc).__name__) from None
        return str(created.name)

    async def update_message(
        self, *, name: str, text: str, cards_v2: Sequence[Mapping[str, Any]]
    ) -> None:
        try:
            message = _to_message(name, text, cards_v2)
            await self._chat().update_message(
                message=message, update_mask=field_mask_pb2.FieldMask(paths=list(_UPDATE_MASK))
            )
        except (GoogleAPIError, json_format.ParseError) as exc:
            raise ChatApiError(type(exc).__name__) from None


class RecordingChatApi:
    """ChatApi port that appends every call to a JSON-lines file instead of calling Chat.

    Local smoke adapter: BotSettings refuses it outside DEPLOY_ENV=local. It gives compose and
    kind a hermetic chat round trip through the real composition root (Chat has no emulator).
    The parent directory must exist; nothing is created. Errors surface as ChatApiError with the
    exception type name only, the same shape as GoogleChatApi.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._created = 0

    def _append(self, record: Mapping[str, Any]) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
        except OSError as exc:
            raise ChatApiError(type(exc).__name__) from None

    async def create_message(self, *, space: str, thread: str | None, text: str) -> str:
        self._created += 1
        name = f"{space}/messages/rec-{self._created}"
        self._append(
            {
                "op": "create",
                "name": name,
                "space": space,
                "thread": thread,
                "text": text,
                "cards_v2": [],
            }
        )
        return name

    async def update_message(
        self, *, name: str, text: str, cards_v2: Sequence[Mapping[str, Any]]
    ) -> None:
        self._append(
            {
                "op": "update",
                "name": name,
                "space": None,
                "thread": None,
                "text": text,
                "cards_v2": list(cards_v2),
            }
        )
