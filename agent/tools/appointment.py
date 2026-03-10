import uuid
from agent.tools.base import BaseTool


class BookAppointmentTool(BaseTool):

    @property
    def name(self) -> str:
        return "book_appointment"

    def run(self, **kwargs) -> dict:
        return {
            "booking_id": f"booking_{uuid.uuid4().hex[:8]}",
            "channel_id": kwargs.get("channel_id", "unknown_channel"),
            "time": kwargs.get("time", ""),
            "place": kwargs.get("place", ""),
            "status": "confirmed"
        }
