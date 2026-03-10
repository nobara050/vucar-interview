# Motorbike Marketplace AI Agent
### Take-Home Assignment — AI Product Engineer

---

## Table of Contents

1. [Understanding the Problem](#1-understanding-the-problem)
2. [Architecture and Flow](#2-architecture-and-flow)
3. [Key Design Decisions and Trade-offs](#3-key-design-decisions-and-trade-offs)
4. [Failure Modes](#4-failure-modes)
5. [How I Would Iterate Next](#5-how-i-would-iterate-next)
6. [State Schema and Tool Schema](#6-state-schema-and-tool-schema)
7. [Memory Strategy](#7-memory-strategy)
8. [Evaluation Plan](#8-evaluation-plan)
9. [Running Locally](#9-running-locally)

---

## 1. Understanding the Problem

A motorbike marketplace brings together buyers and sellers who often fail to close deals due to information asymmetry, price friction, and trust gaps. The agent's role is not simply to relay messages — it must actively reduce friction, surface risks early, and guide both parties toward a successful outcome.

Three core failure scenarios emerge from the sample data:

- **Price tension (c1):** Seller asks 32M VND, buyer's ceiling is 26M VND. Without a mediator, this conversation ends in silence. The agent must facilitate negotiation before either party disengages.
- **Document risk (c2):** The listing has a pending title transfer. The buyer senses risk but lacks the expertise to evaluate it. The agent must surface this clearly and escalate if necessary.
- **Seller bypass (c3):** The seller distrusts intermediaries and wants direct contact. The agent must demonstrate platform value rather than forcing compliance.

The central hypothesis is that an agent maintaining structured state, detecting risk signals early, and guiding negotiation will increase appointment booking rate compared to unassisted communication.

---

## 2. Architecture and Flow

### System Overview

The system separates concerns into two independently runnable processes: a FastAPI backend responsible for all agent logic, and a Streamlit frontend responsible for the user interface. Communication between them occurs over HTTP.

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

### Per-Message Processing Steps

Each incoming message is processed through the following sequence:

1. Load the conversation state from disk.
2. Assign a sequential index to the new message and append it to the in-memory message list.
3. Log a USER_MESSAGE event.
4. Check whether memory compaction is needed; if so, summarize and update the rolling summary.
5. Build the LLM context from the rolling summary, current state, and recent messages.
6. Call the extractor to pull structured facts from the new message (LLM Call 1).
7. Merge extracted facts into the conversation state.
8. Call the decision module to determine which tool, if any, to invoke (LLM Call 2, using Gemini native function calling).
9. Execute the chosen tool and collect results.
10. If the sender is a buyer, generate a reply using the updated state and tool results (LLM Call 3). If the sender is a seller, skip reply generation entirely — the agent only updates state.
11. Auto-detect outcome signals and persist feedback if applicable.
12. Save the updated state to disk and log an AGENT_ACTION event.

### Repository Structure

```
motorbike-agent/
├── server.py
├── app.py
├── config.py
├── agent/
│   ├── llm.py
│   ├── prompt_loader.py
│   ├── state.py
│   ├── memory.py
│   ├── extractor.py
│   ├── decision.py
│   ├── replier.py
│   ├── executor.py
│   ├── logger.py
│   ├── feedback.py
│   ├── agent.py
│   └── tools/
│       ├── base.py
│       ├── search.py
│       ├── listing.py
│       ├── bridge.py
│       ├── appointment.py
│       └── escalate.py
├── prompts/
│   ├── extract_facts.txt
│   ├── decide_tools.txt
│   ├── generate_reply.txt
│   └── compact_summary.txt
└── data/
    ├── mock_data.py
    ├── feedback.jsonl
    ├── states/
    └── logs/
```

---

## 3. Key Design Decisions and Trade-offs

### Three LLM Calls Per Message

The agent uses three separate LLM calls per message rather than one combined prompt. The first call extracts structured facts, the second decides which tool to invoke, and the third generates the reply.

This separation exists because each task requires a fundamentally different type of reasoning. Extraction requires precision and JSON output. Tool selection requires logical reasoning about state and priorities. Reply generation requires natural language and tone awareness. Combining these into a single prompt would produce output that is harder to validate, harder to debug, and harder to improve independently.

The trade-off is additional latency per message. Given that the bottleneck is the Gemini API response time regardless, and that the clarity gained far outweighs the marginal cost, this was deemed the correct choice for this stage.

### Gemini Native Function Calling for Tool Selection

Rather than prompting the LLM to output a JSON object and parsing it manually, the decision module uses Gemini's native function calling mechanism via `FunctionDeclaration`. This means tool schemas are declared formally with typed parameters, and the LLM selects and parameterizes tools using the API's built-in structured output mechanism.

The trade-off is tighter coupling to the Gemini SDK. However, the benefit of eliminating manual JSON parsing — and the class of silent errors it produces — is significant enough to justify this dependency.

### Seller Messages Do Not Trigger a Reply

When the sender is a seller, the agent extracts facts and updates state but does not generate a reply. The agent only responds to sellers in two specific situations: to request confirmation before creating a chat bridge, and to confirm appointment availability before booking.

This decision was made to prevent the agent from becoming intrusive or appearing to represent the seller's interests. The agent's role is to serve the buyer's journey; seller messages are inputs to the agent's understanding, not conversations requiring reciprocal engagement.

### No Search on Price Gap

When a price gap is detected, the agent prioritizes negotiation over immediately searching for alternative listings. Search is only triggered when the buyer explicitly requests it.

The reasoning is that surfacing alternative listings prematurely signals to the buyer that the current deal is unlikely to close, which reduces the chance of negotiation succeeding. An agent that abandons the current deal too early is not serving the platform's goal of closing transactions.

### JSON File Storage

State and logs are persisted to JSON files rather than a database. This was a deliberate trade-off to minimize setup complexity for the prototype. The interfaces for reading and writing state are fully encapsulated in `state.py`, making it straightforward to replace the file backend with PostgreSQL or Redis in production without touching any other module.

---

## 4. Failure Modes

### LLM Fails to Return Valid JSON from Extraction

The extractor wraps JSON parsing in a try/except block and returns an empty dictionary on failure. The conversation continues without a state update for that message. While this degrades accuracy, it prevents a complete failure of the pipeline.

The root cause is typically that the LLM adds explanatory text around the JSON. The prompt explicitly instructs the LLM to return only JSON, but this instruction is not always followed. A more robust fix would be to use structured output mode where supported.

### Gemini Returns Text Instead of a Function Call

The decision module expects a function call but may receive a plain text response when the LLM decides no tool is needed. The module handles this by attempting to parse a JSON object from the text to extract `next_best_action`, and falling back to a default CLARIFY action if parsing fails. The conversation continues, but tool execution is skipped.

### deepcopy Fails on Gemini Protobuf Objects

Gemini's `MapComposite` objects returned in function call arguments cannot be deep-copied by Python's standard `copy.deepcopy`. This was resolved by serializing all tool call results to plain Python dictionaries immediately after receiving them from the SDK, before any logging or state update occurs.

### Context Window Overflow

Two layers of protection prevent the context from exceeding the model's token limit. The first layer is proactive compaction: when the number of uncompacted messages exceeds a threshold, the agent calls the LLM to produce a rolling summary. The second layer is reactive trimming: before injecting recent messages into the context, the memory module trims the oldest messages until the estimated token count falls within the allowed range.

### State Inconsistency After Crash

State is saved to disk only after the full processing pipeline completes. If the process crashes mid-pipeline, the state on disk reflects the previous message, not the current one. The current message will be lost, but the state will remain internally consistent. Recovering from this would require a write-ahead log, which is outside the scope of this prototype.

---

## 5. How I Would Iterate Next

### Immediate Next Steps

The most important immediate action is to run all three sample scenarios end-to-end, collect the resulting logs, and compute the defined metrics against real outputs. Error analysis based on actual log data will reveal which failure modes are most frequent and which prompt changes are most needed.

### Short-Term Improvements

The extraction prompt should include concrete few-shot examples derived from the sample data. The current prompt relies entirely on the LLM's general instruction-following ability. Adding examples of how "chờ rút hồ sơ gốc" maps to a `document_issue` risk with `severity: high` would make extraction more reliable.

The decision prompt would benefit from clearer state-conditional rules. Currently the LLM reasons from general principles. Making the rules more explicit — for example, "if `risks` contains any entry with `severity: high`, the only permitted action is `escalate_to_human`" — would reduce deviation.

### Medium-Term Improvements

An automated evaluation pipeline that runs a fixed set of test conversations after each prompt change would enable systematic regression testing. Without this, it is difficult to know whether a prompt change improved one scenario while breaking another.

The feedback loop should be extended to include a lightweight LLM-assisted analysis script that reads `data/feedback.jsonl`, groups conversations by outcome, and produces a summary of patterns associated with failures. This summary can then inform the next round of prompt revisions.

### Long-Term Improvements

For production deployment, the JSON file storage should be replaced with a proper database. The agent pipeline should be made asynchronous to handle concurrent conversations without blocking. The rolling summary compaction should be evaluated against alternative approaches such as selective fact pinning, where critical facts are explicitly preserved before compaction rather than relying on the summarization LLM to retain them.

---

## 6. State Schema and Tool Schema

### State Schema

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
    "keywords": ["tay ga", "xe đẹp"]
  },
  "listing_context": {
    "listing_id": "L001",
    "price": 32000000,
    "key_attributes": {
      "name": "Honda Air Blade 2021",
      "odo": 19000,
      "condition": "zin, giữ kỹ"
    }
  },
  "risks": [
    {
      "type": "price_gap",
      "description": "Seller asking 32M, buyer ceiling 26M",
      "severity": "high"
    }
  ],
  "open_questions": [],
  "next_best_action": {
    "action": "NEGOTIATE",
    "reason": "Price gap of 6M exists; negotiation not yet attempted"
  },
  "tool_history": [],
  "memory": {
    "last_compacted_index": 0,
    "summary": ""
  }
}
```

Lead stage transitions follow the path: `DISCOVERY → MATCHING → NEGOTIATION → CLOSING → APPOINTMENT → DROPPED`.

### Tool Schema

```
search_listings(
    price_max: number,
    price_min: number,
    brands: string[],
    year_from: number,
    location: string,
    odo_max: number
) → { listings: Listing[] }

get_listing_detail(
    listing_id: string  [required]
) → { listing_id, key_attributes, seller }

create_chat_bridge(
    buyer_id: string    [required],
    listing_id: string  [required],
    seller_id: string
) → { channel_id, buyer_id, seller_id, listing_id, status, created_at }

book_appointment(
    channel_id: string  [required],
    time: string        [required],
    place: string       [required]
) → { booking_id, channel_id, time, place, status }

escalate_to_human(
    reason: string      [required],
    severity: string
) → { status, reason, severity, message }
```

All tools are mocked in this prototype. In production, each would correspond to an internal API endpoint. The agent determines when and why to call each tool through Gemini native function calling, not through hardcoded logic.

---

## 7. Memory Strategy

The system maintains three distinct layers of memory, each serving a different purpose.

### Layer 1: Raw Logs

All events are appended to `data/logs/{conversation_id}.jsonl` and are never modified or deleted. The event types logged are USER_MESSAGE, AGENT_ACTION, TOOL_CALL, TOOL_RESULT, STATE_UPDATE, ESCALATION, HANDOFF, and FEEDBACK. This layer serves as the audit trail and is the primary data source for error analysis and future training data. It is never injected into the LLM context.

### Layer 2: Structured State

Extracted facts are merged into the conversation state after each message and persisted to `data/states/{conversation_id}.json`. Only structured, validated information is stored here — raw message text is not. This layer is injected into every LLM call as a compact representation of what the agent knows about the conversation.

### Layer 3: Rolling Summary

When the number of uncompacted messages exceeds four, or when the estimated token count of recent messages exceeds 1,500, the agent calls the LLM to produce a 3–5 sentence summary of the messages since the last compaction. This summary is combined with any existing summary and stored in `state.memory.summary`. The `last_compacted_index` is updated accordingly.

### Context Construction

Each LLM call receives context assembled in the following order:

1. The rolling summary, which replaces the full message history prior to `last_compacted_index`.
2. The current structured state, including constraints, listing context, risks, and next best action.
3. Recent messages, defined as those with an index greater than `last_compacted_index`.

If the total estimated token count exceeds the allowed limit, the oldest recent messages are trimmed first, preserving the most recent context.

---

## 8. Evaluation Plan

### Problem Statement

Success is defined as a completed deal: buyer and seller reach an agreement and conduct the transaction. The primary measurable proxy for success in this prototype is appointment booking rate, as it represents the last verifiable step before the transaction leaves the platform.

The central hypothesis is that an agent that detects risk signals early, facilitates negotiation rather than abandoning it, and guides both parties through structured stages will produce a higher appointment booking rate than unassisted communication.

### Metrics

The following metrics can be computed automatically from event logs:

| Metric | Definition |
|---|---|
| Appointment booking rate | Conversations containing a successful `book_appointment` call divided by total conversations |
| Match success rate | Conversations where `search_listings` returned at least one result divided by total conversations that reached the MATCHING stage |
| Escalation rate | Conversations containing an `escalate_to_human` call divided by total conversations |
| Next-action correctness | Conversations where `next_best_action` matches the tool called in the following step divided by total tool-calling steps |
| Slot coverage | Number of non-null constraint fields after the first three messages divided by total constraint fields |
| Time to first match | Timestamp of first `search_listings` call minus timestamp of first message, in seconds |
| Drop-off rate | Conversations where `create_chat_bridge` was called but `book_appointment` was never called divided by total bridged conversations |

The following metrics require human review:

- **Hallucination rate:** The proportion of agent replies that contain factual claims not supported by the conversation context or tool results.
- **Policy violations:** The proportion of replies where the agent suggested alternative listings during an active negotiation, or replied to a seller when not appropriate.

### Error Analysis

**Scenario c1 — Price gap, wrong action taken**

The most likely failure is that the agent calls `search_listings` immediately upon detecting a price gap, rather than initiating negotiation. The signal that triggers the wrong action is the presence of a `price_gap` risk combined with a low `budget_max`. The signal that is missing is the absence of any prior negotiation attempt recorded in the tool history. The fix is to add an explicit rule to the decision prompt stating that `search_listings` is only permitted if `tool_history` contains a prior NEGOTIATE action that did not resolve the gap, or if the buyer has explicitly requested alternative listings.

**Scenario c2 — Document risk, missing escalation**

The most likely failure is that the agent does not escalate despite a serious document issue. The extraction step may not classify "chờ rút hồ sơ gốc" as a `document_issue` with `severity: high` because the phrase is colloquial and not covered by the prompt's examples. The fix is to add few-shot examples of Vietnamese phrases that map to each risk type and severity level.

**Scenario c3 — Seller bypass, weak response**

The most likely failure is that the agent provides a generic acknowledgment rather than a substantive explanation of platform value. The signal being missed is that `seller_bypass` should trigger a HANDOFF action with a specific script, not a generic CLARIFY response. The fix is to add explicit handling for the `seller_bypass` risk type in the reply generation prompt, with a concrete example of what the agent should say.

### Feedback Loop

Outcome signals are collected from two sources. The first is automatic detection from the event log: a successful `book_appointment` call sets outcome to "booked", a call to `escalate_to_human` sets it to "escalated", and a transition to lead stage DROPPED sets it to "dropped". The second is manual input from the UI, where the buyer can indicate whether the deal succeeded or was abandoned.

Each feedback entry stored in `data/feedback.jsonl` contains the conversation ID, outcome, lead stage at the time of outcome, last recorded action, list of active risks, number of constraint fields filled, and any notes provided by the user.

This data is used to improve the agent through a human-in-the-loop prompt engineering cycle. Periodically, an analysis script submits a batch of failed conversations to the LLM alongside successful ones and asks it to identify differentiating patterns. A human reviewer evaluates the suggested prompt changes, applies them manually, and validates the changes against the existing log data before deploying. This process is explicitly not automated model training — the Gemini model weights are fixed, and all improvement occurs through prompt revision and few-shot example augmentation.

---

## 9. Running Locally

### Requirements

```bash
pip install fastapi uvicorn streamlit requests google-generativeai
```

### Configuration

Open `config.py` and set your API key and preferred model:

```python
LLM_PROVIDER = "gemini"
LLM_MODEL = "gemini-2.0-flash-lite"
LLM_API_KEY = "your_api_key_here"
```

### Starting the Services

Open two terminal windows. In the first, start the backend:

```bash
uvicorn server:app --reload --port 8000
```

In the second, start the frontend:

```bash
streamlit run app.py
```

The interactive API documentation is available at `http://localhost:8000/docs`.

### Sample Data

The file `data/chat_history.jsonl` contains three sample conversations demonstrating the core scenarios. To run a scenario, select a conversation ID in the sidebar, choose a role (buyer or seller), and enter the messages from the sample file in order.

- Conversation **c1** demonstrates price gap handling: the agent should negotiate before considering alternatives.
- Conversation **c2** demonstrates document risk detection: the agent should warn the buyer and escalate.
- Conversation **c3** demonstrates seller bypass: the agent should explain platform value rather than conceding.

Three mock sellers (S001–S003) and three mock buyers (B001–B003) are pre-loaded. S001 owns listings L001 and L002. S002 owns listings L003 and L004. S003 has no active listings.
