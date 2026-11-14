"""Video upload and URL rewrite (D-16, D-17): bucket upload, md5 skip, rewritten index links."""

import logging
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from tests.unit.buddy_core.conftest import FakeBucket
from tests.unit.buddy_sync.test_video_map import all_chunks

from buddy_core.index_reader import open_index
from buddy_core.models import video_link
from buddy_sync.chunker import heading_outline
from buddy_sync.cli import main
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_index import write_guides_index
from buddy_sync.video_map import (
    VideoMapError,
    gcs_video_url,
    parse_readme_videos,
    resolve_video_links,
)
from buddy_sync.video_upload import UploadReport, VideoUploadError, upload_videos

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
README_TEXT = (FIXTURES / "guides_videos" / "README.md").read_text(encoding="utf-8")
NAMES = ("demo.mp4", "fallback.mp4", "multi_part1.mp4", "multi_part2.mp4")
BUCKET = "demo-ai-buddy-videos"
GCS_PREFIX = f"https://storage.cloud.google.com/{BUCKET}/videos/"
RepoFactory = Callable[[Mapping[str, str] | Path], Path]
LOGGER = logging.getLogger("buddy_sync.test")


def _video_dir(root: Path, names: tuple[str, ...] = NAMES, *, body: bytes = b"fake-mp4") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in names:
        (root / name).write_bytes(body + name.encode("ascii"))
    return root


def test_upload_stores_every_readme_video_with_private_inline_headers(tmp_path: Path) -> None:
    bucket = FakeBucket()
    videos = parse_readme_videos(README_TEXT)
    report = upload_videos(videos, [_video_dir(tmp_path / "v")], bucket)
    assert report == UploadReport(uploaded=4, unchanged=0)
    assert sorted(bucket.objects) == [f"videos/{name}" for name in NAMES]
    for name in NAMES:
        assert bucket.objects[f"videos/{name}"] == b"fake-mp4" + name.encode("ascii")
        assert bucket.metadata[f"videos/{name}"] == {
            "content_type": "video/mp4",
            "content_disposition": "inline",
            "cache_control": "private",
        }


def test_gcs_video_url_rewrites_a_readme_url_to_the_authenticated_object_url() -> None:
    rewrite = gcs_video_url("b")
    assert (
        rewrite("https://github.com/o/r/releases/download/videos/demo.mp4")
        == "https://storage.cloud.google.com/b/videos/demo.mp4"
    )


def test_resolve_video_links_rewrite_points_every_link_at_the_bucket() -> None:
    links = resolve_video_links(
        FIXTURES / "guides_videos", all_chunks(), logger=LOGGER, url_for=gcs_video_url(BUCKET)
    )
    assert links
    assert all(link.video_url.startswith(GCS_PREFIX) for link in links.values())
    scenes = [link for link in links.values() if link.source == "scene"]
    assert scenes
    for link in scenes:
        playable = video_link(link)
        assert playable == f"{link.video_url}#t={int(link.start_seconds or 0)}"
        assert "?" not in playable


def test_resolve_video_links_without_url_for_keeps_the_readme_urls() -> None:
    links = resolve_video_links(FIXTURES / "guides_videos", all_chunks(), logger=LOGGER)
    assert all(link.video_url.startswith("https://videos.example.invalid/") for link in links.values())


# --- pipeline and CLI ------------------------------------------------------------------------


def _guides_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "guides-tree"
    shutil.copytree(FIXTURES / "guides_repo", tree)
    shutil.copy(FIXTURES / "guides_videos" / "README.md", tree / "README.md")
    shutil.copytree(FIXTURES / "guides_videos" / "videos" / "demo", tree / "videos" / "demo")
    outline = {
        relpath: heading_outline((tree / relpath).read_text(encoding="utf-8"))
        for relpath in select_guide_files(tree)
    }
    write_guides_index(tree, outline)
    return tree


@pytest.fixture
def sync_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_repo_factory: RepoFactory
) -> Path:
    """Environment for ``run`` over fixtures; returns the artifact dir."""
    repo = git_repo_factory(_guides_tree(tmp_path))
    handbook = tmp_path / "handbook"
    shutil.copytree(FIXTURES / "handbook", handbook)
    monkeypatch.delenv("VIDEO_BUCKET", raising=False)
    for name, value in {
        "HANDBOOK_DIR": str(handbook),
        "REDACT_PAGE_FILES": "04-rete-ospiti.md",
        "GUIDES_REPO_URL": str(repo),
        "GUIDES_BRANCH": "master",
        "GUIDES_CHECKOUT_DIR": str(tmp_path / "checkout"),
        "ARTIFACT_DIR": str(tmp_path / "artifacts"),
    }.items():
        monkeypatch.setenv(name, value)
    return tmp_path / "artifacts"


def _video_urls(artifact_dir: Path) -> set[str]:
    with open_index(artifact_dir / "index.db") as reader:
        return {link.video_url for link in reader.video_links().values()}


def test_pipeline_run_with_video_bucket_publishes_the_rewritten_links(
    sync_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("VIDEO_BUCKET", BUCKET)
    assert main(["run"]) == 0
    capsys.readouterr()
    assert _video_urls(sync_env) == {f"{GCS_PREFIX}demo.mp4"}
    with open_index(sync_env / "index.db") as reader:
        links = [video_link(link) for link in reader.video_links().values()]
    assert f"{GCS_PREFIX}demo.mp4#t=30" in links


def test_pipeline_run_without_video_bucket_keeps_the_readme_urls(
    sync_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run"]) == 0
    capsys.readouterr()
    assert _video_urls(sync_env) == {"https://videos.example.invalid/demo.mp4"}


def test_upload_videos_cli_prints_the_counts_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    guides = tmp_path / "guides"
    guides.mkdir()
    (guides / "README.md").write_text(README_TEXT, encoding="utf-8")
    videos = _video_dir(tmp_path / "videos")
    bucket = FakeBucket()
    monkeypatch.setenv("VIDEO_BUCKET", BUCKET)
    requested: list[str] = []

    def factory(name: str) -> FakeBucket:
        requested.append(name)
        return bucket

    code = main(
        ["upload-videos", "--guides-dir", str(guides), "--videos-dir", str(videos)],
        bucket_factory=factory,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out.strip() == "uploaded=4 unchanged=0"
    assert requested == [BUCKET]
    assert len(bucket.objects) == 4


def test_a_basename_that_is_not_a_plain_mp4_name_cannot_become_an_object_name() -> None:
    with pytest.raises(VideoMapError):
        gcs_video_url(BUCKET)("https://h.example.invalid/..%2Fx.mp4")
