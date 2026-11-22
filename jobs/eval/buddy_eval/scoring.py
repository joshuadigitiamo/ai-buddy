"""Deterministic per-kind checks (D-09). Pure: no mlflow, no I/O.

A reason is a short check name, never reply text. `facts` stays None until the judge (05-08)
decides the key facts, so an answerable item that passes every other check is `unjudged`, never
`correct`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from buddy_eval.golden import HANDBOOK_SCHEME, GoldenItem
from buddy_eval.sources import matches

if TYPE_CHECKING:
    from buddy_eval.runner import ItemOutcome

Status = Literal["correct", "wrong", "unjudged", "errored"]
SourceResolver = Callable[[str], str | None]

_SMALLTALK: Final = "classified as smalltalk"


@dataclass(frozen=True, slots=True)
class ItemVerdict:
    """The verdict on one item; `checks` maps a check name to True, False or None (not judged)."""

    item_id: str
    kind: str
    status: Status
    checks: Mapping[str, bool | None]
    reasons: tuple[str, ...]
    invented: bool | None
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class Headline:
    """Counts the report and the gate read; `invented` is None while it is not measured."""

    correct: int
    total: int
    unjudged: int
    errored: int
    invented: int | None


def handbook_only(source_url: str) -> str | None:
    """Resolve a cited source to its handbook id, or None for anything that is not a page."""
    return source_url if source_url.startswith(HANDBOOK_SCHEME) else None


def _role_matches(actual: str | None, expected: str | None) -> bool:
    # A-03-2: exact after strip and casefold.
    if actual is None or expected is None:
        return False
    return actual.strip().casefold() == expected.strip().casefold()


def _needs_facts(item: GoldenItem) -> bool:
    return item.kind in ("handbook", "guides") or item.sensitive_branch == "rule"


def _verdict(
    item: GoldenItem,
    outcome: ItemOutcome,
    status: Status,
    checks: Mapping[str, bool | None],
    reasons: tuple[str, ...],
) -> ItemVerdict:
    return ItemVerdict(item.id, item.kind, status, checks, reasons, None, outcome.trace_id)


def _checks(item: GoldenItem, outcome: ItemOutcome, resolve: SourceResolver) -> dict[str, bool]:
    reply = outcome.reply
    assert reply is not None
    # The expected entries any resolved citation satisfies: several citations of one section
    # (its parts) fill the same entry once, and an unresolvable citation matches nothing.
    matched = {
        entry
        for source in reply.sources
        if (resolved := resolve(source.source_url)) is not None
        for entry in item.expected_sources
        if matches(resolved, entry)
    }
    cited = bool(matched)
    gap = reply.gap_reported
    role = _role_matches(
        reply.referente.role if reply.referente else None, item.expected_referente_role
    )
    if item.kind == "no_answer":
        return {"kind_refusal": reply.kind == "refusal", "gap_logged": gap}
    if item.sensitive_branch == "no_rule":
        return {
            "kind_referral": reply.kind == "referral",
            "referente_role": role,
            "gap_logged": gap,
        }
    if item.sensitive_branch == "rule":
        return {"kind_answer": reply.kind == "answer", "referente_role": role, "citation": cited}
    return {"kind_answer": reply.kind == "answer", "citation": cited}


def score_item(
    item: GoldenItem, outcome: ItemOutcome, *, resolve: SourceResolver = handbook_only
) -> ItemVerdict:
    """Apply the D-09 table for the item's kind to one collected outcome."""
    if outcome.status == "errored" or outcome.reply is None:
        reason = f"errored: {outcome.error or 'no reply'}"
        return _verdict(item, outcome, "errored", {}, (reason,))
    checks: dict[str, bool | None] = dict(_checks(item, outcome, resolve))
    if outcome.reply.kind == "smalltalk":
        # A-03-1: the bot neither answered nor refused, so it is a wrong answer, not an error.
        checks = {name: False for name in checks}
        return _verdict(item, outcome, "wrong", checks, (_SMALLTALK,))
    failed = tuple(f"{name}: failed" for name, ok in checks.items() if ok is False)
    if failed:
        return _verdict(item, outcome, "wrong", checks, failed)
    if _needs_facts(item):
        checks["facts"] = None
        return _verdict(item, outcome, "unjudged", checks, ("facts: not judged yet",))
    return _verdict(item, outcome, "correct", checks, ())


def headline(verdicts: Iterable[ItemVerdict]) -> Headline:
    """Count verdicts by status; the invented-policy count is None until the judge exists."""
    items = list(verdicts)
    return Headline(
        correct=sum(1 for v in items if v.status == "correct"),
        total=len(items),
        unjudged=sum(1 for v in items if v.status == "unjudged"),
        errored=sum(1 for v in items if v.status == "errored"),
        invented=None,
    )
