"""Structural pins of scripts/sync-and-publish.sh: the forced Cloud Run revision (INFRA-05, 04-20).

The script cannot run in the test image (it needs docker and gcloud), so these tests read its text.
CI names its revisions `<service>-r<run id>-<attempt>`; a publish names its own `p<build>-<epoch>`, so
the two never collide, and a second publish of the same build id (after an index-object repair) still
gets a new name.
"""

import re

from tests.unit.test_repo_layout import ROOT

SCRIPT = ROOT / "scripts" / "sync-and-publish.sh"


def _code() -> str:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_forced_revision_names_itself_after_the_build() -> None:
    code = _code()
    update = [line for line in code.splitlines() if "run services update" in line]
    assert len(update) == 1
    assert '--revision-suffix "${REVISION_SUFFIX}"' in update[0]
    assert "INDEX_BUILD_ID" in update[0], "D-08 kept: the build id still goes into the env"
    assert "^[a-z0-9]([a-z0-9-]*[a-z0-9])?$" in code, "the suffix is checked against a DNS label"
    assert not re.search(r"\bset\s+-[a-z]*x", code), "tracing would print the project id"


def test_forced_revision_suffix_is_unique_per_run() -> None:
    code = _code()
    assigned = re.search(r'^REVISION_SUFFIX="p\$\{BUILD_PART\}-\$\(date -u \+%s\)"$', code, re.M)
    assert assigned, "the suffix is p, the build part, a hyphen and the epoch seconds of this run"
    assert "${BUILD_PART:0:32}" in code, "the build part is cut to 32 characters"
    assert re.search(r"\$\{#REVISION_SUFFIX\}\s*-gt\s*44|\$\{#REVISION_SUFFIX\}\s*>\s*44", code)
    assert code.index("REVISION_SUFFIX=") < code.index("run services update")
