"""Tracer: golden files -> real run_workflow over MCP -> trace port -> verdict -> gate -> exit code.

Everything runs in-process: a scripted model, the in-process MCP server and a recording trace sink.
Synthetic data only.
"""

import io
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from fastmcp import FastMCP
from pydantic import ValidationError
from tests.unit.buddy_eval.conftest import RecordingTraceSink, golden_item, write_golden
from tests.unit.chat_bot.conftest import GOOD_DRAFT, REFORMULATION, FakeLlm

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmUnavailableError
from buddy_bot.schemas import AnswerDraft, Reformulation, RetryPlan
from buddy_eval import cli
from buddy_eval.config import EvalSettings
from buddy_eval.gate import GateInputs, evaluate, format_verdict
from buddy_eval.golden import GoldenError, load_golden
from buddy_eval.report import write_json_report
from buddy_mcp.gaplog import InMemoryGapLog

SENTINEL = "SENTINEL-QUESTION-TEXT-7f3a"
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


def _public(settings: EvalSettings, *items: dict[str, object]) -> None:
    write_golden(settings.golden_public_path, items)


def _private(settings: EvalSettings, *items: dict[str, object]) -> None:
    write_golden(settings.golden_private_path, items)


def _both_items(settings: EvalSettings) -> None:
    _public(settings, golden_item(GAP_ID, "no_answer", question=SENTINEL))
    _private(settings, golden_item(LEAVE_ID, "handbook", question=SENTINEL + "-leave"))


def _happy_llm() -> FakeLlm:
    return FakeLlm(
        {
            # Items run in id order: the no_answer item first, then the handbook item.
            Reformulation: [NO_RESULT, REFORMULATION],
            RetryPlan: [NO_RESULT_RETRY],
            AnswerDraft: [GOOD_DRAFT],
        }
    )


class Harness:
    """Runs `cli.main` with in-process collaborators and captures what it printed."""

    def __init__(self, settings: EvalSettings, server: FastMCP, llm: FakeLlm) -> None:
        self.settings = settings
        self.llm = llm
        self.sink = RecordingTraceSink()
        self.sink_factory_calls = 0
        self._server = server

    def _sink_factory(self, _settings: EvalSettings) -> RecordingTraceSink:
        self.sink_factory_calls += 1
        return self.sink

    def main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        code = cli.main(
            list(argv),
            llm_factory=lambda: self.llm,
            sink_factory=self._sink_factory,
            settings=self.settings,
            connector_factory=lambda _url: FastMcpConnector(self._server),
            out=out,
        )
        return code, out.getvalue()


@pytest.fixture
def harness_factory(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> Callable[[FakeLlm], Harness]:
    return lambda llm: Harness(eval_settings, mcp_server, llm)


def test_run_prints_one_line_per_item_in_id_order(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _both_items(eval_settings)
    harness = harness_factory(_happy_llm())

    code, text = harness.main("run")

    lines = text.splitlines()
    assert code == 0
    assert lines[0] == f"{GAP_ID} no_answer correct trace=http://ui/#/t/tr-1 (tr-1)"
    assert lines[1] == f"{LEAVE_ID} handbook unjudged trace=http://ui/#/t/tr-2 (tr-2)"
    assert "correctness_with_citation: not measured (1 of 2 items not judged)" in lines
    assert "invented_policies: not measured" in lines


def test_run_gives_the_sink_one_trace_per_item_with_expectations_then_one_score(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _both_items(eval_settings)
    harness = harness_factory(_happy_llm())

    harness.main("run")

    sink = harness.sink
    assert len(sink.runs) == 1
    assert [(c.name, c.tags["item_id"]) for c in sink.traced_calls] == [
        ("bot_run", GAP_ID),
        ("bot_run", LEAVE_ID),
    ]
    assert sink.expectations["tr-2"] == {
        "expected_sources": ["handbook://02-ferie"],
        "key_facts": ["synthetic fact"],
        "expected_referente_role": None,
        "kind": "handbook",
    }
    assert set(sink.expectations["tr-1"]) == {
        "expected_sources",
        "key_facts",
        "expected_referente_role",
        "kind",
    }
    assert len(sink.score_calls) == 1
    score = sink.score_calls[0]
    assert score.traced_before == 2
    assert score.trace_ids == ("tr-1", "tr-2")
    assert {t: v.status for t, v in score.verdicts.items()} == {
        "tr-1": "correct",
        "tr-2": "unjudged",
    }


def test_the_no_answer_item_logs_its_gap_through_the_real_workflow(
    eval_settings: EvalSettings,
    harness_factory: Callable[[FakeLlm], Harness],
    gaplog: InMemoryGapLog,
) -> None:
    _both_items(eval_settings)

    harness_factory(_happy_llm()).main("run")

    assert len(gaplog.records) == 1


def test_gate_prints_fail_with_one_line_per_failing_metric(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _both_items(eval_settings)

    code, text = harness_factory(_happy_llm()).main("gate")

    lines = text.splitlines()
    assert code == 1
    assert lines[lines.index("GATE: FAIL") + 1 :] == [
        "FAIL correctness_with_citation: 1 answered items not judged",
        "FAIL invented_policies: not measured",
        "FAIL empty_context: not run",
    ]


def test_missing_private_file_warns_once_runs_public_items_and_fails_the_gate(
    eval_settings: EvalSettings,
    harness_factory: Callable[[FakeLlm], Harness],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer", question=SENTINEL))
    llm = FakeLlm({Reformulation: [NO_RESULT], RetryPlan: [NO_RESULT_RETRY]})
    harness = harness_factory(llm)

    with caplog.at_level(logging.INFO):
        code, text = harness.main("gate")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(eval_settings.golden_private_path) in warnings[0].getMessage()
    assert [c.tags["item_id"] for c in harness.sink.traced_calls] == [GAP_ID]
    assert code == 1
    assert "FAIL golden_set: private handbook file missing (incomplete set)" in text


def test_public_item_citing_the_handbook_is_a_load_error_with_no_model_call(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _public(
        eval_settings,
        golden_item("item-leak-01", "guides", expected_sources=["handbook://02-ferie"]),
    )
    llm = _happy_llm()
    harness = harness_factory(llm)

    code, text = harness.main("run")

    assert code == 1
    errors = [line for line in text.splitlines() if line.startswith("ERROR")]
    assert len(errors) == 1
    assert "item-leak-01" in errors[0]
    assert str(eval_settings.golden_public_path) in errors[0]
    assert llm.calls == []
    assert harness.sink_factory_calls == 0


@pytest.mark.parametrize("review", ["draft", "rejected"])
def test_a_set_without_approved_items_exits_1_and_never_builds_a_sink(
    review: str, eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer", review=review))
    harness = harness_factory(FakeLlm({}))

    code, text = harness.main("run")

    assert code == 1
    assert text.strip() == "no approved items"
    assert harness.sink_factory_calls == 0


def test_gate_over_zero_approved_items_fails_without_a_sink(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer", review="draft"))
    harness = harness_factory(FakeLlm({}))

    code, text = harness.main("gate")

    assert code == 1
    assert "GATE: FAIL" in text
    assert "FAIL golden_set: 1 draft items (golden set not fully reviewed)" in text
    assert "FAIL golden_set: no approved items" in text
    assert harness.sink_factory_calls == 0


def test_an_unavailable_model_makes_the_item_errored_not_wrong(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _private(eval_settings, golden_item(LEAVE_ID, "handbook"))
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION],
            AnswerDraft: [LlmUnavailableError("unavailable")],
        }
    )
    _public(eval_settings, golden_item(GAP_ID, "no_answer", review="rejected"))
    harness = harness_factory(llm)

    code, text = harness.main("run")

    assert code == 1
    assert f"{LEAVE_ID} handbook errored trace=none error=LlmUnavailableError" in text
    assert harness.sink.score_calls[0].trace_ids == ()


def test_gate_reports_errored_items_as_an_incomplete_run(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _private(eval_settings, golden_item(LEAVE_ID, "handbook"))
    _public(eval_settings, golden_item(GAP_ID, "no_answer", review="rejected"))
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [LlmUnavailableError("x")]})

    code, text = harness_factory(llm).main("gate")

    assert code == 1
    assert "FAIL errored: 1 items errored (incomplete run)" in text


def test_a_wrong_kind_of_reply_is_a_wrong_verdict_not_an_error(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    # The no_answer item gets an answer: the bot invented one, which is wrong.
    _public(eval_settings, golden_item(GAP_ID, "no_answer"))
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    harness = harness_factory(llm)

    code, text = harness.main("run")

    assert code == 0
    assert f"{GAP_ID} no_answer wrong " in text
    verdict = harness.sink.score_calls[0].verdicts["tr-1"]
    assert verdict.reasons == ("kind_refusal: failed", "gap_logged: failed")


def test_smalltalk_is_wrong_not_errored(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer"))
    chitchat = REFORMULATION.model_copy(update={"intent": "chitchat"})
    harness = harness_factory(FakeLlm({Reformulation: [chitchat]}))

    code, _ = harness.main("run")

    assert code == 0
    assert harness.sink.score_calls[0].verdicts["tr-1"].reasons == ("classified as smalltalk",)


def test_run_item_selects_only_that_approved_item(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _both_items(eval_settings)
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    harness = harness_factory(llm)

    code, text = harness.main("run", "--item", LEAVE_ID)

    assert code == 0
    assert [c.tags["item_id"] for c in harness.sink.traced_calls] == [LEAVE_ID]
    assert text.startswith(f"{LEAVE_ID} handbook unjudged")


def test_run_item_with_an_unknown_id_is_an_error(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _both_items(eval_settings)
    harness = harness_factory(FakeLlm({}))

    code, text = harness.main("run", "--item", "item-nope-01")

    assert code == 1
    assert text.strip() == "ERROR: item item-nope-01 is not an approved item"
    assert harness.sink_factory_calls == 0


def test_bad_arguments_exit_2(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    code, _ = harness_factory(FakeLlm({})).main("nonsense")

    assert code == 2


def test_duplicate_ids_across_the_two_files_are_a_load_error(
    eval_settings: EvalSettings, harness_factory: Callable[[FakeLlm], Harness]
) -> None:
    _public(eval_settings, golden_item(LEAVE_ID, "no_answer"))
    _private(eval_settings, golden_item(LEAVE_ID, "handbook"))

    code, text = harness_factory(FakeLlm({})).main("run")

    assert code == 1
    assert f"duplicate golden item id: {LEAVE_ID}" in text


def test_an_invalid_setting_ends_with_one_error_line_naming_variables_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JUDGE_MODEL", "same-model")
    monkeypatch.setenv("ANSWER_MODEL", "same-model")
    out = io.StringIO()

    code = cli.main(
        ["run"],
        llm_factory=lambda: FakeLlm({}),
        sink_factory=lambda _s: RecordingTraceSink(),
        out=out,
    )

    assert code == 1
    assert (
        out.getvalue().strip()
        == "ERROR: invalid settings: JUDGE_MODEL must differ from ANSWER_MODEL (D-08)"
    )
    assert "same-model" not in out.getvalue()


def test_question_text_never_reaches_stdout_stderr_or_logs(
    eval_settings: EvalSettings,
    harness_factory: Callable[[FakeLlm], Harness],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _both_items(eval_settings)
    harness = harness_factory(_happy_llm())

    with caplog.at_level(logging.DEBUG):
        _, text = harness.main("gate")

    captured = capsys.readouterr()
    for stream in (text, captured.out, captured.err, caplog.text):
        assert SENTINEL not in stream
    assert any(SENTINEL in call.user for call in harness.llm.calls)  # it did reach the model


class TestEvalSettings:
    def test_defaults_are_valid(self) -> None:
        settings = EvalSettings()

        assert settings.llm_backend == "meridian"
        assert settings.judge_model != settings.answer_model
        assert settings.item_pause_seconds == 0.5

    def test_judge_model_equal_to_answer_model_is_refused(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EvalSettings(judge_model="model-x", answer_model="model-x")

        assert "JUDGE_MODEL" in str(caught.value)
        assert "model-x" not in str(caught.value)

    def test_vertex_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="LLM_BACKEND=vertex"):
            EvalSettings(llm_backend="vertex")

    def test_api_without_a_key_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
            EvalSettings(llm_backend="api")

    def test_api_key_value_never_reaches_an_error(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EvalSettings(
                llm_backend="api", anthropic_api_key="sk-secret-value", llm_timeout_seconds=-1
            )

        assert "sk-secret-value" not in str(caught.value)

    @pytest.mark.parametrize("name", ["LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"])
    def test_tracing_to_a_third_party_is_refused(
        self, name: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(name, "true")

        with pytest.raises(ValidationError, match="LANGSMITH_TRACING must be false"):
            EvalSettings()


class TestGolden:
    def test_load_sorts_items_by_id_across_both_files(self, tmp_path: Path) -> None:
        public = write_golden(tmp_path / "pub.yaml", [golden_item("zz-last-01", "no_answer")])
        private = write_golden(
            tmp_path / "priv.yaml",
            [golden_item("aa-first-01", "handbook"), golden_item("mm-mid-001", "sensitive")],
        )

        loaded = load_golden(public, private)

        assert [i.id for i in loaded.items] == ["aa-first-01", "mm-mid-001", "zz-last-01"]
        assert loaded.private_file_present is True

    def test_review_buckets_and_sensitive_branches(self, tmp_path: Path) -> None:
        public = write_golden(
            tmp_path / "pub.yaml",
            [
                golden_item(
                    "sens-rule-01",
                    "sensitive",
                    key_facts=["f"],
                    expected_sources=["https://x.invalid/a"],
                ),
                golden_item("sens-none-01", "sensitive", review="draft"),
                golden_item("gap-reject-01", "no_answer", review="rejected"),
                golden_item("guide-ok-001", "guides"),
            ],
        )

        loaded = load_golden(public, tmp_path / "absent.yaml")

        assert loaded.private_file_present is False
        assert [i.id for i in loaded.approved()] == ["guide-ok-001", "sens-rule-01"]
        assert [i.id for i in loaded.drafts()] == ["sens-none-01"]
        assert [i.id for i in loaded.rejected()] == ["gap-reject-01"]
        branches = {i.id: i.sensitive_branch for i in loaded.items}
        assert branches == {
            "sens-rule-01": "rule",
            "sens-none-01": "no_rule",
            "gap-reject-01": None,
            "guide-ok-001": None,
        }

    def test_a_single_item_file_loads(self, tmp_path: Path) -> None:
        public = write_golden(tmp_path / "pub.yaml", [golden_item("only-one-01", "no_answer")])

        assert len(load_golden(public, tmp_path / "absent.yaml").items) == 1

    @pytest.mark.parametrize(
        ("overrides", "kind", "field"),
        [
            ({"id": "Bad Id"}, "no_answer", "id"),
            ({"key_facts": []}, "guides", "key_facts"),
            (
                {"expected_sources": ["https://x.invalid"], "key_facts": ["f"]},
                "no_answer",
                "no_answer",
            ),
            ({"expected_referente_role": None}, "no_answer", "expected_referente_role"),
            ({"expected_sources": ["not-a-handbook-url"]}, "handbook", "handbook"),
            ({"expected_referente_role": None}, "sensitive", "expected_referente_role"),
            ({"unknown_field": 1}, "no_answer", "unknown_field"),
        ],
    )
    def test_schema_violations_name_the_file_and_the_field(
        self, tmp_path: Path, overrides: dict[str, object], kind: str, field: str
    ) -> None:
        item = golden_item("bad-item-01", kind, question=SENTINEL, **overrides)
        public = write_golden(tmp_path / "pub.yaml", [item])

        with pytest.raises(GoldenError) as caught:
            load_golden(public, tmp_path / "absent.yaml")

        assert str(public) in str(caught.value)
        assert field in str(caught.value)
        assert SENTINEL not in str(caught.value)

    def test_sensitive_facts_without_sources_are_refused(self, tmp_path: Path) -> None:
        public = write_golden(
            tmp_path / "pub.yaml", [golden_item("sens-bad-001", "sensitive", key_facts=["f"])]
        )

        with pytest.raises(GoldenError, match="key_facts exactly when"):
            load_golden(public, tmp_path / "absent.yaml")

    def test_a_missing_public_file_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(GoldenError, match="public golden file is missing"):
            load_golden(tmp_path / "absent.yaml", tmp_path / "absent2.yaml")

    @pytest.mark.parametrize(
        "text",
        [
            "items: []\n",
            "schema_version: 2\nitems: []\n",
            "schema_version: 1\nitems: 3\n",
            "- a\n",
            "schema_version: 1\nitems: [3]\n",
        ],
    )
    def test_wrong_file_shapes_are_errors(self, tmp_path: Path, text: str) -> None:
        public = tmp_path / "pub.yaml"
        public.write_text(text, encoding="utf-8")

        with pytest.raises(GoldenError, match="pub.yaml"):
            load_golden(public, tmp_path / "absent.yaml")

    def test_invalid_yaml_is_an_error_that_does_not_echo_the_content(self, tmp_path: Path) -> None:
        public = tmp_path / "pub.yaml"
        public.write_text(f"{SENTINEL}: [unclosed\n", encoding="utf-8")

        with pytest.raises(GoldenError, match="not valid YAML") as caught:
            load_golden(public, tmp_path / "absent.yaml")

        assert SENTINEL not in str(caught.value)

    def test_an_item_with_an_unusable_id_is_named_by_position(self, tmp_path: Path) -> None:
        public = write_golden(tmp_path / "pub.yaml", [{"kind": "no_answer"}])

        with pytest.raises(GoldenError, match=r"items\[0\]"):
            load_golden(public, tmp_path / "absent.yaml")


class TestGateAndReport:
    def _inputs(self, **overrides: object) -> GateInputs:
        base: dict[str, object] = {
            "approved_total": 10,
            "correct": 10,
            "unjudged": 0,
            "errored": 0,
            "drafts": 0,
            "private_file_present": True,
            "invented": 0,
            "empty_context_passed": True,
        }
        base.update(overrides)
        return GateInputs(**base)  # type: ignore[arg-type]

    def test_everything_measured_and_met_passes(self) -> None:
        assert format_verdict(evaluate(self._inputs())) == ["GATE: PASS"]

    def test_the_bar_is_exactly_ninety_percent(self) -> None:
        assert evaluate(self._inputs(correct=9)).passed
        verdict = evaluate(self._inputs(correct=8))
        assert verdict.failures == ("correctness_with_citation: 80.0% < 90% (8/10)",)

    def test_failures_come_in_the_d17_order(self) -> None:
        verdict = evaluate(
            self._inputs(
                approved_total=0,
                correct=0,
                drafts=2,
                errored=1,
                private_file_present=False,
                invented=3,
                empty_context_passed=False,
            )
        )

        assert [f.split(":")[0] for f in verdict.failures] == [
            "golden_set",
            "golden_set",
            "golden_set",
            "errored",
            "invented_policies",
            "empty_context",
        ]
        assert "invented_policies: 3 > 0" in verdict.failures

    def test_write_json_report_is_atomic_and_stamped(self, tmp_path: Path) -> None:
        path = write_json_report(tmp_path / "reports", "run", {"a": 1})

        assert path.parent == tmp_path / "reports"
        assert path.name.startswith("run-") and path.name.endswith("Z.json")
        assert path.read_text(encoding="utf-8").strip().startswith("{")
        assert [p.name for p in path.parent.iterdir()] == [path.name]
