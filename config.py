import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "") # gemini, openai 
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Memory settings
MAX_RECENT_MESSAGES = 4
MAX_RECENT_TOKENS = 1500
MAX_TOOL_HISTORY = 2

# Lead stages
LEAD_STAGES = [
    "DISCOVERY",
    "MATCHING",
    "NEGOTIATION",
    "CLOSING",
    "APPOINTMENT",
    "DROPPED"
]

# Event types for logging
EVENT_TYPES = [
    "USER_MESSAGE", # Ghi lại tin nhắn đến từ buyer hoặc seller. Dùng để biết conversation bắt đầu từ đâu và ai nói gì.
    "AGENT_ACTION", # Ghi lại reply mà agent trả về sau khi xử lý xong một message. Dùng để biết agent đã phản hồi gì.
    "TOOL_CALL", # Ghi lại việc agent quyết định gọi tool nào với params gì. Dùng để debug xem agent có gọi đúng tool không.
    "TOOL_RESULT", # Ghi lại kết quả trả về từ tool. Đi kèm với TOOL_CALL để biết tool trả về gì.
    "STATE_UPDATE", # Ghi lại mỗi lần state được cập nhật. Dùng để xem state thay đổi như thế nào theo thời gian.
    "ESCALATION", # Ghi lại khi agent quyết định escalate, kèm lý do. Dùng để đánh giá escalation có hợp lý không.
    "HANDOFF", # Ghi lại khi create_chat_bridge thành công và channel được tạo. Đánh dấu thời điểm buyer và seller được kết nối.
    "FEEDBACK" # Ghi lại outcome của conversation, có thể từ auto-detect hoặc từ nút bấm thủ công trên UI.
]

# Paths
DATA_DIR = "data"
STATES_DIR = "data/states"
LOGS_DIR = "data/logs"
CHAT_HISTORY_FILE = "data/chat_history.jsonl"
PROMPTS_DIR = "prompts"

# API settings
API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_URL = f"http://{API_HOST}:{API_PORT}"
