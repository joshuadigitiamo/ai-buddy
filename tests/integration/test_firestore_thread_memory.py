"""BOT-11 on the Firestore emulator: the stored memory document has no place for an identity."""

import os
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from google.cloud import firestore

from buddy_bot.memory import FirestoreThreadMemory, thread_key
from buddy_bot.ports import Turn

pytestmark = [
    pytest.mark.firestore,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not os.environ.get("FIRESTORE_EMULATOR_HOST"),
        reason="needs the Firestore emulator: run ./run-unit-tests.sh --emulator",
    ),
]

IDENTITY_KEY = re.compile(r"(?i)user|email|ip|session|client|sub")
SECRET = "synthetic-test-secret-0123456789-abcdef"  # 40 characters, test only
SOURCE = "spaces/AAAAsyntheticDM"
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)


def _memory(
    factory: Callable[[], firestore.AsyncClient],
    collection: str,
    *,
    max_turns: int = 3,
    now: Callable[[], datetime] = lambda: NOW,
) -> FirestoreThreadMemory:
    return FirestoreThreadMemory(
        factory, secret=SECRET, collection=collection, max_turns=max_turns, clock=now
    )


async def _document(
    factory: Callable[[], firestore.AsyncClient], collection: str
) -> tuple[str, dict[str, object]]:
    reader = factory()
    try:
        docs = [d async for d in reader.collection(collection).stream()]
        assert len(docs) == 1
        data = docs[0].to_dict()
        assert data is not None
        await reader.collection(collection).document(docs[0].id).delete()
        return str(docs[0].id), data
    finally:
        reader.close()  # type: ignore[no-untyped-call]  # sync close, untyped in google-cloud-core


async def test_turns_round_trip_under_hmac_key_with_only_three_fields(
    firestore_client_factory: Callable[[], firestore.AsyncClient], unique_collection: str
) -> None:
    memory = _memory(firestore_client_factory, unique_collection)
    first, second = Turn("Come chiedo le ferie?", "Scrivi a HR."), Turn("E la malattia?", "Idem.")

    await memory.append(SOURCE, first)
    await memory.append(SOURCE, second)

    assert await memory.recent(SOURCE, 3) == [first, second]
    assert await memory.recent(SOURCE, 1) == [second]
    doc_id, data = await _document(firestore_client_factory, unique_collection)
    assert doc_id == thread_key(SECRET, SOURCE)
    assert set(data) == {"turns", "updated_at", "expire_at"}
    turns = data["turns"]
    assert isinstance(turns, list)
    assert [set(turn) for turn in turns] == [{"q", "a"}, {"q", "a"}]
    assert not [key for key in data if IDENTITY_KEY.search(key)]
    assert "AAAAsyntheticDM" not in repr(data)
    assert "AAAAsyntheticDM" not in doc_id
    assert data["expire_at"] - data["updated_at"] == timedelta(hours=24)  # type: ignore[operator]


async def test_only_the_last_max_turns_are_kept(
    firestore_client_factory: Callable[[], firestore.AsyncClient], unique_collection: str
) -> None:
    memory = _memory(firestore_client_factory, unique_collection, max_turns=2)
    turns = [Turn(f"q{i}", f"a{i}") for i in range(3)]

    for turn in turns:
        await memory.append(SOURCE, turn)

    assert await memory.recent(SOURCE, 10) == turns[1:]
    _, data = await _document(firestore_client_factory, unique_collection)
    assert data["turns"] == [{"q": "q1", "a": "a1"}, {"q": "q2", "a": "a2"}]


async def test_an_expired_document_reads_empty(
    firestore_client_factory: Callable[[], firestore.AsyncClient], unique_collection: str
) -> None:
    clock = {"now": NOW}
    memory = _memory(firestore_client_factory, unique_collection, now=lambda: clock["now"])
    await memory.append(SOURCE, Turn("q", "a"))

    clock["now"] = NOW + timedelta(hours=24)

    assert await memory.recent(SOURCE, 3) == []
    await _document(firestore_client_factory, unique_collection)
