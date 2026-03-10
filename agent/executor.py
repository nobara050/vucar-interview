import json
from datetime import datetime, timezone
import config
from agent.tools import call_tool
from agent.logger import log_event

# Executor module: Chịu trách nhiệm thực thi các công cụ được gọi bởi agent, log các sự kiện liên quan và cập nhật trạng thái lịch sử công cụ.

# =============================================================================
# =========== Helper Function to convert objects to plain dict/list ===========
# =============================================================================
# json.dumps(obj, default=str) chuyển object → JSON string
# json.loads(...) chuyển JSON string → Python object (dict/list) 
# Việc này giúp loại bỏ các trường hợp lỗi khi Gemini protobuf objects không thể serialize trực tiếp.

def _to_plain(obj):
    return json.loads(json.dumps(obj, default=str))

# =============================================================================
# ============= Function to execute tool calls and log results ================
# =============================================================================

def execute_tool_calls(conversation_id: str, tool_calls: list, state: dict) -> list:
    results = [] # Kết quả trả về sau khi gọi tất cả công cụ, sẽ là một list các dict với "tool" và "result"

    for tool_call in tool_calls:
        # Lấy tên công cụ, tham số và chuyển thành plain dict/list
        tool_name = tool_call.get("tool") 
        params = _to_plain(tool_call.get("params", {})) 

        # Log sự kiện gọi công cụ với tên và tham số
        log_event(conversation_id, "TOOL_CALL", {"tool": tool_name, "params": params}) 
        
        # Gọi công cụ và nhận kết quả
        result = call_tool(tool_name, params)
        # Convert kết quả về plain dict/list
        result = _to_plain(result)

        # Log sự kiện kết quả công cụ với tên và kết quả
        log_event(conversation_id, "TOOL_RESULT", {"tool": tool_name, "result": result}) 

        # Thêm kết quả vào list trả về
        results.append({"tool": tool_name, "result": result})

        # Cập nhật lịch sử công cụ trong state
        state["tool_history"].append({
            "tool": tool_name,
            "input": params,
            "output": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        state["tool_history"] = state["tool_history"][-config.MAX_TOOL_HISTORY:]

    return results
