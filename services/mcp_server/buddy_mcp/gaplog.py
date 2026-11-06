"""Gap log port and adapters (D-15).

Records question, timestamps, marker and build id; never a caller identity (D-10).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

from google.cloud import firestore

from buddy_mcp.models import GAP_MARKER

MAX_QUESTION_CHARS: Final = 2000
MAX_TRIED_ITEMS: Final = 10
MAX_TRIED_CHARS: Final = 200


class GapRecordError(ValueError):
    """A gap record broke a rule; messages never carry the question text."""


@dataclass(frozen=True, slots=True)
class GapRecord:
    """One unanswered question. Carries no caller identity by construction (D-10)."""

    question: str
    created_at: datetime
    expire_at: datetime
    build_id: str
    tried: tuple[str, ...] = ()

    @classmethod
    def new(
        cls,
        question: str,
        *,
        build_id: str,
        now: datetime,
        ttl_days: int,
        tried: Sequence[str] = (),
    ) -> "GapRecord":
        text = question.strip()
        if not text:
            raise GapRecordError("question must not be empty")
        if len(text) > MAX_QUESTION_CHARS:
            raise GapRecordError(f"question longer than {MAX_QUESTION_CHARS} characters")
        if now.tzinfo is None or now.utcoffset() is None:
            raise GapRecordError("now must be timezone-aware")
        if ttl_days < 1:
            raise GapRecordError("ttl_days must be at least 1")
        created_at = now.astimezone(UTC)
        kept = tuple(item[:MAX_TRIED_CHARS] for item in (t.strip() for t in tried) if item)
        return cls(
            question=text,
            created_at=created_at,
            expire_at=created_at + timedelta(days=ttl_days),
            build_id=build_id,
            tried=kept[:MAX_TRIED_ITEMS],
        )


def gap_document(gap: GapRecord) -> dict[str, object]:
    """The exact Firestore document for a gap: six keys, none of them an identity."""
    return {
        "question": gap.question,
        "marker": GAP_MARKER,
        "created_at": gap.created_at,
        "expire_at": gap.expire_at,
        "build_id": gap.build_id,
        "tried": list(gap.tried),
    }


class GapLog(Protocol):
    """Where unanswered questions are recorded; adapters hide the storage."""

    async def record(self, gap: GapRecord) -> str: ...


class FirestoreGapLog:
    """GapLog on a Firestore collection; the client is created on the first record call.

    gRPC aio channels bind to the event loop they are created on, and the composition
    root builds adapters before the server loop starts, so the factory runs lazily.
    """

    def __init__(
        self,
        client_factory: Callable[[], firestore.AsyncClient],
        collection: str = "gaps",
    ) -> None:
        self._client_factory = client_factory
        self._collection = collection
        self._client: firestore.AsyncClient | None = None

    async def record(self, gap: GapRecord) -> str:
        if self._client is None:
            self._client = self._client_factory()
        ref = self._client.collection(self._collection).document()
        await ref.set(gap_document(gap))
        return str(ref.id)


class InMemoryGapLog:
    """Test double beside the real adapter (D-15): keeps records in a list."""

    def __init__(self) -> None:
        self.records: list[GapRecord] = []

    async def record(self, gap: GapRecord) -> str:
        self.records.append(gap)
        return f"memory-{len(self.records)}"
