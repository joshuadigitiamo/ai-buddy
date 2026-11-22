"""Production defaults of `buddy_eval.cli.main` and the `python -m buddy_eval` entry point.

Synthetic data only; the model, the MCP server and the trace sink stay in-process.
"""

import io
import runpy
import sys

import pytest
from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import (
    GOOD_VERDICT,
    RecordingTraceSink,
    golden_item,
    write_golden,
)
from tests.unit.chat_bot.conftest import GOOD_DRAFT, REFORMULATION, FakeLlm

from buddy_bot.llm import AnthropicMessagesClient, build_llm_client
from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.schemas import AnswerDraft, Reformulation, RetryPlan
from buddy_eval import cli
from buddy_eval.config import EvalSettings
from buddy_eval.judge import JudgeVerdict

GAP_ID = "item-gap-01"
LEAVE_ID = "item-leave-01"

NO_RESULT = Reformulation(
    standalone_question="Domanda senza risposta?",
    keywords_it=["zzzz"],
    keywords_en=["zzzz"],
    intent="question",
    sensitive_topic=None,
)
NO_RESULT_RETRY = RetryPlan(keywords_it=["yyyy"], keywords_en=["yyyy"])


def _write_items(settings: EvalSettings) -> None:
    write_golden(settings.golden_public_path, [golden_item(GAP_ID, "no_answer")])
    write_golden(settings.golden_private_path, [golden_item(LEAVE_ID, "handbook")])


class _ConstructedSink(RecordingTraceSink):
    """Stands in for MlflowTraceSink on buddy_eval.cli and remembers how it was built."""

    built_with: list[EvalSettings] = []  # noqa: RUF012 - reset by the fixture

    def __init__(self, settings: EvalSettings) -> None:
        super().__init__()
        type(self).built_with.append(settings)


@pytest.fixture
def constructed_sink(monkeypatch: pytest.MonkeyPatch) -> type[_ConstructedSink]:
    _ConstructedSink.built_with = []
    monkeypatch.setattr(cli, "MlflowTraceSink", _ConstructedSink)
    return _ConstructedSink


class TestLlmSeam:
    def test_build_llm_client_accepts_eval_settings_for_meridian_without_network(self) -> None:
        client = build_llm_client(
            EvalSettings(llm_backend="meridian", llm_base_url="http://stub:8090")
        )

        assert isinstance(client, AnthropicMessagesClient)

    def test_build_llm_client_accepts_eval_settings_for_the_api_backend(self) -> None:
        settings = EvalSettings.model_validate(
            {"llm_backend": "api", "anthropic_api_key": "synthetic-key"}
        )

        assert isinstance(build_llm_client(settings), AnthropicMessagesClient)


class TestProductionDefaults:
    def test_run_without_injected_factories_builds_the_client_and_the_sink_from_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
        eval_settings: EvalSettings,
        mcp_server: FastMCP,
        constructed_sink: type[_ConstructedSink],
    ) -> None:
        _write_items(eval_settings)
        llm = FakeLlm(
            {
                Reformulation: [NO_RESULT, REFORMULATION],
                RetryPlan: [NO_RESULT_RETRY],
                AnswerDraft: [GOOD_DRAFT],
                JudgeVerdict: [GOOD_VERDICT],
            }
        )
        built_for: list[EvalSettings] = []

        def fake_build(settings: EvalSettings) -> FakeLlm:
            built_for.append(settings)
            return llm

        monkeypatch.setattr(cli, "build_llm_client", fake_build)
        out = io.StringIO()

        code = cli.main(
            ["run"],
            settings=eval_settings,
            connector_factory=lambda _url: FastMcpConnector(mcp_server),
            out=out,
        )

        lines = out.getvalue().splitlines()
        assert code == 0
        assert [line for line in lines if line.startswith("item-")] == [
            f"{GAP_ID} no_answer correct trace=http://ui/#/t/tr-1 (tr-1)",
            f"{LEAVE_ID} handbook correct trace=http://ui/#/t/tr-2 (tr-2)",
        ]
        assert constructed_sink.built_with == [eval_settings]
        assert built_for and all(settings is eval_settings for settings in built_for)

    def test_run_without_a_tracking_uri_ends_with_one_error_line_and_no_model_call(
        self,
        monkeypatch: pytest.MonkeyPatch,
        eval_settings: EvalSettings,
        mcp_server: FastMCP,
    ) -> None:
        _write_items(eval_settings)
        assert eval_settings.mlflow_tracking_uri is None
        model_calls: list[EvalSettings] = []

        def counting_build(settings: EvalSettings) -> FakeLlm:
            model_calls.append(settings)
            return FakeLlm({})

        monkeypatch.setattr(cli, "build_llm_client", counting_build)
        out = io.StringIO()

        code = cli.main(
            ["run"],
            settings=eval_settings,
            connector_factory=lambda _url: FastMcpConnector(mcp_server),
            out=out,
        )

        lines = out.getvalue().splitlines()
        assert code == 1
        assert len(lines) == 1
        assert lines[0].startswith("ERROR:")
        assert "MLFLOW_TRACKING_URI" in lines[0]
        assert model_calls == []

    def test_injected_factories_take_precedence_over_the_defaults(
        self,
        monkeypatch: pytest.MonkeyPatch,
        eval_settings: EvalSettings,
        mcp_server: FastMCP,
        constructed_sink: type[_ConstructedSink],
    ) -> None:
        _write_items(eval_settings)
        monkeypatch.setattr(cli, "build_llm_client", lambda _s: pytest.fail("default llm used"))
        injected = RecordingTraceSink()
        llm = FakeLlm(
            {
                Reformulation: [NO_RESULT, REFORMULATION],
                RetryPlan: [NO_RESULT_RETRY],
                AnswerDraft: [GOOD_DRAFT],
                JudgeVerdict: [GOOD_VERDICT],
            }
        )

        code = cli.main(
            ["run"],
            settings=eval_settings,
            llm_factory=lambda: llm,
            sink_factory=lambda _s: injected,
            connector_factory=lambda _url: FastMcpConnector(mcp_server),
            out=io.StringIO(),
        )

        assert code == 0
        assert len(injected.traced_calls) == 2
        assert constructed_sink.built_with == []


class TestEntryPoint:
    def test_python_dash_m_buddy_eval_help_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["buddy_eval", "--help"])

        with pytest.raises(SystemExit) as exit_info:
            runpy.run_module("buddy_eval", run_name="__main__")

        assert exit_info.value.code == 0
        assert "usage: buddy_eval" in capsys.readouterr().out
