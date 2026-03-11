from datetime import datetime, timezone
from agent.state import load_state, save_state, update_state
from agent.memory import should_compact, compact_memory, build_context
from agent.extractor import extract_facts
from agent.decision import decide_tools
from agent.replier import generate_reply
from agent.executor import execute_tool_calls
from agent.feedback import auto_detect_outcome, save_feedback
from agent.logger import log_event


def process_message(conversation_id: str, messages: list, new_message: dict) -> tuple[str, list]:
    debug_steps = []
    step_counter = [0]

    def add_step(name: str, data: dict):
        step_counter[0] += 1
        import json
        safe_data = json.loads(json.dumps(data, default=str))
        debug_steps.append({
            "step": f"[{step_counter[0]}] {name}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": safe_data
        })

    # ==========================
    # 1. Load state khởi tạo
    # ==========================
    state = load_state(conversation_id)
    add_step("Load State", {"conversation_id": conversation_id, "state": state})

    # ==========================
    # 2. Gán index cho message mới
    #    thêm vào danh sách messages
    # ==========================
    new_message["index"] = len(messages) + 1
    messages.append(new_message)
    add_step("New Message", {
        "index": new_message["index"],
        "sender": new_message["sender"],
        "text": new_message["text"]
    })

    # ==========================
    # 3. Log message mới vào hệ thống
    # ==========================
    log_event(conversation_id, "USER_MESSAGE", {
        "sender": new_message["sender"],
        "text": new_message["text"],
        "index": new_message["index"]
    })

    # ==========================
    # 4. Compact memory (nếu cần, nằm trong state["memory"])
    # ==========================
    compacted = should_compact(messages, state["memory"]["last_compacted_index"])
    add_step("Check Compact Memory", {
        "should_compact": compacted,
        "total_messages": len(messages),
        "last_compacted_index": state["memory"]["last_compacted_index"]
    })

    if compacted:
        new_summary = compact_memory(
            messages,
            state["memory"]["last_compacted_index"],
            state["memory"]["summary"]
        )
        state["memory"]["summary"] = new_summary
        state["memory"]["last_compacted_index"] = new_message["index"]
        log_event(conversation_id, "STATE_UPDATE", {"type": "memory_compacted"})
        add_step("Memory Compacted", {"new_summary": new_summary})

    # =========================
    # 5. Build context + Extract facts + Update state
    # =========================
    context = build_context(state, messages)
    extracted, extract_prompt = extract_facts(context, new_message)
    add_step("Extract Facts", {"prompt": extract_prompt, "extracted": extracted})

    if extracted:
        state = update_state(state, extracted)
        log_event(conversation_id, "STATE_UPDATE", {"extracted": extracted})
        add_step("Update State", {"state": state})

    # =========================
    # 6. Decide tools (LLM call 2)
    #    Quyết định tool nào cần gọi, chưa sinh reply
    #    Chạy với cả buyer lẫn seller để update state đúng
    # =========================
    decision, decision_prompt = decide_tools(state, context)
    add_step("Decide Tools", {"prompt": decision_prompt, "decision": decision})

    # =========================
    # 7. Execute tool calls
    #    Chạy tool, lấy kết quả
    # =========================
    tool_results = []
    if decision.get("tool_calls"):
        tool_results = execute_tool_calls(conversation_id, decision["tool_calls"], state)
        add_step("Tool Results", {"results": tool_results})

        # Gán channel_id + seller vào state nếu create_chat_bridge thành công
        for result in tool_results:
            if result["tool"] == "create_chat_bridge" and result["result"].get("channel_id"):
                r = result["result"]
                state["channel_id"] = r["channel_id"]
                if not state["participants"]["seller_id"]:
                    state["participants"]["seller_id"] = r.get("seller_id")
                    state["participants"]["seller_name"] = r.get("seller_name")
                log_event(conversation_id, "HANDOFF", {"channel_id": r["channel_id"]})
                add_step("Channel Created", {
                    "channel_id": r["channel_id"],
                    "seller": r.get("seller_name")
                })

    # =========================
    # 8. Update next best action + handle escalation
    # =========================
    if decision.get("next_best_action"):
        state["next_best_action"] = decision["next_best_action"]

    if decision.get("escalate"):
        state["lead_stage"] = "DROPPED"
        log_event(conversation_id, "ESCALATION", {"reason": decision.get("escalate_reason", "")})
        add_step("Escalation Triggered", {"reason": decision.get("escalate_reason", "")})

    # =========================
    # 9. Generate reply (LLM call 3)
    #     Chỉ reply khi sender là buyer
    #     Seller chỉ cung cấp thông tin, agent không cần reply lại
    # =========================
    reply = ""
    if new_message["sender"] == "buyer":
        reply, reply_prompt = generate_reply(state, context, tool_results)
        add_step("Generate Reply", {"prompt": reply_prompt, "reply": reply})
    else:
        add_step("Skip Reply", {"reason": "sender là seller, agent không reply"})

    # =========================
    # 10. Auto detect outcome + Save feedback nếu xác định được
    # =========================
    outcome = auto_detect_outcome(state, state.get("tool_history", []))
    if outcome:
        save_feedback(conversation_id, outcome, state)
        log_event(conversation_id, "FEEDBACK", {"outcome": outcome, "auto_detected": True})
        add_step("Auto Feedback", {"outcome": outcome})

    # =========================
    # 11. Save state
    # =========================
    save_state(state)
    log_event(conversation_id, "AGENT_ACTION", {"reply": reply})
    add_step("Final State Saved", {"state": state})

    return reply, debug_steps
