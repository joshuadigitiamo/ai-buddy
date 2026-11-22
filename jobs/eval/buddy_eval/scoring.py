"""Per-kind checks (D-09) and the invented-policy flag (D-10). Pure: no mlflow, no I/O.

A reason is a short check name, never reply text. The deterministic checks come from the reply;
the key facts and the invented claims come from the judge's verdict. Without a verdict an
answerable item that passes every other check is `unjudged`, never `correct`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from buddy_eval.golden import HANDBOOK_SCHEME, GoldenItem
from buddy_eval.judge import JudgeVerdict
from buddy_eval.sources import matches

if TYPE_CHECKING:
    from buddy_eval.runner import ItemOutcome

Status = Literal["correct", "wrong", "unjudged", "errored"]
SourceResolver = Callable[[str], str | None]

_SMALLTALK: Final = "classified as smalltalk"
# Part of every verdict cache key: bump when the per-kind rules or the use of a judge verdict
# change, so verdicts cached under the older rules stop matching.
SCORING_VERSION: Final = "1"


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
    judge: JudgeVerdict | None = None


@dataclass(frozen=True, slots=True)
class Headline:
    """Counts the report and the gate read; `invented` counts items with an unsupported claim."""

    correct: int
    total: int
    unjudged: int
    errored: int
    invented: int


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
    *,
    judge: JudgeVerdict | None = None,
) -> ItemVerdict:
    """Build a verdict; `invented` is decided by the judge for an answered reply (D-10)."""
    reply = outcome.reply
    invented: bool | None = None
    if reply is not None and reply.kind != "answer":
        invented = False
    elif judge is not None:
        invented = bool(judge.invented_claims)
    return ItemVerdict(
        item.id, item.kind, status, checks, reasons, invented, outcome.trace_id, judge
    )


def _facts_present(item: GoldenItem, judge: JudgeVerdict) -> bool:
    """Every key fact present and none contradicted; matched by position (A-08-1).

    A missing judge entry counts as an absent fact and an extra entry is ignored.
    """
    for position in range(len(item.key_facts)):
        if position >= len(judge.facts):
            return False
        entry = judge.facts[position]
        if not entry.present or entry.contradicted:
            return False
    return True


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
    item: GoldenItem,
    outcome: ItemOutcome,
    *,
    resolve: SourceResolver = handbook_only,
    judge: JudgeVerdict | None = None,
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
    needs_facts = _needs_facts(item)
    if needs_facts and judge is not None:
        checks["facts"] = _facts_present(item, judge)
    failed = tuple(f"{name}: failed" for name, ok in checks.items() if ok is False)
    if failed:
        return _verdict(item, outcome, "wrong", checks, failed, judge=judge)
    if needs_facts and judge is None:
        checks["facts"] = None
        return _verdict(item, outcome, "unjudged", checks, ("facts: not judged yet",))
    return _verdict(item, outcome, "correct", checks, (), judge=judge)


def headline(verdicts: Iterable[ItemVerdict]) -> Headline:
    """Count verdicts by status and the items flagged with an invented policy (D-10)."""
    items = list(verdicts)
    return Headline(
        correct=sum(1 for v in items if v.status == "correct"),
        total=len(items),
        unjudged=sum(1 for v in items if v.status == "unjudged"),
        errored=sum(1 for v in items if v.status == "errored"),
        invented=sum(1 for v in items if v.invented is True),
    )
