"""Toolchain smoke tests: prove the Dockerized quality gate runs real code end to end."""

import re
import sqlite3
import subprocess
import sys

import buddy_core
import buddy_sync


def test_runs_python_312() -> None:
    assert (sys.version_info.major, sys.version_info.minor) == (3, 12)


def test_sqlite_has_fts5() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE t USING fts5("
            "body, tokenize='porter unicode61 remove_diacritics 2')"
        )
    finally:
        conn.close()


def test_git_is_at_least_2_31() -> None:
    out = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout
    match = re.search(r"(\d+)\.(\d+)", out)
    assert match is not None
    assert (int(match.group(1)), int(match.group(2))) >= (2, 31)


def test_packages_import() -> None:
    assert buddy_core.__version__ == "0.1.0"
    assert buddy_sync.__version__ == "0.1.0"
