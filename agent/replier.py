import json
import re
from agent.llm import llm_client
from agent.prompt_loader import load_prompt

# Reply module: Chịu trách nhiệm tạo phản hồi dựa trên trạng thái hiện tại, ngữ cảnh và kết quả công cụ.

# =============================================================================
# =========================== REPLY GENERATION ================================
# =============================================================================

def generate_reply(state: dict, context: str, tool_results: list) -> tuple[str, str]:
    # Tải prompt template và điền thông tin vào
    prompt_template = load_prompt("generate_reply.txt")
    prompt = prompt_template.format(
        context=context,
        state=json.dumps(state, ensure_ascii=False, indent=2),
        tool_results=json.dumps(tool_results, ensure_ascii=False, indent=2)
    )

    # Gọi LLM để tạo phản hồi
    reply = llm_client.generate(prompt)
    return reply.strip(), prompt
