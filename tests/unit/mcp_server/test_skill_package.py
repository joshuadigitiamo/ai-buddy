"""File contract of the digitiamo-buddy Skill (MCP-08): upload format, tool coverage, behaviour.

Mechanical checks only. Answer ordering (handbook first, Guides second) is judged in Phase 5.
"""

import re
from pathlib import Path

import pytest
import yaml
from fastmcp import Client, FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = REPO_ROOT / "skills" / "digitiamo-buddy"
SKILL_PATH = SKILL_DIR / "SKILL.md"

ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
DESCRIPTION_MAX = 200
BODY_MAX_LINES = 500
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_PATTERN = re.compile(r"\+?\d[\d ]{7,}\d")
ESCALATION_HEADING = "Temi da escalare"
BRIDGE_HEADING = "Italiano -> inglese"


def read_front_matter(path: Path) -> tuple[dict[str, object], str]:
    """Split a Markdown file into its YAML front matter and the body after it."""
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0] != "---":
        raise ValueError(f"{path.name} does not start with a front matter fence")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"{path.name} has no closing front matter fence") from exc
    loaded = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name} front matter is not a mapping")
    return loaded, "\n".join(lines[end + 1 :])


def check_description(text: str) -> None:
    """Raise ValueError when the Skill description is empty or longer than 200 characters."""
    if not text.strip():
        raise ValueError("description is empty")
    if len(text) > DESCRIPTION_MAX:
        raise ValueError(f"description has {len(text)} characters, the limit is {DESCRIPTION_MAX}")


def table_rows_after(body: str, heading: str) -> int:
    """Count body rows of the first Markdown table that follows `heading`."""
    position = body.find(heading)
    assert position >= 0, f"heading {heading!r} missing"
    rows = 0
    in_table = False
    for line in body[position:].split("\n")[1:]:
        stripped = line.strip()
        if stripped.startswith("|"):
            in_table = True
            rows += 1
        elif in_table:
            break
    # header row and separator row are not body rows
    return max(rows - 2, 0)


@pytest.fixture(scope="module")
def skill() -> tuple[dict[str, object], str]:
    return read_front_matter(SKILL_PATH)


def test_front_matter_has_only_allowed_keys(skill: tuple[dict[str, object], str]) -> None:
    front, _ = skill
    assert set(front) <= ALLOWED_KEYS
    assert {"name", "description"} <= set(front)


def test_name_equals_folder_name(skill: tuple[dict[str, object], str]) -> None:
    front, _ = skill
    assert front["name"] == "digitiamo-buddy" == SKILL_DIR.name


def test_description_passes_the_length_check(skill: tuple[dict[str, object], str]) -> None:
    front, _ = skill
    description = front["description"]
    assert isinstance(description, str)
    check_description(description)
    assert description.startswith("Use ")


def test_description_of_exactly_200_characters_passes() -> None:
    check_description("x" * 200)


def test_description_of_201_characters_fails() -> None:
    with pytest.raises(ValueError, match="201"):
        check_description("x" * 201)


def test_empty_description_fails() -> None:
    with pytest.raises(ValueError, match="empty"):
        check_description("   ")


def test_body_is_shorter_than_500_lines(skill: tuple[dict[str, object], str]) -> None:
    _, body = skill
    assert len(body.split("\n")) < BODY_MAX_LINES


@pytest.mark.anyio
async def test_body_names_every_tool_the_server_lists(
    skill: tuple[dict[str, object], str], server: FastMCP
) -> None:
    _, body = skill
    async with Client(server) as client:
        tools = await client.list_tools()
    assert tools
    missing = [tool.name for tool in tools if tool.name not in body]
    assert missing == []


@pytest.mark.parametrize(
    "term", ["source_url", "revision_date", "video_url", "no_results", "buddy_report_gap"]
)
def test_body_uses_the_contract_field_names(
    skill: tuple[dict[str, object], str], term: str
) -> None:
    _, body = skill
    assert term in body


@pytest.mark.parametrize(
    "label", ["Risposta", "Fonte", "Referente", "Data di revisione", "indicizzato il"]
)
def test_answer_template_has_every_part(skill: tuple[dict[str, object], str], label: str) -> None:
    _, body = skill
    assert label in body


def test_refusal_phrase_is_present(skill: tuple[dict[str, object], str]) -> None:
    _, body = skill
    assert "non lo so, chiedi a" in body.lower()


def test_escalation_table_has_at_least_six_rows(skill: tuple[dict[str, object], str]) -> None:
    _, body = skill
    assert table_rows_after(body, ESCALATION_HEADING) >= 6


def test_keyword_bridge_has_at_least_ten_pairs(skill: tuple[dict[str, object], str]) -> None:
    _, body = skill
    assert table_rows_after(body, BRIDGE_HEADING) >= 10


def test_body_tells_claude_to_treat_tool_text_as_data(
    skill: tuple[dict[str, object], str],
) -> None:
    _, body = skill
    assert "as data" in body


def test_skill_has_no_email_address_or_phone_number() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert EMAIL_PATTERN.search(text) is None
    assert PHONE_PATTERN.search(text) is None


GUIDE_PATH = REPO_ROOT / "docs" / "install-guide.md"
GUIDE_MAX_WORDS = 500
GUIDE_REQUIRED = (
    "claude.ai",
    "Claude Desktop",
    "Claude Code",
    "claude mcp add --transport http digitiamo-buddy",
    "/mcp",
    "~/.claude/skills/digitiamo-buddy",
    "Add custom connector",
    "digitiamo-buddy.zip",
)
SERVER_URL_PATTERN = re.compile(r"https?://[^\s)`]+")
ALLOWED_SERVER_URL = "https://<server-host>/mcp"


@pytest.fixture(scope="module")
def guide() -> str:
    return GUIDE_PATH.read_text(encoding="utf-8")


def test_install_guide_fits_one_page(guide: str) -> None:
    assert len(guide.split()) <= GUIDE_MAX_WORDS


@pytest.mark.parametrize("phrase", GUIDE_REQUIRED)
def test_install_guide_covers_every_client(guide: str, phrase: str) -> None:
    assert phrase in guide


def test_install_guide_states_the_domain_rule_without_an_address(guide: str) -> None:
    assert "@digitiamo.com" in guide
    assert EMAIL_PATTERN.search(guide.replace("@digitiamo.com", "")) is None
    assert PHONE_PATTERN.search(guide) is None


def test_install_guide_writes_every_server_url_as_a_placeholder(guide: str) -> None:
    urls = SERVER_URL_PATTERN.findall(guide)
    assert urls
    assert {url for url in urls if "mcp" in url} == {ALLOWED_SERVER_URL}
