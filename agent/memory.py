import config
from agent.llm import llm_client
from agent.prompt_loader import load_prompt


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def should_compact(messages: list, last_compacted_index: int) -> bool:
    recent = [m for m in messages if m["index"] > last_compacted_index]
    recent_text = " ".join(m["text"] for m in recent)
    token_count = estimate_tokens(recent_text)
    return len(recent) >= config.MAX_RECENT_MESSAGES or token_count >= config.MAX_RECENT_TOKENS


def compact_memory(messages: list, last_compacted_index: int, existing_summary: str) -> str:
    to_compact = [m for m in messages if m["index"] > last_compacted_index]
    if not to_compact:
        return existing_summary

    prompt_template = load_prompt("compact_summary.txt")
    chat_text = "\n".join(f"[{m['sender']}]: {m['text']}" for m in to_compact)
    prompt = prompt_template.format(
        existing_summary=existing_summary or "Chưa có tóm tắt.",
        chat_text=chat_text
    )
    return llm_client.generate(prompt)


def build_context(state: dict, messages: list) -> str:
    last_compacted_index = state["memory"]["last_compacted_index"]
    summary = state["memory"]["summary"]

    recent = [m for m in messages if m["index"] > last_compacted_index]

    while len(recent) > 1:
        recent_text = " ".join(m["text"] for m in recent)
        if estimate_tokens(recent_text) <= config.MAX_RECENT_TOKENS:
            break
        recent = recent[1:]

    recent_text = "\n".join(f"[{m['sender']}]: {m['text']}" for m in recent)

    return f"""
=== TÓM TẮT CUỘC HỘI THOẠI ===
{summary or 'Chưa có tóm tắt.'}

=== TRẠNG THÁI HIỆN TẠI ===
Lead stage: {state['lead_stage']}
Channel ID: {state.get('channel_id') or 'null (chưa kết nối với seller)'}
Seller: {state['participants'].get('seller_name') or 'chưa xác định'}
Constraints (buyer): {state['constraints']}
Listing đang xem xét: {state['listing_context']}
Risks: {state['risks']}
Open questions: {state['open_questions']}
Next best action: {state['next_best_action']}

=== TIN NHẮN GẦN ĐÂY ===
{recent_text}
""".strip()
