"""OAuth proxy state store (RED stub: always memory, no checks)."""

from typing import Literal

from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.memory import MemoryStore


class OAuthStorageError(ValueError):
    """The OAuth store could not be built from the given settings."""


def build_oauth_storage(
    kind: Literal["memory", "firestore"],
    *,
    project: str | None = None,
    encryption_key: str | None = None,
    collection: str = "oauth_state",
) -> AsyncKeyValue:
    return MemoryStore()
