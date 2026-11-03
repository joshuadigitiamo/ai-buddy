"""Local-only false-positive check over the gitignored raw handbook snapshot.

The corpus directory is gitignored, so CI and other machines skip this module. Every
assertion compares integers or booleans: a failure never prints corpus text, and nothing
read from the corpus is copied into code or logs.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from buddy_sync.redaction import MASK, RULE_NAMES, Redactor

RAW_DIR = Path(__file__).resolve().parents[3] / "docs" / "research" / "handbook-raw"
WIFI_FILE = "07-wi-fi.md"  # local test only; production denylist is file-based (D-25)
NON_MASKING_RULES = {"image_link", "signed_url_query"}

pytestmark = pytest.mark.skipif(
    not RAW_DIR.is_dir(), reason="local-only corpus docs/research/handbook-raw is absent"
)

_FILES = sorted(p.name for p in RAW_DIR.glob("*.md")) if RAW_DIR.is_dir() else []
_OTHER_FILES = [name for name in _FILES if name != WIFI_FILE]

_DIGITIAMO_EMAIL = re.compile(r"@digitiamo\.com", re.IGNORECASE)
_OFFICE_NUMBER = re.compile(r"(?<![\w+/])(?:\+39[ .-]?)?0\d{1,3}[ .-]?\d{4,8}(?!\d)")
_VAT_LIKE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_SDI_WORD = re.compile(r"\bSDI\b", re.IGNORECASE)


def _body(name: str) -> str:
    """File text without its YAML front matter."""
    text = (RAW_DIR / name).read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :]
    return text


def _d16_counts(text: str) -> dict[str, int]:
    return {
        "digitiamo_email": len(_DIGITIAMO_EMAIL.findall(text)),
        "office_number": len(_OFFICE_NUMBER.findall(text)),
        "vat_like": len(_VAT_LIKE.findall(text)),
        "sdi_word": len(_SDI_WORD.findall(text)),
    }


@pytest.fixture(scope="module")
def redactor() -> Redactor:
    return Redactor(email_allow_domains=frozenset({"digitiamo.com"}))


def test_corpus_snapshot_has_the_expected_pages() -> None:
    assert len(_OTHER_FILES) == 22
    assert (WIFI_FILE in _FILES) is True


@pytest.mark.parametrize("name", _OTHER_FILES)
def test_work_data_survives_redaction(redactor: Redactor, name: str) -> None:
    text = _body(name)
    result = redactor.redact(text)
    assert _d16_counts(result.text) == _d16_counts(text)


@pytest.mark.parametrize("name", _OTHER_FILES)
def test_every_mask_is_reported_by_rule(redactor: Redactor, name: str) -> None:
    result = redactor.redact(_body(name))
    reported = sum(h.count for h in result.hits if h.rule not in NON_MASKING_RULES)
    assert result.text.count(MASK) == reported


def test_wifi_page_credential_label_is_caught(redactor: Redactor) -> None:
    result = redactor.redact(_body(WIFI_FILE))
    labelled = sum(h.count for h in result.hits if h.rule == "labelled_secret")
    assert labelled >= 1


def test_per_rule_hit_table(redactor: Redactor, capsys: pytest.CaptureFixture[str]) -> None:
    totals: Counter[str] = Counter()
    baseline: Counter[str] = Counter()
    for name in _OTHER_FILES:
        baseline.update(_d16_counts(_body(name)))
        for hit in redactor.redact(_body(name)).hits:
            totals[hit.rule] += hit.count
    with capsys.disabled():
        print("\ncorpus hits per rule (22 non-Wi-Fi pages):")
        for rule in RULE_NAMES:
            print(f"  {rule:<20} {totals[rule]}")
        print("D-16 baseline counts before redaction (a zero means that check is not exercised):")
        for key, value in sorted(baseline.items()):
            print(f"  {key:<20} {value}")
    assert set(totals) <= set(RULE_NAMES)
