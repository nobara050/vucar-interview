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

### Tách pipeline thành 3 LLM calls độc lập

Một prompt làm tất cả sẽ nhanh nhưng khó scale — không biết lỗi ở đâu khi output sai, không thể optimize từng phần riêng lẻ, không thể swap model cho từng task.

Tách thành 3 stages: extract facts cập nhật state, decision chọn action, generation viết reply. Mỗi stage có prompt và temperature riêng.

Trade-off là latency tăng — trong production, extraction và decision có thể chạy song song để bù lại.

### Logging được hardcode, không phải tool

Nếu logging là tool LLM có thể gọi hoặc không, audit trail phụ thuộc vào quyết định của model — và model có thể bỏ qua. Mất một log USER_MESSAGE hay AGENT_ACTION là mất khả năng debug và mất data để improve sau này.

Logging được gọi trực tiếp tại mỗi bước, không qua LLM. Tools như search hay bridge là business actions — LLM nên tự quyết định. Logging thì không.

### Single tool call per turn và tại sao production cần ReAct

Mỗi turn hiện tại chỉ execute một tool. Kiến trúc đúng cho production là **ReAct loop**: reason → gọi tool → quan sát kết quả → reason tiếp, lặp lại đến khi đủ thông tin thì reply. Với ReAct, một message có thể trigger chuỗi search → get detail → bridge seller trong một turn mà buyer không cần nhắn thêm.

Pipeline hiện tại đã được thiết kế để dễ chuyển sang ReAct: bọc `decide_tools` trong vòng lặp với MAX_STEPS, inject tool result vào context sau mỗi bước trước khi reason tiếp.

### Agent phân biệt 2 chế độ theo channel_id

Tìm xe và thương lượng là 2 giai đoạn cần agent hành xử khác nhau hoàn toàn. `channel_id` là signal phân biệt: null thì tập trung tìm listing, có giá trị thì chuyển hoàn toàn sang mode thương lượng — không search, không bridge mới.

### Storage layer tách biệt khỏi business logic

JSON files trong demo, nhưng toàn bộ read/write được encapsulate trong `state.py` và `logger.py`. Business logic không biết storage là gì — swap sang PostgreSQL hay Redis chỉ cần thay 2 files đó.

---

## 4. Failure modes

### LLM output không đúng format

Extraction và tool selection đều phụ thuộc LLM trả về đúng format. Khi fail, pipeline fallback an toàn: extraction trả `{}` không update state, decision fallback về CLARIFY. Conversation không crash nhưng turn đó không có tiến triển. Fix đúng hướng là dùng structured output mode thay vì parse output thủ công.

### State drift sau nhiều turns

Nếu extraction sai một lần — hiểu nhầm budget, gán sai risk — state bị nhiễm và các turns sau reason trên dữ liệu không đúng. Production cần versioned state: mỗi turn tạo snapshot mới thay vì mutate in place, để rollback được khi phát hiện drift.

### Location ambiguity

"HCM", "TP.HCM", "Sài Gòn" là cùng một nơi nhưng string match sẽ fail. Mock data hiện tại không có location filter nên chưa ảnh hưởng. Production cần normalize trước khi filter, hoặc chuyển sang embedding retrieval để handle semantic similarity.

### Memory loss khi compact

Compact giữ được facts nhưng mất nuance — tone của buyer, các lần từ chối trước, thỏa thuận ngầm. Production nên xem xét memory retrieval: lưu toàn bộ turns nhưng chỉ retrieve đoạn relevant thay vì summarize toàn bộ.

### Durability sau crash

State chỉ persist sau khi pipeline hoàn thành. Crash giữa chừng mất toàn bộ turn đó. Production cần write-ahead log để restart có thể tiếp tục hoặc rollback về trạng thái nhất quán.

---

## 5. Hướng cải thiện tiếp theo

### Validate trên data thật trước khi làm gì khác

Prompt engineering dựa trên assumption sẽ dẫn đến cải thiện sai chỗ. Bước đầu tiên là chạy đủ 3 scenario, đọc log thật, và để error pattern chỉ ra đâu là điểm yếu thực sự — extraction hay decision hay generation.

### Tăng độ chính xác của extraction

Extraction là bước đầu tiên trong pipeline và là nơi lỗi lan sang các bước sau. Tiếng Việt colloquial là thách thức lớn nhất — "chờ rút hồ sơ gốc" hay "xe chưa sang tên" cần được map đúng sang risk type với severity phù hợp. Few-shot examples dựa trên log thật là cách nhanh nhất để cải thiện, không cần thay model.

Song song đó cần automated eval script chạy tập test cố định sau mỗi lần thay prompt, để biết thay đổi nào giúp ích và thay đổi nào break case khác.

### Chuyển sang ReAct loop

Đây là cải thiện UX lớn nhất có thể làm. Hiện tại buyer cần nhắn nhiều bước để agent tìm xe, xem chi tiết, rồi kết nối seller. Với ReAct loop, toàn bộ chuỗi đó xảy ra trong một turn — agent tự reason và gọi tool liên tiếp cho đến khi đủ thông tin mới reply. Về implementation, pipeline hiện tại đã được thiết kế để dễ chuyển đổi.

### Mở rộng hệ thống

Location normalization cần được xử lý trước khi thêm lại location filter — map các variant về cùng key, hoặc chuyển sang embedding retrieval để handle semantic similarity thay vì exact match.

Storage cần swap sang database thật khi có concurrent conversations. Pipeline cần async để không block. Feedback loop cần được tự động hóa — LLM analyzer đọc log, so sánh conversations thành công và thất bại, đề xuất rule mới để human review trước khi apply vào prompt.

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

`lead_stage` theo dõi buyer đang ở đâu trong quy trình: `DISCOVERY → MATCHING → NEGOTIATION → CLOSING → APPOINTMENT → DROPPED`. Agent dùng stage này kết hợp với `channel_id` để quyết định chế độ hoạt động — chưa có channel thì tìm xe, đã có channel thì thương lượng.

`constraints` tích lũy dần theo conversation. Buyer không cần khai báo hết ngay từ đầu — mỗi message extraction sẽ merge thêm thông tin mới vào.

`risks` là danh sách các vấn đề phát hiện được, mỗi risk có type, description và severity. Đây là input chính để agent quyết định có cần escalate không.

`memory` lưu rolling summary của các turns cũ đã compact. Agent inject summary này vào context thay vì toàn bộ history, giữ context window trong giới hạn mà không mất thông tin quan trọng.

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
