# Decision Log — Monday.com BI Agent

**Author:** BI Agent Implementation  
**Date:** March 2025  
**Version:** 1.0

---

## 1. Problem Framing

The core challenge is building an agent that can answer *unstructured, natural-language business questions* against *structured but messy* Monday.com data — without preloading or caching any data. Every query must trigger live API calls.

This rules out simple ETL pipelines or static dashboards. The solution must be:
- **Conversational** — interpret ambiguous founder questions
- **Live** — no stale data, no caching
- **Resilient** — handle missing values, inconsistent formats
- **Transparent** — show what API calls were made

---

## 2. Architecture Decisions

### 2.1 Tech Stack: FastAPI + OpenRouter (Qwen3) + Monday.com GraphQL

**Decision:** Python FastAPI backend, OpenRouter-hosted `qwen/qwen3-next-80b-a3b-instruct:free` with function calling, Monday.com v2 GraphQL API, vanilla JS frontend with SSE streaming.

**Rationale:**

| Option | Considered | Decision |
|--------|-----------|----------|
| FastAPI (Python) | ✅ | **Chosen** — async-native, SSE support, fast iteration |
| Flask | ✅ | Rejected — no native async, SSE is awkward |
| Node.js/Express | ✅ | Rejected — Python ecosystem better for data processing |
| Next.js full-stack | ✅ | Rejected — overkill, adds build complexity |
| OpenRouter + Qwen3-80B | ✅ | **Chosen** — free tier, strong reasoning, function calling, OpenAI-compatible API |
| OpenAI GPT-4o | ✅ | Viable but requires paid API key; OpenRouter provides model flexibility |
| Claude 3.5 | ✅ | Viable alternative; OpenRouter supports it too via same API |
| LangChain | ✅ | Rejected — adds abstraction overhead; direct OpenAI SDK is cleaner and more debuggable |
| React frontend | ✅ | Rejected — no build step needed; vanilla JS + SSE is simpler and faster to deploy |

### 2.2 Agentic Loop: OpenAI Function Calling

**Decision:** Use OpenAI's native function-calling (tool use) API rather than a framework like LangChain or LlamaIndex.

**Rationale:**
- Direct control over the agentic loop — easier to debug and trace
- OpenAI function calling is production-stable and well-documented
- Avoids framework version conflicts and abstraction leakage
- The tool-call trace is naturally available from the API response, making it easy to surface in the UI

**Loop design:** `LLM → selects tool → execute tool → return result to LLM → repeat until final answer`. Max 8 iterations to prevent runaway loops.

### 2.3 Monday.com Integration: GraphQL API (No MCP Server)

**Decision:** Use Monday.com's v2 GraphQL API directly via `httpx` async HTTP client, rather than setting up a separate MCP server process.

**Rationale:**
- Monday.com's official API is GraphQL-based and well-documented
- A separate MCP server process adds deployment complexity without benefit for this use case
- The "MCP-style" tool definitions are implemented as OpenAI function-calling tools — same conceptual pattern, simpler execution
- Every query triggers a fresh `httpx` async call — no caching, no connection pooling that could serve stale data
- The tool definitions in `agent_tools.py` follow the MCP tool schema pattern (name, description, parameters)

### 2.4 Streaming: Server-Sent Events (SSE)

**Decision:** Stream agent events (thinking, tool calls, tool results, answer) via SSE rather than WebSockets or polling.

**Rationale:**
- SSE is unidirectional (server → client), which matches the agent response pattern perfectly
- No WebSocket handshake overhead
- Works through standard HTTP proxies and CDNs
- Native browser `EventSource` support — no client library needed
- Each event type (thinking/tool_call/tool_result/answer/done) is a distinct JSON payload, enabling the real-time trace panel

### 2.5 Data Normalization: In-Memory at Query Time

**Decision:** Normalize data (currency, dates, text) in Python at query time, not pre-processed or stored.

**Rationale:**
- Assignment explicitly prohibits caching/preloading
- Normalization is fast enough for board sizes up to ~500 items
- Keeps the data pipeline simple and auditable
- Data quality issues are surfaced to the LLM so it can communicate caveats to the user

---

## 3. Data Resilience Strategy

The data is described as "intentionally messy." The agent handles:

| Issue | Handling |
|-------|---------|
| Missing/null values | `None` returned; excluded from aggregations; count reported |
| Currency formats (`$1,234`, `1.2M`, `€500`) | Regex normalization to float |
| Date formats (`MM/DD/YYYY`, `DD-MM-YYYY`, ISO) | `datetime.strptime` with multiple format attempts |
| Inconsistent column names | Fuzzy key matching — search for candidate substrings (e.g., "sector", "industry", "vertical" all map to sector filter) |
| Inconsistent status/stage text | Case-insensitive partial matching |
| Empty strings vs null | Both treated as missing |
| Data quality caveats | Automatically computed and included in tool results; LLM instructed to surface them |

---

## 4. Tool Design

Nine tools were defined to cover the full range of BI queries:

- **Fetch tools** (`get_deals`, `get_work_orders`): Full board data for open-ended analysis
- **Summary tools** (`get_deals_summary`, `get_work_orders_summary`): Lightweight metadata for quick overviews
- **Filter tools** (`filter_deals`, `filter_work_orders`): Targeted queries with multiple filter dimensions
- **Aggregate tools** (`aggregate_deals_by_field`, `aggregate_work_orders_by_field`): Group-by with count/sum/avg
- **Cross-board tool** (`cross_board_analysis`): Client overlap, revenue vs operations, full summary

The LLM selects the most appropriate tool(s) based on the query. For complex queries (e.g., "energy sector pipeline this quarter"), it may chain: `filter_deals` (sector=energy, date range) → synthesize answer.

---

## 5. Session Management

**Decision:** In-memory session store (Python dict) keyed by UUID session ID.

**Rationale:**
- Sufficient for a prototype/demo
- Enables multi-turn conversation with context retention
- For production: replace with Redis or a database-backed session store

---

## 6. Trade-offs & Limitations

| Trade-off | Decision |
|-----------|---------|
| No pagination for large boards | Fetch up to 500 items per board. Monday.com's cursor-based pagination could be added for larger datasets. |
| In-memory sessions | Lost on server restart. Acceptable for prototype. |
| Single-tenant | No auth/multi-user isolation. Add OAuth for production. |
| LLM cost | OpenRouter free tier used (`qwen/qwen3-next-80b-a3b-instruct:free`). Rate limits apply; exponential backoff retry logic handles 429s. Swap model in `.env` for paid tiers. |
| No real-time board updates | Agent fetches fresh data per query but doesn't subscribe to Monday.com webhooks. |

---
