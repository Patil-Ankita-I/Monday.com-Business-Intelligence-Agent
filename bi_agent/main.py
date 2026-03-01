"""
Monday.com BI Agent - FastAPI Backend
Serves the conversational interface and streams agent responses via SSE.
"""

import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

import agent as bi_agent_module

load_dotenv()

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("[BI Agent] Monday.com BI Agent starting up...")
    print(f"   Deals Board ID: {os.getenv('DEALS_BOARD_ID', 'NOT SET')}")
    print(f"   Work Orders Board ID: {os.getenv('WORK_ORDERS_BOARD_ID', 'NOT SET')}")
    print(f"   OpenAI Model: {os.getenv('OPENAI_MODEL', 'gpt-4o')}")
    yield
    print("[BI Agent] Shutting down.")


app = FastAPI(
    title="Monday.com BI Agent",
    description="AI-powered Business Intelligence Agent for Monday.com boards",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# In-memory session store (keyed by session_id)
sessions: dict[str, bi_agent_module.BIAgent] = {}


# ─────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────

class QueryRequest(BaseModel):
    message: str
    session_id: str | None = None


class SessionResponse(BaseModel):
    session_id: str


class HealthResponse(BaseModel):
    status: str
    monday_configured: bool
    openai_configured: bool
    deals_board_id: str
    work_orders_board_id: str


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main chat UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        monday_configured=bool(os.getenv("MONDAY_API_TOKEN")),
        openai_configured=bool(os.getenv("OPENROUTER_API_KEY")),
        deals_board_id=os.getenv("DEALS_BOARD_ID", "not set"),
        work_orders_board_id=os.getenv("WORK_ORDERS_BOARD_ID", "not set"),
    )


@app.post("/session", response_model=SessionResponse)
async def create_session():
    """Create a new conversation session."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = bi_agent_module.BIAgent()
    return SessionResponse(session_id=session_id)


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Clear a conversation session."""
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "cleared"}


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Stream agent response as Server-Sent Events (SSE).
    Each event is a JSON object with type: thinking | tool_call | tool_result | answer | done
    """
    session_id = request.session_id or str(uuid.uuid4())

    # Get or create agent for this session
    if session_id not in sessions:
        sessions[session_id] = bi_agent_module.BIAgent()

    agent = sessions[session_id]

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in agent.query(request.message):
                data = json.dumps(event, default=str)
                yield f"data: {data}\n\n"
        except Exception as e:
            error_event = json.dumps({
                "type": "error",
                "content": f"Agent error: {str(e)}",
            })
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-ID": session_id,
        },
    )


@app.post("/query")
async def query_sync(request: QueryRequest):
    """
    Non-streaming query endpoint.
    Returns the full response after all tool calls complete.
    """
    session_id = request.session_id or str(uuid.uuid4())

    if session_id not in sessions:
        sessions[session_id] = bi_agent_module.BIAgent()

    agent = sessions[session_id]

    events = []
    answer = ""
    trace = []

    try:
        async for event in agent.query(request.message):
            events.append(event)
            if event["type"] == "answer":
                answer = event["content"]
            elif event["type"] == "done":
                trace = event.get("trace", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "session_id": session_id,
        "answer": answer,
        "trace": trace,
        "events": events,
    }


@app.get("/boards/status")
async def boards_status():
    """Check connectivity to Monday.com boards."""
    import monday_client as mc

    results = {}

    deals_id = os.getenv("DEALS_BOARD_ID", "")
    wo_id = os.getenv("WORK_ORDERS_BOARD_ID", "")

    if deals_id:
        try:
            summary = await mc.get_board_summary(deals_id)
            results["deals_board"] = {
                "status": "connected",
                "name": summary.get("board_name"),
                "total_items": summary.get("total_items"),
                "columns": summary.get("columns"),
            }
        except Exception as e:
            results["deals_board"] = {"status": "error", "error": str(e)}
    else:
        results["deals_board"] = {"status": "not_configured"}

    if wo_id:
        try:
            summary = await mc.get_board_summary(wo_id)
            results["work_orders_board"] = {
                "status": "connected",
                "name": summary.get("board_name"),
                "total_items": summary.get("total_items"),
                "columns": summary.get("columns"),
            }
        except Exception as e:
            results["work_orders_board"] = {"status": "error", "error": str(e)}
    else:
        results["work_orders_board"] = {"status": "not_configured"}

    return results


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run("main:app", host=host, port=port, reload=debug)

# Made with Bob
