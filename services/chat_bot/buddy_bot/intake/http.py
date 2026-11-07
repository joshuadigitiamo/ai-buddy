"""HTTP intake (BOT-02): the Cloud Run transport, with Google Chat request verification.

Chat signs every HTTP request with a Google ID token (RS256). Only the "HTTP endpoint URL"
audience mode is supported (RESEARCH Pitfall 7): the token's `aud` must equal CHAT_JWT_AUDIENCE
exactly and its `email` must equal CHAT_JWT_ISSUER_EMAIL. The token is verified and discarded,
never forwarded. No route, log line or error text carries the token, claims or body (BOT-11).

Answer window (03-01 decision http_ack b): the endpoint awaits the run for up to ACK_SECONDS and
then returns `{}`; a slower run keeps going in a task the app keeps referenced, and still patches
the placeholder. ack_seconds 0 returns at once (option a).
"""

import asyncio
import json
import logging
from collections.abc import Mapping
from typing import Any, Final

import uvicorn
from google.auth.transport import Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from starlette.applications import Starlette
from starlette.requests import Request as HttpRequest
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from buddy_bot.ports import EventHandler

ACK_SECONDS: Final = 25.0
MAX_BODY_BYTES: Final = 1_048_576

_LOGGER = logging.getLogger("buddy_bot")


class ChatTokenVerifier:
    """Accepts a bearer token only when Google signed it for this endpoint and for Chat."""

    def __init__(self, audience: str, issuer_email: str, *, request: Request | None = None) -> None:
        if not audience:
            # An empty audience would make google-auth skip the audience check altogether.
            raise ValueError("audience must not be empty")
        self._audience = audience
        self._issuer_email = issuer_email.strip().lower()
        self._request: Request = request if request is not None else google_requests.Request()

    async def verify(self, token: str) -> bool:
        try:
            claims = await asyncio.to_thread(self._decode, token)
        except Exception:
            return False
        email = claims.get("email")
        if not isinstance(email, str) or email.lower() != self._issuer_email:
            return False
        return str(claims.get("email_verified", True)).lower() != "false"

    def _decode(self, token: str) -> Mapping[str, Any]:
        # google-auth leaves this function unannotated.
        claims: Mapping[str, Any] = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token, self._request, audience=self._audience
        )
        return claims


def _bearer_token(request: HttpRequest) -> str | None:
    parts = request.headers.get("authorization", "").split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def _read_body(request: HttpRequest, limit: int) -> bytes | None:
    """The request body, or None when it exceeds `limit` (declared or actually streamed)."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return None
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            return None
    return bytes(body)


async def _run_handler(handler: EventHandler, event: Mapping[str, Any]) -> None:
    try:
        await handler(event)
    except Exception as exc:
        _LOGGER.error("http intake handler failed: %s", type(exc).__name__)


def build_http_app(
    handler: EventHandler,
    verifier: ChatTokenVerifier,
    *,
    ack_seconds: float = ACK_SECONDS,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> Starlette:
    """The ASGI app: `POST /` only; everything else is Starlette's 404 or 405."""
    tasks: set[asyncio.Task[None]] = set()

    async def receive(request: HttpRequest) -> Response:
        token = _bearer_token(request)
        if token is None or not await verifier.verify(token):
            _LOGGER.warning("http intake rejected a request: unauthorized")
            return Response(status_code=401)
        body = await _read_body(request, max_body_bytes)
        if body is None:
            _LOGGER.warning("http intake rejected a request: body too large")
            return Response(status_code=413)
        try:
            event = json.loads(body)
        except ValueError:
            event = None
        if not isinstance(event, dict):
            _LOGGER.warning("http intake rejected a request: body is not a JSON object")
            return Response(status_code=400)
        task = asyncio.create_task(_run_handler(handler, event))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        if ack_seconds > 0:
            await asyncio.wait({task}, timeout=ack_seconds)
        return JSONResponse({})

    app = Starlette(routes=[Route("/", receive, methods=["POST"])])
    app.state.tasks = tasks
    return app


class HttpIntake:
    """IntakePort over HTTP: serves `build_http_app` with uvicorn until cancelled."""

    def __init__(
        self,
        verifier: ChatTokenVerifier,
        *,
        host: str,
        port: int,
        ack_seconds: float = ACK_SECONDS,
    ) -> None:
        self._verifier = verifier
        self._host = host
        self._port = port
        self._ack_seconds = ack_seconds

    def uvicorn_config(self, handler: EventHandler) -> uvicorn.Config:
        app = build_http_app(handler, self._verifier, ack_seconds=self._ack_seconds)
        # Access logging stays off: it would record client IPs and paths (BOT-11).
        return uvicorn.Config(
            app, host=self._host, port=self._port, access_log=False, log_level="warning"
        )

    async def run(self, handler: EventHandler) -> None:
        server = uvicorn.Server(self.uvicorn_config(handler))
        serving = asyncio.ensure_future(server.serve())
        try:
            await asyncio.shield(serving)
        except asyncio.CancelledError:
            server.should_exit = True
            await serving
            raise
