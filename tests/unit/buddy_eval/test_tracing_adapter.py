"""MlflowTraceSink call contract with the mlflow attributes monkeypatched (no server, no network).

Synthetic data only.
"""

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import mlflow
import mlflow.anthropic
import mlflow.genai
import mlflow.langchain
import pytest
from pydantic import ValidationError

from buddy_eval import tracing
from buddy_eval.config import EvalSettings
from buddy_eval.scoring import ItemVerdict
from buddy_eval.tracing import MlflowTraceSink, TracingError

TRACKING_URI = "http://mlflow:5000"


@dataclass
class FakeMlflow:
    """Records every call the adapter makes on the mlflow module."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    last_trace_id: str | None = "tr-1"
    evaluate_error: Exception | None = None
    evaluate_kwargs: dict[str, Any] = field(default_factory=dict)
    autolog_state_during_evaluate: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def record(self, event: str, /, **kwargs: Any) -> None:
        self.calls.append((event, kwargs))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def count(self, name: str) -> int:
        return self.names().count(name)

    def kwargs_of(self, name: str) -> dict[str, Any]:
        return next(kwargs for call, kwargs in self.calls if call == name)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeMlflow:
    state = FakeMlflow()

    def set_tracking_uri(uri: str) -> None:
        state.record("set_tracking_uri", uri=uri)

    def set_experiment(name: str) -> SimpleNamespace:
        state.record("set_experiment", name=name)
        return SimpleNamespace(experiment_id="7")

    def langchain_autolog(**kwargs: Any) -> None:
        state.record("langchain.autolog", **kwargs)

    def anthropic_autolog(**kwargs: Any) -> None:
        state.record("anthropic.autolog", **kwargs)

    def update_current_trace(**kwargs: Any) -> None:
        state.record("update_current_trace", **kwargs)

    def get_last_active_trace_id() -> str | None:
        return state.last_trace_id

    def log_expectation(**kwargs: Any) -> None:
        state.record("log_expectation", **kwargs)

    def get_trace(trace_id: str) -> SimpleNamespace:
        state.record("get_trace", trace_id=trace_id)
        return SimpleNamespace(info=SimpleNamespace(trace_id=trace_id))

    def evaluate(**kwargs: Any) -> None:
        state.record("evaluate")
        state.evaluate_kwargs = kwargs
        state.autolog_state_during_evaluate = list(state.calls)
        if state.evaluate_error is not None:
            raise state.evaluate_error

    class StartRun:
        def __init__(self, **kwargs: Any) -> None:
            state.record("start_run", **kwargs)

        def __enter__(self) -> SimpleNamespace:
            return SimpleNamespace(info=SimpleNamespace(run_id="run-9"))

        def __exit__(self, *_exc: object) -> None:
            state.record("end_run")

    def trace(*, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                state.record("trace", name=name)
                return await fn(*args, **kwargs)

            return wrapper

        return decorate

    monkeypatch.setattr(mlflow, "set_tracking_uri", set_tracking_uri)
    monkeypatch.setattr(mlflow, "set_experiment", set_experiment)
    monkeypatch.setattr(mlflow.langchain, "autolog", langchain_autolog)
    monkeypatch.setattr(mlflow.anthropic, "autolog", anthropic_autolog)
    monkeypatch.setattr(mlflow, "update_current_trace", update_current_trace)
    monkeypatch.setattr(mlflow, "get_last_active_trace_id", get_last_active_trace_id)
    monkeypatch.setattr(mlflow, "log_expectation", log_expectation)
    monkeypatch.setattr(mlflow, "get_trace", get_trace)
    monkeypatch.setattr(mlflow, "start_run", StartRun)
    monkeypatch.setattr(mlflow, "trace", trace)
    monkeypatch.setattr(mlflow.genai, "evaluate", evaluate)
    return state


def _settings(**overrides: Any) -> EvalSettings:
    values: dict[str, Any] = {"mlflow_tracking_uri": TRACKING_URI, **overrides}
    return EvalSettings(**values)


def _verdict(trace_id: str, status: str, citation: bool | None, *reasons: str) -> ItemVerdict:
    return ItemVerdict(
        item_id=f"item-{trace_id}",
        kind="handbook",
        status=status,  # type: ignore[arg-type]
        checks={"citation": citation},
        reasons=tuple(reasons),
        invented=None,
        trace_id=trace_id,
    )


class TestConstruction:
    def test_sets_uri_experiment_and_enables_both_autologs_once(self, fake: FakeMlflow) -> None:
        MlflowTraceSink(_settings(mlflow_experiment="exp-x"))

        assert fake.kwargs_of("set_tracking_uri") == {"uri": TRACKING_URI}
        assert fake.kwargs_of("set_experiment") == {"name": "exp-x"}
        assert fake.count("langchain.autolog") == 1
        assert fake.count("anthropic.autolog") == 1

    def test_without_a_tracking_uri_it_raises_naming_the_variable_and_calls_nothing(
        self, fake: FakeMlflow
    ) -> None:
        with pytest.raises(TracingError, match="MLFLOW_TRACKING_URI"):
            MlflowTraceSink(EvalSettings())

        assert fake.calls == []


class TestCollect:
    def test_traced_returns_output_and_trace_id_and_tags_the_trace(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings())

        async def fn() -> dict[str, Any]:
            return {"kind": "answer"}

        output, trace_id = asyncio.run(sink.traced("bot_run", {"item_id": "item-a"}, fn))

        assert output == {"kind": "answer"}
        assert trace_id == "tr-1"
        assert fake.kwargs_of("trace") == {"name": "bot_run"}
        assert fake.kwargs_of("update_current_trace") == {"tags": {"item_id": "item-a"}}

    def test_traced_without_a_trace_id_raises(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings())
        fake.last_trace_id = None

        async def fn() -> dict[str, Any]:
            return {}

        with pytest.raises(TracingError):
            asyncio.run(sink.traced("bot_run", {}, fn))

    def test_log_expectations_writes_one_expectation_per_key(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings())

        sink.log_expectations("tr-1", {"expected_sources": ["a"], "key_facts": ["b"]})

        logged = [kw for name, kw in fake.calls if name == "log_expectation"]
        assert logged == [
            {"trace_id": "tr-1", "name": "expected_sources", "value": ["a"]},
            {"trace_id": "tr-1", "name": "key_facts", "value": ["b"]},
        ]

    def test_run_wraps_start_run_and_yields_the_run_id(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings())

        with sink.run("eval-run", {"suite": "golden"}) as run_id:
            assert run_id == "run-9"

        assert fake.kwargs_of("start_run") == {"run_name": "eval-run", "tags": {"suite": "golden"}}
        assert fake.count("end_run") == 1

    def test_trace_url_uses_the_ui_base_and_experiment_id(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings(mlflow_ui_base_url="http://127.0.0.1:5000/"))

        assert sink.trace_url("tr-3") == (
            "http://127.0.0.1:5000/#/experiments/7/traces?selectedEvaluationId=tr-3"
        )


class TestScore:
    def test_evaluate_gets_only_data_and_scorers_with_the_fetched_traces(
        self, fake: FakeMlflow
    ) -> None:
        sink = MlflowTraceSink(_settings())
        verdicts = {
            "tr-1": _verdict("tr-1", "correct", True),
            "tr-2": _verdict("tr-2", "wrong", False),
        }

        sink.score(["tr-1", "tr-2"], verdicts)

        assert set(fake.evaluate_kwargs) == {"data", "scorers"}
        assert [t.info.trace_id for t in fake.evaluate_kwargs["data"]] == ["tr-1", "tr-2"]
        assert [s.name for s in fake.evaluate_kwargs["scorers"]] == ["correctness", "citation"]

    def test_scorers_read_the_precomputed_verdict_for_the_trace(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings())
        verdicts = {
            "tr-1": _verdict("tr-1", "correct", True),
            "tr-2": _verdict("tr-2", "wrong", False, "citation: failed", "gap not reported"),
            "tr-3": _verdict("tr-3", "unjudged", None),
        }
        sink.score(["tr-1", "tr-2", "tr-3"], verdicts)
        correctness, citation = fake.evaluate_kwargs["scorers"]
        traces = {t.info.trace_id: t for t in fake.evaluate_kwargs["data"]}

        good, bad, unjudged = (correctness(trace=traces[t]) for t in ("tr-1", "tr-2", "tr-3"))
        cited = [citation(trace=traces[t]) for t in ("tr-1", "tr-2", "tr-3")]

        assert good.feedback.value is True
        assert bad.feedback.value is False
        assert bad.rationale == "citation: failed; gap not reported"
        assert unjudged.feedback.value is False
        assert [c.feedback.value for c in cited] == [True, False, None]

    def test_anthropic_autolog_is_suspended_during_evaluate_and_re_enabled_after(
        self, fake: FakeMlflow
    ) -> None:
        sink = MlflowTraceSink(_settings())
        fake.calls.clear()

        sink.score(["tr-1"], {"tr-1": _verdict("tr-1", "correct", True)})

        assert fake.names()[-3:] == ["anthropic.autolog", "evaluate", "anthropic.autolog"]
        autologs = [kw for name, kw in fake.calls if name == "anthropic.autolog"]
        assert autologs == [{"disable": True}, {}]

    def test_anthropic_autolog_is_re_enabled_when_evaluate_raises(self, fake: FakeMlflow) -> None:
        sink = MlflowTraceSink(_settings())
        fake.calls.clear()
        fake.evaluate_error = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            sink.score(["tr-1"], {"tr-1": _verdict("tr-1", "correct", True)})

        autologs = [kw for name, kw in fake.calls if name == "anthropic.autolog"]
        assert autologs == [{"disable": True}, {}]

    def test_a_trace_without_a_verdict_is_refused_before_any_mlflow_call(
        self, fake: FakeMlflow
    ) -> None:
        sink = MlflowTraceSink(_settings())
        fake.calls.clear()

        with pytest.raises(TracingError, match="no verdict"):
            sink.score(["tr-1", "tr-2"], {"tr-1": _verdict("tr-1", "correct", True)})

        assert fake.calls == []

    def test_the_adapter_never_runs_evaluate_with_a_prediction_function(self) -> None:
        # Trace mode only (amended D-20); the call keywords are pinned in the test above.
        assert "predict_fn" not in inspect.getsource(tracing)


class TestTrackingUriLocality:
    @pytest.mark.parametrize(
        "uri", ["http://mlflow:5000", "http://localhost:5000", "http://127.0.0.1:5000"]
    )
    def test_local_servers_are_accepted(self, uri: str) -> None:
        assert EvalSettings(mlflow_tracking_uri=uri).mlflow_tracking_uri == uri

    @pytest.mark.parametrize(
        "uri",
        [
            "https://tracking.example.com",
            "https://mlflow:5000",
            "http://tracking.example.com:5000",
            "http://mlflow.evil.example:5000",
            "databricks",
            "file:///tmp/mlruns",
        ],
    )
    def test_anything_off_the_host_is_refused_naming_only_the_variable(self, uri: str) -> None:
        with pytest.raises(ValidationError) as exc:
            EvalSettings(mlflow_tracking_uri=uri)

        text = str(exc.value)
        assert "MLFLOW_TRACKING_URI must point at the local MLflow server" in text
        assert uri not in text

    def test_unset_is_accepted(self) -> None:
        assert EvalSettings().mlflow_tracking_uri is None
