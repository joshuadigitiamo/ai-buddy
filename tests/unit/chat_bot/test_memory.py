"""Thread memory rules (D-10, D-11, BOT-11): key, cap, expiry, text caps, lazy Firestore client."""

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from google.cloud import firestore

from buddy_bot.memory import (
    MAX_ANSWER_CHARS,
    MAX_QUESTION_CHARS,
    MEMORY_TTL,
    FirestoreThreadMemory,
    InMemoryThreadMemory,
    memory_document,
    thread_key,
)
from buddy_bot.ports import Turn

pytestmark = pytest.mark.anyio

SECRET = "s" * 40
SOURCE = "spaces/AAAAsyntheticDM"
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
HEX64 = re.compile(r"[0-9a-f]{64}")


class _Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _Document:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self.id = doc_id

    async def get(self) -> _Snapshot:
        return _Snapshot(self._store.get(self.id))

    async def set(self, data: dict[str, Any]) -> None:
        self._store[self.id] = data


class _Collection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _Document:
        return _Document(self._store, doc_id)


class _FakeClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> _Collection:
        return _Collection(self.collections.setdefault(name, {}))


class _Factory:
    def __init__(self) -> None:
        self.client = _FakeClient()
        self.calls = 0

    def __call__(self) -> firestore.AsyncClient:
        self.calls += 1
        return cast(firestore.AsyncClient, self.client)


def _in_memory(clock: _Clock | None = None, *, max_turns: int = 3) -> InMemoryThreadMemory:
    return InMemoryThreadMemory(secret=SECRET, max_turns=max_turns, clock=clock or _Clock())


def _firestore(
    factory: _Factory, clock: _Clock | None = None, *, max_turns: int = 3
) -> FirestoreThreadMemory:
    return FirestoreThreadMemory(
        factory,
        secret=SECRET,
        collection="thread_memory",
        max_turns=max_turns,
        clock=clock or _Clock(),
    )


def test_thread_key_is_64_lowercase_hex_and_depends_on_source_and_secret() -> None:
    key = thread_key(SECRET, "spaces/A")
    assert HEX64.fullmatch(key)
    assert key != thread_key(SECRET, "spaces/B")
    assert key != thread_key("t" * 40, "spaces/A")


def test_thread_key_hashes_the_utf8_bytes_of_the_source() -> None:
    source = "spaces/città-è"
    expected = hmac.new(SECRET.encode(), source.encode("utf-8"), hashlib.sha256).hexdigest()
    assert thread_key(SECRET, source) == expected


async def test_in_memory_keeps_the_last_max_turns_oldest_first() -> None:
    twin = _in_memory(max_turns=3)
    turns = [Turn(f"q{i}", f"a{i}") for i in range(4)]
    for turn in turns:
        await twin.append(SOURCE, turn)

    assert await twin.recent(SOURCE, 10) == turns[1:]
    assert await twin.recent(SOURCE, 1) == [turns[3]]
    assert await twin.recent(SOURCE, 0) == []
    assert list(twin.documents) == [thread_key(SECRET, SOURCE)]
    assert SOURCE not in repr(twin.documents)


async def test_in_memory_reads_empty_after_expiry_and_append_starts_fresh() -> None:
    clock = _Clock()
    twin = _in_memory(clock)
    await twin.append(SOURCE, Turn("old", "old"))

    clock.now = NOW + MEMORY_TTL - timedelta(seconds=1)
    assert await twin.recent(SOURCE, 3) == [Turn("old", "old")]

    clock.now = NOW + MEMORY_TTL
    assert await twin.recent(SOURCE, 3) == []
    await twin.append(SOURCE, Turn("new", "new"))
    assert await twin.recent(SOURCE, 3) == [Turn("new", "new")]


async def test_append_refreshes_the_expiry_window() -> None:
    clock = _Clock()
    twin = _in_memory(clock)
    await twin.append(SOURCE, Turn("a", "a"))
    clock.now = NOW + timedelta(hours=23)
    await twin.append(SOURCE, Turn("b", "b"))

    clock.now = NOW + timedelta(hours=40)

    assert await twin.recent(SOURCE, 3) == [Turn("a", "a"), Turn("b", "b")]


async def test_question_and_answer_are_stored_truncated() -> None:
    twin = _in_memory()
    await twin.append(SOURCE, Turn("q" * (MAX_QUESTION_CHARS + 50), "a" * (MAX_ANSWER_CHARS + 50)))

    [turn] = await twin.recent(SOURCE, 1)

    assert (len(turn.question), len(turn.answer)) == (MAX_QUESTION_CHARS, MAX_ANSWER_CHARS)


async def test_blank_key_source_reads_empty_and_stores_nothing() -> None:
    twin = _in_memory()
    factory = _Factory()
    remote = _firestore(factory)

    await twin.append("  ", Turn("q", "a"))
    await remote.append("", Turn("q", "a"))

    assert await twin.recent("  ", 3) == []
    assert await remote.recent("\n", 3) == []
    assert twin.documents == {}
    assert factory.calls == 0


async def test_firestore_client_is_created_on_the_first_call_only() -> None:
    factory = _Factory()
    remote = _firestore(factory)
    assert factory.calls == 0

    assert await remote.recent(SOURCE, 3) == []
    await remote.append(SOURCE, Turn("q", "a"))

    assert factory.calls == 1


async def test_firestore_writes_exactly_three_keys_under_the_hmac_id() -> None:
    factory = _Factory()
    remote = _firestore(factory)
    await remote.append(SOURCE, Turn("Come chiedo le ferie?", "Scrivi a HR."))

    assert await remote.recent(SOURCE, 3) == [Turn("Come chiedo le ferie?", "Scrivi a HR.")]
    [(doc_id, data)] = factory.client.collections["thread_memory"].items()
    assert doc_id == thread_key(SECRET, SOURCE)
    assert set(data) == {"turns", "updated_at", "expire_at"}
    assert data["turns"] == [{"q": "Come chiedo le ferie?", "a": "Scrivi a HR."}]
    assert data["expire_at"] - data["updated_at"] == timedelta(hours=24)


async def test_firestore_keeps_the_last_max_turns_and_ignores_an_expired_document() -> None:
    factory = _Factory()
    clock = _Clock()
    remote = _firestore(factory, clock, max_turns=2)
    for i in range(3):
        await remote.append(SOURCE, Turn(f"q{i}", f"a{i}"))
    assert await remote.recent(SOURCE, 10) == [Turn("q1", "a1"), Turn("q2", "a2")]

    clock.now = NOW + MEMORY_TTL
    assert await remote.recent(SOURCE, 10) == []
    await remote.append(SOURCE, Turn("q9", "a9"))
    assert await remote.recent(SOURCE, 10) == [Turn("q9", "a9")]


async def test_a_naive_clock_is_rejected() -> None:
    naive = datetime(2026, 11, 3, 10, 0)
    for adapter in (_in_memory(_Clock(naive)), _firestore(_Factory(), _Clock(naive))):
        with pytest.raises(ValueError, match="timezone-aware"):
            await adapter.append(SOURCE, Turn("q", "a"))
        with pytest.raises(ValueError, match="timezone-aware"):
            await adapter.recent(SOURCE, 1)


def test_memory_document_rejects_a_naive_now() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        memory_document([], now=datetime(2026, 11, 3, 10, 0))


def test_max_turns_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_turns"):
        _in_memory(max_turns=0)
    with pytest.raises(ValueError, match="max_turns"):
        _firestore(_Factory(), max_turns=0)


async def test_a_malformed_stored_document_reads_empty() -> None:
    factory = _Factory()
    remote = _firestore(factory)
    store = factory.client.collection("thread_memory")._store
    doc_id = thread_key(SECRET, SOURCE)
    for bad in (
        {"turns": [{"q": "q", "a": "a"}], "updated_at": NOW},
        {"turns": "oops", "updated_at": NOW, "expire_at": NOW + MEMORY_TTL},
        {"turns": ["oops"], "updated_at": NOW, "expire_at": NOW + MEMORY_TTL},
    ):
        store[doc_id] = bad
        assert await remote.recent(SOURCE, 3) == []
