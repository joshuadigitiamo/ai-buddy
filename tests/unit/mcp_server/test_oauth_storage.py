"""build_oauth_storage: memory store, and the checks that guard the encrypted Firestore store."""

import pytest
from cryptography.fernet import Fernet

from buddy_mcp.oauth_storage import OAuthStorageError, build_oauth_storage


@pytest.mark.anyio
async def test_memory_store_round_trips_a_value() -> None:
    store = build_oauth_storage("memory")
    await store.put("k", {"v": "x"}, collection="c")
    assert await store.get("k", collection="c") == {"v": "x"}


def test_firestore_without_encryption_key_is_refused() -> None:
    with pytest.raises(OAuthStorageError, match="OAUTH_STORAGE_ENCRYPTION_KEY"):
        build_oauth_storage("firestore", project="demo-ai-buddy", encryption_key=None)


def test_firestore_with_blank_encryption_key_is_refused() -> None:
    with pytest.raises(OAuthStorageError, match="OAUTH_STORAGE_ENCRYPTION_KEY"):
        build_oauth_storage("firestore", project="demo-ai-buddy", encryption_key="  ")


def test_firestore_without_project_is_refused() -> None:
    key = Fernet.generate_key().decode()
    with pytest.raises(OAuthStorageError, match="GOOGLE_CLOUD_PROJECT"):
        build_oauth_storage("firestore", project=None, encryption_key=key)


def test_invalid_fernet_key_is_refused_without_echoing_it() -> None:
    bad = "not-a-fernet-key-sentinel"
    with pytest.raises(OAuthStorageError, match="OAUTH_STORAGE_ENCRYPTION_KEY") as raised:
        build_oauth_storage("firestore", project="demo-ai-buddy", encryption_key=bad)
    assert bad not in str(raised.value)
