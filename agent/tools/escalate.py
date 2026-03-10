from datetime import datetime, timezone
from agent.tools.base import BaseTool


class EscalateToHumanTool(BaseTool):

    @property
    def name(self) -> str:
        return "escalate_to_human"

    def run(self, **kwargs) -> dict:
        return {
            "status": "escalated",
            "reason": kwargs.get("reason", ""),
            "severity": kwargs.get("severity", "high"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Cuộc hội thoại đã được chuyển cho nhân viên hỗ trợ."
        }
