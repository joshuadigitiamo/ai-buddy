"""D-06 output contract: parsed by the Phase 3 bot and referenced by the Skill.

Rename only together with both.
"""

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["ok", "no_results"]
RevisionKind = Literal["last_updated", "indexed_on"]

TOOL_NAMES: Final = (
    "handbook_get",
    "handbook_search",
    "guides_search",
    "guides_get_section",
    "buddy_report_gap",
)
GAP_MARKER: Final = "nessuna fonte trovata"
DEFAULT_LIMIT: Final = 5
MAX_LIMIT: Final = 10


def clamp_limit(limit: int) -> int:
    """Clamp a requested result count to 1..MAX_LIMIT (D-09)."""
    return max(1, min(limit, MAX_LIMIT))


def _citation_always_present(schema: dict[str, Any]) -> None:
    """Advertise revision_kind as required: every result carries it, whatever the default."""
    required: list[str] = schema.setdefault("required", [])
    if "revision_kind" not in required:
        required.append("revision_kind")


_CITED = ConfigDict(json_schema_extra=_citation_always_present)


class HandbookPageResult(BaseModel):
    """One whole handbook page (D-03), cited with its last-updated date."""

    model_config = _CITED

    page_id: str
    title: str
    text: str
    source_url: str = Field(min_length=1)
    revision_date: str = Field(min_length=1)
    revision_kind: Literal["last_updated"] = "last_updated"


class HandbookTocEntry(BaseModel):
    """One table-of-contents line for handbook_get() (D-07)."""

    model_config = _CITED

    page_id: str
    title: str
    source_url: str = Field(min_length=1)
    revision_date: str = Field(min_length=1)
    revision_kind: Literal["last_updated"]


class GuidesSectionResult(BaseModel):
    """One cited Guides section."""

    model_config = _CITED

    section_id: str
    file: str
    heading: str
    line_start: int
    line_end: int
    text: str
    source_url: str = Field(min_length=1)
    revision_date: str = Field(min_length=1)
    revision_kind: Literal["indexed_on"] = "indexed_on"
    video_url: str | None = None


class HandbookSearchOutput(BaseModel):
    """handbook_search result envelope."""

    status: Status
    query: str
    results: list[HandbookPageResult]


class HandbookGetOutput(BaseModel):
    """handbook_get result envelope: one page, or the table of contents when query is None."""

    status: Status
    query: str | None = None
    results: list[HandbookPageResult]
    toc: list[HandbookTocEntry]


class GuidesSearchOutput(BaseModel):
    """guides_search result envelope."""

    status: Status
    query: str
    results: list[GuidesSectionResult]


class GuidesGetSectionOutput(BaseModel):
    """guides_get_section result envelope; query is the requested id."""

    status: Status
    query: str
    results: list[GuidesSectionResult]


class GapReportOutput(BaseModel):
    """buddy_report_gap acknowledgement: the marker is the fixed refusal phrase."""

    status: Literal["recorded"]
    gap_id: str
    marker: Literal["nessuna fonte trovata"]
