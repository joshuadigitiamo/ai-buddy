"""Per-item JSON cache under PRIVATE_DIR (D-14): reruns are free, interrupted runs resume.

Cached replies hold handbook text, so the root lives in the private directory, never in a
tracked path (T-05-17). A file that cannot be read back is a miss, never a crash; writes are
atomic. Logs name the namespace and the key only, never cached content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal

import buddy_bot
import buddy_core

LOGGER: Final = logging.getLogger("buddy_eval")

Namespace = Literal["reformulation", "outcome", "verdict", "empty_context", "scored"]

# The files whose content decides what the bot says: every module of the bot (prompt table
# included) and the escalation table it reads (A-07-2).
BOT_DIR: Path = Path(buddy_bot.__file__).resolve().parent
ESCALATION_TOPICS: Path = (
    Path(buddy_core.__file__).resolve().parent / "data" / "escalation_topics.yaml"
)

_SAFE_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def key_for(**ingredients: object) -> str:
    """sha256 of the canonical JSON of the ingredients: any changed ingredient changes the key."""
    canonical = json.dumps(ingredients, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bot_version() -> str:
    """sha256 over the relative paths and bytes of every bot module and the escalation table."""
    digest = hashlib.sha256()
    for path in sorted(BOT_DIR.rglob("*.py")):
        digest.update(path.relative_to(BOT_DIR).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    digest.update(ESCALATION_TOPICS.name.encode("utf-8") + b"\0")
    digest.update(ESCALATION_TOPICS.read_bytes())
    return digest.hexdigest()


class ResultCache:
    """JSON files at `<root>/<namespace>/<key>.json`; one writer at a time (sequential eval)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, namespace: Namespace, name: str) -> Path:
        # Keys are digests and trace ids; refuse anything that could leave the namespace folder.
        if _SAFE_NAME.fullmatch(name) is None:
            raise ValueError(f"unsafe cache key in namespace {namespace}")
        return self._root / namespace / f"{name}.json"

    def get(self, namespace: Namespace, key: str) -> dict[str, Any] | None:
        """The stored payload, or None for a missing, unreadable or non-object file."""
        path = self._path(namespace, key)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError):
            LOGGER.warning("cache file unreadable: namespace=%s key=%s", namespace, key)
            return None
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            LOGGER.warning("cache file is not a JSON object: namespace=%s key=%s", namespace, key)
            return None
        return payload

    def put(self, namespace: Namespace, key: str, payload: Mapping[str, object]) -> None:
        """Write the payload atomically: a temp file in the same folder, then `os.replace`."""
        target = self._path(namespace, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, target)

    def is_scored(self, trace_id: str, version: str) -> bool:
        """True when feedback of this scorer-set version was already attached to the trace."""
        return self._path("scored", f"{trace_id}-{version}").is_file()

    def mark_scored(self, trace_id: str, version: str) -> None:
        self.put("scored", f"{trace_id}-{version}", {"trace_id": trace_id, "version": version})
