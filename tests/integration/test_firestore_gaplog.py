"""MCP-05 on the Firestore emulator: a gap document has the D-10 fields and no identity."""

import os
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from google.cloud import firestore

from buddy_mcp.gaplog import FirestoreGapLog, GapRecord

pytestmark = [
    pytest.mark.firestore,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not os.environ.get("FIRESTORE_EMULATOR_HOST"),
        reason="needs the Firestore emulator: run ./run-unit-tests.sh --emulator",
    ),
]

IDENTITY_KEY = re.compile(r"(?i)user|email|ip|session|client|sub")


async def test_record_writes_one_gap_document(
    firestore_client_factory: Callable[[], firestore.AsyncClient], unique_collection: str
) -> None:
    created = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
    gap = GapRecord(
        question="Domanda sintetica di prova?",
        created_at=created,
        expire_at=created + timedelta(days=90),
        build_id="build-test",
        tried=("handbook_search: ferie",),
    )
    gaplog = FirestoreGapLog(firestore_client_factory, unique_collection)

    doc_id = await gaplog.record(gap)

    reader = firestore_client_factory()
    try:
        docs = [d async for d in reader.collection(unique_collection).stream()]
        assert [d.id for d in docs] == [doc_id]
        data = docs[0].to_dict()
        assert data is not None
        assert set(data) == {"question", "marker", "created_at", "expire_at", "build_id", "tried"}
        assert data["marker"] == "nessuna fonte trovata"
        assert data["question"] == "Domanda sintetica di prova?"
        assert data["build_id"] == "build-test"
        assert data["tried"] == ["handbook_search: ferie"]
        assert data["expire_at"] - data["created_at"] == timedelta(days=90)
        assert not [key for key in data if IDENTITY_KEY.search(key)]
        await reader.collection(unique_collection).document(doc_id).delete()
    finally:
        reader.close()  # type: ignore[no-untyped-call]  # sync close, untyped in google-cloud-core
