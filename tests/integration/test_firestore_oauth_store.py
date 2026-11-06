"""OAuth state store on the Firestore emulator: round trip, ciphertext at rest (user decision 1)."""

import os
import uuid
from collections.abc import Callable

import pytest
from cryptography.fernet import Fernet
from google.cloud import firestore

from buddy_mcp.oauth_storage import build_oauth_storage

pytestmark = [
    pytest.mark.firestore,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not os.environ.get("FIRESTORE_EMULATOR_HOST"),
        reason="needs the Firestore emulator: run ./run-unit-tests.sh --emulator",
    ),
]

SENTINEL = "sentinel-oauth-value"


async def _all_documents_text(client: firestore.AsyncClient) -> list[str]:
    texts: list[str] = []
    async for collection in client.collections():
        async for doc in collection.stream():
            texts.append(repr(doc.to_dict()))
    return texts


async def test_encrypted_store_round_trips_and_stores_no_plaintext(
    firestore_project: str, firestore_client_factory: Callable[[], firestore.AsyncClient]
) -> None:
    collection = f"oauth-test-{uuid.uuid4().hex}"
    # Built outside the running loop on purpose: the store must not bind a loop at construction.
    store = build_oauth_storage(
        "firestore",
        project=firestore_project,
        encryption_key=Fernet.generate_key().decode(),
        collection=collection,
    )
    key = f"key-{uuid.uuid4().hex}"

    await store.put(key, {"token": SENTINEL})

    assert await store.get(key) == {"token": SENTINEL}
    reader = firestore_client_factory()
    try:
        texts = await _all_documents_text(reader)
        assert texts, "the emulator holds at least the stored document"
        assert not [t for t in texts if SENTINEL in t]
    finally:
        await store.delete(key)
        reader.close()  # type: ignore[no-untyped-call]  # sync close, untyped in google-cloud-core


async def test_wrong_key_does_not_read_the_value(
    firestore_project: str,
) -> None:
    collection = f"oauth-test-{uuid.uuid4().hex}"
    key = f"key-{uuid.uuid4().hex}"
    writer = build_oauth_storage(
        "firestore",
        project=firestore_project,
        encryption_key=Fernet.generate_key().decode(),
        collection=collection,
    )
    other = build_oauth_storage(
        "firestore",
        project=firestore_project,
        encryption_key=Fernet.generate_key().decode(),
        collection=collection,
    )
    await writer.put(key, {"token": SENTINEL})
    try:
        assert await other.get(key) is None
    finally:
        await writer.delete(key)
