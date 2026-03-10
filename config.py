import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "") 
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
    "USER_MESSAGE",
    "AGENT_ACTION",
    "TOOL_CALL",
    "TOOL_RESULT",
    "STATE_UPDATE",
    "ESCALATION",
    "HANDOFF",
    "FEEDBACK"
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
