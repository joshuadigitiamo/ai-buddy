"""Key derivation, bot version and the JSON file cache. Synthetic data only."""

import logging
import os
from pathlib import Path
from typing import Any

import pytest

from buddy_eval import cache as cache_module
from buddy_eval.cache import ResultCache, bot_version, key_for

BASE: dict[str, Any] = {
    "item": {"id": "item-aa-01", "question": "synthetic question"},
    "content_hash": "c" * 64,
    "guides_commit_sha": "1" * 40,
    "bot_version": "b" * 64,
    "reformulate_model": "test-haiku",
    "answer_model": "test-sonnet",
    "confidence_threshold": 0.7,
    "outcome_schema": 1,
}


class TestKeyFor:
    def test_equal_ingredients_give_the_same_key_whatever_the_argument_order(self) -> None:
        reordered = dict(reversed(list(BASE.items())))

        assert key_for(**BASE) == key_for(**reordered)
        assert len(key_for(**BASE)) == 64

    @pytest.mark.parametrize("name", sorted(BASE))
    def test_changing_any_one_ingredient_changes_the_key(self, name: str) -> None:
        changed = dict(BASE)
        changed[name] = (
            {"id": "item-aa-01", "question": "another synthetic question"}
            if name == "item"
            else f"{BASE[name]}-changed"
        )

        assert key_for(**changed) != key_for(**BASE)

    def test_non_ascii_text_is_hashed_as_is(self) -> None:
        assert key_for(question="città") != key_for(question="citta")


class TestBotVersion:
    @pytest.fixture
    def fake_bot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        package = tmp_path / "buddy_bot"
        (package / "sub").mkdir(parents=True)
        (package / "prompts.py").write_text("SYSTEM = 'one'\n", encoding="utf-8")
        (package / "sub" / "inner.py").write_text("X = 1\n", encoding="utf-8")
        topics = tmp_path / "escalation_topics.yaml"
        topics.write_text("topics: []\n", encoding="utf-8")
        monkeypatch.setattr(cache_module, "BOT_DIR", package)
        monkeypatch.setattr(cache_module, "ESCALATION_TOPICS", topics)
        return package

    def test_it_is_stable_while_nothing_changes(self, fake_bot: Path) -> None:
        assert bot_version() == bot_version()

    def test_editing_a_bot_module_changes_it(self, fake_bot: Path) -> None:
        before = bot_version()

        (fake_bot / "prompts.py").write_text("SYSTEM = 'two'\n", encoding="utf-8")

        assert bot_version() != before

    def test_editing_a_nested_module_changes_it(self, fake_bot: Path) -> None:
        before = bot_version()

        (fake_bot / "sub" / "inner.py").write_text("X = 2\n", encoding="utf-8")

        assert bot_version() != before

    def test_adding_a_module_changes_it(self, fake_bot: Path) -> None:
        before = bot_version()

        (fake_bot / "extra.py").write_text("", encoding="utf-8")

        assert bot_version() != before

    def test_editing_the_escalation_table_changes_it(self, fake_bot: Path) -> None:
        before = bot_version()

        cache_module.ESCALATION_TOPICS.write_text("topics: [x]\n", encoding="utf-8")

        assert bot_version() != before

    def test_the_real_bot_hashes_to_a_digest(self) -> None:
        assert len(bot_version()) == 64


class TestResultCache:
    def test_put_then_get_round_trips_under_namespace_and_key(self, tmp_path: Path) -> None:
        cache = ResultCache(tmp_path / "cache")

        cache.put("outcome", "abc123", {"trace_id": "tr-1", "n": 2})

        assert cache.get("outcome", "abc123") == {"trace_id": "tr-1", "n": 2}
        assert (tmp_path / "cache" / "outcome" / "abc123.json").is_file()
        assert cache.get("verdict", "abc123") is None

    def test_a_missing_file_is_a_silent_miss(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="buddy_eval"):
            assert ResultCache(tmp_path).get("outcome", "nothing") is None

        assert caplog.records == []

    @pytest.mark.parametrize("content", ['{"reply": "SECRET QUESTION TEXT', "[1, 2]", '"text"', ""])
    def test_an_unreadable_file_is_a_miss_with_one_warning_naming_namespace_and_key(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, content: str
    ) -> None:
        cache = ResultCache(tmp_path)
        cache.put("outcome", "k1", {"a": 1})
        (tmp_path / "outcome" / "k1.json").write_text(content, encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="buddy_eval"):
            assert cache.get("outcome", "k1") is None

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "outcome" in message
        assert "k1" in message
        assert "SECRET" not in message

    def test_a_write_leaves_no_temp_file_behind(self, tmp_path: Path) -> None:
        cache = ResultCache(tmp_path)

        cache.put("outcome", "k1", {"a": 1})
        cache.put("outcome", "k1", {"a": 2})

        assert sorted(p.name for p in (tmp_path / "outcome").iterdir()) == ["k1.json"]
        assert cache.get("outcome", "k1") == {"a": 2}

    def test_a_failed_replace_keeps_the_previous_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = ResultCache(tmp_path)
        cache.put("outcome", "k1", {"a": 1})
        monkeypatch.setattr(os, "replace", _failing_replace)

        with pytest.raises(OSError, match="disk"):
            cache.put("outcome", "k1", {"a": 2})

        monkeypatch.undo()
        assert cache.get("outcome", "k1") == {"a": 1}

    @pytest.mark.parametrize("name", ["../escape", "a/b", ".hidden", "", "a b"])
    def test_a_key_that_could_leave_the_namespace_folder_is_refused(
        self, tmp_path: Path, name: str
    ) -> None:
        with pytest.raises(ValueError, match="unsafe cache key"):
            ResultCache(tmp_path).put("outcome", name, {})


def _failing_replace(src: object, dst: object) -> None:
    raise OSError("disk")


class TestScoredMarkers:
    def test_a_marker_is_per_trace_and_per_version(self, tmp_path: Path) -> None:
        cache = ResultCache(tmp_path)
        assert cache.is_scored("tr-1", "1") is False

        cache.mark_scored("tr-1", "1")

        assert cache.is_scored("tr-1", "1") is True
        assert cache.is_scored("tr-1", "2") is False
        assert cache.is_scored("tr-2", "1") is False
        assert (tmp_path / "scored" / "tr-1-1.json").is_file()
