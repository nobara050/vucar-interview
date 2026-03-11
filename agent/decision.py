import json
import re
import google.generativeai as genai
from agent.llm import llm_client
from agent.prompt_loader import load_prompt


# =============================================================================
# =========================== TOOL DECLARATIONS ===============================
# =============================================================================

TOOL_DECLARATIONS = [
    genai.protos.Tool(
        function_declarations=[
            
            # HÀM SEARCH_LISTINGS: Tìm xe máy theo tiêu chí của buyer, 
            # trả về list các xe phù hợp với thông tin cơ bản (ID, tên xe, giá, vị trí)
            genai.protos.FunctionDeclaration(
                name="search_listings",
                description="Tìm xe máy theo tiêu chí của buyer",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "price_max": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Giá tối đa (VND)"),
                        "price_min": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Giá tối thiểu (VND)"),
                        "brands": genai.protos.Schema(
                            type=genai.protos.Type.ARRAY,
                            items=genai.protos.Schema(type=genai.protos.Type.STRING),
                            description="Danh sách hãng xe, ví dụ: [Honda, Yamaha]"
                        ),
                        "year_from": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Đời xe từ năm nào trở lên"),
                        "location": genai.protos.Schema(type=genai.protos.Type.STRING, description="Khu vực, ví dụ: HCM, HN"),
                        "odo_max": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Số km tối đa"),
                    }
                )
            ),

            # HÀM GET_LISTING_DETAIL: Lấy thông tin chi tiết một xe cụ thể khi buyer quan tâm, 
            # bao gồm mô tả, hình ảnh, thông số kỹ thuật, lịch sử bảo dưỡng, v.v.
            genai.protos.FunctionDeclaration(
                name="get_listing_detail",
                description="Lấy thông tin chi tiết một xe cụ thể",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "listing_id": genai.protos.Schema(type=genai.protos.Type.STRING, description="ID của xe, ví dụ: L001"),
                    },
                    required=["listing_id"]
                )
            ),

            # HÀM CREATE_CHAT_BRIDGE: Chính thức kết nối buyer và seller sau khi buyer đồng ý tiến tới, 
            # tạo một channel chat riêng giữa hai bên để trao đổi thông tin chi tiết và thương lượng.
            genai.protos.FunctionDeclaration(
                name="create_chat_bridge",
                description="Chính thức kết nối buyer và seller sau khi buyer đồng ý tiến tới",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "buyer_id": genai.protos.Schema(type=genai.protos.Type.STRING, description="ID của buyer"),
                        "seller_id": genai.protos.Schema(type=genai.protos.Type.STRING, description="ID của seller"),
                        "listing_id": genai.protos.Schema(type=genai.protos.Type.STRING, description="ID của xe"),
                    },
                    required=["buyer_id", "listing_id"]
                )
            ),

            # HÀM BOOK_APPOINTMENT: Đặt lịch hẹn xem xe giữa buyer và seller, 
            # sau khi hai bên đã trao đổi và thống nhất về việc tiến tới xem xe.
            genai.protos.FunctionDeclaration(
                name="book_appointment",
                description="Đặt lịch hẹn xem xe giữa buyer và seller",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "channel_id": genai.protos.Schema(type=genai.protos.Type.STRING, description="ID channel đã tạo"),
                        "time": genai.protos.Schema(type=genai.protos.Type.STRING, description="Thời gian hẹn"),
                        "place": genai.protos.Schema(type=genai.protos.Type.STRING, description="Địa điểm hẹn"),
                    },
                    required=["channel_id", "time"]
                )
            ),

            # HÀM ESCALATE_TO_HUMAN: Chuyển conversation cho nhân viên hỗ trợ khi có rủi ro nghiêm trọng 
            # hoặc conflict không giải quyết được
            genai.protos.FunctionDeclaration(
                name="escalate_to_human",
                description="Chuyển conversation cho nhân viên hỗ trợ khi có rủi ro nghiêm trọng hoặc conflict không giải quyết được",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "reason": genai.protos.Schema(type=genai.protos.Type.STRING, description="Lý do escalate"),
                        "severity": genai.protos.Schema(type=genai.protos.Type.STRING, description="Mức độ nghiêm trọng: high | critical"),
                    },
                    required=["reason"]
                )
            ),
        ]
    )
]


# =============================================================================
# ========================= DECISION FUNCTION =================================
# =============================================================================

def decide_tools(state: dict, context: str) -> tuple[dict, str]:
    # Load prompt template và format với context, state
    prompt_template = load_prompt("decide_tools.txt")
    prompt = prompt_template.format(
        context=context,
        state=json.dumps(state, ensure_ascii=False, indent=2)
    )

    # Gọi LLM với prompt và tool declarations
    result = llm_client.generate_with_tools(prompt, TOOL_DECLARATIONS)

    # Parse next_best_action từ text nếu có
    next_best_action = {"action": "CLARIFY", "reason": ""}
    escalate = False
    escalate_reason = ""

    if result.get("text"):
        text = result["text"]
        # LLM có thể trả về next_best_action trong text
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                next_best_action = parsed.get("next_best_action", next_best_action)
                escalate = parsed.get("escalate", False)
                escalate_reason = parsed.get("escalate_reason", "")
        except Exception:
            pass

    # Serialize tool_calls sang dict thuần để tránh lỗi deepcopy với protobuf
    raw_tool_calls = result.get("tool_calls", [])
    serialized_tool_calls = []
    for tc in raw_tool_calls:
        serialized_tool_calls.append({
            "tool": tc.get("tool", ""),
            "params": {k: v for k, v in tc.get("params", {}).items()}
        })

    decision = {
        "tool_calls": serialized_tool_calls,
        "next_best_action": next_best_action,
        "escalate": escalate,
        "escalate_reason": escalate_reason
    }

    return decision, prompt
