import json
import re
from agent.llm import llm_client
from agent.prompt_loader import load_prompt

# Extractor module: chịu trách nhiệm trích xuất các facts từ một message mới dựa trên ngữ cảnh hiện tại.

# =============================================================================
# ================= Function to extract facts from a message ==================
# =============================================================================

def extract_facts(context: str, new_message: dict) -> tuple[dict, str]:

    # Load prompt template và đưa content và message vào để tạo prompt hoàn chỉnh 
    prompt_template = load_prompt("extract_facts.txt") 
    prompt = prompt_template.format(
        context=context,
        sender=new_message["sender"],
        message=new_message["text"]
    )

    # Gọi LLM để tạo ra output
    raw = llm_client.generate(prompt)
    
    # Loại bỏ các markdown code block nếu có
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Cố gắng parse output thành JSON, nếu không thành công thì trả về dict rỗng
    try:
        return json.loads(raw), prompt
    except json.JSONDecodeError:
        return {}, prompt