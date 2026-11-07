"""Escalation table (D-08): loader tests and the SKILL.md drift guard."""

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from buddy_core import escalation
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


def first_drift(yaml_rows: list[tuple[str, str]], skill_rows: list[tuple[str, str]]) -> int | None:
    """Return the 1-based number of the first row that differs, or None when equal."""
    for number, (from_yaml, from_skill) in enumerate(zip(yaml_rows, skill_rows), 1):
        if from_yaml != from_skill:
            return number
    if len(yaml_rows) != len(skill_rows):
        return min(len(yaml_rows), len(skill_rows)) + 1
    return None


def default_yaml_rows() -> list[tuple[str, str]]:
    return [(t.tema, t.referente) for t in load_escalation_table(DEFAULT_TABLE_PATH).topics]


def test_yaml_matches_skill_table() -> None:
    yaml_rows = default_yaml_rows()
    skill_rows = skill_escalation_rows(SKILL_PATH.read_text(encoding="utf-8"))
    drift = first_drift(yaml_rows, skill_rows)
    assert drift is None, (
        f"row {drift} drifted: YAML {yaml_rows[drift - 1 : drift]!r} "
        f"vs SKILL.md {skill_rows[drift - 1 : drift]!r}"
    )


def test_drift_check_reports_the_changed_row() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    changed = skill_text.replace("| responsabile diretto, poi HR |", "| responsabile, poi HR |")
    assert changed != skill_text
    assert first_drift(default_yaml_rows(), skill_escalation_rows(changed)) == 7


def test_drift_check_reports_a_missing_row() -> None:
    skill_rows = skill_escalation_rows(SKILL_PATH.read_text(encoding="utf-8"))
    assert first_drift(default_yaml_rows(), skill_rows[:5]) == 6


@pytest.mark.parametrize(
    ("topic_id", "role"),
    [
        ("ferie_personali", "responsabile diretto"),
        ("malattia", "HR"),
        (None, "HR"),
        ("sconosciuto", "HR"),
    ],
)
def test_referente_role(topic_id: str | None, role: str) -> None:
    assert load_escalation_table().referente_role(topic_id) == role


def test_topic_lookup() -> None:
    table = load_escalation_table()
    molestie = table.topic("molestie")
    assert molestie is not None
    assert molestie.referente.startswith("HR (se HR è coinvolta")
    assert table.topic("sconosciuto") is None


def test_ids_are_eight_unique_items() -> None:
    ids = load_escalation_table().ids()
    assert len(ids) == 8
    assert len(set(ids)) == 8


def valid_table() -> dict[str, Any]:
    loaded = yaml.safe_load(DEFAULT_TABLE_PATH.read_text(encoding="utf-8"))
    return copy.deepcopy(loaded)  # type: ignore[no-any-return]


def duplicate_id(table: dict[str, Any]) -> None:
    table["topics"][1]["id"] = table["topics"][0]["id"]


def bad_id(table: dict[str, Any]) -> None:
    table["topics"][0]["id"] = "Stipendio-1"


def empty_tema(table: dict[str, Any]) -> None:
    table["topics"][2]["tema"] = "  "


def missing_fallback(table: dict[str, Any]) -> None:
    del table["fallback_role"]


def wrong_version(table: dict[str, Any]) -> None:
    table["version"] = 2


def empty_topics(table: dict[str, Any]) -> None:
    table["topics"] = []


def non_mapping_topic(table: dict[str, Any]) -> None:
    table["topics"][3] = "HR"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (duplicate_id, "topics[1].id"),
        (bad_id, "topics[0].id"),
        (empty_tema, "topics[2].tema"),
        (missing_fallback, "fallback_role"),
        (wrong_version, "version"),
        (empty_topics, "topics"),
        (non_mapping_topic, "topics[3]"),
    ],
)
def test_malformed_table_names_the_field(tmp_path: Path, mutate: Any, expected: str) -> None:
    table = valid_table()
    mutate(table)
    path = tmp_path / "table.yaml"
    path.write_text(yaml.safe_dump(table, allow_unicode=True), encoding="utf-8")
    with pytest.raises(escalation.EscalationTableError, match=expected.replace("[", r"\[")):
        load_escalation_table(path)


def test_non_mapping_top_level_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "table.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(escalation.EscalationTableError, match="mapping"):
        load_escalation_table(path)


def test_error_message_does_not_echo_the_value(tmp_path: Path) -> None:
    table = valid_table()
    bad_id(table)
    path = tmp_path / "table.yaml"
    path.write_text(yaml.safe_dump(table, allow_unicode=True), encoding="utf-8")
    with pytest.raises(escalation.EscalationTableError) as caught:
        load_escalation_table(path)
    assert "Stipendio-1" not in str(caught.value)
