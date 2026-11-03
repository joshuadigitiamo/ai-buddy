"""Which files of the Guides checkout are indexed (D-19)."""

from pathlib import Path

from buddy_sync.guides import select_guide_files

EXTRA = "AI-Engineering/MULTI_AGENT_ARCHITECTURE_DESIGN.md"


def _touch(root: Path, relpath: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## S\n\nbody\n", encoding="utf-8")


def test_globs(tmp_path: Path) -> None:
    root = tmp_path / "guides"
    for relpath in (
        "AI-Engineering/A_GUIDE.md",
        "AI-Engineering/LangChain/B_GUIDE.md",
        "Foundations/C_GUIDE.md",
        "AI-Engineering/MULTI_AGENT_ARCHITECTURE_DESIGN.md",
        "README.md",
        "CLAUDE.md",
        "AI-Engineering/CLAUDE.md",
        "videos/demo/D_GUIDE.md",
        ".git/E_GUIDE.md",
    ):
        _touch(root, relpath)
    outside = tmp_path / "outside" / "F_GUIDE.md"
    _touch(tmp_path, "outside/F_GUIDE.md")
    (root / "Foundations" / "F_GUIDE.md").symlink_to(outside)

    assert select_guide_files(root) == [
        "AI-Engineering/A_GUIDE.md",
        "AI-Engineering/LangChain/B_GUIDE.md",
        "AI-Engineering/MULTI_AGENT_ARCHITECTURE_DESIGN.md",
        "Foundations/C_GUIDE.md",
    ]


def test_extra_files_are_listed_only_when_present(tmp_path: Path) -> None:
    root = tmp_path / "guides"
    _touch(root, "Foundations/C_GUIDE.md")
    assert select_guide_files(root) == ["Foundations/C_GUIDE.md"]


def test_extra_file_symlinked_outside_the_checkout_is_excluded(tmp_path: Path) -> None:
    root = tmp_path / "guides"
    root.mkdir()
    _touch(tmp_path, "outside/MULTI_AGENT_ARCHITECTURE_DESIGN.md")
    target = root / EXTRA
    target.parent.mkdir(parents=True)
    target.symlink_to(tmp_path / "outside" / "MULTI_AGENT_ARCHITECTURE_DESIGN.md")
    assert select_guide_files(root) == []
