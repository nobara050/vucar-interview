import json
import re
from agent.llm import llm_client
from agent.prompt_loader import load_prompt


def extract_facts(context: str, new_message: dict) -> tuple[dict, str]:
    prompt_template = load_prompt("extract_facts.txt")
    prompt = prompt_template.format(
        context=context,
        sender=new_message["sender"],
        message=new_message["text"]
    )

    raw = llm_client.generate(prompt)
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw), prompt
    except json.JSONDecodeError:
        return {}, prompt