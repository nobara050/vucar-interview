import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from data.mock_data import get_listing, get_seller_by_listing
from agent.tools.base import BaseTool


class GetListingDetailTool(BaseTool):

    @property
    def name(self) -> str:
        return "get_listing_detail"

    def run(self, **kwargs) -> dict:
        listing_id = kwargs.get("listing_id")
        listing = get_listing(listing_id)
        if not listing:
            return {"error": f"Không tìm thấy listing: {listing_id}"}
        seller = get_seller_by_listing(listing_id)
        return {
            "listing_id": listing_id,
            "key_attributes": listing,
            "seller": seller
        }
