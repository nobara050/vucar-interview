BUYERS = [
    {"buyer_id": "B001", "name": "Nguyễn Văn A"},
    {"buyer_id": "B002", "name": "Nguyễn Văn B"},
    {"buyer_id": "B003", "name": "Nguyễn Văn C"},
]

SELLERS = [
    {"seller_id": "S001", "name": "Nguyễn Văn D"},
    {"seller_id": "S002", "name": "Nguyễn Văn E"},
    {"seller_id": "S003", "name": "Nguyễn Văn F"},  # không có xe
]

LISTINGS = [
    {
        "listing_id": "L001",
        "seller_id": "S001",
        "name": "Honda Air Blade 2021",
        "brand": "Honda",
        "year": 2021,
        "price": 32000000,
        "odo": 19000,
        "location": "HCM",
        "document_status": "ok"
    },
    {
        "listing_id": "L002",
        "seller_id": "S001",
        "name": "Honda Vision 2020",
        "brand": "Honda",
        "year": 2020,
        "price": 22000000,
        "odo": 25000,
        "location": "HCM",
        "document_status": "pending"
    },
    {
        "listing_id": "L003",
        "seller_id": "S002",
        "name": "Yamaha Freego 2022",
        "brand": "Yamaha",
        "year": 2022,
        "price": 25500000,
        "odo": 10000,
        "location": "HCM",
        "document_status": "ok"
    },
    {
        "listing_id": "L004",
        "seller_id": "S002",
        "name": "Yamaha NVX 2021",
        "brand": "Yamaha",
        "year": 2021,
        "price": 26000000,
        "odo": 18000,
        "location": "HCM",
        "document_status": "ok"
    },
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
