"""Google Chat API adapter skeleton (RED step: names exist, behavior does not)."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

CHAT_BOT_SCOPE: Final = "https://www.googleapis.com/auth/chat.bot"


class ChatApiError(Exception):
    """A Chat API call failed; the message is the exception type name only."""


def build_chat_client() -> Any:
    raise NotImplementedError


class GoogleChatApi:
    def __init__(self, client_factory: Callable[[], Any]) -> None:
        self._client_factory = client_factory

    async def create_message(self, *, space: str, thread: str | None, text: str) -> str:
        return ""

    async def update_message(
        self, *, name: str, text: str, cards_v2: Sequence[Mapping[str, Any]]
    ) -> None:
        return None
