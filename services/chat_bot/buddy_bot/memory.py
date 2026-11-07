"""Thread memory adapters (D-10, D-11, BOT-11).

One Firestore document per conversation, holding only the last N question/answer pairs.
Safeguards, all structural:

- the document id is HMAC-SHA256(THREAD_KEY_SECRET, key source), so no raw space, thread or
  user id is ever stored (the caller picks the key source: the space name for a DM space,
  the thread name for a room);
- the document shape is exactly ``turns``, ``updated_at`` and ``expire_at``; there is no field
  that could hold a sender identity;
- a document expires 24 h after its last write; the read side treats an expired document as
  empty, so the guarantee does not depend on the Firestore TTL policy being applied (Phase 4).

Concurrent runs in one conversation may lose a turn (read-modify-write, last write wins);
accepted for the single-user scope, and it can only drop history, never add an identity.
"""

import hashlib
import hmac
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final

from google.cloud import firestore

from buddy_bot.ports import Turn

MEMORY_TTL: Final = timedelta(hours=24)
MAX_QUESTION_CHARS: Final = 2000
MAX_ANSWER_CHARS: Final = 4000

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def thread_key(secret: str, key_source: str) -> str:
    """Pseudonymous document id: HMAC-SHA256 over the UTF-8 key source, lowercase hex."""
    digest = hmac.new(secret.encode("utf-8"), key_source.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def _aware_utc(value: datetime, message: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(message)
    return value.astimezone(UTC)


def memory_document(turns: Sequence[Turn], *, now: datetime) -> dict[str, object]:
    """The exact stored document: three keys, none of them an identity."""
    stamp = _aware_utc(now, "now must be a timezone-aware datetime")
    return {
        "turns": [
            {"q": turn.question[:MAX_QUESTION_CHARS], "a": turn.answer[:MAX_ANSWER_CHARS]}
            for turn in turns
        ],
        "updated_at": stamp,
        "expire_at": stamp + MEMORY_TTL,
    }


def live_turns(data: Mapping[str, object] | None, now: datetime) -> list[Turn]:
    """Turns of a stored document; a missing, malformed or expired document has none."""
    if data is None:
        return []
    expire_at = data.get("expire_at")
    if not isinstance(expire_at, datetime) or expire_at <= now:
        return []
    raw = data.get("turns")
    if not isinstance(raw, list):
        return []
    return [Turn(question=str(t["q"]), answer=str(t["a"])) for t in raw if isinstance(t, Mapping)]


def next_document(
    existing: Mapping[str, object] | None, turn: Turn, *, now: datetime, max_turns: int
) -> dict[str, object]:
    """The document after appending a turn: live turns plus the new one, last max_turns kept."""
    kept = [*live_turns(existing, now), turn][-max_turns:]
    return memory_document(kept, now=now)


def _tail(turns: list[Turn], n: int) -> list[Turn]:
    return turns[-n:] if n > 0 else []


def _check_max_turns(max_turns: int) -> int:
    if max_turns < 1:
        raise ValueError("max_turns must be at least 1")
    return max_turns


def _read_clock(clock: Clock) -> datetime:
    return _aware_utc(clock(), "clock must return a timezone-aware datetime")


class FirestoreThreadMemory:
    """ThreadMemory on a Firestore collection; the client is created on the first call.

    gRPC aio channels bind to the event loop they are created on, and the composition root
    builds adapters before the loop runs, so the factory is called lazily (as FirestoreGapLog).
    """

    def __init__(
        self,
        client_factory: Callable[[], firestore.AsyncClient],
        *,
        secret: str,
        collection: str,
        max_turns: int,
        clock: Clock = utc_now,
    ) -> None:
        self._client_factory = client_factory
        self._secret = secret
        self._collection = collection
        self._max_turns = _check_max_turns(max_turns)
        self._clock = clock
        self._client: firestore.AsyncClient | None = None

    def _reference(self, key_source: str) -> firestore.AsyncDocumentReference:
        if self._client is None:
            self._client = self._client_factory()
        return self._client.collection(self._collection).document(
            thread_key(self._secret, key_source)
        )

    async def recent(self, key_source: str, n: int) -> list[Turn]:
        if not key_source.strip():
            return []
        now = _read_clock(self._clock)
        snapshot = await self._reference(key_source).get()
        data = snapshot.to_dict() if snapshot.exists else None
        return _tail(live_turns(data, now), n)

    async def append(self, key_source: str, turn: Turn) -> None:
        if not key_source.strip():
            return
        now = _read_clock(self._clock)
        reference = self._reference(key_source)
        snapshot = await reference.get()
        data = snapshot.to_dict() if snapshot.exists else None
        await reference.set(next_document(data, turn, now=now, max_turns=self._max_turns))
