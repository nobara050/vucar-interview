import uuid
import sys
import os
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from data.mock_data import get_seller_by_listing
from agent.tools.base import BaseTool


class CreateChatBridgeTool(BaseTool):

    @property
    def name(self) -> str:
        return "create_chat_bridge"

    def run(self, **kwargs) -> dict:
        buyer_id = kwargs.get("buyer_id", "unknown")
        listing_id = kwargs.get("listing_id", "unknown")

        # Tự động lấy seller từ listing
        seller = get_seller_by_listing(listing_id)
        seller_id = seller["seller_id"] if seller else kwargs.get("seller_id", "unknown")
        seller_name = seller["name"] if seller else "unknown"

        channel_id = f"CH{uuid.uuid4().hex[:6].upper()}"

        return {
            "channel_id": channel_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "seller_name": seller_name,
            "listing_id": listing_id,
            "status": "connected",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
