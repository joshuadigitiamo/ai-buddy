"""Gap log port and adapters (D-15).

Records question, timestamps, marker and build id; never a caller identity (D-10).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from google.cloud import firestore

from buddy_mcp.models import GAP_MARKER


@dataclass(frozen=True, slots=True)
class GapRecord:
    """One unanswered question. Carries no caller identity by construction (D-10)."""

    question: str
    created_at: datetime
    expire_at: datetime
    build_id: str
    tried: tuple[str, ...] = ()


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
