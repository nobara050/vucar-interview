import json
import requests
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from data.mock_data import BUYERS, SELLERS

import config

API_URL = config.API_URL

st.set_page_config(page_title="Motorbike Marketplace Agent", layout="wide")
st.title("Motorbike Marketplace Agent")

# --- Session init ---
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = "c_demo"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "role" not in st.session_state:
    st.session_state.role = "buyer"
if "last_debug_steps" not in st.session_state:
    st.session_state.last_debug_steps = []

# --- Sidebar ---
with st.sidebar:
    st.header("Cài đặt")
    conversation_id = st.text_input("Conversation ID", value=st.session_state.conversation_id)
    st.session_state.conversation_id = conversation_id

    role = st.selectbox("Bạn đang nhắn với tư cách:", ["buyer", "seller"])
    st.session_state.role = role

    st.divider()
    st.subheader("Participants")
    buyer_options = {f"{b['buyer_id']} - {b['name']}": b["buyer_id"] for b in BUYERS}
    selected_buyer = st.selectbox("Buyer", list(buyer_options.keys()))
    st.session_state.buyer_id = buyer_options[selected_buyer]

    seller_options = {f"{s['seller_id']} - {s['name']}": s["seller_id"] for s in SELLERS}
    selected_seller = st.selectbox("Seller", list(seller_options.keys()))
    st.session_state.seller_id = seller_options[selected_seller]

    st.divider()
    if st.button("Reset Conversation", type="primary", use_container_width=True):
        try:
            requests.post(f"{API_URL}/reset/{st.session_state.conversation_id}")
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.last_debug_steps = []
        st.rerun()

    st.divider()
    st.header("State hiện tại")
    try:
        state = requests.get(f"{API_URL}/state/{st.session_state.conversation_id}").json()
        st.json(state)
    except Exception:
        st.warning("Không thể kết nối backend.")

# --- Tabs ---
tab_chat, tab_debug, tab_log = st.tabs(["Chat", "Debug", "Event Log"])

# --- Tab Chat ---
with tab_chat:
    for msg in st.session_state.messages:
        sender = msg["sender"]
        text = msg["text"]
        if sender == "agent":
            with st.chat_message("assistant"):
                st.markdown(f"**Agent:** {text}")
        elif sender == "buyer":
            with st.chat_message("user"):
                st.markdown(f"**Buyer:** {text}")
        else:
            with st.chat_message("user"):
                st.markdown(f"**Seller:** {text}")

    user_input = st.chat_input(f"Nhắn tin với tư cách {st.session_state.role}...")

    if user_input:
        new_message = {
            "sender": st.session_state.role,
            "text": user_input,
            "index": len(st.session_state.messages) + 1
        }
        st.session_state.messages.append(new_message)

        with st.spinner("Agent đang xử lý..."):
            try:
                response = requests.post(
                    f"{API_URL}/message",
                    json={
                        "conversation_id": st.session_state.conversation_id,
                        "sender": st.session_state.role,
                        "text": user_input,
                        "buyer_id": st.session_state.get("buyer_id", "B001"),
                        "seller_id": st.session_state.get("seller_id", "S001")
                    }
                )
                data = response.json()
                reply = data.get("reply", "")
                st.session_state.last_debug_steps = data.get("debug_steps", [])
            except Exception as e:
                reply = f"Lỗi kết nối backend: {e}"
                st.session_state.last_debug_steps = []

        # Chỉ hiển thị agent message nếu có reply
        if reply:
            agent_message = {
                "sender": "agent",
                "text": reply,
                "index": len(st.session_state.messages) + 1
            }
            st.session_state.messages.append(agent_message)
        st.rerun()

# --- Tab Debug ---
with tab_debug:
    st.subheader("Debug - Các bước xử lý của message cuối cùng")
    if not st.session_state.last_debug_steps:
        st.info("Chưa có message nào được xử lý.")
    else:
        for step in st.session_state.last_debug_steps:
            label = f"`{step['step']}` — {step['timestamp'][11:19]}"
            with st.expander(label, expanded=False):
                st.json(step["data"])

# --- Tab Event Log ---
with tab_log:
    st.subheader("Event Log - Toàn bộ lịch sử")
    try:
        logs_data = requests.get(f"{API_URL}/logs/{st.session_state.conversation_id}").json()
        logs = logs_data.get("logs", [])
        if logs:
            st.caption(f"Tổng {len(logs)} events")
            for entry in reversed(logs):
                label = f"`{entry['event_type']}` — {entry['timestamp'][11:19]}"
                with st.expander(label, expanded=False):
                    st.json(entry["detail"])
        else:
            st.info("Chưa có log.")
    except Exception:
        st.warning("Không thể kết nối backend.")
