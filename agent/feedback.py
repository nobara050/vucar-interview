import json
import os
from datetime import datetime, timezone
import config


def save_feedback(conversation_id: str, outcome: str, state: dict, notes: str = ""):
    """
    Lưu feedback signal vào data/feedback.jsonl.

    outcome: "booked" | "closed" | "dropped" | "escalated" | "connected"
    state: state snapshot tại thời điểm kết thúc
    notes: ghi chú tùy chọn từ user
    """
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = os.path.join(config.DATA_DIR, "feedback.jsonl")

    entry = {
        "conversation_id": conversation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "lead_stage": state.get("lead_stage"),
        "last_action": state.get("next_best_action", {}).get("action"),
        "risks": state.get("risks", []),
        "constraints_filled": _count_filled(state.get("constraints", {})),
        "tool_history": state.get("tool_history", []),
        "channel_id": state.get("channel_id"),
        "notes": notes
    }

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_feedback() -> list:
    path = os.path.join(config.DATA_DIR, "feedback.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()]


def auto_detect_outcome(state: dict, tool_history: list) -> str | None:
    """
    Tự động phát hiện outcome từ state và tool history.
    Trả về None nếu chưa xác định được.
    """
    tool_names = [t.get("tool") for t in tool_history]

    if "book_appointment" in tool_names:
        return "booked"
    if state.get("lead_stage") == "DROPPED":
        return "dropped"
    if "escalate_to_human" in tool_names:
        return "escalated"
    if "create_chat_bridge" in tool_names:
        return "connected"
    return None


def _count_filled(constraints: dict) -> int:
    """Đếm số fields constraints đã được điền."""
    count = 0
    for k, v in constraints.items():
        if v is not None and v != [] and v != "":
            count += 1
    return count
