import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from data.mock_data import LISTINGS
from agent.tools.base import BaseTool


class SearchListingsTool(BaseTool):

    @property
    def name(self) -> str:
        return "search_listings"

    def run(self, **kwargs) -> dict:
        keywords = kwargs.get("keywords") or []
        brands = kwargs.get("brands") or ([kwargs.get("brand")] if kwargs.get("brand") else [])

        results = LISTINGS.copy()

        # Filter theo brand nếu có
        if brands:
            brands_lower = [b.lower() for b in brands if b]
            results = [
                l for l in results
                if any(b in l["name"].lower() for b in brands_lower)
            ]

        # Filter theo keywords nếu có
        if keywords:
            keywords_lower = [k.lower() for k in keywords if k]
            results = [
                l for l in results
                if any(k in l["name"].lower() for k in keywords_lower)
            ]

        return {"listings": results, "total": len(results)}
