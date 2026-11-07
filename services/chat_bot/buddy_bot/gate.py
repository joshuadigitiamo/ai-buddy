"""Deterministic citation and confidence gate (D-01, D-02, BOT-05).

The model cites by source_url. A citation counts only when it equals, after strip, a source_url
the tools returned in this run. No fuzzy match and no repair.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from buddy_bot.schemas import AnswerDraft, Evidence


@dataclass(frozen=True, slots=True)
class GateResult:
    """Outcome of the gate; `reason` is an internal label, never shown to the user."""

    ok: bool
    reason: str


def check(evidence: Mapping[str, Evidence], draft: AnswerDraft, threshold: float) -> GateResult:
    """Apply the checks in a fixed order; the first failure names the reason."""
    if not evidence:
        return GateResult(False, "no_evidence")
    if not draft.citations:
        return GateResult(False, "no_citation")
    if any(citation.strip() not in evidence for citation in draft.citations):
        return GateResult(False, "unsupported_citation")
    if not draft.grounded:
        return GateResult(False, "not_grounded")
    if draft.confidence < threshold:
        return GateResult(False, "low_confidence")
    return GateResult(True, "ok")


def cited_sources(evidence: Mapping[str, Evidence], draft: AnswerDraft) -> list[Evidence]:
    """Evidence of the citations in order of first appearance, each once."""
    seen: set[str] = set()
    sources: list[Evidence] = []
    for citation in draft.citations:
        key = citation.strip()
        if key in evidence and key not in seen:
            seen.add(key)
            sources.append(evidence[key])
    return sources
