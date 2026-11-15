"""Hashed dependency locks (INFRA-01, INFRA-06, review WR-04): every image installs only from a
committed lock where each distribution is pinned with `==` and carries a sha256 hash, and the
locks of the shipped images carry the same versions as the lock of the tested image.

Pure text parsing, no network. Regenerate the locks with scripts/lock-requirements.sh."""

import re

import pytest
from tests.unit.test_repo_layout import ROOT, _lines, _pins

REGENERATE = "run scripts/lock-requirements.sh"
APPROVED_PIP_TOOLS = "pip-tools==7.6.2"

DEV_LOCK = "requirements-dev.lock"
# lock path -> the plain requirement files it is compiled from
STAGE_LOCKS = {
    "services/mcp_server/requirements.lock": (
        "requirements.txt",
        "services/mcp_server/requirements.txt",
    ),
    "services/chat_bot/requirements.lock": (
        "requirements.txt",
        "services/chat_bot/requirements.txt",
    ),
    "jobs/sync/requirements.lock": ("requirements.txt", "jobs/sync/requirements.txt"),
}
DEV_INPUTS = (
    "requirements.txt",
    "requirements-dev.txt",
    "services/mcp_server/requirements.txt",
    "services/chat_bot/requirements.txt",
    "jobs/sync/requirements.txt",
)
ALL_LOCKS = (DEV_LOCK, *STAGE_LOCKS)

ENTRY = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)(\[[^]]+\])?==(?P<version>[^\s;\\]+)")
HASH = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_lock(text: str) -> tuple[dict[str, tuple[str, list[str]]], list[str]]:
    """Entries (name -> (version, hashes)) and a message for every line that is not a pinned,
    hashed requirement. A lock with no entry at all is itself a problem."""
    entries: dict[str, tuple[str, list[str]]] = {}
    problems: list[str] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip().removesuffix("\\").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash="):
            if current is None or not HASH.match(line):
                problems.append(f"hash without a requirement or malformed: {line[:40]}")
            else:
                entries[current][1].append(line)
            continue
        match = ENTRY.match(line)
        if match is None:
            problems.append(f"not a pinned requirement: {line[:60]}")
            current = None
            continue
        current = _normalise(match["name"])
        entries[current] = (match["version"], [])
    unhashed = [name for name, (_, hashes) in entries.items() if not hashes]
    problems.extend(f"{name}: no sha256 hash" for name in unhashed)
    if not entries:
        problems.append("no hashed requirement line at all")
    return entries, problems


def _lock(name: str) -> dict[str, tuple[str, list[str]]]:
    path = ROOT / name
    assert path.is_file(), f"{name} is missing, {REGENERATE}"
    return _parse_lock(path.read_text())[0]


@pytest.mark.parametrize("name", ALL_LOCKS)
def test_lock_is_pinned_and_every_entry_has_a_hash(name: str) -> None:
    path = ROOT / name
    assert path.is_file(), f"{name} is missing, {REGENERATE}"
    _, problems = _parse_lock(path.read_text())
    assert problems == [], f"{name}: {problems}; {REGENERATE}"


def test_lock_parser_rejects_empty_unpinned_and_unhashed_locks() -> None:
    good = "foo==1.0 \\\n    --hash=sha256:" + "a" * 64 + "\n    # via bar\n"
    assert _parse_lock(good)[1] == []
    assert _parse_lock("")[1] == ["no hashed requirement line at all"]
    assert _parse_lock("# only a comment\n")[1] == ["no hashed requirement line at all"]
    assert _parse_lock("foo==1.0\n")[1] == ["foo: no sha256 hash"]
    assert any("not a pinned" in p for p in _parse_lock("foo>=1.0 \\\n --hash=sha256:00\n")[1])
    assert any("malformed" in p for p in _parse_lock("foo==1.0 \\\n --hash=sha256:00\n")[1])


@pytest.mark.parametrize("name", ALL_LOCKS)
def test_lock_has_hashed_entries(name: str) -> None:
    """Edge INFRA-06 empty: a lock that pins nothing cannot back an install."""
    assert len(_lock(name)) > 0, f"{name} pins nothing; {REGENERATE}"


def _drift(
    lock_name: str,
    lock: dict[str, tuple[str, list[str]]],
    pins_by_input: dict[str, dict[str, str]],
) -> list[str]:
    """A message naming the package for every input pin that differs from the lock."""
    drifted = []
    for input_name, pins in pins_by_input.items():
        for package, version in pins.items():
            locked = lock.get(_normalise(package), ("missing", []))[0]
            if locked != version:
                drifted.append(f"{package}: {input_name} pins {version}, {lock_name} has {locked}")
    return drifted


def _assert_inputs_agree(lock_name: str, input_names: tuple[str, ...]) -> None:
    drifted = _drift(lock_name, _lock(lock_name), {n: _pins(n) for n in input_names})
    assert drifted == [], f"{drifted}; {REGENERATE}"


def test_dev_lock_agrees_with_every_input_pin() -> None:
    _assert_inputs_agree(DEV_LOCK, DEV_INPUTS)


@pytest.mark.parametrize("name", STAGE_LOCKS)
def test_stage_lock_agrees_with_its_input_pins(name: str) -> None:
    _assert_inputs_agree(name, STAGE_LOCKS[name])


def test_input_pin_drift_names_the_package_and_an_equal_pin_passes() -> None:
    """Edge INFRA-06 adjacency: equal pins pass, any difference is reported by package name."""
    lock: dict[str, tuple[str, list[str]]] = {"pydantic": ("2.14.2", []), "pyyaml": ("6.0.3", [])}
    equal = {"requirements.txt": {"pydantic": "2.14.2", "PyYAML": "6.0.3"}}
    assert _drift(DEV_LOCK, lock, equal) == []
    drifted = _drift(DEV_LOCK, lock, {"requirements.txt": {"pydantic": "2.14.3"}})
    assert drifted == [f"pydantic: requirements.txt pins 2.14.3, {DEV_LOCK} has 2.14.2"]
    assert _drift(DEV_LOCK, lock, {"requirements.txt": {"absent": "1.0"}}) == [
        f"absent: requirements.txt pins 1.0, {DEV_LOCK} has missing"
    ]


@pytest.mark.parametrize("name", STAGE_LOCKS)
def test_stage_lock_versions_equal_the_dev_lock(name: str) -> None:
    """The code CI tests and the code CI ships resolve the same dependency set (T-04-59)."""
    dev = _lock(DEV_LOCK)
    differing = [
        f"{package}: {name} has {version}, {DEV_LOCK} has {dev.get(package, ('missing',))[0]}"
        for package, (version, _) in _lock(name).items()
        if dev.get(package, (None,))[0] != version
    ]
    assert differing == [], f"{differing}; {REGENERATE}"


def _stage_instructions(stage: str, keyword: str) -> list[str]:
    """Arguments of every `keyword` instruction of one stage, whatever its FROM image."""
    text = (ROOT / "Dockerfile").read_text().replace("\\\n", " ")
    match = re.search(rf"^FROM \S+ AS {stage}$(.*?)(?=^FROM |\Z)", text, re.M | re.S)
    assert match, f"Dockerfile has no {stage} stage"
    return [
        line.split(None, 1)[1].strip()
        for line in match[1].splitlines()
        if line.split(None, 1)[:1] == [keyword]
    ]


def test_test_stage_installs_the_dev_lock_with_require_hashes() -> None:
    assert _stage_instructions("test", "RUN") == [f"pip install --require-hashes -r {DEV_LOCK}"]
    assert DEV_LOCK in " ".join(_stage_instructions("base", "COPY")).split()


def test_lock_script_pins_the_approved_pip_tools_and_generates_hashes() -> None:
    script = (ROOT / "scripts/lock-requirements.sh").read_text()
    assert APPROVED_PIP_TOOLS in script
    assert "--generate-hashes" in script
    assert "set -euo pipefail" in script


def test_pip_tools_stays_out_of_the_images_and_requirement_files() -> None:
    """INFRA-06 prohibition: pip-tools runs only in the throwaway lock container."""
    for name in (*DEV_INPUTS, *ALL_LOCKS):
        assert "pip-tools" not in "\n".join(_lines(name)).lower(), f"{name} lists pip-tools"
    assert "pip-tools" not in (ROOT / "Dockerfile").read_text().lower()
