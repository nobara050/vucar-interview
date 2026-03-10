import os
import config

# Prompt module: chịu trách nhiệm tải prompt từ file và cung cấp cho các agent khác sử dụng

# =============================================================================
# =========================== PROMPT LOADING ==================================
# =============================================================================

def load_prompt(filename: str) -> str:
    path = os.path.join(config.PROMPTS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file không tồn tại: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
