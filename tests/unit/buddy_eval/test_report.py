"""The run report: console lines, the private JSON report and what never reaches the console.

Built from hand-made verdicts, so the report is exercised without a bot run. Synthetic data only.
"""

import io
import json
import logging
from pathlib import Path

import pytest
from tests.unit.buddy_eval.conftest import RecordingTraceSink

from buddy_bot.prompts import MAX_EVIDENCE_CHARS
from buddy_bot.schemas import BotReply
from buddy_eval.config import EvalSettings
from buddy_eval.judge import FactCheck, JudgeVerdict
from buddy_eval.report import emit, format_run, run_payload
from buddy_eval.runner import ItemOutcome, RunResult
from buddy_eval.scoring import ItemVerdict
from buddy_eval.sources import IndexIdentity

SENTINEL_REASONING = "SENTINEL-REASONING-91c2"
SENTINEL_CLAIM = "SENTINEL-CLAIM-4d7e"
SENTINEL_ANSWER = "SENTINEL-ANSWER-b05a"
IDENTITY = IndexIdentity(
    content_hash="0123456789abcdef0123456789abcdef",
    guides_commit_sha="a" * 40,
    build_id="build-7",
)
FACT = FactCheck(fact="synthetic fact", present=True, contradicted=False)


def _trace(item_id: str) -> str:
    return f"tr-{item_id[5:7]}"


def _verdict(
    item_id: str,
    status: str,
    *,
    kind: str = "handbook",
    reasons: tuple[str, ...] = (),
    judge: JudgeVerdict | None = None,
    invented: bool | None = False,
) -> ItemVerdict:
    return ItemVerdict(
        item_id=item_id,
        kind=kind,
        status=status,  # type: ignore[arg-type]
        checks={"citation": status == "correct"},
        reasons=reasons,
        invented=invented,
        trace_id=_trace(item_id),
        judge=judge,
    )


def _outcome(item_id: str, answer: str = "") -> ItemOutcome:
    reply = BotReply(kind="answer", answer=answer)
    return ItemOutcome(item_id, "completed", reply, _trace(item_id), None)


def _result(verdicts: list[ItemVerdict], *, identity: IndexIdentity | None = IDENTITY) -> RunResult:
    outcomes = tuple(_outcome(v.item_id, SENTINEL_ANSWER) for v in verdicts)
    return RunResult(outcomes, tuple(verdicts), aborted=False, identity=identity)


def _mixed() -> RunResult:
    judged = JudgeVerdict(facts=[FACT], invented_claims=[], reasoning="fine")
    flagged = JudgeVerdict(
        facts=[FACT],
        invented_claims=[SENTINEL_CLAIM, "another claim"],
        reasoning=SENTINEL_REASONING,
    )
    return _result(
        [
            _verdict("item-aa-01", "correct", judge=judged),
            _verdict("item-bb-01", "correct", judge=flagged, invented=True),
            _verdict("item-cc-01", "wrong", reasons=("citation: failed",), judge=judged),
            _verdict("item-dd-01", "correct", judge=judged),
        ]
    )


def _settings(tmp_path: Path) -> EvalSettings:
    return EvalSettings(
        private_dir=tmp_path / "private",
        artifact_dir=tmp_path / "artifacts",
        reformulate_model="model-haiku",
        answer_model="model-sonnet",
        judge_model="model-opus",
    )


def _lines(result: RunResult, tmp_path: Path) -> list[str]:
    return format_run(
        result, settings=_settings(tmp_path), trace_url=RecordingTraceSink().trace_url
    )


class TestConsole:
    def test_the_header_names_the_index_and_the_three_models(self, tmp_path: Path) -> None:
        lines = _lines(_mixed(), tmp_path)

        assert (
            lines[0]
            == "index content_hash=0123456789abcdef guides_commit=aaaaaaaaaaaa build_id=build-7"
        )
        assert lines[1] == "models reformulate=model-haiku answer=model-sonnet judge=model-opus"

    def test_a_run_without_an_index_has_only_the_models_line(self, tmp_path: Path) -> None:
        lines = _lines(_result([], identity=None), tmp_path)

        assert lines[0].startswith("models ")
        assert not any(line.startswith("index ") for line in lines)

    def test_items_are_listed_in_id_order_with_their_trace_link(self, tmp_path: Path) -> None:
        lines = _lines(_mixed(), tmp_path)

        assert [line for line in lines if line.startswith("item-")] == [
            "item-aa-01 handbook correct trace=http://ui/#/t/tr-aa (tr-aa)",
            "item-bb-01 handbook correct trace=http://ui/#/t/tr-bb (tr-bb)",
            "item-cc-01 handbook wrong trace=http://ui/#/t/tr-cc (tr-cc)",
            "item-dd-01 handbook correct trace=http://ui/#/t/tr-dd (tr-dd)",
        ]

    def test_the_headline_numbers(self, tmp_path: Path) -> None:
        lines = _lines(_mixed(), tmp_path)

        assert "correctness_with_citation: 75.0% (3/4 approved items)" in lines
        assert "invented_policies: 1" in lines

    def test_failed_items_and_invented_flags_are_listed_with_their_trace_link(
        self, tmp_path: Path
    ) -> None:
        lines = _lines(_mixed(), tmp_path)

        failed = lines.index("failed items:")
        flags = lines.index("invented-policy flags:")
        assert lines[failed + 1] == (
            "  item-cc-01 handbook citation: failed trace=http://ui/#/t/tr-cc (tr-cc)"
        )
        assert failed < flags
        assert lines[flags + 1] == "  item-bb-01 claims=2 trace=http://ui/#/t/tr-bb (tr-bb)"
        assert len(lines) == flags + 2

    def test_a_clean_run_says_none_for_both_lists(self, tmp_path: Path) -> None:
        judged = JudgeVerdict(facts=[FACT], invented_claims=[], reasoning="fine")
        lines = _lines(_result([_verdict("item-aa-01", "correct", judge=judged)]), tmp_path)

        assert lines[-2:] == ["failed items: none", "invented-policy flags: none"]
        assert "correctness_with_citation: 100.0% (1/1 approved items)" in lines
        assert "invented_policies: 0" in lines

    def test_an_item_without_a_trace_says_so(self, tmp_path: Path) -> None:
        verdict = ItemVerdict(
            "item-aa-01",
            "handbook",
            "errored",
            {},
            ("errored: LlmUnavailableError",),
            None,
            None,
        )
        outcome = ItemOutcome("item-aa-01", "errored", None, None, "LlmUnavailableError")
        result = RunResult((outcome,), (verdict,), aborted=False, identity=IDENTITY)

        lines = _lines(result, tmp_path)

        assert "item-aa-01 handbook errored trace=none error=LlmUnavailableError" in lines
        assert "  item-aa-01 handbook errored: LlmUnavailableError trace=none" in lines
        assert "correctness_with_citation: not measured (1 of 1 items not judged)" in lines
        assert "invented_policies: 0 (partial: 1 of 1 items not judged)" in lines

    def test_an_empty_run_is_not_measured(self, tmp_path: Path) -> None:
        lines = _lines(_result([], identity=None), tmp_path)

        assert "correctness_with_citation: not measured (0 of 0 items not judged)" in lines


class TestJsonReport:
    def test_the_payload_has_every_documented_field(self, tmp_path: Path) -> None:
        payload = run_payload(
            _mixed(), _settings(tmp_path), trace_url=RecordingTraceSink().trace_url
        )

        assert set(payload) == {
            "generated_at",
            "identity",
            "models",
            "bot_version",
            "totals",
            "items",
            "notes",
        }
        assert payload["identity"] == {
            "content_hash": IDENTITY.content_hash,
            "guides_commit_sha": IDENTITY.guides_commit_sha,
            "build_id": "build-7",
        }
        assert payload["models"] == {
            "reformulate": "model-haiku",
            "answer": "model-sonnet",
            "judge": "model-opus",
        }
        assert payload["totals"] == {
            "approved": 4,
            "correct": 3,
            "wrong": 1,
            "errored": 0,
            "invented": 1,
        }
        assert len(str(payload["bot_version"])) == 64

    def test_an_item_holds_the_judge_findings_and_the_trace(self, tmp_path: Path) -> None:
        payload = run_payload(
            _mixed(), _settings(tmp_path), trace_url=RecordingTraceSink().trace_url
        )

        flagged = payload["items"][1]
        assert set(flagged) == {
            "id",
            "kind",
            "status",
            "checks",
            "reasons",
            "answer",
            "judge_facts",
            "invented_claims",
            "reasoning",
            "trace_id",
            "trace_url",
        }
        assert flagged["invented_claims"] == [SENTINEL_CLAIM, "another claim"]
        assert flagged["reasoning"] == SENTINEL_REASONING
        assert flagged["answer"] == SENTINEL_ANSWER
        assert flagged["judge_facts"] == [
            {"fact": "synthetic fact", "present": True, "contradicted": False}
        ]
        assert flagged["trace_id"] == "tr-bb"
        assert flagged["trace_url"] == "http://ui/#/t/tr-bb"

    def test_without_a_trace_link_builder_the_url_is_null(self, tmp_path: Path) -> None:
        payload = run_payload(_mixed(), _settings(tmp_path))

        assert payload["items"][0]["trace_url"] is None

    def test_a_run_without_an_index_has_a_null_identity(self, tmp_path: Path) -> None:
        assert run_payload(_result([], identity=None), _settings(tmp_path))["identity"] is None

    def test_the_note_states_the_evidence_truncation(self, tmp_path: Path) -> None:
        payload = run_payload(_mixed(), _settings(tmp_path))

        assert any(str(MAX_EVIDENCE_CHARS) in note for note in payload["notes"])


class TestEmit:
    def test_the_json_report_is_written_under_private_dir_and_its_path_printed(
        self, tmp_path: Path
    ) -> None:
        settings = _settings(tmp_path)
        out = io.StringIO()

        emit(_mixed(), settings=settings, sink=RecordingTraceSink(), out=out)

        report_line = out.getvalue().splitlines()[-1]
        assert report_line.startswith(f"report: {settings.private_dir / 'eval' / 'reports'}/run-")
        path = Path(report_line.removeprefix("report: "))
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["items"][1]["reasoning"] == SENTINEL_REASONING
        assert written["items"][1]["invented_claims"][0] == SENTINEL_CLAIM
        assert written["items"][1]["answer"] == SENTINEL_ANSWER

    def test_reasoning_claims_and_answers_never_reach_the_console_or_the_logs(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        out = io.StringIO()

        with caplog.at_level(logging.DEBUG):
            emit(_mixed(), settings=_settings(tmp_path), sink=RecordingTraceSink(), out=out)

        for sentinel in (SENTINEL_REASONING, SENTINEL_CLAIM, SENTINEL_ANSWER):
            assert sentinel not in out.getvalue()
            assert sentinel not in caplog.text

    def test_the_stop_message_stays_the_last_line(self, tmp_path: Path) -> None:
        result = RunResult((), (), aborted=True, identity=None)
        out = io.StringIO()

        emit(result, settings=_settings(tmp_path), sink=RecordingTraceSink(), out=out)

        lines = out.getvalue().splitlines()
        assert lines[-1].startswith("stopped after 3 consecutive errors")
        assert lines[-2].startswith("report: ")
