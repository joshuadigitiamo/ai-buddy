"""video-coverage: scene and fallback rows per guide, from the index and a Guides tree (D-18)."""

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, IndexContent, make_chunk_key
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.cli import main
from buddy_sync.coverage import (
    BASELINE_SCENE_ROWS,
    BASELINE_TOTAL_ROWS,
    CoverageRow,
    coverage_from_index,
    coverage_from_tree,
    format_report,
)
from buddy_sync.video_map import VideoMapError, resolve_video_links

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "guides_videos"
DEMO = "AI-Engineering/DEMO_GUIDE.md"
MULTI = "AI-Engineering/MULTI_GUIDE.md"
FALLBACK = "AI-Engineering/FALLBACK_GUIDE.md"
NOVIDEO = "Foundations/NOVIDEO_GUIDE.md"
LOGGER = logging.getLogger("buddy_sync.test")
TOTAL_LINE = "scene=7 fallback=5 rows=12 (baseline 238/2524)"


def _chunk(file: str, h2: str, h3: str | None, line_start: int) -> GuideChunk:
    return GuideChunk(
        chunk_key=make_chunk_key(file, h2, h3, 0),
        file=file,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=line_start,
        line_end=line_start + 3,
        part_index=0,
        text="Synthetic chunk text.",
    )


def _chunks() -> list[GuideChunk]:
    return [
        _chunk(DEMO, "1. Basics", None, 5),
        _chunk(DEMO, "1. Basics", "Chunking", 9),
        _chunk(DEMO, "2. Only Section", None, 20),
        _chunk(MULTI, "Overview", None, 2),
        _chunk(MULTI, "1. Basics", None, 6),
        _chunk(MULTI, "1. Basics", "Detail", 10),
        _chunk(MULTI, "2. Recap", None, 20),
        _chunk(MULTI, "2. Recap", "Deep", 24),
        _chunk(MULTI, "2. Recap", "Other", 28),
        _chunk(MULTI, "3. Appendix", None, 40),
        _chunk(FALLBACK, "1. Intro", None, 3),
        _chunk(FALLBACK, "1. Intro", "Part", 7),
        _chunk(NOVIDEO, "1. Intro", None, 3),
    ]


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    """An artifact directory holding an index built over the fixture Guides videos."""
    chunks = _chunks()
    content = IndexContent(
        handbook=(),
        chunks=tuple(chunks),
        videos=resolve_video_links(FIXTURE_ROOT, chunks, logger=LOGGER),
        source_doc_id="doc-synthetic",
        guides_commit_sha="1" * 40,
        pipeline_version="test-1",
        redaction_version="test-1",
    )
    store = LocalDirArtifactStore(tmp_path / "artifacts")
    staged = store.staging_path()
    meta = build_index(content, staged, now=datetime.now(UTC))
    store.publish(staged, meta)
    return tmp_path / "artifacts"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "guides-tree"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


def _by_file(rows: list[CoverageRow]) -> dict[str, CoverageRow]:
    return {row.file: row for row in rows}


def test_coverage_from_index_splits_scene_and_fallback_rows_per_guide(artifact_dir: Path) -> None:
    rows = _by_file(coverage_from_index(artifact_dir / "index.db"))
    assert set(rows) == {DEMO, MULTI, FALLBACK}  # a guide without a video has no rows
    assert (rows[DEMO].rows, rows[DEMO].scene, rows[DEMO].fallback) == (3, 2, 1)
    assert (rows[MULTI].rows, rows[MULTI].scene, rows[MULTI].fallback) == (7, 5, 2)
    assert (rows[FALLBACK].rows, rows[FALLBACK].scene, rows[FALLBACK].fallback) == (2, 0, 2)
    assert all(row.rows == row.scene + row.fallback for row in rows.values())


def test_format_report_ends_with_the_total_line_and_the_baseline(artifact_dir: Path) -> None:
    assert (BASELINE_SCENE_ROWS, BASELINE_TOTAL_ROWS) == (238, 2524)
    lines = format_report(coverage_from_index(artifact_dir / "index.db")).splitlines()
    assert lines[-1] == TOTAL_LINE
    assert len(lines) == 4  # three guides plus the total
    assert lines[0].startswith(f"{DEMO}  ")


def test_projected_report_without_sections_yaml_loses_scene_rows_and_says_why(
    artifact_dir: Path, tree: Path
) -> None:
    (tree / "videos" / "demo" / "sections.yaml").unlink()
    rows = _by_file(coverage_from_tree(tree, artifact_dir / "index.db"))
    assert (rows[DEMO].scene, rows[DEMO].fallback, rows[DEMO].label) == (0, 3, "durations only")
    assert (rows[MULTI].scene, rows[MULTI].label) == (5, "sections.yaml")
    assert rows[FALLBACK].label == "no durations"


def test_projected_report_of_the_unchanged_tree_matches_the_index_counts(
    artifact_dir: Path, tree: Path
) -> None:
    actual = _by_file(coverage_from_index(artifact_dir / "index.db"))
    projected = _by_file(coverage_from_tree(tree, artifact_dir / "index.db"))
    assert {f: (r.rows, r.scene, r.fallback) for f, r in projected.items()} == {
        f: (r.rows, r.scene, r.fallback) for f, r in actual.items()
    }
    assert format_report(list(projected.values())).splitlines()[-1] == TOTAL_LINE


def test_projected_report_reflects_a_new_scene_map_before_it_is_committed(
    artifact_dir: Path, tree: Path
) -> None:
    topic = tree / "videos" / "fallback"
    (topic / "out").mkdir(parents=True)
    (topic / "out" / "durations.json").write_text('{"S01Intro": 5.0}', encoding="utf-8")
    (topic / "sections.yaml").write_text(
        f"schema: 1\nguide: {FALLBACK}\nvideo: fallback\nsections:\n"
        '  - scene: S01Intro\n    h2: "1. Intro"\n',
        encoding="utf-8",
    )
    rows = _by_file(coverage_from_tree(tree, artifact_dir / "index.db"))
    assert (rows[FALLBACK].scene, rows[FALLBACK].fallback) == (2, 0)
    assert rows[FALLBACK].label == "sections.yaml"


def test_projected_report_with_a_broken_sections_file_raises_a_map_error(
    artifact_dir: Path, tree: Path
) -> None:
    (tree / "videos" / "demo" / "sections.yaml").write_text("schema: 2\n", encoding="utf-8")
    with pytest.raises(VideoMapError):
        coverage_from_tree(tree, artifact_dir / "index.db")


def test_cli_prints_the_report_and_returns_zero(
    artifact_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["video-coverage", "--artifact-dir", str(artifact_dir)]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == TOTAL_LINE


def test_cli_with_guides_dir_prints_the_labels(
    artifact_dir: Path, tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["video-coverage", "--artifact-dir", str(artifact_dir), "--guides-dir", str(tree)])
    out = capsys.readouterr().out
    assert code == 0
    assert "no durations" in out
    assert out.splitlines()[-1] == TOTAL_LINE


def test_cli_reports_a_missing_index_with_one_error_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["video-coverage", "--artifact-dir", str(tmp_path / "empty")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.strip().splitlines()) == 1
    assert captured.err.startswith("ERROR ")


def test_cli_reports_a_broken_sections_file_with_one_error_line(
    artifact_dir: Path, tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tree / "videos" / "demo" / "sections.yaml").write_text("schema: 2\n", encoding="utf-8")
    code = main(["video-coverage", "--artifact-dir", str(artifact_dir), "--guides-dir", str(tree)])
    captured = capsys.readouterr()
    assert code == 1
    assert len(captured.err.strip().splitlines()) == 1


def test_the_report_holds_only_paths_labels_and_counts(
    artifact_dir: Path, tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["video-coverage", "--artifact-dir", str(artifact_dir), "--guides-dir", str(tree)])
    out = capsys.readouterr().out
    for forbidden in (
        "Synthetic chunk text",
        "Basics",
        "Chunking",
        "Recap",
        "example.invalid",
        "http",
    ):
        assert forbidden not in out
