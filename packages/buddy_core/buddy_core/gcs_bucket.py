"""BucketPort over google-cloud-storage with Application Default Credentials (D-06).

The client is built on first use, so constructing a GcsBucket makes no network call. Every storage
failure surfaces as ``BucketError`` carrying the exception type name only: no URL, token or
response body can reach a log line.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Final

import google.cloud.storage as storage
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import GoogleAuthError

# Errors from the storage client that become BucketError. OSError covers connection failures and
# local disk errors during a download; none of their messages are passed on.
_STORAGE_ERRORS: Final = (GoogleAPIError, GoogleAuthError, OSError)


class BucketError(Exception):
    """A storage call failed; the message is the exception type name and nothing else."""


class GcsBucket:
    """One bucket, read and written through the storage client (ADC on Cloud Run or a laptop)."""

    def __init__(
        self,
        bucket_name: str,
        *,
        client_factory: Callable[[], storage.Client] = storage.Client,
    ) -> None:
        self._bucket_name = bucket_name
        self._client_factory = client_factory
        self._client: storage.Client | None = None

    def _blob(self, name: str) -> storage.Blob:
        if self._client is None:
            self._client = self._client_factory()
        return self._client.bucket(self._bucket_name).blob(name)

    def read_bytes(self, name: str) -> bytes | None:
        try:
            data = self._blob(name).download_as_bytes()
        except NotFound:
            return None
        except _STORAGE_ERRORS as exc:
            raise BucketError(type(exc).__name__) from None
        return bytes(data)

    def download_to(self, name: str, dest: Path) -> None:
        try:
            self._blob(name).download_to_filename(str(dest))
        except NotFound:
            raise FileNotFoundError("object not found") from None
        except _STORAGE_ERRORS as exc:
            raise BucketError(type(exc).__name__) from None

    def upload_file(
        self,
        src: Path,
        name: str,
        *,
        content_type: str,
        content_disposition: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        try:
            blob = self._blob(name)
            if content_disposition is not None:
                blob.content_disposition = content_disposition
            if cache_control is not None:
                blob.cache_control = cache_control
            blob.upload_from_filename(str(src), content_type=content_type)
        except _STORAGE_ERRORS as exc:
            raise BucketError(type(exc).__name__) from None

    def upload_bytes(self, data: bytes, name: str, *, content_type: str) -> None:
        try:
            self._blob(name).upload_from_string(data, content_type=content_type)
        except _STORAGE_ERRORS as exc:
            raise BucketError(type(exc).__name__) from None

    def md5_base64(self, name: str) -> str | None:
        try:
            blob = self._blob(name)
            blob.reload()
        except NotFound:
            return None
        except _STORAGE_ERRORS as exc:
            raise BucketError(type(exc).__name__) from None
        digest = blob.md5_hash
        return digest if isinstance(digest, str) else None
