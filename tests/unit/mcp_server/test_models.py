"""D-06 contract: the five tool output shapes and the limit clamp."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from buddy_mcp import models

_CITED = ("HandbookPageResult", "HandbookTocEntry", "GuidesSectionResult")

_VALID: dict[str, dict[str, Any]] = {
    "HandbookPageResult": {
        "page_id": "02-ferie",
        "title": "Ferie",
        "text": "Corpo.",
        "source_url": "handbook://02-ferie",
        "revision_date": "2026-10-03T00:00:00+00:00",
    },
    "HandbookTocEntry": {
        "page_id": "02-ferie",
        "title": "Ferie",
        "source_url": "handbook://02-ferie",
        "revision_date": "2026-10-03T00:00:00+00:00",
        "revision_kind": "last_updated",
    },
    "GuidesSectionResult": {
        "section_id": "k",
        "file": "A/B.md",
        "heading": "H",
        "line_start": 1,
        "line_end": 2,
        "text": "t",
        "source_url": "https://github.com/example-org/guides/blob/abc/A/B.md#L1-L2",
        "revision_date": "2026-11-03T10:00:00+00:00",
        "revision_kind": "indexed_on",
        "video_url": None,
    },
}


def _model(name: str) -> type[BaseModel]:
    cls = getattr(models, name, None)
    assert cls is not None, f"buddy_mcp.models.{name} is missing"
    assert isinstance(cls, type)
    return cls


def test_tool_names_are_the_five_contract_names() -> None:
    expected = ("handbook_get", "handbook_search", "guides_search", "guides_get_section")
    assert getattr(models, "TOOL_NAMES", None) == (*expected, "buddy_report_gap")


@pytest.mark.parametrize(
    ("requested", "clamped"), [(0, 1), (-3, 1), (1, 1), (5, 5), (10, 10), (11, 10), (500, 10)]
)
def test_clamp_limit_keeps_one_to_ten(requested: int, clamped: int) -> None:
    assert models.clamp_limit(requested) == clamped


def test_default_limit_is_five() -> None:
    assert models.DEFAULT_LIMIT == 5


@pytest.mark.parametrize("name", _CITED)
def test_schema_lists_citation_fields_as_required(name: str) -> None:
    required = set(_model(name).model_json_schema()["required"])
    assert {"source_url", "revision_date", "revision_kind"} <= required


@pytest.mark.parametrize("name", _CITED)
@pytest.mark.parametrize("field", ["source_url", "revision_date"])
def test_empty_citation_field_is_rejected(name: str, field: str) -> None:
    cls = _model(name)
    cls(**_VALID[name])
    with pytest.raises(ValidationError):
        cls(**{**_VALID[name], field: ""})


def test_guides_section_accepts_missing_video() -> None:
    item = _model("GuidesSectionResult")(**_VALID["GuidesSectionResult"])
    assert getattr(item, "video_url") is None  # noqa: B009 - model is looked up dynamically


def test_gap_marker_only_accepts_the_refusal_phrase() -> None:
    cls = _model("GapReportOutput")
    ok = cls(status="recorded", gap_id="g-1", marker="nessuna fonte trovata")
    assert ok.model_dump() == {
        "status": "recorded",
        "gap_id": "g-1",
        "marker": "nessuna fonte trovata",
    }
    with pytest.raises(ValidationError):
        cls(status="recorded", gap_id="g-1", marker="altro")


def test_gap_marker_constant_matches_the_contract() -> None:
    assert getattr(models, "GAP_MARKER", None) == "nessuna fonte trovata"


@pytest.mark.parametrize(
    "name",
    [
        "HandbookSearchOutput",
        "GuidesSearchOutput",
        "HandbookGetOutput",
        "GuidesGetSectionOutput",
        "GapReportOutput",
    ],
)
def test_every_tool_has_an_output_model(name: str) -> None:
    assert "status" in _model(name).model_json_schema()["properties"]


def test_handbook_get_carries_toc_and_optional_query() -> None:
    cls = _model("HandbookGetOutput")
    out = cls(status="ok", results=[], toc=[])
    assert out.model_dump()["query"] is None
