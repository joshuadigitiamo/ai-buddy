"""Presentation of a run: item lines, summary lines and the JSON report file.

Output carries item ids, kinds, statuses, counts and trace links only; question, answer and
evidence text never reach it (D-06, BOT-11 posture).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from buddy_eval.config import EvalSettings
from buddy_eval.runner import RunResult
from buddy_eval.scoring import headline
from buddy_eval.tracing import TraceSink


def format_run(result: RunResult, *, trace_url: Callable[[str], str]) -> list[str]:
    """One line per item in id order, then the summary lines."""
    errors = {o.item_id: o.error for o in result.outcomes if o.error}
    lines: list[str] = []
    for verdict in result.verdicts:
        if verdict.trace_id is None:
            link = "trace=none"
        else:
            link = f"trace={trace_url(verdict.trace_id)} ({verdict.trace_id})"
        line = f"{verdict.item_id} {verdict.kind} {verdict.status} {link}"
        if verdict.item_id in errors:
            line += f" error={errors[verdict.item_id]}"
        lines.append(line)
    summary = headline(result.verdicts)
    not_judged = summary.unjudged + summary.errored
    if not_judged:
        lines.append(
            f"correctness_with_citation: not measured ({not_judged} of {summary.total} items "
            "not judged)"
        )
    elif summary.total:
        pct = summary.correct * 100 / summary.total
        lines.append(
            f"correctness_with_citation: {pct:.1f}% ({summary.correct}/{summary.total} "
            "approved items)"
        )
    else:
        lines.append("correctness_with_citation: not measured (0 of 0 items not judged)")
    lines.append("invented_policies: not measured")
    return lines


def write_json_report(directory: Path, name: str, payload: Mapping[str, object]) -> Path:
    """Write `<directory>/<name>-<UTC stamp>.json` atomically and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"{name}-{stamp}.json"
    temporary = directory / f".{target.name}.tmp"
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target


def emit(result: RunResult, *, settings: EvalSettings, sink: TraceSink, out: TextIO) -> None:
    """Present a run: the only presentation call the CLI makes (extended by 05-05 and 05-08)."""
    for line in format_run(result, trace_url=sink.trace_url):
        print(line, file=out)
