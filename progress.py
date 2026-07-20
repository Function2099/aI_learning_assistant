import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PROGRESS_FILE = Path(__file__).parent / "learning_progress.json"

PHASE_LABELS = {
    1: "第一階段（Python 環境 + Git）",
    2: "第二階段（AI Backend 基礎）",
    3: "第三階段（AI Framework）",
    4: "第四階段（資料庫 + 向量搜尋）",
    5: "第五階段（Cloud + 部署）",
}

RECORD_INTENT_PATTERN = re.compile(
    r"記錄進度|幫我記|幫我記錄|更新進度|標記完成",
    re.IGNORECASE,
)
REMOVE_INTENT_PATTERN = re.compile(
    r"移除進度|刪除進度|取消完成|標記未完成|移除記錄|撤回進度|改回未完成|取消.*完成",
    re.IGNORECASE,
)
COMPLETION_CLAIM_PATTERN = re.compile(
    r"進度.*(完成|做完了)|(已經?)?(完成|做完|學完|學會了?)|做完了",
    re.IGNORECASE,
)
INCOMPLETE_CLAIM_PATTERN = re.compile(
    r"還沒(做|完成|學)|尚未完成|其實沒(做|完成)|並未完成|改回未完成",
    re.IGNORECASE,
)
QUESTION_PATTERN = re.compile(
    r"^(什麼|何謂|如何|怎麼|為什麼|啥是|請問|能不能解釋)",
    re.IGNORECASE,
)
CONFIRMATION_PATTERN = re.compile(
    r"^(確認|是的|好|ok|OK|沒問題|可以)$",
    re.IGNORECASE,
)
CANCELLATION_PATTERN = re.compile(
    r"^(取消|不要|算了|不用)$",
    re.IGNORECASE,
)
PROGRESS_QUERY_PATTERN = re.compile(
    r"(我的?|目前|現在).{0,10}進度"
    r"|進度.{0,10}(有啥|哪些|多少|狀態|完成了)"
    r"|有啥.{0,10}進度"
    r"|學到哪"
    r"|完成(了)?哪些(項目)?",
    re.IGNORECASE,
)

pending_actions: dict[str, dict[str, Any]] = {}
# session_id -> {"action": "complete"|"remove", "item_ids": [...]}

# 本地關鍵字對應（避免 LLM 解析失敗；僅用於未完成項目比對）
ITEM_KEYWORDS: dict[str, list[str]] = {
    "fastapi_basics": ["fastapi", "crud"],
    "pydantic": ["pydantic"],
    "async_await": ["async", "await", "非同步"],
    "uv_package": ["uv", "poetry", "套件管理"],
    "pytest": ["pytest"],
    "git_advanced": ["git", "branch", "merge", "rebase"],
    "llm_api": ["llm", "groq", "openai", "claude"],
    "streaming": ["streaming", "sse", "串流"],
    "system_prompt": ["system prompt", "提示詞", "prompt"],
    "frontend": ["前端", "介面", "ui"],
    "session_management": ["session", "對話記憶", "多輪"],
    "dynamic_progress": ["動態學習進度", "動態進度", "學習進度"],
}

# 使用者查詢進度時的顯示標籤（含 Java 類比）
ITEM_DISPLAY_LABELS: dict[str, str] = {
    "fastapi_basics": "FastAPI REST API / CRUD",
    "pydantic": "Pydantic 資料驗證（類似 Spring Boot 的 DTO 驗證）",
    "async_await": "async/await 非同步處理",
    "uv_package": "uv 套件管理工具",
    "pytest": "pytest 測試（與 JUnit 功能對等）",
    "git_advanced": "Git 分支管理（branch/merge/rebase）",
    "llm_api": "串接 LLM API 基礎",
    "streaming": "Streaming SSE 實作",
    "system_prompt": "System Prompt 設計與邊界測試",
    "frontend": "前端聊天介面整合",
    "session_management": "Session 管理機制",
    "dynamic_progress": "動態學習進度調適",
}


class LearningItem(BaseModel):
    id: str
    title: str
    phase: int
    completed: bool = False


class LearningProgress(BaseModel):
    current_phase: int = 1
    current_week: int = 1
    items: list[LearningItem] = Field(default_factory=list)


class ExtractResult(BaseModel):
    item_ids: list[str] = Field(default_factory=list)


class ProgressTurnResult(BaseModel):
    """Result of handling progress logic for one user turn."""

    progress_updated: list[str] = Field(default_factory=list)
    progress_removed: list[str] = Field(default_factory=list)
    pending_confirmation: list[str] = Field(default_factory=list)
    pending_action: str = ""  # "complete" | "remove"
    pending_cleared: bool = False
    extraction_failed: bool = False
    system_extra: str = ""
    progress_query_reply: str = ""


def load_progress() -> LearningProgress:
    if not PROGRESS_FILE.exists():
        return LearningProgress()
    data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return LearningProgress.model_validate(data)


def save_progress(progress: LearningProgress) -> None:
    PROGRESS_FILE.write_text(
        progress.model_dump_json(indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_item_by_id(progress: LearningProgress, item_id: str) -> LearningItem | None:
    for item in progress.items:
        if item.id == item_id:
            return item
    return None


def get_titles_for_ids(progress: LearningProgress, item_ids: list[str]) -> list[str]:
    titles: list[str] = []
    for item_id in item_ids:
        item = get_item_by_id(progress, item_id)
        if item:
            titles.append(item.title)
    return titles


def get_display_label(item: LearningItem) -> str:
    return ITEM_DISPLAY_LABELS.get(item.id, item.title)


def format_progress_reply(progress: LearningProgress) -> str:
    """產生進度查詢的固定條列式回覆（直接回傳給使用者，不經 LLM 改寫）。"""
    phase_label = PHASE_LABELS.get(progress.current_phase, f"第 {progress.current_phase} 階段")
    completed = [get_display_label(item) for item in progress.items if item.completed]
    incomplete = [
        get_display_label(item)
        for item in progress.items
        if not item.completed and item.phase <= progress.current_phase
    ]

    lines = [
        "【系統目前維護進度】",
        "",
        f"目前位置：{phase_label}，第 {progress.current_week} 週",
        "",
        "✅ 已完成項目：",
        "",
    ]
    if completed:
        lines.extend(f"- {title}" for title in completed)
    else:
        lines.append("- （尚無）")

    lines.extend(["", "⚠️ 未完成核心項目（需補強）：", ""])
    if incomplete:
        lines.extend(f"{index}. {title}" for index, title in enumerate(incomplete, 1))
    else:
        lines.append("1. （尚無）")

    lines.extend(
        [
            "",
            "若要更新進度，請說「幫我記錄進度：xxx 完成」；"
            "若要移除錯誤記錄，請說「幫我移除進度：xxx」",
        ]
    )
    return "\n".join(lines)


def build_progress_section(progress: LearningProgress) -> str:
    phase_label = PHASE_LABELS.get(progress.current_phase, f"第 {progress.current_phase} 階段")
    completed = [get_display_label(item) for item in progress.items if item.completed]
    incomplete = [
        get_display_label(item)
        for item in progress.items
        if not item.completed and item.phase <= progress.current_phase
    ]

    completed_lines = "\n".join(f"  - {title}" for title in completed) or "  - （尚無）"
    incomplete_lines = (
        "\n".join(f"  {index}. {title}" for index, title in enumerate(incomplete, 1))
        or "  1. （尚無）"
    )

    return (
        "【使用者目前學習進度】（系統自動維護，非使用者輸入）\n"
        f"目前位置：{phase_label}，第 {progress.current_week} 週\n\n"
        "✅ 已完成項目：\n"
        f"{completed_lines}\n\n"
        "⚠️ 未完成核心項目（需補強）：\n"
        f"{incomplete_lines}\n\n"
        "以上為系統維護進度，請依此建議，勿建議跳躍超過 1 個階段。\n"
        "若使用者詢問進度，必須逐條列出上述項目，禁止用頓號或逗號合併成段落。"
    )


def is_progress_query(message: str) -> bool:
    """使用者詢問個人學習進度（非觀念題、非記錄意圖）。"""
    text = message.strip()
    if re.search(r"^(什麼是|何謂|啥是)", text):
        return False
    return bool(PROGRESS_QUERY_PATTERN.search(text))


def has_record_intent(message: str) -> bool:
    return bool(RECORD_INTENT_PATTERN.search(message.strip()))


def has_completion_claim(message: str) -> bool:
    text = message.strip()
    if QUESTION_PATTERN.search(text):
        return False
    return bool(COMPLETION_CLAIM_PATTERN.search(text))


def has_progress_remove_intent(message: str) -> bool:
    """明確移除指令，或聲稱某項目尚未完成（仍須兩段式確認才寫入）。"""
    text = message.strip()
    if QUESTION_PATTERN.search(text):
        return False
    if has_record_intent(text):
        return False
    if REMOVE_INTENT_PATTERN.search(text):
        return True
    return bool(INCOMPLETE_CLAIM_PATTERN.search(text))


def has_progress_update_intent(message: str) -> bool:
    """明確記錄指令，或聲稱某項目已完成（仍須兩段式確認才寫入）。"""
    text = message.strip()
    if QUESTION_PATTERN.search(text):
        return False
    if has_progress_remove_intent(text):
        return False
    return has_record_intent(text) or has_completion_claim(text)


def match_items_locally(message: str, progress: LearningProgress) -> list[str]:
    """依關鍵字比對白名單項目，不依賴 LLM。"""
    text = message.lower()
    compact = re.sub(r"\s+", "", text)
    matched: list[str] = []

    for item in progress.items:
        if item.completed:
            continue
        keywords = list(ITEM_KEYWORDS.get(item.id, []))
        keywords.append(item.id.replace("_", " "))
        keywords.append(item.id.replace("_", ""))

        for kw in keywords:
            kw_lower = kw.lower()
            kw_compact = re.sub(r"\s+", "", kw_lower)
            if kw_lower in text or kw_compact in compact:
                matched.append(item.id)
                break

    return matched


def match_completed_items_locally(message: str, progress: LearningProgress) -> list[str]:
    """依關鍵字比對已完成的白名單項目（用於移除進度）。"""
    text = message.lower()
    compact = re.sub(r"\s+", "", text)
    matched: list[str] = []

    for item in progress.items:
        if not item.completed:
            continue
        keywords = list(ITEM_KEYWORDS.get(item.id, []))
        keywords.append(item.id.replace("_", " "))
        keywords.append(item.id.replace("_", ""))

        for kw in keywords:
            kw_lower = kw.lower()
            kw_compact = re.sub(r"\s+", "", kw_lower)
            if kw_lower in text or kw_compact in compact:
                matched.append(item.id)
                break

    return matched


def is_confirmation(message: str) -> bool:
    return bool(CONFIRMATION_PATTERN.match(message.strip()))


def is_cancellation(message: str) -> bool:
    return bool(CANCELLATION_PATTERN.match(message.strip()))


def apply_updates(progress: LearningProgress, item_ids: list[str]) -> list[str]:
    """Mark items completed. Unknown ids are silently skipped."""
    updated_titles: list[str] = []
    known_ids = {item.id for item in progress.items}
    for item_id in item_ids:
        if item_id not in known_ids:
            continue
        item = get_item_by_id(progress, item_id)
        if item and not item.completed:
            item.completed = True
            updated_titles.append(item.title)
    return updated_titles


def apply_removals(progress: LearningProgress, item_ids: list[str]) -> list[str]:
    """Mark items incomplete. Unknown or already-incomplete ids are skipped."""
    removed_titles: list[str] = []
    known_ids = {item.id for item in progress.items}
    for item_id in item_ids:
        if item_id not in known_ids:
            continue
        item = get_item_by_id(progress, item_id)
        if item and item.completed:
            item.completed = False
            removed_titles.append(item.title)
    return removed_titles


def resolve_item_ids(message: str, progress: LearningProgress, client: Any) -> list[str]:
    """先本地比對，失敗再呼叫 LLM。"""
    local_ids = match_items_locally(message, progress)
    if local_ids:
        return local_ids
    if client is not None:
        return extract_item_ids(message, progress, client)
    return []


def resolve_remove_item_ids(message: str, progress: LearningProgress, client: Any) -> list[str]:
    """先本地比對已完成項目，失敗再呼叫 LLM。"""
    local_ids = match_completed_items_locally(message, progress)
    if local_ids:
        return local_ids
    if client is not None:
        return extract_remove_item_ids(message, progress, client)
    return []


def extract_remove_item_ids(message: str, progress: LearningProgress, client: Any) -> list[str]:
    """Use LLM to map user message to completed allowlisted item ids."""
    allowlist = [
        {"id": item.id, "title": item.title}
        for item in progress.items
        if item.completed
    ]
    if not allowlist:
        return []

    system = (
        "從使用者訊息判斷要標記為「未完成」、移除完成記錄的學習項目。"
        "只能回傳 allowlist 中的 id。"
        "若不確定、只是在問問題、或沒有明確移除意圖，回傳空陣列。"
        "禁止回傳 allowlist 以外的 id。"
        f"\n\nallowlist:\n{json.dumps(allowlist, ensure_ascii=False)}"
    )

    try:
        completion = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            temperature=0,
            max_tokens=128,
            response_format={"type": "json_object"},
            extra_body={"reasoning_format": "hidden"},
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = ExtractResult.model_validate_json(raw)
    except Exception:
        return []

    known_ids = {item.id for item in progress.items}
    return [item_id for item_id in parsed.item_ids if item_id in known_ids]


def extract_item_ids(message: str, progress: LearningProgress, client: Any) -> list[str]:
    """Use a separate LLM call to map user message to allowlisted item ids."""
    allowlist = [
        {"id": item.id, "title": item.title}
        for item in progress.items
        if not item.completed
    ]
    if not allowlist:
        return []

    system = (
        "從使用者訊息判斷要標記完成的學習項目。"
        "只能回傳 allowlist 中的 id。"
        "若不確定、只是在問問題、或沒有明確完成意圖，回傳空陣列。"
        "禁止回傳 allowlist 以外的 id。"
        f"\n\nallowlist:\n{json.dumps(allowlist, ensure_ascii=False)}"
    )

    try:
        completion = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            temperature=0,
            max_tokens=128,
            response_format={"type": "json_object"},
            extra_body={"reasoning_format": "hidden"},
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = ExtractResult.model_validate_json(raw)
    except Exception:
        return []

    known_ids = {item.id for item in progress.items}
    return [item_id for item_id in parsed.item_ids if item_id in known_ids]


def handle_progress_turn(
    session_id: str,
    message: str,
    progress: LearningProgress,
    client: Any | None = None,
) -> ProgressTurnResult:
    """Process progress-related logic before the main LLM call."""
    result = ProgressTurnResult()

    if is_confirmation(message) and session_id in pending_actions:
        pending = pending_actions.pop(session_id)
        action = pending["action"]
        item_ids = pending["item_ids"]

        if action == "complete":
            updated = apply_updates(progress, item_ids)
            if updated:
                save_progress(progress)
                result.progress_updated = updated
                result.system_extra = (
                    f"【內部指示】進度已更新：{'、'.join(updated)}。"
                    "請簡短確認並建議下一步。"
                )
        elif action == "remove":
            removed = apply_removals(progress, item_ids)
            if removed:
                save_progress(progress)
                result.progress_removed = removed
                result.system_extra = (
                    f"【內部指示】進度已移除：{'、'.join(removed)}，已改回未完成。"
                    "請簡短確認。"
                )
        return result

    if is_cancellation(message) and session_id in pending_actions:
        pending_actions.pop(session_id)
        result.pending_cleared = True
        result.system_extra = "【內部指示】使用者已取消進度變更，請簡短確認即可。"
        return result

    if has_progress_remove_intent(message):
        if client is None and not match_completed_items_locally(message, progress):
            result.extraction_failed = True
            result.system_extra = (
                "【內部指示】無法解析要移除的進度項目，"
                "請請使用者用具體名稱再說一次（僅能移除已完成的項目）。"
            )
            return result

        item_ids = resolve_remove_item_ids(message, progress, client)
        if item_ids:
            pending_actions[session_id] = {"action": "remove", "item_ids": item_ids}
            titles = get_titles_for_ids(progress, item_ids)
            result.pending_confirmation = titles
            result.pending_action = "remove"
            result.system_extra = (
                f"【內部指示】使用者要求移除進度，待確認項目：{'、'.join(titles)}。"
                "請用 1～2 句話請使用者回覆「確認」或「取消」，不要宣稱已移除。"
            )
        else:
            result.extraction_failed = True
            result.system_extra = (
                "【內部指示】無法對應到已完成的學習項目，"
                "請請使用者用具體名稱再說一次（例如：pytest 測試）。"
            )
        return result

    if has_progress_update_intent(message):
        if client is None and not match_items_locally(message, progress):
            result.extraction_failed = True
            result.system_extra = (
                "【內部指示】無法解析進度項目，請請使用者用具體學習項目名稱再說一次。"
            )
            return result

        item_ids = resolve_item_ids(message, progress, client)
        if item_ids:
            pending_actions[session_id] = {"action": "complete", "item_ids": item_ids}
            titles = get_titles_for_ids(progress, item_ids)
            result.pending_confirmation = titles
            result.pending_action = "complete"
            result.system_extra = (
                f"【內部指示】使用者要求記錄進度，待確認項目：{'、'.join(titles)}。"
                "請用 1～2 句話請使用者回覆「確認」或「取消」，不要宣稱已記錄。"
            )
        else:
            result.extraction_failed = True
            result.system_extra = (
                "【內部指示】無法對應到學習項目，"
                "請請使用者用具體名稱再說一次（例如：pytest 測試、動態學習進度）。"
            )
        return result

    if is_progress_query(message):
        result.progress_query_reply = format_progress_reply(progress)
        return result

    return result


def clear_pending_for_session(session_id: str) -> None:
    pending_actions.pop(session_id, None)
