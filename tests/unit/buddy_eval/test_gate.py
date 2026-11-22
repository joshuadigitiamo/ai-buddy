"""D-17 truth table: every rule and boundary of the milestone gate, with the exact printed lines.

Pure: no model, no server, no files. Synthetic numbers only.
"""

from typing import Any

import pytest

from buddy_eval.gate import GateInputs, GateVerdict, evaluate, format_verdict

CORRECTNESS_UNJUDGED = "FAIL correctness_with_citation: 2 answered items not judged"


def _inputs(**overrides: Any) -> GateInputs:
    base: dict[str, Any] = {
        "approved_total": 10,
        "correct": 10,
        "unjudged": 0,
        "errored": 0,
        "drafts": 0,
        "private_file_present": True,
        "invented": 0,
        "empty_context_passed": True,
    }
    base.update(overrides)
    return GateInputs(**base)


CASES: list[tuple[str, dict[str, Any], list[str]]] = [
    ("all_met", {}, []),
    ("boundary_9_of_10_passes", {"correct": 9}, []),
    (
        "boundary_8_of_10_fails",
        {"correct": 8},
        ["FAIL correctness_with_citation: 80.0% < 90% (8/10)"],
    ),
    (
        "boundary_899_of_1000_fails",
        {"approved_total": 1000, "correct": 899},
        ["FAIL correctness_with_citation: 89.9% < 90% (899/1000)"],
    ),
    ("boundary_900_of_1000_passes", {"approved_total": 1000, "correct": 900}, []),
    ("invented_zero_passes", {"invented": 0}, []),
    ("invented_one_fails", {"invented": 1}, ["FAIL invented_policies: 1 > 0"]),
    ("invented_not_measured", {"invented": None}, ["FAIL invented_policies: not measured"]),
    ("empty_context_failed", {"empty_context_passed": False}, ["FAIL empty_context: failed"]),
    ("empty_context_not_run", {"empty_context_passed": None}, ["FAIL empty_context: not run"]),
    (
        "one_draft",
        {"drafts": 1},
        ["FAIL golden_set: 1 draft items (golden set not fully reviewed)"],
    ),
    (
        "private_file_missing",
        {"private_file_present": False},
        ["FAIL golden_set: private handbook file missing (incomplete set)"],
    ),
    (
        "no_approved_items",
        {"approved_total": 0, "correct": 0},
        ["FAIL golden_set: no approved items"],
    ),
    (
        "one_errored_item",
        {"errored": 1},
        ["FAIL errored: 1 items errored (incomplete run)"],
    ),
    ("unjudged_items", {"unjudged": 2}, [CORRECTNESS_UNJUDGED]),
    (
        "unjudged_outranks_a_low_percentage",
        {"unjudged": 2, "correct": 1},
        [CORRECTNESS_UNJUDGED],
    ),
    (
        "several_failures_in_the_fixed_order",
        {
            "approved_total": 20,
            "correct": 10,
            "errored": 2,
            "drafts": 3,
            "private_file_present": False,
            "invented": 4,
            "empty_context_passed": False,
        },
        [
            "FAIL golden_set: private handbook file missing (incomplete set)",
            "FAIL golden_set: 3 draft items (golden set not fully reviewed)",
            "FAIL errored: 2 items errored (incomplete run)",
            "FAIL correctness_with_citation: 50.0% < 90% (10/20)",
            "FAIL invented_policies: 4 > 0",
            "FAIL empty_context: failed",
        ],
    ),
    (
        "nothing_measured",
        {"invented": None, "empty_context_passed": None},
        ["FAIL invented_policies: not measured", "FAIL empty_context: not run"],
    ),
]


@pytest.mark.parametrize(
    ("overrides", "failure_lines"),
    [pytest.param(o, f, id=name) for name, o, f in CASES],
)
def test_the_truth_table(overrides: dict[str, Any], failure_lines: list[str]) -> None:
    verdict = evaluate(_inputs(**overrides))

    assert verdict.passed is (not failure_lines)
    expected = ["GATE: PASS"] if not failure_lines else ["GATE: FAIL", *failure_lines]
    assert format_verdict(verdict) == expected


def test_a_pass_has_zero_failure_lines() -> None:
    verdict = evaluate(_inputs())

    assert verdict == GateVerdict(passed=True, failures=())
    assert not any(line.startswith("FAIL") for line in format_verdict(verdict))


def test_the_zero_approved_case_never_divides_and_names_only_the_golden_set() -> None:
    verdict = evaluate(_inputs(approved_total=0, correct=0))

    assert [f.split(":")[0] for f in verdict.failures] == ["golden_set"]


def test_every_failure_is_named_on_its_own_line_with_the_fail_prefix() -> None:
    verdict = evaluate(
        _inputs(
            correct=0,
            errored=1,
            drafts=1,
            private_file_present=False,
            invented=None,
            empty_context_passed=None,
        )
    )

    lines = format_verdict(verdict)
    assert lines[0] == "GATE: FAIL"
    assert len(lines) == 1 + len(verdict.failures)
    assert all(line.startswith("FAIL ") for line in lines[1:])
    assert [line.split(":")[0].removeprefix("FAIL ") for line in lines[1:]] == [
        "golden_set",
        "golden_set",
        "errored",
        "correctness_with_citation",
        "invented_policies",
        "empty_context",
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"invented": None},
        {"empty_context_passed": None},
        {"drafts": 1},
        {"errored": 1},
        {"unjudged": 1},
        {"private_file_present": False},
        {"approved_total": 0, "correct": 0},
    ],
    ids=["invented", "empty_context", "draft", "errored", "unjudged", "private_file", "no_items"],
)
def test_no_unmeasured_draft_errored_or_missing_input_ever_prints_pass(
    overrides: dict[str, Any],
) -> None:
    lines = format_verdict(evaluate(_inputs(**overrides)))

    assert "GATE: PASS" not in lines
    assert lines[0] == "GATE: FAIL"
