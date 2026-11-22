"""The empty-context fixture: reproducible build, loadable index, vocabulary disjoint from the
office and Guides questions, and the `build-fixture` command. Synthetic data only."""

import io
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastmcp import FastMCP
from tests.unit.mcp_server.conftest import NOW, WEB_BASE

from buddy_bot.mcp_client import FastMcpConnector
from buddy_core.escalation import load_escalation_table
from buddy_core.store import INDEX_NAME, MANIFEST_NAME
from buddy_eval import cli, fixture
from buddy_eval.fixture import FixtureError, build_fixture, build_fixture_content
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import load_snapshot

pytestmark = pytest.mark.anyio

EVAL_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "eval"
OFFICE_KEYWORDS = ("ferie", "rimborsi", "deploy", "chunking")
_TOKEN = re.compile(r"[a-zà-ÿ]{4,}")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _fixture_tokens() -> set[str]:
    content = build_fixture_content()
    found: set[str] = set()
    for page in content.handbook:
        found |= _tokens(f"{page.title} {page.content_md}")
    for chunk in content.chunks:
        found |= _tokens(f"{chunk.h2} {chunk.h3 or ''} {chunk.heading} {chunk.text}")
    return found


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def served(tmp_path: Path) -> Iterator[FastMCP]:
    build_fixture(tmp_path / "empty")
    snapshot = load_snapshot(tmp_path / "empty" / INDEX_NAME)
    settings = McpSettings(
        artifact_dir=tmp_path / "empty",
        guides_web_base=WEB_BASE,
        auth_mode="off",
        deploy_env="local",
    )
    yield build_server(settings, snapshot=snapshot, gaplog=InMemoryGapLog(), now=lambda: NOW)
    snapshot.reader.close()
    snapshot.handbook_index.close()


def test_build_writes_a_loadable_index_with_two_pages_three_chunks_and_no_video(
    tmp_path: Path,
) -> None:
    meta = build_fixture(tmp_path / "out")

    assert (tmp_path / "out" / INDEX_NAME).is_file()
    assert (tmp_path / "out" / MANIFEST_NAME).is_file()
    manifest = json.loads((tmp_path / "out" / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["content_hash"] == meta.content_hash
    snapshot = load_snapshot(tmp_path / "out" / INDEX_NAME)
    try:
        assert len(snapshot.pages) == 2
        assert len(snapshot.chunks) == 3
        assert dict(snapshot.videos) == {}
        assert snapshot.meta.source_doc_id == "eval-empty-fixture"
    finally:
        snapshot.reader.close()
        snapshot.handbook_index.close()


def test_two_builds_of_the_same_sources_give_the_same_content_hash(tmp_path: Path) -> None:
    first = build_fixture(tmp_path / "a")
    second = build_fixture(tmp_path / "b")

    assert first.content_hash == second.content_hash
    assert first.build_id == second.build_id
    assert first.created_at_utc == second.created_at_utc


def test_a_second_build_into_the_same_directory_replaces_the_index(tmp_path: Path) -> None:
    first = build_fixture(tmp_path / "out")
    second = build_fixture(tmp_path / "out")

    assert second.content_hash == first.content_hash
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [INDEX_NAME, MANIFEST_NAME]


def test_different_sources_give_a_different_content_hash(tmp_path: Path) -> None:
    raw = yaml.safe_load(fixture.FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["pages"][0]["text"] += " ife"
    changed = tmp_path / "changed.yaml"
    changed.write_text(yaml.safe_dump(raw), encoding="utf-8")

    assert (
        build_fixture(tmp_path / "a", changed).content_hash
        != build_fixture(tmp_path / "b").content_hash
    )


def test_fixture_vocabulary_is_disjoint_from_the_fixture_golden_questions() -> None:
    questions: set[str] = set()
    for path in sorted(EVAL_FIXTURES.glob("golden-*.yaml")):
        for item in yaml.safe_load(path.read_text(encoding="utf-8"))["items"]:
            questions |= _tokens(str(item["question"]))
    assert questions, "the golden fixtures hold questions"

    assert _fixture_tokens() & questions == set()


def test_fixture_vocabulary_is_disjoint_from_the_escalation_topics() -> None:
    table = load_escalation_table()
    topics: set[str] = set()
    for topic in table.topics:
        topics |= _tokens(f"{topic.tema} {topic.referente} {topic.ruolo}")
    assert topics, "the escalation table holds topics"

    assert _fixture_tokens() & topics == set()


def test_fixture_vocabulary_is_disjoint_from_the_office_keywords() -> None:
    assert _fixture_tokens() & set(OFFICE_KEYWORDS) == set()


async def test_a_server_over_the_fixture_finds_nothing_for_office_queries(
    served: FastMCP,
) -> None:
    async with FastMcpConnector(served).session() as tools:
        for keyword in OFFICE_KEYWORDS:
            handbook = await tools.handbook_search(keyword)
            guides = await tools.guides_search(keyword)
            assert handbook.status == "no_results", keyword
            assert guides.status == "no_results", keyword


async def test_a_server_over_the_fixture_does_find_its_own_terms(served: FastMCP) -> None:
    # Guards the test above against a fixture the server cannot search at all.
    async with FastMcpConnector(served).session() as tools:
        assert (await tools.handbook_search("micelio")).status == "ok"
        assert (await tools.guides_search("perihelion")).status == "ok"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.pop("pages"),
        lambda raw: raw.update(pages=[]),
        lambda raw: raw["pages"][0].pop("last_updated"),
        lambda raw: raw["chunks"][0].update(line_start=0),
        lambda raw: raw.update(schema_version=2),
        lambda raw: raw["pages"].append("not a mapping"),
        lambda raw: raw["chunks"][0].update(h3=""),
    ],
)
def test_a_malformed_fixture_is_refused(tmp_path: Path, mutate: object) -> None:
    raw = yaml.safe_load(fixture.FIXTURE_PATH.read_text(encoding="utf-8"))
    mutate(raw)  # type: ignore[operator]
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(FixtureError):
        build_fixture_content(bad)


def test_a_fixture_that_is_not_yaml_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("pages: [unclosed", encoding="utf-8")

    with pytest.raises(FixtureError, match="not valid YAML"):
        build_fixture_content(bad)


def test_build_fixture_command_prints_the_build_id_and_hash_only(tmp_path: Path) -> None:
    out = io.StringIO()

    code = cli.main(["build-fixture", "--dest", str(tmp_path / "out")], out=out)

    meta = build_fixture(tmp_path / "again")
    assert code == 0
    assert out.getvalue() == (
        f"fixture built: build_id={meta.build_id} content_hash={meta.content_hash}\n"
    )
    assert (tmp_path / "out" / INDEX_NAME).is_file()


def test_build_fixture_command_needs_no_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The eval-fixture container has no env file: settings must not be required.
    monkeypatch.setenv("JUDGE_MODEL", "same")
    monkeypatch.setenv("ANSWER_MODEL", "same")

    assert cli.main(["build-fixture", "--dest", str(tmp_path / "out")], out=io.StringIO()) == 0


def test_build_fixture_command_reports_an_unwritable_destination_as_one_error_line(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    out = io.StringIO()

    code = cli.main(["build-fixture", "--dest", str(blocker / "sub")], out=out)

    assert code == 1
    lines = out.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("ERROR: ")


def test_build_fixture_command_reports_a_malformed_source_as_one_error_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 9\n", encoding="utf-8")
    monkeypatch.setattr(fixture, "FIXTURE_PATH", bad)
    monkeypatch.setattr(cli, "build_fixture", lambda dest: build_fixture(dest, bad))
    out = io.StringIO()

    code = cli.main(["build-fixture", "--dest", str(tmp_path / "out")], out=out)

    assert code == 1
    assert out.getvalue().startswith("ERROR: FixtureError: bad.yaml: schema_version")


def test_build_fixture_command_requires_a_destination() -> None:
    assert cli.main(["build-fixture"], out=io.StringIO()) == 2
