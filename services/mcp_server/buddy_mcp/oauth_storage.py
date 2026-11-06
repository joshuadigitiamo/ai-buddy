"""OAuth proxy state store: memory (default, lost on restart) or Fernet-encrypted Firestore.

The Firestore store survives scale-to-zero. There is no file-backed option (MCP-01).
"""

from typing import Literal

from cryptography.fernet import Fernet
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.firestore import (
    FirestoreStore,
    FirestoreV1CollectionSanitizationStrategy,
    FirestoreV1KeySanitizationStrategy,
)
from key_value.aio.stores.memory import MemoryStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper


class OAuthStorageError(ValueError):
    """The OAuth store could not be built; messages name settings, never their values."""


def build_oauth_storage(
    kind: Literal["memory", "firestore"],
    *,
    project: str | None = None,
    encryption_key: str | None = None,
    collection: str = "oauth_state",
) -> AsyncKeyValue:
    """Return the client_storage for the OAuth proxy.

    The Firestore store takes its Fernet key from the caller (env only) and is always
    wrapped in encryption. The underlying google-cloud-firestore client opens its gRPC
    channel on first use, inside the running event loop, so building the store before the
    server loop starts is safe.
    """
    if kind == "memory":
        return MemoryStore()
    if kind != "firestore":
        raise OAuthStorageError("unknown OAuth storage kind")
    if not encryption_key or not encryption_key.strip():
        raise OAuthStorageError("OAUTH_STORAGE_ENCRYPTION_KEY is required for the Firestore store")
    if not project or not project.strip():
        raise OAuthStorageError("GOOGLE_CLOUD_PROJECT is required for the Firestore store")
    try:
        fernet = Fernet(encryption_key.strip().encode())
    except (ValueError, TypeError):
        raise OAuthStorageError("OAUTH_STORAGE_ENCRYPTION_KEY is not a valid Fernet key") from None
    firestore_store = FirestoreStore(
        project=project,
        default_collection=collection,
        key_sanitization_strategy=FirestoreV1KeySanitizationStrategy(),
        collection_sanitization_strategy=FirestoreV1CollectionSanitizationStrategy(),
    )
    # A value that fails to decrypt (rotated key) reads as missing, like fastmcp's own default
    # store: the OAuth client re-registers instead of the server failing.
    return FernetEncryptionWrapper(
        key_value=firestore_store, fernet=fernet, raise_on_decryption_error=False
    )
