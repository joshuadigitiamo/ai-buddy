"""GapRecord rules, InMemoryGapLog and FirestoreGapLog against a fake client (D-10, D-15)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest
from google.cloud import firestore

from buddy_mcp.gaplog import (
    FirestoreGapLog,
    GapRecord,
    GapRecordError,
    InMemoryGapLog,
    gap_document,
)

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)
QUESTION = "Come chiedo un rimborso?"


def _new(question: str = QUESTION, **overrides: Any) -> GapRecord:
    params: dict[str, Any] = {"build_id": "b1", "now": NOW, "ttl_days": 90}
    params.update(overrides)
    return GapRecord.new(question, **params)


def test_new_strips_question_and_sets_utc_timestamps() -> None:
    gap = _new("  Come chiedo un rimborso?  ")
    assert gap.question == QUESTION
    assert gap.created_at == NOW
    assert gap.expire_at == NOW + timedelta(days=90)
    assert gap.build_id == "b1"
    assert gap.tried == ()


def test_new_converts_aware_non_utc_now_to_utc() -> None:
    plus_two = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    gap = _new(now=plus_two)
    assert gap.created_at.utcoffset() == timedelta(0)
    assert gap.created_at == NOW


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_new_rejects_blank_question(question: str) -> None:
    with pytest.raises(GapRecordError):
        _new(question)


def test_new_accepts_2000_characters_and_rejects_2001() -> None:
    assert len(_new("x" * 2000).question) == 2000
    with pytest.raises(GapRecordError):
        _new("x" * 2001)


def test_new_counts_code_points_not_bytes() -> None:
    assert len(_new("è" * 2000).question) == 2000


def test_new_rejects_naive_now() -> None:
    with pytest.raises(GapRecordError):
        _new(now=datetime(2026, 11, 3, 10, 0, 0))


@pytest.mark.parametrize("ttl_days", [0, -1])
def test_new_rejects_ttl_below_one(ttl_days: int) -> None:
    with pytest.raises(GapRecordError):
        _new(ttl_days=ttl_days)


def test_new_accepts_ttl_of_one_day() -> None:
    assert _new(ttl_days=1).expire_at == NOW + timedelta(days=1)


def test_new_caps_tried_entries_and_truncates_each() -> None:
    tried = [f"tool-{n}" for n in range(10)] + ["   ", "y" * 300]
    gap = _new(tried=tried)
    assert len(gap.tried) == 10
    assert all(0 < len(item) <= 200 for item in gap.tried)
    long_gap = _new(tried=["   ", "y" * 300])
    assert long_gap.tried == ("y" * 200,)


def test_errors_never_contain_the_question() -> None:
    secret = "domanda-riservata-" + "z" * 2000
    with pytest.raises(GapRecordError) as too_long:
        _new(secret)
    assert "domanda-riservata" not in str(too_long.value)
    with pytest.raises(GapRecordError) as naive:
        _new("domanda-riservata", now=datetime(2026, 11, 3))
    assert "domanda-riservata" not in str(naive.value)


def test_gap_document_has_exactly_the_six_keys() -> None:
    doc = gap_document(_new(tried=["handbook_search: ferie"]))
    assert set(doc) == {"question", "marker", "created_at", "expire_at", "build_id", "tried"}
    assert doc["marker"] == "nessuna fonte trovata"
    assert doc["tried"] == ["handbook_search: ferie"]


class _FakeRef:
    def __init__(self, doc_id: str, sink: list[tuple[str, dict[str, object]]], name: str) -> None:
        self.id = doc_id
        self._sink = sink
        self._name = name

    async def set(self, data: dict[str, object]) -> None:
        self._sink.append((self._name, data))


class _FakeCollection:
    def __init__(self, name: str, client: "_FakeClient") -> None:
        self._name = name
        self._client = client

    def document(self) -> _FakeRef:
        self._client.issued += 1
        return _FakeRef(f"doc-{self._client.issued}", self._client.written, self._name)


class _FakeClient:
    def __init__(self) -> None:
        self.issued = 0
        self.written: list[tuple[str, dict[str, object]]] = []

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(name, self)


def _factory(client: _FakeClient, calls: list[int]) -> Callable[[], firestore.AsyncClient]:
    def build() -> firestore.AsyncClient:
        calls.append(1)
        return cast(firestore.AsyncClient, client)

    return build


@pytest.mark.anyio
async def test_firestore_gaplog_builds_client_lazily_once_and_writes_the_document() -> None:
    client = _FakeClient()
    calls: list[int] = []
    gaplog = FirestoreGapLog(_factory(client, calls), "gaps-x")
    assert calls == []

    gap = _new()
    first = await gaplog.record(gap)
    second = await gaplog.record(gap)

    assert calls == [1]
    assert (first, second) == ("doc-1", "doc-2")
    assert client.written == [("gaps-x", gap_document(gap)), ("gaps-x", gap_document(gap))]


@pytest.mark.anyio
async def test_in_memory_gaplog_appends_and_returns_distinct_ids() -> None:
    gaplog = InMemoryGapLog()
    first, second = _new(), _new("Altra domanda?")
    ids = [await gaplog.record(first), await gaplog.record(second)]
    assert gaplog.records == [first, second]
    assert len(set(ids)) == 2
