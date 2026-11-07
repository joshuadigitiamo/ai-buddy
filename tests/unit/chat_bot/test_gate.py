"""Gate edges pinned explicitly: exact string equality after strip, no normalization (D-02).

Covers the BOT-05 adjacency (prefix, case, anchor), empty and encoding edges and the
confidence threshold boundary.
"""

import pytest
from tests.unit.mcp_server.conftest import SHA, WEB_BASE

from buddy_bot.gate import check
from buddy_bot.schemas import AnswerDraft, Evidence

THRESHOLD = 0.7
HANDBOOK_ID = "handbook://02-ferie"
GUIDE_FILE = "AI-Engineering/My%20Guide.md"
GUIDE_ID = f"{WEB_BASE}/blob/{SHA}/{GUIDE_FILE}#L10-L14"


def _evidence(source_url: str, kind: str = "handbook") -> Evidence:
    return Evidence(
        source_url=source_url,
        kind="guides" if kind == "guides" else "handbook",
        title="t",
        text="x",
        revision_date="2026-10-03T00:00:00+00:00",
        revision_kind="indexed_on" if kind == "guides" else "last_updated",
    )


EVIDENCE = {
    HANDBOOK_ID: _evidence(HANDBOOK_ID),
    GUIDE_ID: _evidence(GUIDE_ID, "guides"),
}


def _draft(**changes: object) -> AnswerDraft:
    base = AnswerDraft(answer="Risposta.", citations=[HANDBOOK_ID], grounded=True, confidence=0.9)
    return base.model_copy(update=changes)


@pytest.mark.parametrize(
    "citation",
    [
        "handbook://02-feri",
        "HANDBOOK://02-ferie",
        f"{WEB_BASE}/blob/{SHA}/{GUIDE_FILE}#L10-L13",
        f"{WEB_BASE}/blob/{SHA}/{GUIDE_FILE}",
        f"{WEB_BASE}/blob/{SHA}/AI-Engineering/My Guide.md#L10-L14",
    ],
    ids=["prefix", "case_variant", "anchor_differs", "anchor_missing", "percent_decoded"],
)
def test_near_miss_citation_fails(citation: str) -> None:
    result = check(EVIDENCE, _draft(citations=[citation]), THRESHOLD)

    assert (result.ok, result.reason) == (False, "unsupported_citation")


def test_surrounding_whitespace_is_stripped_before_comparison() -> None:
    result = check(EVIDENCE, _draft(citations=[f" {HANDBOOK_ID}\n"]), THRESHOLD)

    assert result.ok


def test_one_unsupported_citation_among_valid_ones_fails() -> None:
    result = check(EVIDENCE, _draft(citations=[HANDBOOK_ID, "handbook://99-inventata"]), THRESHOLD)

    assert result.reason == "unsupported_citation"


def test_empty_citations_fail() -> None:
    assert check(EVIDENCE, _draft(citations=[]), THRESHOLD).reason == "no_citation"


@pytest.mark.parametrize("answer", ["", "   ", "\n\t"])
def test_blank_answer_with_a_valid_citation_fails(answer: str) -> None:
    result = check(EVIDENCE, _draft(answer=answer), THRESHOLD)

    assert (result.ok, result.reason) == (False, "blank_answer")


def test_blank_answer_is_checked_before_citations() -> None:
    assert check(EVIDENCE, _draft(answer=" ", citations=[]), THRESHOLD).reason == "blank_answer"


def test_empty_evidence_fails_before_anything_else() -> None:
    assert check({}, _draft(answer=" "), THRESHOLD).reason == "no_evidence"


def test_confidence_equal_to_threshold_passes() -> None:
    assert check(EVIDENCE, _draft(confidence=THRESHOLD), THRESHOLD).ok


def test_confidence_just_below_threshold_fails() -> None:
    result = check(EVIDENCE, _draft(confidence=THRESHOLD - 0.0001), THRESHOLD)

    assert (result.ok, result.reason) == (False, "low_confidence")
