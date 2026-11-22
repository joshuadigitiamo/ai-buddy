"""D-09 per-kind verdicts with the judge's facts, and the D-10 invented-policy flag.

Pure scoring: synthetic items and replies, no model, no trace backend.
"""

from typing import Any

import pytest
from tests.unit.buddy_eval.conftest import golden_item

from buddy_bot.schemas import BotReply, Evidence, Referente
from buddy_eval.golden import GoldenItem
from buddy_eval.judge import FactCheck, JudgeVerdict
from buddy_eval.runner import ItemOutcome
from buddy_eval.scoring import SCORING_VERSION, headline, score_item

HANDBOOK_ID = "handbook://02-ferie"


def _source(url: str = HANDBOOK_ID) -> Evidence:
    return Evidence(
        source_url=url,
        kind="handbook",
        title="Ferie",
        text="synthetic source text",
        revision_date="2026-10-03",
        revision_kind="last_updated",
    )


def _reply(kind: str, **fields: Any) -> BotReply:
    return BotReply(kind=kind, **fields)


def _outcome(item: GoldenItem, reply: BotReply | None, *, error: str | None = None) -> ItemOutcome:
    status = "errored" if reply is None else "completed"
    return ItemOutcome(item.id, status, reply, "tr-1", error)  # type: ignore[arg-type]


def _item(kind: str, **overrides: Any) -> GoldenItem:
    return GoldenItem.model_validate(golden_item("item-aa-01", kind, **overrides))


def _judge(facts: list[tuple[bool, bool]], claims: tuple[str, ...] = ()) -> JudgeVerdict:
    return JudgeVerdict(
        facts=[
            FactCheck(fact=f"fact {n}", present=p, contradicted=c) for n, (p, c) in enumerate(facts)
        ],
        invented_claims=list(claims),
        reasoning="synthetic reasoning",
    )


ANSWER = _reply("answer", answer="synthetic answer", sources=[_source()])
HR = Referente(role="HR")
GOOD = _judge([(True, False)])


def _sensitive_rule() -> GoldenItem:
    return _item(
        "sensitive",
        key_facts=["synthetic fact"],
        expected_sources=[HANDBOOK_ID],
        expected_referente_role="HR",
    )


def _sensitive_no_rule() -> GoldenItem:
    return _item("sensitive", expected_referente_role="HR")


@pytest.mark.parametrize(
    ("name", "item", "reply", "judge", "status", "reasons"),
    [
        ("all facts present", _item("handbook"), ANSWER, GOOD, "correct", ()),
        (
            "one fact missing",
            _item("handbook", key_facts=["a", "b"]),
            ANSWER,
            _judge([(True, False), (False, False)]),
            "wrong",
            ("facts: failed",),
        ),
        (
            "one fact contradicted",
            _item("handbook"),
            ANSWER,
            _judge([(True, True)]),
            "wrong",
            ("facts: failed",),
        ),
        (
            "judge returned fewer facts than key facts",
            _item("handbook", key_facts=["a", "b"]),
            ANSWER,
            _judge([(True, False)]),
            "wrong",
            ("facts: failed",),
        ),
        (
            "judge returned no fact entry at all",
            _item("handbook"),
            ANSWER,
            _judge([]),
            "wrong",
            ("facts: failed",),
        ),
        (
            "extra judge entries are ignored",
            _item("handbook"),
            ANSWER,
            _judge([(True, False), (False, True)]),
            "correct",
            (),
        ),
        (
            "answer with zero citations",
            _item("handbook"),
            _reply("answer", answer="synthetic answer"),
            GOOD,
            "wrong",
            ("citation: failed",),
        ),
        (
            "citation of another page",
            _item("handbook"),
            _reply("answer", answer="x", sources=[_source("handbook://01-benvenuto")]),
            GOOD,
            "wrong",
            ("citation: failed",),
        ),
        (
            "no_answer refusal with gap",
            _item("no_answer"),
            _reply("refusal", gap_reported=True),
            None,
            "correct",
            (),
        ),
        (
            "no_answer refusal without gap",
            _item("no_answer"),
            _reply("refusal", gap_reported=False),
            None,
            "wrong",
            ("gap_logged: failed",),
        ),
        (
            "no_answer answered",
            _item("no_answer"),
            ANSWER,
            _judge([]),
            "wrong",
            ("kind_refusal: failed", "gap_logged: failed"),
        ),
        (
            "sensitive rule branch with role and facts",
            _sensitive_rule(),
            _reply("answer", answer="x", sources=[_source()], referente=HR),
            GOOD,
            "correct",
            (),
        ),
        (
            "sensitive rule branch with a missing fact",
            _sensitive_rule(),
            _reply("answer", answer="x", sources=[_source()], referente=HR),
            _judge([(False, False)]),
            "wrong",
            ("facts: failed",),
        ),
        (
            "sensitive no-rule referral with role and gap",
            _sensitive_no_rule(),
            _reply("referral", referente=HR, gap_reported=True),
            None,
            "correct",
            (),
        ),
        (
            "referral naming another role",
            _sensitive_no_rule(),
            _reply("referral", referente=Referente(role="IT"), gap_reported=True),
            None,
            "wrong",
            ("referente_role: failed",),
        ),
        (
            "smalltalk",
            _item("handbook"),
            _reply("smalltalk"),
            None,
            "wrong",
            ("classified as smalltalk",),
        ),
    ],
)
def test_the_per_kind_table_with_the_judge_verdict(
    name: str,
    item: GoldenItem,
    reply: BotReply,
    judge: JudgeVerdict | None,
    status: str,
    reasons: tuple[str, ...],
) -> None:
    verdict = score_item(item, _outcome(item, reply), judge=judge)

    assert verdict.status == status, name
    assert verdict.reasons == reasons, name
    assert verdict.status != "unjudged"


def test_an_answerable_item_without_a_judge_verdict_stays_unjudged() -> None:
    item = _item("handbook")

    verdict = score_item(item, _outcome(item, ANSWER))

    assert verdict.status == "unjudged"
    assert verdict.checks["facts"] is None
    assert verdict.invented is None


def test_a_judged_item_that_failed_a_deterministic_check_still_records_the_facts() -> None:
    item = _item("handbook")
    reply = _reply("answer", answer="x")

    verdict = score_item(item, _outcome(item, reply), judge=_judge([(False, False)]))

    assert verdict.checks["citation"] is False
    assert verdict.checks["facts"] is False
    assert verdict.reasons == ("citation: failed", "facts: failed")


def test_a_collect_error_is_errored_and_is_not_judged() -> None:
    item = _item("handbook")

    verdict = score_item(item, _outcome(item, None, error="LlmUnavailableError"))

    assert verdict.status == "errored"
    assert verdict.invented is None
    assert verdict.judge is None


@pytest.mark.parametrize(
    ("claims", "expected"), [((), False), (("a 30 day notice nobody states",), True)]
)
def test_an_answered_reply_is_invented_when_the_judge_lists_an_unsupported_claim(
    claims: tuple[str, ...], expected: bool
) -> None:
    item = _item("handbook")
    judge = _judge([(True, False)], claims)

    verdict = score_item(item, _outcome(item, ANSWER), judge=judge)

    assert verdict.invented is expected
    assert verdict.judge is judge


def test_a_wrong_item_with_an_invented_claim_counts_as_invented() -> None:
    # The no_answer item that wrongly answered: invented claims are still counted (D-10).
    item = _item("no_answer")
    judge = _judge([], ("a made up rule",))

    verdict = score_item(item, _outcome(item, ANSWER), judge=judge)

    assert verdict.status == "wrong"
    assert verdict.invented is True


@pytest.mark.parametrize(
    "reply",
    [
        _reply("refusal", gap_reported=True),
        _reply("referral", referente=HR, gap_reported=True),
        _reply("smalltalk"),
    ],
)
def test_a_reply_that_is_not_an_answer_is_never_invented(reply: BotReply) -> None:
    item = _item("no_answer")

    verdict = score_item(item, _outcome(item, reply))

    assert verdict.invented is False


def test_the_headline_counts_the_invented_items() -> None:
    clean, flagged = _item("handbook"), _item("handbook")
    refusal_item = _item("no_answer")
    verdicts = [
        score_item(clean, _outcome(clean, ANSWER), judge=_judge([(True, False)])),
        score_item(flagged, _outcome(flagged, ANSWER), judge=_judge([(True, False)], ("x", "y"))),
        score_item(refusal_item, _outcome(refusal_item, _reply("refusal", gap_reported=True))),
    ]

    summary = headline(verdicts)

    assert (summary.correct, summary.total, summary.unjudged, summary.errored) == (3, 3, 0, 0)
    assert summary.invented == 1


def test_the_scoring_version_is_a_non_empty_cache_key_part() -> None:
    assert SCORING_VERSION
