Monday.com Business Intelligence Agent
An AI-powered conversational BI agent that answers founder-level business questions by querying live Monday.com boards containing Deals and Work Orders data.

🚀 Quick Start
Prerequisites
Python 3.11+
A Monday.com account with API access
An OpenRouter API key (free at https://openrouter.ai/keys)
1. Install Dependencies
cd bi_agent
pip install -r requirements.txt
2. Configure Environment
cp .env.example .env
Edit .env with your credentials:

MONDAY_API_TOKEN=your_monday_api_token
DEALS_BOARD_ID=your_deals_board_id
WORK_ORDERS_BOARD_ID=your_work_orders_board_id
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=qwen/qwen3-next-80b-a3b-instruct:free
Getting your OpenRouter API Key:

Go to https://openrouter.ai/keys
Create a new key and copy it
Getting your Monday.com API Token:

Go to monday.com → Profile picture → Developers
Click "My Access Tokens" → Copy your personal token
Getting Board IDs:

Open your board in monday.com
The URL will be: https://monday.com/boards/BOARD_ID_HERE
3. Import Data into Monday.com
Import the provided Excel files as separate boards:

File	Board Name	Board Type
Deal funnel Data.xlsx	Deals Pipeline	Main board
Work_Order_Tracker Data.xlsx	Work Order Tracker	Main board
Import steps:

monday.com → + Add → Import data → Excel
Map columns to appropriate types (see Column Mapping below)
Copy the board IDs from the URLs into your .env
Recommended Column Types:

Deal Value / Amount → Numbers
Close Date / Start Date → Date
Stage / Status → Status
Sector / Industry → Text or Dropdown
Owner / Assigned To → People
4. Run the Agent
python main.py
Open your browser at: http://localhost:8000

🏗️ Architecture
bi_agent/
├── main.py              # FastAPI server, SSE streaming, session management
├── agent.py             # Agentic loop: LLM ↔ tool calls ↔ Monday.com
├── agent_tools.py       # Tool definitions + data processing (filter, aggregate)
├── monday_client.py     # Monday.com GraphQL API client (live, no cache)
├── templates/
│   └── index.html       # Single-page conversational UI with trace panel
├── requirements.txt
├── .env.example
└── README.md
Data Flow
User Query
    ↓
FastAPI /query/stream (SSE)
    ↓
BIAgent.query() — agentic loop
    ↓
OpenRouter → qwen/qwen3-next-80b-a3b-instruct:free (function calling)
    ↓
Tool selected → execute_tool()
    ↓
monday_client.py → Monday.com GraphQL API (LIVE)
    ↓
Data normalized → returned to LLM
    ↓
LLM synthesizes answer
    ↓
Streamed back to UI (SSE events)
🔧 Available Tools (MCP-style)
Tool	Description
get_deals	Fetch all deals from Deals board
get_work_orders	Fetch all work orders
get_deals_summary	Board metadata + item count
get_work_orders_summary	Board metadata + item count
filter_deals	Filter by sector, stage, owner, value, date
filter_work_orders	Filter by client, status, team, date
aggregate_deals_by_field	Group + aggregate deals (count/sum/avg)
aggregate_work_orders_by_field	Group + aggregate work orders
cross_board_analysis	Span both boards: overlap, revenue vs ops
💬 Example Queries
"How's our pipeline looking for the energy sector this quarter?"
"What's the total value of deals in negotiation stage?"
"Show me a breakdown of deals by sector and stage."
"Which work orders are overdue or at risk?"
"Who are our top performing sales reps by pipeline value?"
"Give me a full business health summary."
"Which clients have both active deals and open work orders?"
🔍 Agent Trace Visibility
Every query shows a real-time trace panel on the right side of the UI:

🤔 Reasoning steps — what the LLM is thinking
📡 API calls — exact Monday.com GraphQL calls made
✅ Tool results — summary of data retrieved
💬 Final answer — the synthesized response
🛡️ Data Resilience
The agent handles messy data:

Missing values → reported as N/A, excluded from aggregations
Currency formats → $1,234, 1.2M, €500 all normalized to float
Date formats → MM/DD/YYYY, DD-MM-YYYY, ISO all normalized
Inconsistent text → case-insensitive matching for sectors, stages, owners
Data quality caveats → automatically surfaced in responses
🌐 API Endpoints
Method	Path	Description
GET	/	Chat UI
GET	/health	Configuration status
POST	/session	Create conversation session
DELETE	/session/{id}	Clear session
POST	/query/stream	Streaming SSE query
POST	/query	Synchronous query
GET	/boards/status	Monday.com board connectivity
🚢 Deployment
Railway / Render / Fly.io
# Set environment variables in your platform dashboard
# Then deploy with:
pip install -r requirements.txt
python main.py
Docker
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
📋 Tech Stack
Component	Choice	Reason
Backend	FastAPI	Async, SSE support, fast
LLM Provider	OpenRouter	Free tier, model flexibility, OpenAI-compatible
LLM Model	qwen/qwen3-next-80b-a3b-instruct:free	Free, strong reasoning, function calling
Monday.com	GraphQL API	Official, live data
Frontend	Vanilla JS + SSE	No build step, instant streaming
Streaming	Server-Sent Events	Simple, reliable for chat
See DECISION_LOG.md for full justification.
