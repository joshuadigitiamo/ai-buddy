"""Synthetic fixtures only: no handbook text, no names, no credentials."""

from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastmcp import FastMCP
from tests.unit.chat_bot.conftest import CONTACTS_PAGE
from tests.unit.mcp_server.conftest import NOW, WEB_BASE, make_content, write_index

from buddy_bot.workflow import WorkflowConfig
from buddy_eval.config import EvalSettings
from buddy_eval.scoring import ItemVerdict
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import load_snapshot

# Settings read from the host environment must not leak into the settings under test.
_SETTINGS_VARIABLES = (
    "LLM_BACKEND",
    "LLM_BASE_URL",
    "ANTHROPIC_API_KEY",
    "MERIDIAN_API_KEY",
    "LLM_TIMEOUT_SECONDS",
    "REFORMULATE_MODEL",
    "ANSWER_MODEL",
    "JUDGE_MODEL",
    "CONFIDENCE_THRESHOLD",
    "MCP_URL",
    "GOLDEN_PUBLIC_PATH",
    "GOLDEN_PRIVATE_PATH",
    "PRIVATE_DIR",
    "MLFLOW_TRACKING_URI",
    "MLFLOW_EXPERIMENT",
    "MLFLOW_UI_BASE_URL",
    "MAX_CONSECUTIVE_ERRORS",
    "ITEM_PAUSE_SECONDS",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING_V2",
)


@pytest.fixture(autouse=True)
def _clean_eval_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _SETTINGS_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def gaplog() -> InMemoryGapLog:
    return InMemoryGapLog()


@pytest.fixture
def mcp_server(tmp_path: Path, gaplog: InMemoryGapLog) -> Iterator[FastMCP]:
    base = make_content()
    content = make_content(pages=(*base.handbook, CONTACTS_PAGE))
    directory = tmp_path / "artifacts"
    write_index(directory, content)
    snapshot = load_snapshot(directory / "index.db")
    settings = McpSettings(
        artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
    )
    yield build_server(settings, snapshot=snapshot, gaplog=gaplog, now=lambda: NOW)
    snapshot.reader.close()
    snapshot.handbook_index.close()


@pytest.fixture
def workflow_config() -> WorkflowConfig:
    return WorkflowConfig(
        reformulate_model="test-haiku", answer_model="test-sonnet", confidence_threshold=0.7
    )


@dataclass(frozen=True, slots=True)
class TracedCall:
    name: str
    tags: Mapping[str, str]
    trace_id: str


@dataclass(frozen=True, slots=True)
class ScoreCall:
    trace_ids: tuple[str, ...]
    verdicts: Mapping[str, ItemVerdict]
    traced_before: int


@dataclass
class RecordingTraceSink:
    """A TraceSink that records every call; trace ids are tr-1, tr-2, ..."""

    runs: list[tuple[str, Mapping[str, str]]] = field(default_factory=list)
    traced_calls: list[TracedCall] = field(default_factory=list)
    expectations: dict[str, Mapping[str, object]] = field(default_factory=dict)
    score_calls: list[ScoreCall] = field(default_factory=list)

    def run(self, name: str, tags: Mapping[str, str]) -> AbstractContextManager[str | None]:
        return self._run(name, tags)

    @contextmanager
    def _run(self, name: str, tags: Mapping[str, str]) -> Iterator[str | None]:
        self.runs.append((name, dict(tags)))
        yield "run-1"

    async def traced(
        self,
        name: str,
        tags: Mapping[str, str],
        fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], str]:
        output = await fn()
        trace_id = f"tr-{len(self.traced_calls) + 1}"
        self.traced_calls.append(TracedCall(name, dict(tags), trace_id))
        return output, trace_id

    def log_expectations(self, trace_id: str, expectations: Mapping[str, object]) -> None:
        self.expectations[trace_id] = dict(expectations)

    def score(self, trace_ids: Sequence[str], verdicts: Mapping[str, ItemVerdict]) -> None:
        self.score_calls.append(
            ScoreCall(tuple(trace_ids), dict(verdicts), traced_before=len(self.traced_calls))
        )

    def trace_url(self, trace_id: str) -> str:
        return f"http://ui/#/t/{trace_id}"


def golden_item(item_id: str, kind: str, **overrides: Any) -> dict[str, Any]:
    """A valid raw golden item per kind (synthetic text); overrides replace any field."""
    base: dict[str, Any] = {
        "id": item_id,
        "kind": kind,
        "question": f"synthetic question for {item_id}",
        "expected_answer": "synthetic expected answer",
        "key_facts": [],
        "expected_sources": [],
        "expected_referente_role": None,
        "review": "approved",
        "review_note": "",
    }
    if kind == "handbook":
        base["key_facts"] = ["synthetic fact"]
        base["expected_sources"] = ["handbook://02-ferie"]
    elif kind == "guides":
        base["key_facts"] = ["synthetic fact"]
        base["expected_sources"] = ["https://example.invalid/guides/a.md#s1"]
    elif kind in ("no_answer", "sensitive"):
        base["expected_referente_role"] = "HR"
    base.update(overrides)
    return base


def write_golden(path: Path, items: Sequence[Mapping[str, Any]]) -> Path:
    """Write the golden YAML shape `{schema_version: 1, items: [...]}`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "items": [dict(i) for i in items]}, sort_keys=False),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def eval_settings(tmp_path: Path) -> EvalSettings:
    return EvalSettings(
        golden_public_path=tmp_path / "golden" / "guides.yaml",
        golden_private_path=tmp_path / "private" / "golden-handbook.yaml",
        private_dir=tmp_path / "private",
        item_pause_seconds=0,
    )
