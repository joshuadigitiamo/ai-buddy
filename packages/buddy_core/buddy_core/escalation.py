"""Shared escalation table: sensitive topic -> referral role (D-08).

The bot and the Skill refer the same topics to the same roles. The table lives in one YAML
file shipped inside buddy_core. It holds roles only; the bot looks the actual contact up in
the handbook at answer time (D-04).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_TABLE_PATH = Path(__file__).parent / "data" / "escalation_topics.yaml"


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


def load_escalation_table(path: Path | None = None) -> EscalationTable:
    """Read the escalation table from ``path`` (default: the file shipped with buddy_core)."""
    raw: Any = yaml.safe_load((path or DEFAULT_TABLE_PATH).read_text(encoding="utf-8"))
    topics = tuple(
        EscalationTopic(
            id=row["id"], tema=row["tema"], referente=row["referente"], ruolo=row["ruolo"]
        )
        for row in raw["topics"]
    )
    return EscalationTable(
        version=raw["version"], fallback_role=raw["fallback_role"], topics=topics
    )
