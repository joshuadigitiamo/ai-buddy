"""Golden lint: counts, branches, index existence, duplicates, privacy. Synthetic data only."""

import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from tests.unit.buddy_eval.conftest import golden_item, write_golden
from tests.unit.mcp_server.conftest import MAPPED, PLAIN, make_content, write_index

from buddy_eval import cli
from buddy_eval.config import EvalSettings
from buddy_eval.golden import (
    KIND_TARGETS,
    LintIssue,
    format_lint,
    lint_golden,
    load_golden,
    normalize_question,
)
from buddy_eval.sources import SourceIndex

SENTINEL = "SENTINEL-QUESTION-TEXT"
SECTION = MAPPED.chunk_key.rsplit("/", 1)[0]
GUIDES_SOURCE = [SECTION]


def _items(kind: str, count: int, **overrides: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in range(count):
        item_id = f"{kind.replace('_', '')}-{n:02d}"
        item = golden_item(item_id, kind, question=f"{SENTINEL} {kind} number {n}", **overrides)
        out.append(item)
    return out


def _sensitive(rule: int, no_rule: int) -> list[dict[str, Any]]:
    rules = [
        golden_item(
            f"rule-{n:02d}",
            "sensitive",
            question=f"{SENTINEL} rule {n}",
            key_facts=["synthetic fact"],
            expected_sources=GUIDES_SOURCE,
        )
        for n in range(rule)
    ]
    refers = [
        golden_item(f"norule-{n:02d}", "sensitive", question=f"{SENTINEL} refer {n}")
        for n in range(no_rule)
    ]
    return rules + refers


def _public(extra: Sequence[Mapping[str, Any]] = ()) -> list[Mapping[str, Any]]:
    return [
        *_items("guides", 13, expected_sources=GUIDES_SOURCE),
        *_items("no_answer", 7),
        *_sensitive(3, 2),
        *extra,
    ]


def _private() -> list[Mapping[str, Any]]:
    return list(_items("handbook", 15))


def _write(settings: EvalSettings, public: Sequence[Mapping[str, Any]] | None = None) -> None:
    write_index(settings.artifact_dir, make_content(chunks=(MAPPED, PLAIN)))
    write_golden(settings.golden_public_path, _public() if public is None else public)
    write_golden(settings.golden_private_path, _private())


def _lint(settings: EvalSettings) -> list[LintIssue]:
    golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    texts = {
        p.name: p.read_text(encoding="utf-8")
        for p in (settings.golden_public_path, settings.golden_private_path)
        if p.is_file()
    }
    return lint_golden(golden, SourceIndex.open(settings.artifact_dir), raw_texts=texts)


def _rendered(issues: list[LintIssue]) -> list[str]:
    return [i.render() for i in issues]


def _run_cli(settings: EvalSettings) -> tuple[int, str]:
    out = io.StringIO()
    code = cli.main(["lint"], settings=settings, out=out)
    return code, out.getvalue()


def test_a_synthetic_set_lints_ok_with_counts(eval_settings: EvalSettings) -> None:
    _write(eval_settings)

    code, output = _run_cli(eval_settings)

    assert code == 0
    assert output.splitlines() == [
        "lint: OK (40 items: handbook=15 guides=13 no_answer=7 sensitive=5; "
        "draft=0 approved=40 rejected=0)"
    ]


def _extra_guides(count: int) -> list[Mapping[str, Any]]:
    return [
        golden_item(
            f"extra-{n:02d}",
            "guides",
            question=f"{SENTINEL} extra {n}",
            expected_sources=GUIDES_SOURCE,
        )
        for n in range(count)
    ]


@pytest.mark.parametrize(
    ("public", "total"),
    [(_public()[11:], 29), ([*_public(), *_extra_guides(11)], 51)],
    ids=["29-items", "51-items"],
)
def test_a_count_outside_30_to_50_is_an_error(
    eval_settings: EvalSettings, public: list[Mapping[str, Any]], total: int
) -> None:
    _write(eval_settings, public)

    issues = _rendered(_lint(eval_settings))

    assert f"error: golden_set: count: {total} non-rejected items, expected 30 to 50" in issues


def test_rejected_items_do_not_count(eval_settings: EvalSettings) -> None:
    rejected = [
        golden_item(f"rej-{n:02d}", "guides", review="rejected", question=f"{SENTINEL} r{n}")
        for n in range(25)
    ]
    for item in rejected:
        item["expected_sources"] = ["gone.md#nowhere"]
    _write(eval_settings, _public(rejected))

    code, output = _run_cli(eval_settings)

    assert code == 0
    assert "40 items" in output
    assert "rejected=25" in output


def test_an_expected_source_missing_from_the_index_names_item_and_field(
    eval_settings: EvalSettings,
) -> None:
    public = _public()
    public[0] = dict(public[0], expected_sources=["AI-Engineering/GONE.md#ghost/section"])
    _write(eval_settings, public)

    issues = _rendered(_lint(eval_settings))

    assert (
        f"error: {public[0]['id']}: expected_sources: "
        "AI-Engineering/GONE.md#ghost/section not in the current index"
    ) in issues


def test_a_handbook_source_missing_from_the_index_is_an_error(eval_settings: EvalSettings) -> None:
    _write(eval_settings)
    write_golden(
        eval_settings.golden_private_path,
        [
            *_private()[:-1],
            golden_item("hb-ghost", "handbook", expected_sources=["handbook://99-x"]),
        ],
    )

    issues = _rendered(_lint(eval_settings))

    assert "error: hb-ghost: expected_sources: expected_sources[0] not in the current index" in issues


def test_a_missing_handbook_source_is_named_by_position_never_by_page_id(
    eval_settings: EvalSettings,
) -> None:
    present = _private()[0]["expected_sources"][0]
    _write(eval_settings)
    write_golden(
        eval_settings.golden_private_path,
        [
            *_private()[:-1],
            golden_item("hb-ghost", "handbook", expected_sources=[present, "handbook://99-x"]),
        ],
    )

    issues = [line for line in _rendered(_lint(eval_settings)) if "hb-ghost" in line]

    assert issues == ["error: hb-ghost: expected_sources: expected_sources[1] not in the current index"]
    assert all("handbook://" not in line and "99-x" not in line for line in issues)


def test_no_no_rule_sensitive_item_is_a_branch_error(eval_settings: EvalSettings) -> None:
    public = [*_items("guides", 13, expected_sources=GUIDES_SOURCE), *_items("no_answer", 7)]
    public += _sensitive(5, 0)
    _write(eval_settings, public)

    issues = _rendered(_lint(eval_settings))

    assert "error: golden_set: sensitive: no no_rule branch item" in issues


def test_zero_guides_items_is_a_kind_error(eval_settings: EvalSettings) -> None:
    public = [*_items("no_answer", 20), *_sensitive(3, 2)]
    _write(eval_settings, public)

    issues = _rendered(_lint(eval_settings))

    assert "error: golden_set: kind guides: no items" in issues


def test_equal_normalized_questions_are_a_duplicate_error_naming_both_ids(
    eval_settings: EvalSettings,
) -> None:
    public = _public()
    public[1] = dict(public[1], question=public[0]["question"].upper() + "  !!")
    _write(eval_settings, public)

    issues = _rendered(_lint(eval_settings))

    assert (
        f"error: {public[1]['id']}: question: duplicates the question of {public[0]['id']}"
        in issues
    )


def test_normalize_question_casefolds_strips_punctuation_and_collapses_spaces() -> None:
    assert normalize_question("  Come   RICHIEDO, le ferie?! ") == "come richiedo le ferie"


@pytest.mark.parametrize("spelling", ["ClickUp", "CLICKUP", "clickup"])
def test_a_clickup_string_in_either_file_is_an_error(
    eval_settings: EvalSettings, spelling: str
) -> None:
    public = _public()
    public[0] = dict(public[0], review_note=f"from {spelling}")
    _write(eval_settings, public)

    issues = _rendered(_lint(eval_settings))

    assert "error: guides.yaml: clickup: ClickUp reference found" in issues


def test_a_clickup_string_in_the_private_file_is_an_error(eval_settings: EvalSettings) -> None:
    _write(eval_settings)
    private = _private()
    private[0] = dict(private[0], review_note="see clickup")
    write_golden(eval_settings.golden_private_path, private)

    issues = _rendered(_lint(eval_settings))

    assert "error: golden-handbook.yaml: clickup: ClickUp reference found" in issues


def test_a_missing_private_file_is_an_error(eval_settings: EvalSettings) -> None:
    _write(eval_settings)
    eval_settings.golden_private_path.unlink()

    issues = _rendered(_lint(eval_settings))

    assert "error: golden_set: private handbook file missing" in issues


def test_a_load_error_is_one_error_line_without_question_text(
    eval_settings: EvalSettings,
) -> None:
    public = _public()
    public[0] = dict(public[0], kind="bogus")
    _write(eval_settings, public)

    code, output = _run_cli(eval_settings)

    assert code == 1
    assert output.startswith("error: golden_set: ")
    assert output.splitlines()[-1] == "lint: 1 errors"
    assert SENTINEL not in output


def test_a_missing_public_file_is_one_error_line(eval_settings: EvalSettings) -> None:
    code, output = _run_cli(eval_settings)

    assert code == 1
    assert "public golden file is missing" in output


def test_a_different_kind_mix_is_only_a_warning(eval_settings: EvalSettings) -> None:
    public = [
        *_items("guides", 14, expected_sources=GUIDES_SOURCE),
        *_items("no_answer", 6),
        *_sensitive(3, 2),
    ]
    _write(eval_settings, public)

    code, output = _run_cli(eval_settings)

    assert code == 0
    assert "warning: golden_set: kind guides: 14 items, target 13" in output
    assert "warning: golden_set: kind no_answer: 6 items, target 7" in output
    assert output.splitlines()[-1].startswith("lint: OK (")


def test_errors_print_before_warnings_and_end_with_the_error_count(
    eval_settings: EvalSettings,
) -> None:
    public = _public()
    public[0] = dict(public[0], expected_sources=["x.md#nope"])
    _write(eval_settings, public)
    write_golden(eval_settings.golden_private_path, _private()[:14])

    code, output = _run_cli(eval_settings)
    lines = output.splitlines()

    assert code == 1
    assert lines[-1].startswith("lint: ") and lines[-1].endswith(" errors")
    first_warning = next((n for n, line in enumerate(lines) if line.startswith("warning:")), None)
    last_error = max(n for n, line in enumerate(lines) if line.startswith("error:"))
    assert first_warning is None or last_error < first_warning


def test_lint_output_never_contains_question_text(eval_settings: EvalSettings) -> None:
    public = _public()
    public[0] = dict(public[0], expected_sources=["x.md#nope"])
    public[1] = dict(public[1], question=public[0]["question"])
    _write(eval_settings, public)

    code, output = _run_cli(eval_settings)

    assert code == 1
    assert SENTINEL not in output


def test_the_default_targets_are_the_d03_mix() -> None:
    assert dict(KIND_TARGETS) == {"handbook": 15, "guides": 13, "no_answer": 7, "sensitive": 5}


def test_format_lint_ok_line_counts_reviews(eval_settings: EvalSettings) -> None:
    public = _public()
    public[0] = dict(public[0], review="draft")
    _write(eval_settings, public)
    golden = load_golden(eval_settings.golden_public_path, eval_settings.golden_private_path)

    assert format_lint(golden, [])[-1].endswith("draft=1 approved=39 rejected=0)")


def test_the_lint_never_touches_the_model_or_the_tracking_server(
    eval_settings: EvalSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(eval_settings)
    monkeypatch.setattr(cli, "build_llm_client", lambda _s: pytest.fail("llm built"))
    monkeypatch.setattr(cli, "MlflowTraceSink", lambda _s: pytest.fail("sink built"))

    code, _ = _run_cli(eval_settings)

    assert code == 0


def test_a_missing_index_is_a_reported_failure(eval_settings: EvalSettings, tmp_path: Path) -> None:
    write_golden(eval_settings.golden_public_path, _public())
    write_golden(eval_settings.golden_private_path, _private())

    code, output = _run_cli(eval_settings)

    assert code == 1
    assert "not found under ARTIFACT_DIR" in output
