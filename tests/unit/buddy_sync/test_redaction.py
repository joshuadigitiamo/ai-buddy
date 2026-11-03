"""Redactor behaviour on synthetic text only (no real handbook content)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from buddy_sync.config import SyncSettings
from buddy_sync.redaction import MASK, Redactor, log_hits

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
