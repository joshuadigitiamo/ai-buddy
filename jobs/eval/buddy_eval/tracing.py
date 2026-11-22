"""Trace port of the evaluation job and its MLflow adapter.

This is the only buddy_eval module allowed to depend on mlflow. Everything else (runner,
scoring, gate, report, cli) sees traces only through the `TraceSink` Protocol, so the unit suite
stays offline. The adapter collects one root trace per item, then attaches the precomputed
verdicts to those traces in trace mode, so a rerun never produces a hollow trace.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, Any, Final, Protocol

import mlflow
import mlflow.anthropic
import mlflow.genai
import mlflow.langchain
from mlflow.entities import Feedback
from mlflow.exceptions import MlflowException
from mlflow.genai.scorers import scorer

if TYPE_CHECKING:
    from buddy_eval.config import EvalSettings
    from buddy_eval.scoring import ItemVerdict

CITATION_CHECK: Final = "citation"
# Bump when the set of scorers changes (05-08 adds invented_policy): traces scored by an older
# set are scored again, and keep their earlier feedback next to the new one (A-07-3).
SCORER_SET_VERSION: Final = "1"


class TracingError(RuntimeError):
    """The trace backend failed or is unsafe to use; the message names no run content."""


class TraceSink(Protocol):
    """Where the collect phase records one trace per item and the score phase attaches verdicts."""

    def run(self, name: str, tags: Mapping[str, str]) -> AbstractContextManager[str | None]:
        """Open the run that groups every trace of one evaluation; yields its id, if any."""
        ...

    async def traced(
        self,
        name: str,
        tags: Mapping[str, str],
        fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], str]:
        """Run `fn` under a root trace called `name`; return its output and the trace id."""
        ...

    def log_expectations(self, trace_id: str, expectations: Mapping[str, object]) -> None:
        """Attach an item's expectations to its own trace."""
        ...

    def score(self, trace_ids: Sequence[str], verdicts: Mapping[str, ItemVerdict]) -> None:
        """Attach precomputed verdicts (keyed by trace id) to the traces collected earlier."""
        ...

    def trace_exists(self, trace_id: str) -> bool:
        """True while the backend still holds the trace (a cached outcome links to it)."""
        ...

    def trace_url(self, trace_id: str) -> str:
        """A link that opens the trace in the backend's UI."""
        ...


class MlflowTraceSink:
    """TraceSink over a local MLflow server (D-19 autolog, amended D-20 collect then score)."""

    def __init__(self, settings: EvalSettings) -> None:
        if not settings.mlflow_tracking_uri:
            raise TracingError("MLFLOW_TRACKING_URI is required to record traces")
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        experiment = mlflow.set_experiment(settings.mlflow_experiment)
        mlflow.langchain.autolog()
        mlflow.anthropic.autolog()
        self._experiment_id = experiment.experiment_id
        self._ui_base_url = settings.mlflow_ui_base_url.rstrip("/")

    @contextmanager
    def _run(self, name: str, tags: Mapping[str, str]) -> Iterator[str | None]:
        with mlflow.start_run(run_name=name, tags=dict(tags)) as active:
            yield active.info.run_id

    def run(self, name: str, tags: Mapping[str, str]) -> AbstractContextManager[str | None]:
        return self._run(name, tags)

    async def traced(
        self,
        name: str,
        tags: Mapping[str, str],
        fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], str]:
        # The root span keeps the autologged LLM spans in this item's own trace.
        @mlflow.trace(name=name)
        async def root() -> dict[str, Any]:
            mlflow.update_current_trace(tags=dict(tags))
            return await fn()

        output = await root()
        trace_id = mlflow.get_last_active_trace_id()
        if trace_id is None:
            raise TracingError("no trace was recorded for the item")
        return output, trace_id

    def log_expectations(self, trace_id: str, expectations: Mapping[str, object]) -> None:
        for key, value in expectations.items():
            if value is None:
                # MLflow rejects an Expectation without a value (found by the 05-06 smoke); an
                # absent expectation, such as no referente role, is simply not recorded.
                continue
            mlflow.log_expectation(trace_id=trace_id, name=key, value=value)

    def score(self, trace_ids: Sequence[str], verdicts: Mapping[str, ItemVerdict]) -> None:
        missing = [trace_id for trace_id in trace_ids if trace_id not in verdicts]
        if missing:
            raise TracingError(f"no verdict for {len(missing)} collected trace(s)")

        if not trace_ids:
            # A rerun whose traces were all scored already: nothing to attach, no evaluate run.
            return

        @scorer
        def correctness(trace: Any) -> Feedback:
            verdict = verdicts[trace.info.trace_id]
            return Feedback(
                name="correctness",
                value=verdict.status == "correct",
                rationale="; ".join(verdict.reasons),
            )

        @scorer
        def citation(trace: Any) -> Feedback:
            verdict = verdicts[trace.info.trace_id]
            return Feedback(
                name="citation",
                value=verdict.checks.get(CITATION_CHECK),
                rationale="; ".join(verdict.reasons),
            )

        traces = [mlflow.get_trace(trace_id) for trace_id in trace_ids]
        # Scoring must not write stray LLM traces holding source text (T-05-39).
        mlflow.anthropic.autolog(disable=True)
        try:
            mlflow.genai.evaluate(data=traces, scorers=[correctness, citation])
        finally:
            mlflow.anthropic.autolog()

    def trace_exists(self, trace_id: str) -> bool:
        try:
            return mlflow.get_trace(trace_id) is not None
        except MlflowException:
            return False

    def trace_url(self, trace_id: str) -> str:
        return (
            f"{self._ui_base_url}/#/experiments/{self._experiment_id}"
            f"/traces?selectedEvaluationId={trace_id}"
        )
