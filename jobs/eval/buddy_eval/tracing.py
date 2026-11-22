"""Trace port of the evaluation job.

This is the only buddy_eval module allowed to depend on mlflow; plan 05-04 adds the MLflow
adapter here. Everything else (runner, scoring, gate, report, cli) sees traces only through the
`TraceSink` Protocol, so the unit suite stays offline. This module has no third-party import.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from buddy_eval.scoring import ItemVerdict


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

    def trace_url(self, trace_id: str) -> str:
        """A link that opens the trace in the backend's UI."""
        ...
