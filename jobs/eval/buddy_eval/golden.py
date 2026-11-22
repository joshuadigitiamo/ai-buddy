"""Golden set: schema (D-04) and the split public/private loader (D-02).

Items whose ``expected_sources`` reference ``handbook://`` live only in the private file; the
committed (public) file must never carry one. Errors name the file, the item id and the field,
never question or answer text.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

LOGGER: Final = logging.getLogger("buddy_eval")
HANDBOOK_SCHEME: Final = "handbook://"
SCHEMA_VERSION: Final = 1
_MAX_ID_ECHO: Final = 64

Kind = Literal["handbook", "guides", "no_answer", "sensitive"]
Review = Literal["draft", "approved", "rejected"]


class GoldenError(ValueError):
    """A golden file is missing, malformed or breaks the privacy split; names no content."""


class GoldenItem(BaseModel):
    """One reviewed question with the expectations the scorers check (D-04)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    kind: Kind
    question: str = Field(min_length=1)
    expected_answer: str
    key_facts: list[str]
    expected_sources: list[str]
    expected_referente_role: str | None
    review: Review
    review_note: str = ""

    @model_validator(mode="after")
    def _check_kind_rules(self) -> GoldenItem:
        if not self.question.strip():
            raise ValueError("question must not be blank")
        has_sources = bool(self.expected_sources)
        has_facts = bool(self.key_facts)
        if self.kind in ("handbook", "guides") and not (has_facts and has_sources):
            raise ValueError(f"kind {self.kind} needs at least one key_facts and expected_sources")
        if self.kind == "handbook" and not all(
            s.startswith(HANDBOOK_SCHEME) for s in self.expected_sources
        ):
            raise ValueError(
                f"kind handbook needs every expected_sources to start {HANDBOOK_SCHEME}"
            )
        if self.kind == "guides" and any(
            s.startswith(HANDBOOK_SCHEME) for s in self.expected_sources
        ):
            raise ValueError(f"kind guides must not use {HANDBOOK_SCHEME} in expected_sources")
        if self.kind == "no_answer":
            if has_sources or has_facts:
                raise ValueError("kind no_answer takes no expected_sources and no key_facts")
            if not self.expected_referente_role:
                raise ValueError("kind no_answer needs expected_referente_role")
        if self.kind == "sensitive":
            if not self.expected_referente_role:
                raise ValueError("kind sensitive needs expected_referente_role")
            if has_facts != has_sources:
                raise ValueError(
                    "kind sensitive needs key_facts exactly when expected_sources is non-empty"
                )
        return self

    @property
    def sensitive_branch(self) -> Literal["rule", "no_rule"] | None:
        """A sensitive item with sources answers from a rule; without, it refers (D-09)."""
        if self.kind != "sensitive":
            return None
        return "rule" if self.expected_sources else "no_rule"


@dataclass(frozen=True, slots=True)
class GoldenSet:
    """Every loaded item in id order, and whether the private file was there."""

    items: tuple[GoldenItem, ...]
    private_file_present: bool

    def approved(self) -> tuple[GoldenItem, ...]:
        return tuple(i for i in self.items if i.review == "approved")

    def drafts(self) -> tuple[GoldenItem, ...]:
        return tuple(i for i in self.items if i.review == "draft")

    def rejected(self) -> tuple[GoldenItem, ...]:
        return tuple(i for i in self.items if i.review == "rejected")


def _echo(value: object) -> str:
    return str(value)[:_MAX_ID_ECHO]


def _read_items(path: Path) -> list[Mapping[str, Any]]:
    """Parse one golden file into raw item mappings; the shape is checked, never echoed."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise GoldenError(f"{path}: not valid YAML") from None
    if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
        raise GoldenError(
            f"{path}: top level must be a mapping with schema_version {SCHEMA_VERSION}"
        )
    items = loaded.get("items")
    if not isinstance(items, list):
        raise GoldenError(f"{path}: items must be a list")
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise GoldenError(f"{path}: items[{index}] must be a mapping")
    return items


def _item_label(index: int, raw: Mapping[str, Any]) -> str:
    raw_id = raw.get("id")
    return f"item {_echo(raw_id)}" if isinstance(raw_id, str) else f"items[{index}]"


def _parse_item(path: Path, index: int, raw: Mapping[str, Any]) -> GoldenItem:
    try:
        return GoldenItem.model_validate(raw)
    except ValidationError as exc:
        # Field names and rule messages only: error inputs would carry question text.
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'item'}: {err['msg']}"
            for err in exc.errors()
        )
        raise GoldenError(f"{path}: {_item_label(index, raw)}: {problems}") from None


def _references_handbook(raw: Mapping[str, Any]) -> bool:
    sources = raw.get("expected_sources")
    return isinstance(sources, list) and any(
        isinstance(s, str) and HANDBOOK_SCHEME in s for s in sources
    )


def _load_file(path: Path, *, public: bool) -> list[GoldenItem]:
    raws = _read_items(path)
    if public:
        for index, raw in enumerate(raws):
            if _references_handbook(raw):
                raise GoldenError(
                    f"{path}: {_item_label(index, raw)} references {HANDBOOK_SCHEME} "
                    "and belongs in the private file"
                )
    return [_parse_item(path, index, raw) for index, raw in enumerate(raws)]


def load_golden(public_path: Path, private_path: Path) -> GoldenSet:
    """Load the committed file and the private handbook file, id-sorted (D-02)."""
    if not public_path.is_file():
        raise GoldenError(f"{public_path}: public golden file is missing")
    items = _load_file(public_path, public=True)
    private_present = private_path.is_file()
    if private_present:
        items.extend(_load_file(private_path, public=False))
    else:
        LOGGER.warning(
            "private golden file missing: %s; handbook items absent, "
            "the gate will FAIL (incomplete set)",
            private_path,
        )
    duplicates = sorted(i for i, n in Counter(item.id for item in items).items() if n > 1)
    if duplicates:
        raise GoldenError(f"duplicate golden item id: {duplicates[0]}")
    return GoldenSet(tuple(sorted(items, key=lambda item: item.id)), private_present)
