# Motorbike Marketplace AI Agent
### Take-Home Assignment — AI Product Engineer

---

## Mục lục

1. [Tìm hiểu bài toán](#1-tìm-hiểu-bài-toán)
2. [Architecture và flow](#2-architecture-và-flow)
3. [Key design decisions và trade-offs](#3-key-design-decisions-và-trade-offs)
4. [Failure modes](#4-failure-modes)
5. [Hướng cải thiện tiếp theo](#5-hướng-cải-thiện-tiếp-theo)
6. [State schema và tool schema](#6-state-schema-và-tool-schema)
7. [Memory strategy](#7-memory-strategy)
8. [Evaluation plan](#8-evaluation-plan)
9. [Chạy local](#9-chạy-local)

---

## 1. Tìm hiểu bài toán

Việc mua bán xe máy online có một vấn đề cơ bản: buyer và seller thường không đi đến được thỏa thuận, không phải vì xe không phù hợp, mà vì thiếu người điều phối.

Giá chênh nhau một chút là bỏ cuộc, giấy tờ có vấn đề nhỏ là sợ, seller không muốn qua trung gian là tự liên hệ rồi mất dấu.

Agent trong project này đóng vai trò trung gian — không chỉ chuyển tin nhắn mà còn chủ động điều hướng hai bên đi đến thỏa thuận.

Ba tình huống điển hình từ data mẫu:

- **c1 — Price gap:** Seller muốn 32tr, buyer có tối đa 26tr. Không có ai điều phối thì conversation kết thúc trong im lặng. Agent cần giữ hai bên ở lại và tìm điểm chung trước khi bỏ cuộc.

- **c2 — Document risk:** Giấy tờ đang chờ rút hồ sơ gốc, chưa sang tên được ngay. Buyer lo lắng nhưng không biết đánh giá rủi ro thế nào. Agent cần surface rõ vấn đề và escalate nếu cần.

- **c3 — Seller bypass:** Seller không muốn qua trung gian, chỉ cần số điện thoại người mua. Agent cần giải thích giá trị platform thay vì nhượng bộ.

Giả thuyết chính: agent xử lý được các vấn đề này sớm sẽ tăng tỷ lệ đặt lịch hẹn so với để hai bên tự thương lượng.

---

## 2. Architecture và flow

### Tổng quan hệ thống

```
Streamlit Frontend (app.py)
        |
        | HTTP POST /message
        v
FastAPI Backend (server.py)
        |
        v
process_message() — agent/agent.py
        |
        |-- LLM Call 1: Extract Facts      (agent/extractor.py)
        |-- LLM Call 2: Decide Tools       (agent/decision.py)
        |-- Tool Execution                 (agent/executor.py)
        |-- LLM Call 3: Generate Reply     (agent/replier.py)
        |
        v
State persisted + Events logged
```

### Luồng xử lý mỗi process_message()

1. Tạo mới hoặc load conversation state.
2. Nhận tin nhắn (message) mới, append vào danh sách và log lại.
3. Kiểm tra xem có nên compact memory không (mỗi n tin nhắn hoặc lớn hơn m tokens).
5. Build context từ rolling summary, state hiện tại, và recent messages.
6. Extract facts từ message mới — LLM Call 1.
7. Merge extracted facts vào state.
8. Decide tool nào cần gọi — LLM Call 2.
9. Execute tool, cập nhật state nếu cần (ví dụ: gán channel_id sau khi bridge thành công).
10. Update next_best_action và xử lý escalation nếu có.
11. Nếu sender là buyer thì generate reply — LLM Call 3. Nếu là seller thì bỏ qua.
12. Auto-detect outcome, lưu feedback nếu xác định được.
13. Save state, log AGENT_ACTION.

### Cấu trúc thư mục

```
motorbike-agent/
├── .env                          
├── .gitignore
├── server.py                     ← FastAPI backend
├── app.py                        ← Streamlit frontend
├── config.py                     ← đọc từ .env
├── README.md
│
├── agent/
│   ├── __init__.py
│   ├── agent.py                  ← Pipeline
│   ├── llm.py                    ← Abstract LLM + GeminiLLM + OpenAILLM
│   ├── prompt_loader.py          ← load prompt từ file
│   ├── state.py                  ← state schema + CRUD
│   ├── memory.py                 ← compact + build context
│   ├── extractor.py              ← LLM call 1
│   ├── decision.py               ← LLM call 2
│   ├── replier.py                ← LLM call 3
│   ├── executor.py               ← execute tool calls
│   ├── logger.py                 ← log events
│   ├── feedback.py               ← thu thập và lưu feedback
│   └── tools/
│       ├── __init__.py           ← TOOL_REGISTRY + call_tool()
│       ├── base.py               ← abstract BaseTool
│       ├── search.py             ← search_listings
│       ├── listing.py            ← get_listing_detail
│       ├── bridge.py             ← create_chat_bridge
│       ├── appointment.py        ← book_appointment
│       └── escalate.py           ← escalate_to_human
│
├── prompts/
│   ├── extract_facts.txt
│   ├── decide_tools.txt
│   ├── generate_reply.txt
│   └── compact_summary.txt
│
└── data/
    ├── __init__.py
    ├── mock_data.py              ← buyers, sellers, listings mock
    ├── chat_history.jsonl        ← sample conversations
    ├── feedback.jsonl            ← feedback signals (runtime)
    ├── states/                   ← state JSON per conversation (runtime)
    └── logs/                     ← event logs per conversation (runtime)
```

---

## 3. Key design decisions và trade-offs

### 3 LLM calls riêng biệt mỗi message

Mỗi message đi qua 3 LLM calls với nhiệm vụ hoàn toàn khác nhau: extract facts, decide tools, generate reply. Tách ra như vậy vì mỗi task cần kiểu reasoning khác nhau — extraction cần precision và JSON output, tool selection cần logical reasoning theo state, reply generation cần natural language và tone.

Gộp lại thành 1 call sẽ khó validate từng phần, khó debug khi sai, và khó improve từng bước độc lập. Trade-off là latency cao hơn.

### log_event được hardcode ở tầng system, không phải tool LLM gọi

Đề bài liệt kê `log_event` trong danh sách tools. Tuy nhiên trong implementation này, logging được gọi trực tiếp trong code tại mỗi bước của pipeline, không phải để LLM tự quyết định log hay không.

Lý do: logging là infrastructure, không phải business logic. Nếu để LLM quyết định log, có thể bỏ sót các event quan trọng như USER_MESSAGE hay AGENT_ACTION, làm hỏng toàn bộ audit trail và feedback loop. Các tool còn lại như search, bridge, appointment là business actions có ý nghĩa với deal — LLM nên tự quyết định gọi hay không. Logging thì không.

### Agent chỉ gọi một tool mỗi message turn

Hiện tại mỗi message chỉ trigger tối đa một tool call. Điều này có nghĩa là `search_listings` và `get_listing_detail` phải xảy ra ở 2 turns khác nhau, thay vì tự động gọi liên tiếp.

Đây là trade-off có chủ đích: với giới hạn 3 ngày và scope demo, single tool call đủ để minh họa flow. Trong production, kiến trúc đúng là **ReAct loop** (Reasoning + Acting) — agent có thể reason, gọi tool, nhìn kết quả, rồi reason tiếp và gọi tool khác trong cùng một turn cho đến khi đủ thông tin để trả lời. Ví dụ: search ra xe → tự get_listing_detail → tự bridge seller luôn mà không cần buyer phải nhắn thêm.

### Seller không nhận reply

Khi seller gửi message, agent chỉ extract thông tin và update state, không reply lại. Agent chỉ nhắc đến seller khi cần xác nhận bridge hoặc appointment. Lý do là agent đại diện cho quyền lợi buyer trong hành trình tìm xe — tin nhắn của seller là input để agent hiểu thêm về xe, không phải conversation cần phản hồi.

### Agent phân biệt 2 chế độ theo channel_id

Khi `channel_id` là null, agent đang ở chế độ tìm xe: hỏi nhu cầu, search listings, suggest kết nối. Khi `channel_id` đã có, buyer và seller đang trong cùng channel — agent chuyển sang chế độ thương lượng: không search xe khác, không tạo bridge mới, chỉ tập trung giúp hai bên đi đến deal.

### create_chat_bridge tự lookup seller từ listing_id

Khi agent gọi `create_chat_bridge`, chỉ cần `buyer_id` và `listing_id`. Seller được tự động xác định từ listing — buyer không cần biết seller_id là gì. Điều này đúng với flow thực tế: buyer quan tâm xe nào thì platform kết nối với seller của xe đó, không phải buyer tự chọn seller.

### JSON file storage

State và logs lưu vào JSON files thay vì database để đơn giản hóa setup. Toàn bộ read/write được encapsulate trong `state.py` và `logger.py`, nên production có thể swap sang PostgreSQL hoặc Redis mà không cần thay đổi logic bên ngoài.

---

## 4. Failure modes

### LLM trả về text thay vì JSON trong extraction

Extractor wrap JSON parsing trong try/except, trả về `{}` nếu fail. Conversation tiếp tục nhưng state không được update cho turn đó. Root cause thường là LLM thêm text giải thích xung quanh JSON. Fix đúng hơn là dùng structured output mode khi Gemini hỗ trợ.

### LLM trả về text thay vì function call trong tool selection

Decision module expect function call nhưng có thể nhận plain text. Xử lý bằng cách parse JSON từ text để lấy `next_best_action`, fallback về CLARIFY nếu parse fail. Conversation tiếp tục nhưng không có tool nào được gọi.

### Location string không normalize

LLM có thể expand "HCM" thành "TP.HCM" hoặc "Hồ Chí Minh" khi truyền vào `search_listings`. Mock data hiện tại đơn giản (chỉ có tên xe) nên không ảnh hưởng. Nhưng nếu thêm lại location filter, production cần normalize về dạng chuẩn trước khi compare. Hoặc retrieve theo embedding.

### Context window overflow

Hai lớp bảo vệ: compact memory khi số message chưa compact vượt ngưỡng, và trim oldest recent messages nếu tổng token vẫn còn quá cao. State luôn được giữ nguyên, chỉ message history bị cắt bớt.

### State không nhất quán sau crash

State chỉ được save sau khi toàn bộ pipeline hoàn thành. Nếu crash giữa chừng, state của turn đó bị mất nhưng state cũ vẫn intact. Production cần write-ahead log để recover được.

---

## 5. Hướng cải thiện tiếp theo

### Ngay sau demo

Chạy đủ 3 scenario từ `chat_history.jsonl`, thu thập log thật, tính metrics thực tế. Error analysis từ log thật sẽ chỉ ra prompt nào cần sửa trước.

### Ngắn hạn

Thêm few-shot examples vào `extract_facts.txt` dựa trên log thật — đặc biệt là các phrase tiếng Việt colloquial map sang risk type cụ thể, ví dụ "chờ rút hồ sơ gốc" → `document_issue` severity high.

Thêm automated evaluation script chạy tập test cố định sau mỗi lần thay đổi prompt, để biết thay đổi nào giúp ích và thay đổi nào làm hỏng case khác.

### Trung hạn

Implement **ReAct loop** thay vì single tool call per turn. Với ReAct, agent có thể: search listings → tự get_listing_detail xe buyer quan tâm → tự create_chat_bridge với seller luôn, tất cả trong một turn mà không cần buyer phải nhắn thêm nhiều bước. Đây là cải thiện UX lớn nhất có thể làm.

Thêm location normalization: map các variant như "TP.HCM", "Hồ Chí Minh", "Sài Gòn" về cùng một key trước khi filter.

### Dài hạn

Swap JSON file storage sang database thật. Làm agent pipeline async để handle concurrent conversations. Xây dựng LLM analyzer tự động đọc `feedback.jsonl`, so sánh conversations thành công và thất bại, đề xuất cải thiện prompt để human review.

---

## 6. State schema và tool schema

### State schema

```json
{
  "conversation_id": "c1",
  "created_at": "2026-02-05T09:00:00Z",
  "updated_at": "2026-02-05T09:05:00Z",
  "lead_stage": "NEGOTIATION",
  "participants": {
    "buyer_id": "B001",
    "buyer_name": "Nguyễn Văn A",
    "seller_id": "S001",
    "seller_name": "Nguyễn Văn D"
  },
  "channel_id": null,
  "constraints": {
    "budget_min": null,
    "budget_max": 26000000,
    "location": "HCM",
    "brands": ["Honda", "Yamaha"],
    "year_from": 2020,
    "odo_max": null,
    "keywords": ["tay ga"]
  },
  "listing_context": {
    "listing_id": "L001",
    "price": 32000000,
    "key_attributes": {
      "name": "Honda Air Blade 2021",
      "condition": "zin, giữ kỹ"
    }
  },
  "risks": [
    {
      "type": "price_gap",
      "description": "Seller 32tr, buyer ceiling 26tr",
      "severity": "high"
    }
  ],
  "open_questions": [],
  "next_best_action": {
    "action": "NEGOTIATE",
    "reason": "Price gap 6tr, chưa thương lượng lần nào"
  },
  "tool_history": [],
  "memory": {
    "last_compacted_index": 0,
    "summary": ""
  }
}
```

Lead stage transitions: `DISCOVERY → MATCHING → NEGOTIATION → CLOSING → APPOINTMENT → DROPPED`.

`channel_id` null nghĩa là buyer và seller chưa được kết nối. Khi có giá trị, agent chuyển sang chế độ thương lượng.

### Tool schema

```
search_listings(brands, keywords)
  → Tìm xe theo tên hoặc hãng

get_listing_detail(listing_id)
  → Lấy thông tin chi tiết một xe, kèm thông tin seller

create_chat_bridge(buyer_id, listing_id)
  → Kết nối buyer với seller của listing đó
  → Tự động lookup seller_id từ listing_id
  → Trả về channel_id

book_appointment(channel_id, time, place)
  → Đặt lịch hẹn xem xe
  → Yêu cầu đã có channel_id

escalate_to_human(reason, severity)
  → Chuyển conversation cho nhân viên
  → Cập nhật lead_stage → DROPPED
```

Tất cả tools là mock trong prototype này. Agent tự quyết định gọi tool nào thông qua Gemini native function calling, không hardcode logic.

---

## 7. Memory strategy

Hệ thống có 3 tầng memory riêng biệt, mỗi tầng phục vụ mục đích khác nhau.

**Tầng 1 — Raw logs** (`data/logs/{id}.jsonl`): append-only, không bao giờ sửa hay xóa. Ghi lại toàn bộ events: USER_MESSAGE, AGENT_ACTION, TOOL_CALL, TOOL_RESULT, STATE_UPDATE, ESCALATION, HANDOFF, FEEDBACK. Dùng cho audit và error analysis. Không inject vào LLM.

**Tầng 2 — Structured state** (`data/states/{id}.json`): được update sau mỗi message, chỉ lưu facts đã extract, không lưu raw text. Đây là nguồn thông tin chính để agent ra quyết định.

**Tầng 3 — Rolling summary** (`state.memory.summary`): LLM tóm tắt 3-5 câu, được trigger khi vượt 4 messages chưa compact hoặc 1500 tokens. Thay thế history cũ trong context.

Context inject vào mỗi LLM call theo thứ tự:

```
1. Rolling summary   → thay thế toàn bộ history trước đó
2. Structured state  → constraints, channel_id, risks, listing, next_best_action
3. Recent messages   → chỉ những tin có index > last_compacted_index
```

Nếu vẫn vượt token limit sau khi build context, trim oldest recent messages, giữ lại tin mới nhất.

---

## 8. Evaluation plan

### Problem statement

Success là deal được chốt: buyer và seller gặp nhau và giao dịch thành công. Proxy measurable trong prototype là appointment booking rate — bước cuối cùng có thể verify trước khi transaction rời khỏi platform.

Hypothesis: agent xử lý price gap và document risk sớm sẽ giữ được hai bên ở lại conversation lâu hơn, tăng tỷ lệ đi đến appointment.

### Metrics

Tính tự động từ log:

| Metric | Cách tính |
|---|---|
| Appointment booking rate | Conversations có `book_appointment` thành công / tổng |
| Match success rate | Conversations có `search_listings` trả kết quả / tổng conversations đến MATCHING stage |
| Escalation rate | Conversations có `escalate_to_human` / tổng |
| Slot coverage | Fields constraints không null sau 3 messages đầu / tổng fields |
| Time to first match | Timestamp `search_listings` - timestamp message đầu |
| Drop-off rate | Conversations có `create_chat_bridge` nhưng không có `book_appointment` / tổng bridged |

Cần human review:

- **Hallucination rate:** reply có bịa thông tin không có trong context hoặc tool results không.
- **Policy violations:** agent có search xe khác khi đang thương lượng không, có reply seller khi không cần không.

### Error analysis

**c1 — Price gap, wrong action:**

Lỗi dễ xảy ra là agent gọi `search_listings` ngay khi phát hiện price gap thay vì NEGOTIATE. Signal bị miss là không check `tool_history` để biết đã thương lượng chưa. Fix: thêm rule `search_listings` chỉ được gọi nếu buyer chủ động yêu cầu hoặc đã negotiate mà không thành.

**c2 — Document risk, thiếu escalation:**

Lỗi là agent không escalate dù risk nghiêm trọng. Nguyên nhân là extract_facts không map được "chờ rút hồ sơ gốc" thành `document_issue` severity high. Fix: thêm few-shot examples với Vietnamese phrases cụ thể vào extract_facts prompt.

**c3 — Seller bypass, reply yếu:**

Lỗi là agent trả lời chung chung thay vì giải thích giá trị platform. Signal bị miss là `seller_bypass` risk không trigger đúng action. Fix: thêm handling cho seller_bypass vào generate_reply prompt.

### Feedback loop

Signal tự động từ log:

```
book_appointment thành công   → outcome = "booked"
create_chat_bridge thành công → outcome = "connected"
escalate_to_human gọi         → outcome = "escalated"
lead_stage = DROPPED          → outcome = "dropped"
```

Signal thủ công từ UI: buyer bấm nút "Deal thành công", "Đã đặt lịch", "Buyer bỏ qua", "Cần hỗ trợ".

Mỗi conversation chỉ có một entry trong `data/feedback.jsonl`, update thay vì append khi có signal mới.

Quy trình cải thiện: định kỳ chạy LLM analyzer so sánh conversations thành công và thất bại → LLM đề xuất rule mới → human review → apply vào prompt thủ công → test lại trên log cũ → deploy. Đây là prompt engineering loop, không phải model training — Gemini model weights cố định, cải thiện qua prompt và few-shot examples.

---

## 9. Chạy local

### Cài đặt

```bash
pip install fastapi uvicorn streamlit requests google-generativeai python-dotenv
```

### Cấu hình

Tạo file `.env` ở thư mục gốc:

```
LLM_API_KEY=your_api_key_here
LLM_PROVIDER=gemini
LLM_MODEL=your_model_name
```

### Khởi động

```bash
# Terminal 1
uvicorn server:app --reload --port 8000

# Terminal 2
streamlit run app.py
```

API docs tại `http://localhost:8000/docs`.

### Demo scenarios

Chạy theo 3 conversation từ `data/chat_history.jsonl`:

- **c1** — price gap: agent nên thương lượng trước, không search xe khác ngay.
- **c2** — document risk: agent nên cảnh báo rõ ràng và escalate.
- **c3** — seller bypass: agent nên giải thích giá trị platform.

Để demo nhanh flow buyer-seller mà không cần qua bước tìm xe, dùng nút **"Kết nối demo"** trên sidebar để bridge ngay với seller mặc định, sau đó chuyển role sang seller để simulate cuộc hội thoại.

Mock data có 3 buyers (B001–B003), 3 sellers (S001–S002 có xe, S003 không có), và 4 listings (L001–L004).
