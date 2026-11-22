"""Index identity and source resolution for the citation check (D-01, D-09).

A cited Guides permalink carries line numbers that shift on every Guides edit, so it is resolved
through the index of the run to the stable chunk key of the section it points at, and compared
with the expected section identities of the golden item. The index is read only through
`buddy_core.index_reader` (the only SQL surface) and closed before this module returns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import unquote

from buddy_core.index_reader import open_index
from buddy_core.store import INDEX_NAME

HANDBOOK_SCHEME: Final = "handbook://"

# Anchored on the end so a trailing path or a second fragment never resolves.
_PERMALINK: Final = re.compile(
    r"/blob/(?P<sha>[0-9a-f]{40})/(?P<path>[^#]+)#L(?P<a>\d+)(?:-L(?P<b>\d+))?$"
)
_WEB_SCHEMES: Final = ("http://", "https://")


@dataclass(frozen=True, slots=True)
class IndexIdentity:
    """Which index a run was made against (D-01: runs record the Guides commit and index hash)."""

    content_hash: str
    guides_commit_sha: str
    build_id: str


def matches(key: str, expected: str) -> bool:
    """True when a resolved cited key satisfies one expected source entry.

    Handbook ids match by exact equality. A Guides key matches an expected section prefix when
    it equals it or continues it at a segment boundary, so `file#h2/h3` matches `file#h2/h3/0`
    and `file#h2/h3/1~2` but never `file#h2/h3x/0`.
    """
    if key.startswith(HANDBOOK_SCHEME) or expected.startswith(HANDBOOK_SCHEME):
        return key == expected
    return key == expected or key.startswith(expected + "/")


class SourceIndex:
    """Immutable lookup tables copied from one index.db; holds no connection."""

    def __init__(
        self,
        identity: IndexIdentity,
        spans: dict[tuple[str, int, int], str],
        chunk_keys: frozenset[str],
        page_ids: frozenset[str],
    ) -> None:
        self.identity = identity
        self._spans = spans
        self._chunk_keys = chunk_keys
        self._page_ids = page_ids

    @classmethod
    def open(cls, artifact_dir: Path) -> SourceIndex:
        """Read the index under `artifact_dir`; a missing index names ARTIFACT_DIR."""
        path = artifact_dir / INDEX_NAME
        try:
            reader = open_index(path)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"{INDEX_NAME} not found under ARTIFACT_DIR ({artifact_dir})"
            ) from exc
        with reader:
            meta = reader.meta
            chunks = reader.guide_chunks()
            pages = reader.load_handbook()
        spans: dict[tuple[str, int, int], str] = {}
        for chunk in chunks:
            # Parts that share a line span cannot be told apart by a permalink: the first wins,
            # and a section-prefix expectation matches any part anyway (A-07-1).
            spans.setdefault((chunk.file, chunk.line_start, chunk.line_end), chunk.chunk_key)
        return cls(
            IndexIdentity(meta.content_hash, meta.guides_commit_sha, meta.build_id),
            spans,
            frozenset(chunk.chunk_key for chunk in chunks),
            frozenset(page.page_id for page in pages),
        )

    def resolve(self, source_url: str) -> str | None:
        """Map a cited source to a stable key of this index, or None when it is not one."""
        if source_url.startswith(HANDBOOK_SCHEME):
            return source_url if source_url[len(HANDBOOK_SCHEME) :] in self._page_ids else None
        if not source_url.startswith(_WEB_SCHEMES):
            return None
        found = _PERMALINK.search(source_url)
        if found is None or found["sha"] != self.identity.guides_commit_sha:
            return None
        start = int(found["a"])
        end = int(found["b"]) if found["b"] is not None else start
        return self._spans.get((unquote(found["path"]), start, end))

    def has_expected(self, entry: str) -> bool:
        """True when an expected-source entry points at something this index holds."""
        if entry.startswith(HANDBOOK_SCHEME):
            return entry[len(HANDBOOK_SCHEME) :] in self._page_ids
        return any(matches(key, entry) for key in self._chunk_keys)
