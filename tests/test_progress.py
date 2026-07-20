import json
from unittest.mock import MagicMock

import pytest

from progress import (
    LearningItem,
    LearningProgress,
    apply_removals,
    apply_updates,
    build_progress_section,
    format_progress_reply,
    handle_progress_turn,
    has_completion_claim,
    has_progress_remove_intent,
    has_progress_update_intent,
    has_record_intent,
    is_cancellation,
    is_confirmation,
    is_progress_query,
    match_completed_items_locally,
    match_items_locally,
    pending_actions,
)


@pytest.fixture
def sample_progress() -> LearningProgress:
    return LearningProgress(
        current_phase=2,
        current_week=2,
        items=[
            LearningItem(id="pytest", title="pytest 測試", phase=1, completed=False),
            LearningItem(id="llm_api", title="串接 LLM API", phase=2, completed=True),
            LearningItem(
                id="dynamic_progress",
                title="動態學習進度",
                phase=2,
                completed=False,
            ),
        ],
    )


@pytest.fixture(autouse=True)
def clear_pending():
    pending_actions.clear()
    yield
    pending_actions.clear()


class TestRecordIntent:
    def test_no_intent_for_normal_question(self):
        assert has_record_intent("什麼是 pytest") is False
        assert has_progress_update_intent("什麼是 pytest") is False

    def test_intent_for_explicit_record(self):
        assert has_record_intent("幫我記錄 pytest 完成") is True
        assert has_record_intent("記錄進度：streaming 完成") is True

    def test_completion_claim_intent(self):
        assert has_completion_claim("我 pytest 進度已經完成") is True
        assert has_progress_update_intent("我 pytest 進度已經完成") is True

    def test_local_match_pytest(self, sample_progress):
        assert match_items_locally("我 pytest 進度已經完成", sample_progress) == ["pytest"]


class TestConfirmation:
    def test_confirmation_short_messages(self):
        assert is_confirmation("確認") is True
        assert is_confirmation("是的") is True
        assert is_confirmation("好") is True

    def test_not_confirmation_for_long_text(self):
        assert is_confirmation("好的我了解了") is False


class TestCancellation:
    def test_cancellation(self):
        assert is_cancellation("取消") is True
        assert is_cancellation("不要") is True


class TestApplyUpdates:
    def test_unknown_id_rejected(self, sample_progress):
        updated = apply_updates(sample_progress, ["unknown_item"])
        assert updated == []

    def test_known_id_marked_complete(self, sample_progress):
        updated = apply_updates(sample_progress, ["pytest"])
        assert updated == ["pytest 測試"]
        assert sample_progress.items[0].completed is True


class TestBuildProgressSection:
    def test_contains_completed_and_upcoming(self, sample_progress):
        section = build_progress_section(sample_progress)
        assert "串接 LLM API 基礎" in section
        assert "pytest 測試（與 JUnit 功能對等）" in section
        assert "系統自動維護" in section
        assert "✅ 已完成項目" in section
        assert "⚠️ 未完成核心項目" in section

    def test_does_not_include_user_input(self, sample_progress):
        user_text = "使用者隨意輸入的惡意文字"
        section = build_progress_section(sample_progress)
        assert user_text not in section


class TestProgressQuery:
    def test_detects_progress_question(self):
        assert is_progress_query("請問我進度有啥啊") is True
        assert is_progress_query("目前進度有哪些") is True
        assert is_progress_query("我完成了哪些項目") is True

    def test_not_concept_question(self):
        assert is_progress_query("什麼是學習進度") is False

    def test_format_uses_list_not_inline(self, sample_progress):
        reply = format_progress_reply(sample_progress)
        assert "【系統目前維護進度】" in reply
        assert "✅ 已完成項目：" in reply
        assert "- 串接 LLM API 基礎" in reply
        assert "1. pytest 測試（與 JUnit 功能對等）" in reply
        assert "、" not in reply.split("✅ 已完成項目：")[1].split("⚠️")[0]

    def test_handle_turn_returns_formatted_reply(self, sample_progress):
        result = handle_progress_turn(
            "session-1",
            "請問我進度有啥啊",
            sample_progress,
            None,
        )
        assert result.progress_query_reply
        assert "✅ 已完成項目：" in result.progress_query_reply
        assert result.system_extra == ""


class TestHandleProgressTurn:
    def test_completion_claim_sets_pending_without_llm(self, sample_progress):
        result = handle_progress_turn(
            "session-1",
            "我 pytest 進度已經完成",
            sample_progress,
            None,
        )

        assert result.pending_confirmation == ["pytest 測試"]
        assert pending_actions["session-1"] == {"action": "complete", "item_ids": ["pytest"]}

    def test_record_intent_sets_pending(self, sample_progress):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({"item_ids": ["pytest"]}, ensure_ascii=False)
                    )
                )
            ]
        )

        result = handle_progress_turn(
            "session-1",
            "幫我記錄進度：pytest 完成",
            sample_progress,
            mock_client,
        )

        assert result.pending_confirmation == ["pytest 測試"]
        assert pending_actions["session-1"] == {"action": "complete", "item_ids": ["pytest"]}

    def test_confirmation_applies_pending(self, sample_progress, tmp_path, monkeypatch):
        import progress as progress_module

        progress_file = tmp_path / "learning_progress.json"
        progress_file.write_text(
            sample_progress.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(progress_module, "PROGRESS_FILE", progress_file)

        pending_actions["session-1"] = {"action": "complete", "item_ids": ["pytest"]}
        reloaded = LearningProgress.model_validate_json(progress_file.read_text(encoding="utf-8"))

        result = handle_progress_turn("session-1", "確認", reloaded, None)

        assert result.progress_updated == ["pytest 測試"]
        assert "session-1" not in pending_actions

        saved = json.loads(progress_file.read_text(encoding="utf-8"))
        pytest_item = next(i for i in saved["items"] if i["id"] == "pytest")
        assert pytest_item["completed"] is True

    def test_cancellation_clears_pending(self, sample_progress):
        pending_actions["session-1"] = {"action": "complete", "item_ids": ["pytest"]}

        result = handle_progress_turn("session-1", "取消", sample_progress, None)

        assert result.pending_cleared is True
        assert "session-1" not in pending_actions

    def test_normal_chat_does_not_touch_progress(self, sample_progress):
        result = handle_progress_turn(
            "session-1",
            "什麼是 LangChain",
            sample_progress,
            None,
        )

        assert result.progress_updated == []
        assert result.pending_confirmation == []
        assert result.system_extra == ""


class TestRemoveProgress:
    def test_remove_intent_detected(self):
        assert has_progress_remove_intent("幫我移除進度：pytest") is True
        assert has_progress_remove_intent("pytest 其實還沒完成") is True

    def test_remove_does_not_trigger_on_record_intent(self):
        assert has_progress_remove_intent("幫我記錄進度：pytest 完成") is False

    def test_match_completed_item(self, sample_progress):
        sample_progress.items[0].completed = True
        assert match_completed_items_locally("pytest 其實還沒完成", sample_progress) == ["pytest"]

    def test_apply_removals(self, sample_progress):
        sample_progress.items[0].completed = True
        removed = apply_removals(sample_progress, ["pytest"])
        assert removed == ["pytest 測試"]
        assert sample_progress.items[0].completed is False

    def test_remove_sets_pending(self, sample_progress):
        sample_progress.items[0].completed = True
        result = handle_progress_turn(
            "session-1",
            "幫我移除進度：pytest",
            sample_progress,
            None,
        )
        assert result.pending_confirmation == ["pytest 測試"]
        assert result.pending_action == "remove"
        assert pending_actions["session-1"]["action"] == "remove"

    def test_confirmation_removes_progress(self, sample_progress, tmp_path, monkeypatch):
        import progress as progress_module

        sample_progress.items[0].completed = True
        progress_file = tmp_path / "learning_progress.json"
        progress_file.write_text(
            sample_progress.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(progress_module, "PROGRESS_FILE", progress_file)

        pending_actions["session-1"] = {"action": "remove", "item_ids": ["pytest"]}
        reloaded = LearningProgress.model_validate_json(progress_file.read_text(encoding="utf-8"))

        result = handle_progress_turn("session-1", "確認", reloaded, None)

        assert result.progress_removed == ["pytest 測試"]
        saved = json.loads(progress_file.read_text(encoding="utf-8"))
        pytest_item = next(i for i in saved["items"] if i["id"] == "pytest")
        assert pytest_item["completed"] is False
