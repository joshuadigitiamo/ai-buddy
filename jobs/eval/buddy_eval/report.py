"""Presentation of a run: console lines and the private JSON report (D-11).

The console carries item ids, kinds, statuses, check names, counts and trace links only. The
judge reasoning, the invented claims and the answer text go to the JSON report under
PRIVATE_DIR and to the local trace, never to the console or a log (BOT-11 posture). Nothing here
lets a person change a verdict: failures are listed for inspection.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, TextIO

from buddy_bot.prompts import MAX_EVIDENCE_CHARS
from buddy_eval.cache import bot_version
from buddy_eval.config import EvalSettings
from buddy_eval.runner import STOP_MESSAGE, RunResult
from buddy_eval.scoring import ItemVerdict, headline
from buddy_eval.tracing import TraceSink

REPORT_NOTE: Final = (
    f"The answer step truncates each source to {MAX_EVIDENCE_CHARS} characters; the judge read "
    "the full text of every cited source, so it may have seen text the answer never saw (A-08-3)."
)


def _link(verdict: ItemVerdict, trace_url: Callable[[str], str]) -> str:
    if verdict.trace_id is None:
        return "trace=none"
    return f"trace={trace_url(verdict.trace_id)} ({verdict.trace_id})"


def _claims(verdict: ItemVerdict) -> list[str]:
    return list(verdict.judge.invented_claims) if verdict.judge is not None else []


def _header(result: RunResult, settings: EvalSettings) -> list[str]:
    lines: list[str] = []
    identity = result.identity
    if identity is not None:
        lines.append(
            f"index content_hash={identity.content_hash[:16]} "
            f"guides_commit={identity.guides_commit_sha[:12]} build_id={identity.build_id}"
        )
    lines.append(
        f"models reformulate={settings.reformulate_model} answer={settings.answer_model} "
        f"judge={settings.judge_model}"
    )
    return lines


def format_run(
    result: RunResult, *, settings: EvalSettings, trace_url: Callable[[str], str]
) -> list[str]:
    """Header, one line per item in id order, the two headline numbers, then the failure lists."""
    errors = {o.item_id: o.error for o in result.outcomes if o.error}
    lines = _header(result, settings)
    for verdict in result.verdicts:
        line = f"{verdict.item_id} {verdict.kind} {verdict.status} {_link(verdict, trace_url)}"
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
    partial = f" (partial: {not_judged} of {summary.total} items not judged)" if not_judged else ""
    lines.append(f"invented_policies: {summary.invented}{partial}")
    failed = [v for v in result.verdicts if v.status in ("wrong", "errored")]
    flagged = [v for v in result.verdicts if v.invented is True]
    lines.append("failed items:" if failed else "failed items: none")
    for verdict in failed:
        reasons = "; ".join(verdict.reasons)
        lines.append(f"  {verdict.item_id} {verdict.kind} {reasons} {_link(verdict, trace_url)}")
    lines.append("invented-policy flags:" if flagged else "invented-policy flags: none")
    for verdict in flagged:
        lines.append(
            f"  {verdict.item_id} claims={len(_claims(verdict))} {_link(verdict, trace_url)}"
        )
    return lines


def _item_payload(
    verdict: ItemVerdict, answer: str, trace_url: Callable[[str], str] | None
) -> dict[str, Any]:
    judge = verdict.judge
    return {
        "id": verdict.item_id,
        "kind": verdict.kind,
        "status": verdict.status,
        "checks": dict(verdict.checks),
        "reasons": list(verdict.reasons),
        "answer": answer,
        "judge_facts": [fact.model_dump() for fact in judge.facts] if judge else [],
        "invented_claims": _claims(verdict),
        "reasoning": judge.reasoning if judge else "",
        "trace_id": verdict.trace_id,
        "trace_url": (
            trace_url(verdict.trace_id) if trace_url and verdict.trace_id is not None else None
        ),
    }


def run_payload(
    result: RunResult,
    settings: EvalSettings,
    *,
    trace_url: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """The JSON report: identity, models, totals and, per item, the judge reasoning and links."""
    summary = headline(result.verdicts)
    answers = {o.item_id: o.reply.answer for o in result.outcomes if o.reply is not None}
    wrong = sum(1 for v in result.verdicts if v.status == "wrong")
    identity = result.identity
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "identity": (
            {
                "content_hash": identity.content_hash,
                "guides_commit_sha": identity.guides_commit_sha,
                "build_id": identity.build_id,
            }
            if identity is not None
            else None
        ),
        "models": {
            "reformulate": settings.reformulate_model,
            "answer": settings.answer_model,
            "judge": settings.judge_model,
        },
        "bot_version": bot_version(),
        "totals": {
            "approved": summary.total,
            "correct": summary.correct,
            "wrong": wrong,
            "errored": summary.errored,
            "invented": summary.invented,
        },
        "items": [_item_payload(v, answers.get(v.item_id, ""), trace_url) for v in result.verdicts],
        "notes": [REPORT_NOTE],
    }


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
    """Present a run: the console lines, then the private JSON report and its path."""
    for line in format_run(result, settings=settings, trace_url=sink.trace_url):
        print(line, file=out)
    path = write_json_report(
        settings.private_dir / "eval" / "reports",
        "run",
        run_payload(result, settings, trace_url=sink.trace_url),
    )
    print(f"report: {path}", file=out)
    if result.aborted:
        print(STOP_MESSAGE.format(n=settings.max_consecutive_errors), file=out)
