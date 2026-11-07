"""Pins the intent guidance in the reformulate prompt (live check 2026-11-07).

"Qual è il codice del cancello del parcheggio?" was classified off_topic and got the smalltalk
reply, so no refusal and no gap document were produced. Whether the model now classifies it as
a question is judged by the Phase 5 goldens; this only pins that the rule is in the prompt.
"""

import pytest

from buddy_bot.prompts import REFORMULATE_SYSTEM

LOGISTICS_TERMS = ("parcheggio", "accesso agli uffici", "badge", "wifi", "attrezzatura", "sale")


def _intent_rule() -> str:
    start = REFORMULATE_SYSTEM.index("- intent:")
    return REFORMULATE_SYSTEM[start : REFORMULATE_SYSTEM.index("- sensitive_topic:")]


@pytest.mark.parametrize("term", LOGISTICS_TERMS)
def test_workplace_logistics_counts_as_a_question(term: str) -> None:
    rule = _intent_rule()
    question_part = rule.split('"chitchat"')[0]

    assert term in question_part


def test_an_unanswerable_workplace_question_is_still_a_question() -> None:
    rule = _intent_rule()

    assert "anche se la risposta potrebbe non essere nelle fonti" in rule
    assert "nel dubbio" in rule.lower()


def test_off_topic_is_limited_to_subjects_unrelated_to_work() -> None:
    off_topic_part = _intent_rule().split('"off_topic"')[1]

    assert "non legati al lavoro" in off_topic_part
