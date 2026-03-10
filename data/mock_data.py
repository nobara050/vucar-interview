BUYERS = [
    {"buyer_id": "B001", "name": "Nguyễn Tiến Đạt"},
]

SELLERS = [
    {"seller_id": "S001", "name": "Nguyễn Văn A"},
    {"seller_id": "S002", "name": "Nguyễn Văn B"},
    {"seller_id": "S003", "name": "Nguyễn Văn C"}, 
]

LISTINGS = [
    {"listing_id": "L001", "seller_id": "S001", "name": "Honda Air Blade 2021"},
    {"listing_id": "L002", "seller_id": "S001", "name": "Honda Vision 2020"},
    {"listing_id": "L003", "seller_id": "S002", "name": "Yamaha Freego 2022"},
    {"listing_id": "L004", "seller_id": "S002", "name": "Yamaha NVX 2021"},
]


def get_buyer(buyer_id: str) -> dict:
    return next((b for b in BUYERS if b["buyer_id"] == buyer_id), None)


def get_seller(seller_id: str) -> dict:
    return next((s for s in SELLERS if s["seller_id"] == seller_id), None)


def get_listing(listing_id: str) -> dict:
    return next((l for l in LISTINGS if l["listing_id"] == listing_id), None)


def get_listings_by_seller(seller_id: str) -> list:
    return [l for l in LISTINGS if l["seller_id"] == seller_id]


def get_seller_by_listing(listing_id: str) -> dict:
    listing = get_listing(listing_id)
    if not listing:
        return None
    return get_seller(listing["seller_id"])
