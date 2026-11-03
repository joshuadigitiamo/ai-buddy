"""Acquire the Guides repo with git (D-22): clone once, then fetch and reset a checkout we own.

``GuidesSource`` is the port; ``GitGuidesSource`` is the adapter. The destructive ``reset``
only ever runs in a directory that carries the ``.buddy-sync-checkout`` marker the job wrote
itself, so a misconfigured ``GUIDES_CHECKOUT_DIR`` cannot touch a working repository.
"""

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol
from urllib.parse import urlsplit

from pydantic import SecretStr

MARKER_NAME: Final = ".buddy-sync-checkout"

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_TIMEOUT_S: Final = 300

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class GuidesGitError(Exception):
    """A git step failed or the configuration is unsafe. The message never holds the token."""


@dataclass(frozen=True, slots=True)
class GuidesCheckout:
    """A checked-out Guides tree and the commit it is at."""

    path: Path
    commit_sha: str


class GuidesSource(Protocol):
    """Port: something that can produce a current Guides checkout."""

    def sync(self) -> GuidesCheckout: ...


def _validate_url(url: str) -> None:
    if not url or url.startswith("-") or "::" in url:
        raise GuidesGitError("guides repo url is not acceptable")
    parts = urlsplit(url)
    if parts.scheme in ("http", "https") and ("@" in parts.netloc):
        raise GuidesGitError("guides repo url must not carry credentials")


def _validate_branch(branch: str) -> None:
    if branch.startswith("-") or not _BRANCH_RE.match(branch):
        raise GuidesGitError("guides branch is not acceptable")


class GitGuidesSource:
    """Clone ``url`` on ``branch`` into ``checkout_dir`` and keep it at the branch head."""

    def __init__(
        self,
        *,
        url: str,
        branch: str,
        checkout_dir: Path,
        token: SecretStr | None,
        runner: Runner = subprocess.run,
    ) -> None:
        _validate_url(url)
        _validate_branch(branch)
        self._url = url
        self._branch = branch
        self._dir = checkout_dir
        self._token = token
        self._runner = runner

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")}
        entries: list[tuple[str, str]] = [("safe.directory", "*")]
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_COUNT"] = str(len(entries))
        for index, (key, value) in enumerate(entries):
            env[f"GIT_CONFIG_KEY_{index}"] = key
            env[f"GIT_CONFIG_VALUE_{index}"] = value
        return env

    def _git(self, *args: str) -> str:
        argv = ["git", *args]
        try:
            result = self._runner(
                argv,
                check=True,
                capture_output=True,
                text=True,
                env=self._env(),
                timeout=_TIMEOUT_S,
            )
        except subprocess.CalledProcessError as exc:
            raise GuidesGitError(
                f"git {_subcommand(args)} failed with exit code {exc.returncode}"
            ) from None
        except subprocess.TimeoutExpired:
            raise GuidesGitError(f"git {_subcommand(args)} timed out") from None
        return str(result.stdout).strip()

    def sync(self) -> GuidesCheckout:
        git_dir = self._dir / ".git"
        if not git_dir.exists():
            self._dir.parent.mkdir(parents=True, exist_ok=True)
            self._git(
                "clone",
                "--depth",
                "1",
                "--branch",
                self._branch,
                "--single-branch",
                "--",
                self._url,
                str(self._dir),
            )
            (self._dir / MARKER_NAME).write_text(
                "created by buddy_sync; safe to fetch and reset\n", encoding="utf-8"
            )
        else:
            if not (self._dir / MARKER_NAME).is_file():
                raise GuidesGitError(
                    f"{self._dir} holds a git repository this job did not create; refusing to reset"
                )
            self._git("-C", str(self._dir), "fetch", "--depth", "1", "origin", self._branch)
            self._git("-C", str(self._dir), "reset", "--hard", "FETCH_HEAD")
        sha = self._git("-C", str(self._dir), "rev-parse", "HEAD")
        if not _SHA_RE.match(sha):
            raise GuidesGitError("git rev-parse HEAD did not return a commit id")
        return GuidesCheckout(path=self._dir, commit_sha=sha)


def _subcommand(args: tuple[str, ...]) -> str:
    """The git subcommand in an argv tail, skipping a leading ``-C <dir>``."""
    rest = list(args)
    if rest[:1] == ["-C"]:
        rest = rest[2:]
    return rest[0] if rest else "?"
