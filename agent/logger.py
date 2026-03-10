import json
import os
from datetime import datetime, timezone
import config

# Module logger: log tất cả các sự kiện liên quan đến cuộc trò chuyện, bao gồm

# =============================================================================
# =========================== LOGGING UTILS ===================================
# =============================================================================

def log_event(conversation_id: str, event_type: str, detail: dict):
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    log_path = os.path.join(config.LOGS_DIR, f"{conversation_id}.jsonl")
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "event_type": event_type,
        "detail": detail
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
