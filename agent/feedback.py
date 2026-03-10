import json
import os
from datetime import datetime, timezone
import config


def save_feedback(conversation_id: str, outcome: str, state: dict, notes: str = ""):
    """
    Lưu hoặc cập nhật feedback cho conversation_id.
    Mỗi conversation chỉ có 1 entry, update thay vì append.

    outcome: "booked" | "closed" | "dropped" | "escalated" | "connected"
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
        "channel_id": state.get("channel_id"),
        "notes": notes
    }

    # Load toàn bộ, thay thế entry cũ nếu cùng conversation_id
    entries = load_feedback()
    updated = False
    for i, e in enumerate(entries):
        if e.get("conversation_id") == conversation_id:
            entries[i] = entry
            updated = True
            break

    if not updated:
        entries.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def load_feedback() -> list:
    path = os.path.join(config.DATA_DIR, "feedback.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    return [json.loads(line) for line in lines]


def auto_detect_outcome(state: dict, tool_history: list) -> str | None:
    """
    Tự động phát hiện outcome từ state và tool history.
    Trả về None nếu chưa xác định được.
    """
    tool_names = [t.get("tool") for t in tool_history]

    if "book_appointment" in tool_names:
        return "booked"
    if "escalate_to_human" in tool_names:
        return "escalated"
    if state.get("lead_stage") == "DROPPED":
        return "dropped"
    if "create_chat_bridge" in tool_names:
        return "connected"
    return None


def _count_filled(constraints: dict) -> int:
    count = 0
    for k, v in constraints.items():
        if v is not None and v != [] and v != "":
            count += 1
    return count
