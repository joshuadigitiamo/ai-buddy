"""Token hygiene, marker guard, pull behaviour and the SHA-based skip (D-22, D-24)."""

import base64
import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from buddy_core.index_reader import IndexReader, open_index
from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, IndexContent, make_chunk_key
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.chunker import PIPELINE_VERSION
from buddy_sync.guides import sync_guides
from buddy_sync.guides_git import MARKER_NAME, GitGuidesSource, GuidesCheckout, GuidesGitError
from buddy_sync.redaction import REDACTION_VERSION, Redactor

RepoFactory = Callable[[Mapping[str, str] | Path], Path]
CommitFn = Callable[[Path, str, str], str]

LOGGER = logging.getLogger("buddy_sync.test")
TOKEN = "ghp_SYNTHETICTOKEN000000000000000000000000"
TOKEN_B64 = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
HTTPS_URL = "https://github.com/example/guides.git"
SHA = "a" * 40
GUIDE = "## Section\n\nbody\n"


class RecordingRunner:
    """Fake subprocess.run that records argv and env and can fail on demand."""

    def __init__(self, fail_with: subprocess.CalledProcessError | None = None) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self._fail_with = fail_with

    def __call__(self, argv: Sequence[str], **kwargs: Any) -> "subprocess.CompletedProcess[str]":
        self.calls.append((list(argv), dict(kwargs["env"])))
        if self._fail_with is not None:
            raise self._fail_with
        if "clone" in argv:
            target = Path(argv[-1])
            (target / ".git").mkdir(parents=True)
        stdout = SHA + "\n" if "rev-parse" in argv else ""
        return subprocess.CompletedProcess(list(argv), 0, stdout=stdout, stderr="")


def _source(tmp_path: Path, runner: RecordingRunner, **kwargs: Any) -> GitGuidesSource:
    params: dict[str, Any] = {
        "url": HTTPS_URL,
        "branch": "master",
        "checkout_dir": tmp_path / "checkout",
        "token": SecretStr(TOKEN),
        "runner": runner,
    }
    params.update(kwargs)
    return GitGuidesSource(**params)


def test_pull_picks_up_a_new_commit(
    tmp_path: Path, git_repo_factory: RepoFactory, git_commit: CommitFn
) -> None:
    repo = git_repo_factory({"A_GUIDE.md": GUIDE})
    source = GitGuidesSource(
        url=str(repo), branch="master", checkout_dir=tmp_path / "checkout", token=None
    )
    first = source.sync()
    second_sha = git_commit(repo, "B_GUIDE.md", GUIDE)
    second = source.sync()
    assert second.commit_sha == second_sha
    assert second.commit_sha != first.commit_sha
    assert (second.path / "B_GUIDE.md").is_file()
    assert (second.path / MARKER_NAME).is_file()


def test_token_travels_only_as_http_extra_header_in_the_child_env(tmp_path: Path) -> None:
    runner = RecordingRunner()
    _source(tmp_path, runner).sync()
    assert runner.calls
    for argv, env in runner.calls:
        assert not any(TOKEN in arg or TOKEN_B64 in arg for arg in argv)
        count = int(env["GIT_CONFIG_COUNT"])
        entries = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)}
        assert entries["http.extraHeader"] == f"Authorization: Basic {TOKEN_B64}"
        assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_token_is_not_used_for_a_non_https_url(tmp_path: Path) -> None:
    runner = RecordingRunner()
    _source(tmp_path, runner, url=str(tmp_path / "local-repo")).sync()
    for _argv, env in runner.calls:
        count = int(env["GIT_CONFIG_COUNT"])
        keys = [env[f"GIT_CONFIG_KEY_{i}"] for i in range(count)]
        assert "http.extraHeader" not in keys


def test_local_clone_leaves_neither_token_nor_header_in_git_config(
    tmp_path: Path, git_repo_factory: RepoFactory
) -> None:
    repo = git_repo_factory({"A_GUIDE.md": GUIDE})
    source = GitGuidesSource(
        url=str(repo),
        branch="master",
        checkout_dir=tmp_path / "checkout",
        token=SecretStr(TOKEN),
    )
    checkout = source.sync()
    config = (checkout.path / ".git" / "config").read_text(encoding="utf-8")
    assert TOKEN not in config
    assert TOKEN_B64 not in config
    assert "extraHeader" not in config


def test_failure_message_is_scrubbed_of_token_and_its_base64(tmp_path: Path) -> None:
    stderr = f"fatal: Authentication failed {TOKEN} header Authorization: Basic {TOKEN_B64}"
    failure = subprocess.CalledProcessError(128, ["git", "clone"], stderr=stderr)
    with pytest.raises(GuidesGitError) as caught:
        _source(tmp_path, RecordingRunner(fail_with=failure)).sync()
    message = str(caught.value)
    assert TOKEN not in message
    assert TOKEN_B64 not in message
    assert "clone" in message
    assert "128" in message
    assert "Authentication failed" in message


def test_existing_git_dir_without_marker_is_never_touched(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    runner = RecordingRunner()
    with pytest.raises(GuidesGitError):
        _source(tmp_path, runner, checkout_dir=checkout).sync()
    assert runner.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "-oProxyCommand=x",
        "ext::sh -c x",
        "https://user:pw@github.com/x.git",
        "https://user@github.com/x.git",
    ],
)
def test_unsafe_urls_are_rejected(tmp_path: Path, url: str) -> None:
    runner = RecordingRunner()
    with pytest.raises(GuidesGitError):
        _source(tmp_path, runner, url=url).sync()
    assert runner.calls == []


@pytest.mark.parametrize("branch", ["-x", "--upload-pack=x", "a b"])
def test_unsafe_branches_are_rejected(tmp_path: Path, branch: str) -> None:
    runner = RecordingRunner()
    with pytest.raises(GuidesGitError):
        _source(tmp_path, runner, branch=branch).sync()
    assert runner.calls == []


def _published_reader(tmp_path: Path, commit_sha: str) -> IndexReader:
    """An artifact whose single chunk is a sentinel no rebuild could produce."""
    chunk = GuideChunk(
        chunk_key=make_chunk_key("Old/OLD_GUIDE.md", "Old", None, 0),
        file="Old/OLD_GUIDE.md",
        h2="Old",
        h3=None,
        heading="Old",
        line_start=1,
        line_end=3,
        part_index=0,
        text="text that only the previous index holds",
    )
    content = IndexContent(
        handbook=(),
        chunks=(chunk,),
        videos={},
        source_doc_id="doc-synthetic",
        guides_commit_sha=commit_sha,
        pipeline_version=PIPELINE_VERSION,
        redaction_version=REDACTION_VERSION,
    )
    store = LocalDirArtifactStore(tmp_path / "artifacts")
    staged = store.staging_path()
    meta = build_index(content, staged, now=datetime.now(UTC))
    return open_index(store.publish(staged, meta))


def _checkout(tmp_path: Path, commit_sha: str) -> GuidesCheckout:
    root = tmp_path / "co"
    (root / "Foundations").mkdir(parents=True)
    (root / "Foundations" / "NEW_GUIDE.md").write_text("## New\n\nfresh body\n", encoding="utf-8")
    return GuidesCheckout(path=root, commit_sha=commit_sha)


def _sync(tmp_path: Path, previous: IndexReader, sha: str, *, versions_match: bool) -> Any:
    return sync_guides(
        _checkout(tmp_path, sha),
        previous=previous,
        versions_match=versions_match,
        redactor=Redactor(email_allow_domains=frozenset({"digitiamo.com"})),
        logger=LOGGER,
    )


def test_unchanged_sha_and_versions_reuse_previous_chunks(tmp_path: Path) -> None:
    with _published_reader(tmp_path, SHA) as previous:
        result = _sync(tmp_path, previous, SHA, versions_match=True)
        assert result.rebuilt is False
        assert result.chunks == tuple(previous.guide_chunks())
        assert result.commit_sha == SHA
        assert list(result.outline) == ["Foundations/NEW_GUIDE.md"]


def test_version_mismatch_rebuilds_even_with_the_same_sha(tmp_path: Path) -> None:
    with _published_reader(tmp_path, SHA) as previous:
        result = _sync(tmp_path, previous, SHA, versions_match=False)
        assert result.rebuilt is True
        assert [c.file for c in result.chunks] == ["Foundations/NEW_GUIDE.md"]


def test_new_sha_rebuilds(tmp_path: Path) -> None:
    with _published_reader(tmp_path, SHA) as previous:
        result = _sync(tmp_path, previous, "b" * 40, versions_match=True)
        assert result.rebuilt is True
        assert [c.file for c in result.chunks] == ["Foundations/NEW_GUIDE.md"]
