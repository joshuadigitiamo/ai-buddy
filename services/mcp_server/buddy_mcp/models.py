"""D-06 output contract: parsed by the Phase 3 bot and referenced by the Skill.

Rename only together with both. Task 3 of plan 02-01 completes the contract for all five
tools; this tracer scope holds what guides_search needs.
"""

from typing import Final, Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "no_results"]
RevisionKind = Literal["last_updated", "indexed_on"]

DEFAULT_LIMIT: Final = 5
MAX_LIMIT: Final = 10


def clamp_limit(limit: int) -> int:
    """Clamp a requested result count to 1..MAX_LIMIT (D-09)."""
    return max(1, min(limit, MAX_LIMIT))


class GuidesSectionResult(BaseModel):
    """One cited Guides section."""

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


class GuidesSearchOutput(BaseModel):
    """guides_search result envelope."""

    status: Status
    query: str
    results: list[GuidesSectionResult]
