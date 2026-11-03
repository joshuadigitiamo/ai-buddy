"""Redactor behaviour on synthetic text only (no real handbook content)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from buddy_sync.config import SyncSettings
from buddy_sync.redaction import MASK, RULE_NAMES, Redactor, log_hits

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"


@pytest.fixture
def redactor(monkeypatch: pytest.MonkeyPatch) -> Redactor:
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition("=")
            monkeypatch.setenv(key, value)
    return Redactor.from_settings(SyncSettings())


def test_labelled_password_is_masked_and_logged_by_rule_name_only(
    redactor: Redactor, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "Zq9-synthetic-not-real"
    body = f"Accesso ufficio\n**Password:** {secret}\nChiedi a Mario Rossi"

    result = redactor.redact(body)

    assert f"**Password:** {MASK}" in result.text
    assert "Chiedi a Mario Rossi" in result.text
    assert (secret in result.text) is False

    with caplog.at_level(logging.INFO, logger="buddy_sync.test"):
        log_hits(logging.getLogger("buddy_sync.test"), "page-synthetic-1", result.hits)
    assert any(
        "rule=labelled_secret" in r.getMessage() and "source=page-synthetic-1" in r.getMessage()
        for r in caplog.records
    )
    assert (secret in caplog.text) is False


# --- Task 2: full D-15 rule set, D-16 keeps, D-17 images, D-18 Guides parity ---------------
# Secret-shaped values are assembled at runtime so no literal in the repo looks like a real one.

_RNG_32 = "kQ7xV2mZp9LrT4wB8nHs3JdF6gYc1AeU"
_ALNUM_36 = "A1b2C3d4E5f6G7h8I9j0" + "K1l2M3n4O5p6Q7r8"[:16]


def _hit_rules(redactor: Redactor, text: str) -> dict[str, int]:
    return {h.rule: h.count for h in redactor.redact(text).hits}


def test_rule_names_are_the_registered_order() -> None:
    assert RULE_NAMES == (
        "image_link",
        "signed_url_query",
        "labelled_secret",
        "private_key_block",
        "token_prefix",
        "jwt",
        "iban",
        "mobile_number",
        "private_email",
        "high_entropy",
    )


def test_image_link_keeps_alt_text_and_drops_url(redactor: Redactor) -> None:
    text = "Vedi ![Pianta ufficio](https://t1.p.clickup-attachments.com/x/plan.png) qui"
    result = redactor.redact(text)
    assert result.text == "Vedi Pianta ufficio qui"
    assert _hit_rules(redactor, text) == {"image_link": 1}


def test_signed_url_query_is_stripped_but_plain_query_stays(redactor: Redactor) -> None:
    signed = "https://storage.example.invalid/f.pdf?X-Goog-Signature=abc123&X-Goog-Expires=600"
    plain = "https://t1.p.clickup-attachments.com/x/doc.pdf?open=true"
    assert redactor.redact(signed).text == "https://storage.example.invalid/f.pdf"
    assert _hit_rules(redactor, signed) == {"signed_url_query": 1}
    assert redactor.redact(plain).text == plain
    assert redactor.redact(plain).hits == ()


def test_private_key_block_becomes_one_mask(redactor: Redactor) -> None:
    body = "\n".join(["MIIBSynthetic" + "A1b2C3d4" * 6] * 3)
    block = f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----"
    result = redactor.redact(f"prima\n{block}\ndopo")
    assert result.text == f"prima\n{MASK}\ndopo"
    assert _hit_rules(redactor, block) == {"private_key_block": 1}


@pytest.mark.parametrize(
    "token",
    [
        "ghp_" + _ALNUM_36,
        "github_pat_" + "A1b2C3d4E5" * 3,
        "AKIA" + "ABCD1234EFGH5678",
        "xoxb-" + "1234567890-abcdefghijkl",
        "AIza" + "Sy" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q",
        "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2",
        "pk_" + "A1b2C3d4E5f6G7h8I9j0K1l2",
    ],
)
def test_token_prefix_masks_known_formats(redactor: Redactor, token: str) -> None:
    result = redactor.redact(f"chiave {token} fine")
    assert result.text == f"chiave {MASK} fine"
    assert ("token_prefix" in {h.rule for h in result.hits}) is True


def test_token_prefix_also_applies_inside_guides_code_fences(redactor: Redactor) -> None:
    token = "ghp_" + _ALNUM_36
    guide = f"## Setup\n\n```bash\nexport GH={token}\n```\n"
    result = redactor.redact(guide)
    assert result.text == f"## Setup\n\n```bash\nexport GH={MASK}\n```\n"
    assert _hit_rules(redactor, guide) == {"token_prefix": 1}


def test_jwt_is_masked(redactor: Redactor) -> None:
    jwt = ".".join(["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiJzeW50aGV0aWMifQ", "c3ludGhldGljc2ln"])
    result = redactor.redact(f"Bearer {jwt}")
    assert result.text == f"Bearer {MASK}"
    assert _hit_rules(redactor, f"Bearer {jwt}") == {"jwt": 1}


@pytest.mark.parametrize("iban", ["IT60 X054 2811 1010 0000 0123 456", "GB82WEST12345698765432"])
def test_iban_with_valid_checksum_is_masked(redactor: Redactor, iban: str) -> None:
    result = redactor.redact(f"Bonifico a {iban} grazie")
    assert result.text == f"Bonifico a {MASK} grazie"
    assert _hit_rules(redactor, iban) == {"iban": 1}


def test_iban_masks_even_when_an_uppercase_word_follows(redactor: Redactor) -> None:
    result = redactor.redact("IT60 X054 2811 1010 0000 0123 456 SDI")
    assert result.text == f"{MASK} SDI"


@pytest.mark.parametrize("text", ["IT12345678901", "IT61X0542811101000000123456"])
def test_iban_lookalikes_failing_checksum_stay(redactor: Redactor, text: str) -> None:
    result = redactor.redact(f"codice {text} fine")
    assert result.text == f"codice {text} fine"
    assert result.hits == ()


@pytest.mark.parametrize("number", ["+39 333 123 4567", "3331234567"])
def test_mobile_number_is_masked(redactor: Redactor, number: str) -> None:
    result = redactor.redact(f"chiama {number} ora")
    assert result.text == f"chiama {MASK} ora"
    assert _hit_rules(redactor, number) == {"mobile_number": 1}


@pytest.mark.parametrize("number", ["+39 02 1234 5678", "06 123456", "01234567890"])
def test_office_numbers_and_vat_style_numbers_stay(redactor: Redactor, number: str) -> None:
    result = redactor.redact(f"tel {number} fine")
    assert result.text == f"tel {number} fine"
    assert result.hits == ()


def test_private_email_masked_but_company_domain_and_subdomains_kept(redactor: Redactor) -> None:
    text = "a someone@gmail.example b mario.rossi@digitiamo.com c ops@team.digitiamo.com d"
    result = redactor.redact(text)
    assert result.text == (f"a {MASK} b mario.rossi@digitiamo.com c ops@team.digitiamo.com d")
    assert _hit_rules(redactor, text) == {"private_email": 1}


def test_email_lookalike_domain_is_not_treated_as_company(redactor: Redactor) -> None:
    result = redactor.redact("x@evildigitiamo.com y@digitiamo.com.example.invalid")
    assert result.text == f"{MASK} {MASK}"


def test_high_entropy_string_is_masked(redactor: Redactor) -> None:
    result = redactor.redact(f"valore {_RNG_32} fine")
    assert result.text == f"valore {MASK} fine"
    assert _hit_rules(redactor, _RNG_32) == {"high_entropy": 1}


@pytest.mark.parametrize(
    "text",
    [
        "https://t1.p.clickup-attachments.com/123e4567-e89b-12d3-a456-426614174000/plan.png",
        "https://example.invalid/" + _RNG_32 + "/page",
        "123e4567-e89b-12d3-a456-426614174000",
        "uses: actions/checkout@" + "0123456789abcdef0123456789abcdef01234567",
        "Codice SDI ABC1234",
    ],
)
def test_high_entropy_skips_urls_uuids_hex_shas_and_short_codes(
    redactor: Redactor, text: str
) -> None:
    result = redactor.redact(text)
    assert result.text == text
    assert result.hits == ()


def test_d16_work_contacts_and_company_data_survive_byte_identical(redactor: Redactor) -> None:
    text = (
        "Chiedi a Mario Rossi (Office Manager): mario.rossi@digitiamo.com, "
        "interno 02 1234567 oppure 06 123456.\n"
        "P.IVA 01234567890 - Codice SDI ABC1234 - Via Roma 1, 20100 Milano.\n"
        "Quando accedi riceverai un codice via SMS.\n"
    )
    result = redactor.redact(text)
    assert result.text == text
    assert result.hits == ()


def test_hits_follow_rule_order_and_masked_values_are_not_recounted(redactor: Redactor) -> None:
    text = f"Password: {_RNG_32}\nmail someone@gmail.example tel 3331234567\n![alt](https://x.invalid/i.png)"
    result = redactor.redact(text)
    names = [h.rule for h in result.hits]
    assert names == sorted(names, key=RULE_NAMES.index)
    assert names == ["image_link", "labelled_secret", "mobile_number", "private_email"]
    assert ("high_entropy" in names) is False


def test_redaction_of_one_megabyte_is_fast(redactor: Redactor) -> None:
    paragraph = (
        "Chiedi a Mario Rossi, mario.rossi@digitiamo.com, interno 06 123456. "
        "Vedi https://t1.p.clickup-attachments.com/x/plan.png?open=true per i dettagli.\n"
    )
    adversarial = ("1 " * 40_000) + ("a" * 100_000) + ("-" * 50_000) + ("A1 " * 30_000)
    adversarial += ("+39 " * 20_000) + ("a.a." * 20_000) + ("IT60 " * 20_000)
    text = paragraph * 3_000 + adversarial
    assert len(text) >= 1_000_000
    start = time.perf_counter()
    redactor.redact(text)
    assert (time.perf_counter() - start) < 2.0
