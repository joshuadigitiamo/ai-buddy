"""Milestone gate verdict (D-17). Pure: no mlflow, no I/O.

PASS needs every metric measured and met. Anything unmeasured, unjudged, errored, draft or
missing is a failure with a named reason; the gate never infers a pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Correctness bar as an exact rational: correct / approved_total >= 9 / 10.
_PCT_BAR: Final = 90


@dataclass(frozen=True, slots=True)
class GateInputs:
    """Measured values; None means the metric was not measured in this run."""

    approved_total: int
    correct: int
    unjudged: int
    errored: int
    drafts: int
    private_file_present: bool
    invented: int | None
    empty_context_passed: bool | None


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """`failures` are `<metric>: <detail>` strings in D-17 order; empty exactly when passed."""

    passed: bool
    failures: tuple[str, ...]


def _golden_set_failures(inputs: GateInputs) -> list[str]:
    failures: list[str] = []
    if not inputs.private_file_present:
        failures.append("golden_set: private handbook file missing (incomplete set)")
    if inputs.drafts > 0:
        failures.append(f"golden_set: {inputs.drafts} draft items (golden set not fully reviewed)")
    if inputs.approved_total <= 0:
        failures.append("golden_set: no approved items")
    return failures


def _correctness_failure(inputs: GateInputs) -> str | None:
    if inputs.approved_total <= 0:
        return None
    if inputs.unjudged > 0:
        return f"correctness_with_citation: {inputs.unjudged} answered items not judged"
    if inputs.correct * 10 >= inputs.approved_total * 9:
        return None
    pct = inputs.correct * 100 / inputs.approved_total
    return (
        f"correctness_with_citation: {pct:.1f}% < {_PCT_BAR}% "
        f"({inputs.correct}/{inputs.approved_total})"
    )


def evaluate(inputs: GateInputs) -> GateVerdict:
    """Apply the D-17 rule set; failures come in the fixed order the report prints them."""
    failures = _golden_set_failures(inputs)
    if inputs.errored > 0:
        failures.append(f"errored: {inputs.errored} items errored (incomplete run)")
    correctness = _correctness_failure(inputs)
    if correctness is not None:
        failures.append(correctness)
    if inputs.invented is None:
        failures.append("invented_policies: not measured")
    elif inputs.invented > 0:
        failures.append(f"invented_policies: {inputs.invented} > 0")
    if inputs.empty_context_passed is None:
        failures.append("empty_context: not run")
    elif not inputs.empty_context_passed:
        failures.append("empty_context: failed")
    return GateVerdict(passed=not failures, failures=tuple(failures))


def format_verdict(verdict: GateVerdict) -> list[str]:
    """`GATE: PASS`, or `GATE: FAIL` and one `FAIL <metric>: <detail>` line per failure."""
    if verdict.passed:
        return ["GATE: PASS"]
    return ["GATE: FAIL", *(f"FAIL {failure}" for failure in verdict.failures)]
