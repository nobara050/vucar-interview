import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone

import config
from agent.agent import process_message
from agent.state import load_state, create_initial_state, save_state

app = FastAPI(title="Motorbike Marketplace Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory message store per conversation
# { conversation_id: [message, ...] }
conversation_messages: dict = {}


class MessageRequest(BaseModel):
    conversation_id: str
    sender: str  # "buyer" | "seller"
    text: str
    buyer_id: str = "B001"
    seller_id: str = "S001" 


class MessageResponse(BaseModel):
    reply: str
    debug_steps: list


@app.post("/message", response_model=MessageResponse)
async def receive_message(req: MessageRequest):
    if req.conversation_id not in conversation_messages:
        conversation_messages[req.conversation_id] = []

    new_message = {
        "conversation_id": req.conversation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender": req.sender,
        "text": req.text,
        "index": len(conversation_messages[req.conversation_id]) + 1,
        "buyer_id": req.buyer_id,
        "seller_id": req.seller_id
    }

    # Gán participants vào state trước khi xử lý
    from agent.state import load_state, save_state
    from data.mock_data import get_buyer, get_seller
    state = load_state(req.conversation_id)
    if not state["participants"]["buyer_id"]:
        buyer = get_buyer(req.buyer_id)
        state["participants"]["buyer_id"] = req.buyer_id
        state["participants"]["buyer_name"] = buyer["name"] if buyer else None
    if not state["participants"]["seller_id"]:
        seller = get_seller(req.seller_id)
        state["participants"]["seller_id"] = req.seller_id
        state["participants"]["seller_name"] = seller["name"] if seller else None
    save_state(state)

    reply, debug_steps = process_message(
        conversation_id=req.conversation_id,
        messages=conversation_messages[req.conversation_id].copy(),
        new_message=new_message
    )

    conversation_messages[req.conversation_id].append(new_message)

    # Chỉ thêm agent message nếu có reply (seller nhắn thì reply rỗng)
    if reply:
        agent_message = {
            "conversation_id": req.conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender": "agent",
            "text": reply,
            "index": len(conversation_messages[req.conversation_id]) + 1
        }
        conversation_messages[req.conversation_id].append(agent_message)

    return MessageResponse(reply=reply, debug_steps=debug_steps)


@app.get("/state/{conversation_id}")
async def get_state(conversation_id: str):
    return load_state(conversation_id)


@app.get("/logs/{conversation_id}")
async def get_logs(conversation_id: str):
    log_path = os.path.join(config.LOGS_DIR, f"{conversation_id}.jsonl")
    if not os.path.exists(log_path):
        return {"logs": []}
    with open(log_path, "r", encoding="utf-8") as f:
        logs = [json.loads(line) for line in f.readlines()]
    return {"logs": logs}


@app.post("/reset/{conversation_id}")
async def reset_conversation(conversation_id: str):
    # Xóa messages trong memory
    if conversation_id in conversation_messages:
        del conversation_messages[conversation_id]

    # Xóa state file
    state_path = os.path.join(config.STATES_DIR, f"{conversation_id}.json")
    if os.path.exists(state_path):
        os.remove(state_path)

    # Xóa log file
    log_path = os.path.join(config.LOGS_DIR, f"{conversation_id}.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)

    return {"status": "reset", "conversation_id": conversation_id}


@app.get("/health")
async def health():
    return {"status": "ok"}
