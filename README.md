# Motorbike Marketplace AI Agent

AI chat agent đóng vai trung gian giữa buyer và seller trong marketplace mua bán xe máy, giúp thu thập thông tin, cảnh báo rủi ro, thu hẹp price gap, dẫn dắt đến appointment và tăng cơ hội closing deal.

---

## Understanding the Problem

Trong marketplace xe máy, buyer và seller thường gặp các vấn đề:
- Thiếu thông tin đầy đủ → dễ mismatch (xe không đúng nhu cầu).
- Thiếu niềm tin → rủi ro về giấy tờ thật/giả, tình trạng xe.
- Khó khăn trong thương lượng → price gap lớn, chậm phản hồi → drop-off cao.
- Không có cơ chế dẫn dắt → conversation kéo dài vô ích hoặc kết thúc sớm.

Agent không chỉ là "chatbot chuyển tin" mà phải:
- Hiểu context unstructured từ chat history.
- Duy trì structured state để theo dõi progress (lead_stage, constraints, risks).
- Chủ động gọi tools (search, bridge, book) để đẩy deal tiến lên.
- Phát hiện & escalate rủi ro nghiêm trọng.
- Tối ưu "next best action" để tăng appointment booking rate và close rate.

Điểm khác biệt: Agent stateful, tool-augmented, và có feedback loop để học từ outcome thực tế.

---

## Architecture & Flow

### Tổng quan

```
Streamlit UI (app.py)
      ↓ HTTP POST /message
FastAPI Backend (server.py)
      ↓
process_message (agent/agent.py)
      ↓
┌─────────────────────────────────┐
│  LLM Call 1: Extract Facts      │ ← extractor.py
│  LLM Call 2: Decide Tools       │ ← decision.py (native function calling)
│  LLM Call 3: Generate Reply     │ ← replier.py
└─────────────────────────────────┘
      ↓
State saved + Events logged
```


### Luồng xử lý mỗi message (chi tiết)
1. Load / Init state từ `data/states/{conversation_id}.json`
2. Append message mới, gán index, log **USER_MESSAGE**
3. Compact memory nếu cần (>4 messages chưa compact hoặc >1500 tokens)
4. Build context: rolling summary + structured state + recent messages (ưu tiên mới nhất)
5. **Extract facts** (LLM call 1): constraints, risks, intents, listing mentions → merge update state
6. **Decide tools & next_best_action** (LLM call 2): Gemini native function calling → tool calls + reason
7. **Execute tools** → lưu TOOL_CALL / TOOL_RESULT vào tool_history & logs
8. **Generate reply** (LLM call 3): dựa trên tool results, updated state, next_best_action → tiếng Việt tự nhiên
9. Auto-detect outcome nếu có (e.g., booked → stage=CLOSING), lưu feedback nếu outcome rõ
10. Save state (atomic write), log **AGENT_ACTION**

**Trade-off ở đây:**
- 3 LLM calls/message → latency ~3–6s, nhưng modular (dễ debug, replace từng module).
- Nếu gộp thành 1–2 calls → nhanh hơn nhưng khó trace lỗi, khó few-shot improve riêng extraction/decision.

---

## Key Design Decisions & Trade-offs

| Quyết định | Lý do chọn | Trade-off / Alternative |
|------------|------------|--------------------------|
| Custom state machine (JSON file) thay vì LangGraph / CrewAI | Nhanh implement trong 3 ngày, dễ debug (file-based), full control state update | Không có built-in checkpointing, human-loop, graph visualization → dễ race condition nếu multi-user. Alternative: LangGraph cho production. |
| Gemini native function calling cho decision | Flexible, tự decide tool + params, không cần hardcode if-else | Có thể hallucinate format → mitigate bằng strict JSON schema + few-shots. Alternative: OpenAI tools với strict mode. |
| 3 tầng memory (raw logs, structured state, rolling summary) | Align requirement: raw cho audit, structured cho decision nhanh, summary tránh context overflow | Summary có thể mất nuance → mitigate bằng giữ recent messages + key facts. Alternative: Vector DB cho long-term retrieval (phức tạp hơn). |
| File-based persistence (JSON + jsonl) | Đơn giản, không cần DB setup trong assignment | Không scalable, không concurrent-safe → production: Redis / PostgreSQL + checkpointer. |
| Mock tools + escalate_to_human | Demo nhanh, focus vào logic agent | Không real integration → next: connect real APIs + auth. |

---

## State Schema

**Không lưu vào state (lý do):**
- Full raw messages → quá dài, không cần cho decision (dùng logs).
- Detailed tool outputs → lưu logs, chỉ giữ summary trong tool_history.
- Timestamps per event → logs.jsonl xử lý.

---

## Tool Schema

**escalate_to_human(reason, severity)**  
→ Gọi khi risks high (e.g., "giấy tờ giả", price_gap >30%, ODO suspect).  
→ Cập nhật lead_stage = DROPPED, log ESCALATION, reply: "Mình cần kiểm tra thêm, sẽ chuyển cho nhân viên hỗ trợ nhé!"

---

## Memory Strategy

...  
Nếu tổng token vượt ngưỡng, cắt bớt recent messages từ cũ nhất, luôn giữ lại tin mới nhất.  
**Mitigation cho summary loss:** luôn inject current constraints/risks/next_best_action làm "anchor" để LLM không quên facts quan trọng.

---

## Failure Modes & Mitigation

| Failure Mode | Nguyên nhân phổ biến | Mitigation trong design | Cách detect & fix sau |
|--------------|-----------------------|--------------------------|------------------------|
| Hallucinated extraction (sai constraints) | LLM hiểu nhầm text | Few-shot examples tốt + structured JSON output | Error analysis trên logs → add bad examples vào prompt |
| Wrong tool call (gọi search khi chưa đủ info) | Decision prompt thiếu guardrail | Prompt enforce: "Chỉ gọi search khi constraints >70% đầy đủ" | Log tool_history + outcome → retrain decision prompt |
| Infinite loop / too many steps | Không có termination | Max 15 steps/convo, escalate nếu exceed | Auto-detect trong orchestration |
| Context overflow → quên info cũ | Summary prune mạnh | Giữ recent messages + structured facts | Monitor token usage, force compact sớm hơn nếu cần |
| Reply không align next_best_action | Replier prompt yếu | Prompt enforce: "Dựa chặt vào next_best_action, mention tool result tự nhiên" | Human review replies → add few-shots |
| Miss escalation (rủi ro cao nhưng không handoff) | Risks không detect | Explicit rules trong decision prompt + severity scoring | Add critic LLM check sau decision (nếu kịp) |

Những failure modes này được phát hiện qua error analysis trên sample logs (xem phần Evaluation).

---

## How I Would Iterate Next (Post-Assignment Improvements)

1. **Evaluation & Metrics Dashboard**  
   - Tự động run trên 50+ sample conversations → tính appointment rate, slot coverage (budget/location/brand collected %), escalation accuracy.  
   - LLM-as-Judge đánh giá reply quality (helpfulness, naturalness, alignment).

2. **Feedback Loop thực**  
   - Thu thập outcome từ seller/buyer (booked? closed? dropped?) → lưu feedback.jsonl.  
   - Dùng outcomes để:  
     - Auto-generate few-shot examples (good/bad).  
     - Fine-tune extraction/decision nếu có data lớn.  
     - A/B test prompt versions.

3. **Production Readiness**  
   - Chuyển state → Redis/PostgreSQL với versioning.  
   - Add observability: LangSmith / Phoenix trace full flow.  
   - Human-in-the-loop: pause ở escalate, allow human override state.  
   - Real APIs + auth + rate limiting.

4. **Scale & Optimization**  
   - Gộp LLM calls (extract + decide trong 1 prompt) để giảm latency.  
   - Cache tool results (e.g., search listings cho cùng constraints).  
   - Multi-agent nếu cần: 1 agent extract, 1 negotiate, 1 risk detector.

---

## Evaluation & Feedback Loop

**Success Definition:**  
Tăng closing chance = Appointment booking rate cao hơn (>30% conversations), time-to-match nhanh (<8 messages), drop-off thấp sau contact.

**Metrics chính (sẽ implement sau):**  
- Task: Booking rate, escalation correctness.  
- Quality: Slot coverage (constraints collected), hallucination rate (sai extract).  
- Business: Time to first qualified match, drop-off rate.

**Error Analysis:** (sẽ pick 5–10 samples từ chat_history.jsonl)  
Ví dụ: Sai intent → miss search → reply chung chung → fix bằng better few-shots.

**Minimal Feedback Loop:**  
Log (context + action + outcome) → analyze patterns → update prompts / add guardrails.
