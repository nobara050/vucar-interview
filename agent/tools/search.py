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
        price_max = kwargs.get("price_max") or kwargs.get("budget_max")
        price_min = kwargs.get("price_min") or kwargs.get("budget_min")
        brands = kwargs.get("brands") or ([kwargs.get("brand")] if kwargs.get("brand") else None)
        year_from = kwargs.get("year_from")
        location = kwargs.get("location")
        odo_max = kwargs.get("odo_max")

        results = LISTINGS.copy()

        if price_max:
            results = [l for l in results if l["price"] <= price_max]
        if price_min:
            results = [l for l in results if l["price"] >= price_min]
        if brands:
            brands_lower = [b.lower() for b in brands]
            results = [l for l in results if l["brand"].lower() in brands_lower]
        if year_from:
            results = [l for l in results if l["year"] >= year_from]
        if location:
            results = [l for l in results if l["location"].upper() == location.upper()]
        if odo_max:
            results = [l for l in results if l["odo"] <= odo_max]

        return {"listings": results}
