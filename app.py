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

    st.divider()
    st.subheader("Participants")
    buyer_options = {f"{b['buyer_id']} - {b['name']}": b["buyer_id"] for b in BUYERS}
    selected_buyer = st.selectbox("Buyer", list(buyer_options.keys()))
    st.session_state.buyer_id = buyer_options[selected_buyer]

    # Lấy state để check channel_id và seller
    try:
        current_state = requests.get(f"{API_URL}/state/{st.session_state.conversation_id}").json()
        channel_id = current_state.get("channel_id")
        seller_name = current_state.get("participants", {}).get("seller_name")
    except Exception:
        channel_id = None
        seller_name = None

    seller_display = seller_name if seller_name else "Chưa match"
    st.text_input("Seller", value=seller_display, disabled=True)

    st.divider()
    role_options = ["buyer", "seller"] if channel_id else ["buyer"]
    role = st.selectbox(
        "Bạn đang nhắn với tư cách:",
        role_options,
        help="Seller chỉ khả dụng sau khi có kết nối."
    )
    st.session_state.role = role

    st.divider()
    if st.button("Kết nối demo", use_container_width=True):
        try:
            res = requests.post(f"{API_URL}/demo-bridge", json={
                "conversation_id": st.session_state.conversation_id,
                "buyer_id": st.session_state.get("buyer_id", "B001"),
                "seller_id": "S001",
                "listing_id": "L001"
            }).json()
            if res.get("channel_id"):
                st.success(f"Đã kết nối với {res.get('seller_name')}")
                st.rerun()
        except Exception as e:
            st.error(f"Lỗi: {e}")

    st.divider()
    if st.button("Reset Conversation", type="primary", use_container_width=True):
        try:
            requests.post(f"{API_URL}/reset/{st.session_state.conversation_id}")
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.last_debug_steps = []
        st.rerun()



# --- Tabs ---
tab_chat, tab_debug, tab_log, tab_feedback = st.tabs(["Chat", "Debug", "Event Log", "Feedback"])

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

# --- Tab Feedback ---
with tab_feedback:
    st.subheader("Feedback - Kết quả deal")

    active_cid = st.session_state.conversation_id
    st.caption(f"Conversation đang active: `{active_cid}`")

    def submit_outcome(outcome, notes=""):
        cid = st.session_state.conversation_id
        try:
            requests.post(f"{API_URL}/feedback", json={
                "conversation_id": cid,
                "outcome": outcome,
                "notes": notes
            })
            st.success(f"Đã lưu outcome **{outcome}** cho conversation `{cid}`")
        except Exception as e:
            st.error(f"Lỗi: {e}")

    st.write("**Gán nhãn kết quả conversation này:**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Deal thành công", use_container_width=True):
            submit_outcome("closed")
    with col2:
        if st.button("Đã đặt lịch", use_container_width=True):
            submit_outcome("booked")
    with col3:
        if st.button("Buyer bỏ qua", use_container_width=True):
            submit_outcome("dropped")
    with col4:
        if st.button("Cần hỗ trợ", use_container_width=True):
            submit_outcome("escalated")

    st.divider()
    st.write("**Thống kê tổng hợp:**")
    try:
        summary = requests.get(f"{API_URL}/feedback/summary").json()
        if summary["total"] > 0:
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Booking rate", f"{summary.get('booking_rate', 0)}%")
            col_b.metric("Close rate", f"{summary.get('close_rate', 0)}%")
            col_c.metric("Drop rate", f"{summary.get('drop_rate', 0)}%")
            st.caption(f"Tổng {summary['total_conversations']} conversations")
            st.json(summary["outcomes"])
        else:
            st.info("Chưa có feedback nào.")
    except Exception:
        st.warning("Không thể kết nối backend.")

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
