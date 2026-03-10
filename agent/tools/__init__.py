from agent.tools.search import SearchListingsTool
from agent.tools.listing import GetListingDetailTool
from agent.tools.bridge import CreateChatBridgeTool
from agent.tools.appointment import BookAppointmentTool
from agent.tools.escalate import EscalateToHumanTool

TOOL_REGISTRY: dict = {
    tool.name: tool
    for tool in [
        SearchListingsTool(),
        GetListingDetailTool(),
        CreateChatBridgeTool(),
        BookAppointmentTool(),
        EscalateToHumanTool(),
    ]
}


def call_tool(tool_name: str, params: dict) -> dict:
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return {"error": f"Tool không tồn tại: {tool_name}"}
    return tool.run(**params)
