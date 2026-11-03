"""Shared fixtures: throwaway git repositories for the Guides source tests."""

import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

RepoFactory = Callable[[Mapping[str, str] | Path], Path]
CommitFn = Callable[[Path, str, str], str]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_repo_factory(tmp_path_factory: pytest.TempPathFactory) -> RepoFactory:
    """Build a git repo on branch master with one commit from a path->text map or a directory."""

    def make(source: Mapping[str, str] | Path) -> Path:
        repo = tmp_path_factory.mktemp("guides-src")
        subprocess.run(
            ["git", "-c", "safe.directory=*", "init", "-b", "master", str(repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        _git(repo, "config", "user.name", "Fixture Author")
        _git(repo, "config", "user.email", "fixture@example.invalid")
        _git(repo, "config", "commit.gpgsign", "false")
        if isinstance(source, Path):
            shutil.copytree(source, repo, dirs_exist_ok=True)
        else:
            for relpath, content in source.items():
                target = repo / relpath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        _commit_all(repo, "initial fixture commit")
        return repo

    return make


@pytest.fixture
def git_commit() -> CommitFn:
    """Write one file into a fixture repo, commit it and return the new commit SHA."""

    def commit(repo: Path, relpath: str, content: str) -> str:
        target = repo / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return _commit_all(repo, f"update {relpath}")

    return commit
