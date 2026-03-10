import json
import os
from datetime import datetime, timezone
import config


def create_initial_state(conversation_id: str) -> dict:
    return {
        "conversation_id": conversation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lead_stage": "DISCOVERY",
        "participants": {
            "buyer_id": None,
            "seller_id": None,
            "buyer_name": None,
            "seller_name": None
        },
        "channel_id": None,
        "constraints": {
            "budget_min": None,
            "budget_max": None,
            "location": None,
            "brands": [],
            "year_from": None,
            "odo_max": None,
            "keywords": []
        },
        "listing_context": {
            "listing_id": None,
            "price": None,
            "key_attributes": {}
        },
        "risks": [],
        "open_questions": [],
        "next_best_action": {
            "action": None,
            "reason": None
        },
        "tool_history": [],
        "memory": {
            "last_compacted_index": 0,
            "summary": ""
        }
    }


def load_state(conversation_id: str) -> dict:
    path = os.path.join(config.STATES_DIR, f"{conversation_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return create_initial_state(conversation_id)


def save_state(state: dict):
    os.makedirs(config.STATES_DIR, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = os.path.join(config.STATES_DIR, f"{state['conversation_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_state(state: dict, extracted: dict) -> dict:
    constraints = extracted.get("constraints", {})
    for key, value in constraints.items():
        if value is not None and key in state["constraints"]:
            if isinstance(value, list):
                existing = state["constraints"][key] or []
                state["constraints"][key] = list(set(existing + value))
            else:
                state["constraints"][key] = value

    listing = extracted.get("listing_context", {})
    if listing.get("listing_id"):
        state["listing_context"]["listing_id"] = listing["listing_id"]
    if listing.get("price"):
        state["listing_context"]["price"] = listing["price"]
    if listing.get("key_attributes"):
        state["listing_context"]["key_attributes"].update(listing["key_attributes"])

    existing_risk_types = {r["type"] for r in state["risks"]}
    for risk in extracted.get("risks", []):
        if risk["type"] not in existing_risk_types:
            state["risks"].append(risk)
            existing_risk_types.add(risk["type"])

    new_questions = extracted.get("open_questions", [])
    state["open_questions"] = list(set(state["open_questions"] + new_questions))

    if extracted.get("lead_stage"):
        state["lead_stage"] = extracted["lead_stage"]

    if extracted.get("next_best_action"):
        state["next_best_action"] = extracted["next_best_action"]

    if extracted.get("participants"):
        for role, uid in extracted["participants"].items():
            if uid:
                state["participants"][role] = uid

    return state
