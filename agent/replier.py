import json
import re
from agent.llm import llm_client
from agent.prompt_loader import load_prompt


def generate_reply(state: dict, context: str, tool_results: list) -> tuple[str, str]:
    """
    Dựa vào state + context + kết quả tool,
    sinh reply cuối cùng cho user.
    """
    prompt_template = load_prompt("generate_reply.txt")
    prompt = prompt_template.format(
        context=context,
        state=json.dumps(state, ensure_ascii=False, indent=2),
        tool_results=json.dumps(tool_results, ensure_ascii=False, indent=2)
    )

    reply = llm_client.generate(prompt)
    return reply.strip(), prompt
