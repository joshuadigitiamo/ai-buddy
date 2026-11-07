"""Shared escalation table: sensitive topic -> referral role (D-08).

The bot and the Skill refer the same topics to the same roles. The table lives in one YAML
file shipped inside buddy_core. It holds roles only; the bot looks the actual contact up in
the handbook at answer time (D-04).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

DEFAULT_TABLE_PATH: Final[Path] = Path(__file__).parent / "data" / "escalation_topics.yaml"

_SUPPORTED_VERSION: Final[int] = 1
_ID_RE: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*")
_TOPIC_FIELDS: Final[tuple[str, ...]] = ("id", "tema", "referente", "ruolo")


class EscalationTableError(ValueError):
    """The escalation table is malformed. Messages name the field and row, never the value."""


@dataclass(frozen=True, slots=True)
class EscalationTopic:
    """One sensitive topic and the role that handles it."""

    id: str
    tema: str
    referente: str
    ruolo: str


@dataclass(frozen=True, slots=True)
class EscalationTable:
    """The whole table: topics in Skill order plus the role used when no topic matches."""

    version: int
    fallback_role: str
    topics: tuple[EscalationTopic, ...]

    def ids(self) -> tuple[str, ...]:
        """Return the topic ids in table order."""
        return tuple(topic.id for topic in self.topics)

    def topic(self, topic_id: str) -> EscalationTopic | None:
        """Return the topic with this id, or None when the id is unknown."""
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        return None

    def referente_role(self, topic_id: str | None) -> str:
        """Return the role for a topic id; None or an unknown id gets the fallback role (D-04)."""
        found = self.topic(topic_id) if topic_id is not None else None
        return found.ruolo if found is not None else self.fallback_role


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_topic(index: int, row: object, seen: dict[str, int]) -> EscalationTopic:
    if not isinstance(row, dict):
        raise EscalationTableError(f"topics[{index}] must be a mapping")
    for name in _TOPIC_FIELDS:
        if not _non_empty_string(row.get(name)):
            raise EscalationTableError(f"topics[{index}].{name} must be a non-empty string")
    if _ID_RE.fullmatch(row["id"]) is None:
        raise EscalationTableError(f"topics[{index}].id must match [a-z][a-z0-9_]*")
    if row["id"] in seen:
        raise EscalationTableError(f"topics[{index}].id duplicates topics[{seen[row['id']]}].id")
    seen[row["id"]] = index
    return EscalationTopic(
        id=row["id"], tema=row["tema"], referente=row["referente"], ruolo=row["ruolo"]
    )


def load_escalation_table(path: Path | None = None) -> EscalationTable:
    """Read and validate the table at ``path`` (default: the file shipped with buddy_core)."""
    raw: Any = yaml.safe_load((path or DEFAULT_TABLE_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise EscalationTableError("escalation table must be a mapping")
    if raw.get("version") != _SUPPORTED_VERSION:
        raise EscalationTableError(f"version must be {_SUPPORTED_VERSION}")
    if not _non_empty_string(raw.get("fallback_role")):
        raise EscalationTableError("fallback_role must be a non-empty string")
    rows = raw.get("topics")
    if not isinstance(rows, list) or not rows:
        raise EscalationTableError("topics must be a non-empty list")
    seen: dict[str, int] = {}
    topics = tuple(_parse_topic(index, row, seen) for index, row in enumerate(rows))
    return EscalationTable(
        version=_SUPPORTED_VERSION, fallback_role=raw["fallback_role"], topics=topics
    )
