import json
from datetime import datetime, timezone
import config
from agent.tools import call_tool
from agent.logger import log_event


def _to_plain(obj):
    """Serialize object sang plain dict/list để tránh lỗi với Gemini protobuf objects."""
    return json.loads(json.dumps(obj, default=str))


def execute_tool_calls(conversation_id: str, tool_calls: list, state: dict) -> list:
    results = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("tool")
        params = _to_plain(tool_call.get("params", {}))

        log_event(conversation_id, "TOOL_CALL", {"tool": tool_name, "params": params})
        result = call_tool(tool_name, params)
        result = _to_plain(result)
        log_event(conversation_id, "TOOL_RESULT", {"tool": tool_name, "result": result})

        results.append({"tool": tool_name, "result": result})

        state["tool_history"].append({
            "tool": tool_name,
            "input": params,
            "output": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        state["tool_history"] = state["tool_history"][-config.MAX_TOOL_HISTORY:]

    return results
