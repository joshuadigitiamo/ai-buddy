"""Trace port of the evaluation job and its MLflow adapter.

This is the only buddy_eval module allowed to depend on mlflow. Everything else (runner,
scoring, gate, report, cli) sees traces only through the `TraceSink` Protocol, so the unit suite
stays offline. The adapter collects one root trace per item, then attaches the precomputed
verdicts to those traces in trace mode, so a rerun never produces a hollow trace.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, cast

import mlflow
import mlflow.anthropic
import mlflow.genai
import mlflow.langchain
from mlflow.entities import Feedback
from mlflow.exceptions import MlflowException
from mlflow.genai.scorers import scorer

if TYPE_CHECKING:
    from buddy_eval.config import EvalSettings
    from buddy_eval.empty_context import EmptyContextItem
    from buddy_eval.scoring import ItemVerdict

CITATION_CHECK: Final = "citation"
# Bump when a scorer or its rationale changes (05-08 added invented_policy, 05-16 narrowed the
# citation rationale): traces scored by an older set are scored again, and their earlier
# same-name feedback is replaced by the new value (A-07-3, WR-02).
SCORER_SET_VERSION: Final = "3"
NO_INVENTED_CLAIM: Final = "no unsupported normative claim"
# The empty-context run has its own, single-scorer set (`refused`) and its own version.
EMPTY_SCORER_SET_VERSION: Final = "empty-1"
RUN_FEEDBACK_NAMES: Final = frozenset({"correctness", CITATION_CHECK, "invented_policy"})
EMPTY_FEEDBACK_NAMES: Final = frozenset({"refused"})

ScorerSet = Literal["run", "empty_context"]


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

    def score(
        self,
        trace_ids: Sequence[str],
        verdicts: Mapping[str, ItemVerdict | EmptyContextItem],
        *,
        scorers: ScorerSet = "run",
    ) -> None:
        """Attach precomputed verdicts (keyed by trace id) to the traces collected earlier.

        `scorers` picks the feedback set: "run" for the eval run, "empty_context" for the
        empty-context test (feedback `refused` only).
        """
        ...

    def trace_exists(self, trace_id: str) -> bool:
        """True while the backend still holds the trace (a cached outcome links to it)."""
        ...

    def untraced(self) -> AbstractContextManager[None]:
        """Inside the block LLM calls create no traces (judge calls, RESEARCH Pitfall 4)."""
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

    def score(
        self,
        trace_ids: Sequence[str],
        verdicts: Mapping[str, ItemVerdict | EmptyContextItem],
        *,
        scorers: ScorerSet = "run",
    ) -> None:
        missing = [trace_id for trace_id in trace_ids if trace_id not in verdicts]
        if missing:
            raise TracingError(f"no verdict for {len(missing)} collected trace(s)")

        if not trace_ids:
            # A rerun whose traces were all scored already: nothing to attach, no evaluate run.
            return

        if scorers == "empty_context":
            self._score_empty_context(trace_ids, cast("Mapping[str, EmptyContextItem]", verdicts))
            return
        self._score_run(trace_ids, cast("Mapping[str, ItemVerdict]", verdicts))

    def _score_empty_context(
        self, trace_ids: Sequence[str], items: Mapping[str, EmptyContextItem]
    ) -> None:
        @scorer
        def refused(trace: Any) -> Feedback:
            item = items[trace.info.trace_id]
            return Feedback(name="refused", value=item.status == "refused", rationale=item.status)

        self._evaluate(trace_ids, [refused], EMPTY_FEEDBACK_NAMES)

    def _evaluate(
        self, trace_ids: Sequence[str], scorers: list[Any], names: frozenset[str]
    ) -> None:
        traces = [self._without_stale_feedback(trace_id, names) for trace_id in trace_ids]
        # Scoring must not write stray LLM traces holding source text (T-05-39).
        mlflow.anthropic.autolog(disable=True)
        try:
            mlflow.genai.evaluate(data=traces, scorers=scorers)
        finally:
            mlflow.anthropic.autolog()

    @staticmethod
    def _without_stale_feedback(trace_id: str, names: frozenset[str]) -> Any:
        """The trace after deleting its earlier Feedback named in `names` (WR-02).

        The UI then shows one current value per feedback name; expectations and other
        assessments stay. Deleted rows are derived data the cached verdicts re-create.
        """
        trace = mlflow.get_trace(trace_id)
        stale = [
            assessment.assessment_id
            for assessment in trace.info.assessments
            if assessment.feedback is not None and assessment.name in names
        ]
        if not stale:
            return trace
        for assessment_id in stale:
            mlflow.delete_assessment(trace_id=trace_id, assessment_id=assessment_id)
        return mlflow.get_trace(trace_id)

    def _score_run(self, trace_ids: Sequence[str], verdicts: Mapping[str, ItemVerdict]) -> None:
        @scorer
        def correctness(trace: Any) -> Feedback:
            verdict = verdicts[trace.info.trace_id]
            rationale = "; ".join(verdict.reasons)
            if verdict.judge is not None:
                rationale = "; ".join(
                    filter(None, (rationale, f"judge: {verdict.judge.reasoning}"))
                )
            # An item the judge never decided has no correctness value, not a false one.
            value = None if verdict.status == "unjudged" else verdict.status == "correct"
            return Feedback(name="correctness", value=value, rationale=rationale)

        @scorer
        def citation(trace: Any) -> Feedback:
            value = verdicts[trace.info.trace_id].checks.get(CITATION_CHECK)
            # Only the citation result: other failures belong to the correctness rationale.
            if value is None:
                rationale = "citation: not checked"
            else:
                rationale = "citation: ok" if value else "citation: failed"
            return Feedback(name=CITATION_CHECK, value=value, rationale=rationale)

        @scorer
        def invented_policy(trace: Any) -> Feedback:
            verdict = verdicts[trace.info.trace_id]
            claims = verdict.judge.invented_claims if verdict.judge is not None else []
            return Feedback(
                name="invented_policy",
                value=None if verdict.invented is None else not verdict.invented,
                rationale="; ".join(claims) or NO_INVENTED_CLAIM,
            )

        self._evaluate(trace_ids, [correctness, citation, invented_policy], RUN_FEEDBACK_NAMES)

    @contextmanager
    def untraced(self) -> Iterator[None]:
        mlflow.anthropic.autolog(disable=True)
        mlflow.langchain.autolog(disable=True)
        try:
            yield
        finally:
            mlflow.anthropic.autolog()
            mlflow.langchain.autolog()

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
