"""Escalation table (D-08): loader tests and the SKILL.md drift guard."""

from pathlib import Path

from buddy_core.escalation import DEFAULT_TABLE_PATH, load_escalation_table

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "digitiamo-buddy" / "SKILL.md"
ESCALATION_HEADING = "Temi da escalare"
EXPECTED_IDS = (
    "stipendio",
    "malattia",
    "molestie",
    "disciplinare",
    "contratto",
    "privacy",
    "ferie_personali",
    "rimborsi",
)


def skill_escalation_rows(markdown: str) -> list[tuple[str, str]]:
    """Return the (Tema, Referente) body rows of the first table after the heading."""
    position = markdown.find(ESCALATION_HEADING)
    assert position >= 0, f"heading {ESCALATION_HEADING!r} missing"
    table_lines: list[str] = []
    for line in markdown[position:].split("\n")[1:]:
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break
    rows: list[tuple[str, str]] = []
    for line in table_lines[2:]:  # skip header and separator rows
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 2, f"expected 2 cells, got {len(cells)} in {line!r}"
        rows.append((cells[0], cells[1]))
    return rows


def test_default_table_loads() -> None:
    table = load_escalation_table()
    assert len(table.topics) == 8
    assert table.fallback_role == "HR"
    assert tuple(topic.id for topic in table.topics) == EXPECTED_IDS


def test_yaml_matches_skill_table() -> None:
    yaml_rows = [(t.tema, t.referente) for t in load_escalation_table(DEFAULT_TABLE_PATH).topics]
    skill_rows = skill_escalation_rows(SKILL_PATH.read_text(encoding="utf-8"))
    assert len(yaml_rows) == len(skill_rows), (
        f"row count differs: YAML {len(yaml_rows)}, SKILL.md {len(skill_rows)}"
    )
    for number, (from_yaml, from_skill) in enumerate(zip(yaml_rows, skill_rows, strict=True), 1):
        assert from_yaml == from_skill, (
            f"row {number} drifted: YAML {from_yaml!r} vs SKILL.md {from_skill!r}"
        )
