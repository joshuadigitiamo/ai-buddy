"""HTTP intake skeleton (RED step: names exist, behavior does not)."""

from typing import Final

from google.auth.transport import Request
from starlette.applications import Starlette

from buddy_bot.ports import EventHandler

ACK_SECONDS: Final = 25.0
MAX_BODY_BYTES: Final = 1_048_576


class ChatTokenVerifier:
    def __init__(self, audience: str, issuer_email: str, *, request: Request | None = None) -> None:
        self._request = request

    async def verify(self, token: str) -> bool:
        return False


def build_http_app(
    handler: EventHandler,
    verifier: ChatTokenVerifier,
    *,
    ack_seconds: float = ACK_SECONDS,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> Starlette:
    return Starlette()


class HttpIntake:
    def __init__(
        self, verifier: ChatTokenVerifier, *, host: str, port: int, ack_seconds: float = ACK_SECONDS
    ) -> None:
        self._verifier = verifier

    async def run(self, handler: EventHandler) -> None:
        return None
