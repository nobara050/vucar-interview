import os
import config


def load_prompt(filename: str) -> str:
    path = os.path.join(config.PROMPTS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file không tồn tại: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
