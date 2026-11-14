"""The bot README documents every setting and keeps the rollout checklist; no stray addresses."""

import re
from pathlib import Path

from buddy_bot.config import BotSettings

ROOT = Path(__file__).resolve().parents[3]
README = ROOT / "services" / "chat_bot" / "README.md"

# Public Google system identities needed to configure the Chat app; no person is named.
ALLOWED_ADDRESSES = frozenset(
    {
        "chat-api-push@system.gserviceaccount.com",
        "chat@system.gserviceaccount.com",
    }
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ROLLOUT_HEADING = "Prima di un secondo utente"


def _text() -> str:
    return README.read_text(encoding="utf-8")


def test_every_setting_is_documented() -> None:
    text = _text()
    missing = [name for name in BotSettings.model_fields if name.upper() not in text]
    assert not missing, f"README is missing settings: {missing}"


def test_rollout_checklist_names_the_backend_switch_and_the_memory_recheck() -> None:
    text = _text()
    assert f"## {ROLLOUT_HEADING}" in text
    after = text.split(f"## {ROLLOUT_HEADING}", 1)[1]
    assert "LLM_BACKEND" in after
    assert "D-11" in after


def test_readme_names_no_real_address() -> None:
    for address in EMAIL.findall(_text()):
        domain = address.rsplit("@", 1)[1].lower()
        assert domain == "example.invalid" or address.lower() in ALLOWED_ADDRESSES, (
            f"unexpected address in README: {address}"
        )


def test_readme_documents_the_manual_chat_app_settings() -> None:
    text = _text()
    assert "Joshua only" in text
    assert "Authentication Audience" in text
    assert "ttls update expire_at" in text


def test_readme_names_the_publisher_for_each_app_format() -> None:
    # Live check 2026-11-07: an add-on Chat app publishes as the gsuiteaddons service account,
    # so a grant to chat-api-push alone gave PERMISSION_DENIED.
    text = _text()
    section = text.split("## Pub/Sub and IAM", 1)[1].split("\n## ", 1)[0]
    assert "service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com" in section
    assert "Add-on format" in section
    legacy = section.split("**Legacy format**", 1)[1]
    assert "chat-api-push@system.gserviceaccount.com" in legacy
    assert "non-add-on apps only" in legacy
    assert "PERMISSION_DENIED" in section


def test_readme_documents_markdown_syntax_and_silent_meridian() -> None:
    text = _text()
    assert "Markup syntax: MARKDOWN" in text
    assert "MERIDIAN_SILENT=1" in text
    # 04-06: compose no longer shares the server's network namespace; the bot calls the Service
    # name and the server admits it through MCP_ALLOWED_HOSTS.
    assert "MCP_ALLOWED_HOSTS=mcp-server" in text
    assert "network namespace" not in text
