"""
BI Agent Core Logic
Orchestrates LLM reasoning with Monday.com tool calls.
Implements an agentic loop: think -> call tool -> observe -> respond.
Uses OpenRouter as the LLM provider (OpenAI-compatible API).
"""

import asyncio
import json
import os
from typing import Any, AsyncGenerator, cast
from openai import AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionToolParam, ChatCompletionMessageToolCall
from dotenv import load_dotenv
import agent_tools

MAX_RETRIES = 4  # retry up to 4 times on 429
RETRY_BASE_DELAY = 5  # seconds (doubles each retry: 5, 10, 20, 40)

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen/qwen3-vl-30b-a3b-thinking")
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

APP_SITE_URL = os.getenv("APP_SITE_URL", "http://localhost:8000")
APP_SITE_NAME = os.getenv("APP_SITE_NAME", "Monday.com BI Agent")

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    default_headers={
        "HTTP-Referer": APP_SITE_URL,
        "X-Title": APP_SITE_NAME,
    },
)

SYSTEM_PROMPT = """You are a Business Intelligence Agent for a company using Monday.com to track Deals and Work Orders.

Your role is to answer founder-level business questions with accuracy, clarity, and actionable insights.

## Your Capabilities
You have access to live Monday.com data through these tools:
- **get_deals** / **get_deals_summary**: Fetch all deals or a summary
- **get_work_orders** / **get_work_orders_summary**: Fetch all work orders or a summary
- **filter_deals**: Filter deals by sector, stage, owner, value range, date range, status
- **filter_work_orders**: Filter work orders by client, status, assigned team, date range
- **aggregate_deals_by_field**: Group and aggregate deals (e.g., by sector, stage, owner)
- **aggregate_work_orders_by_field**: Group and aggregate work orders
- **cross_board_analysis**: Analyze data spanning both boards

## Behavior Guidelines
1. **Always use tools** — never guess or fabricate data. Every answer must be backed by a live API call.
2. **Be data-resilient** — handle missing values gracefully. If data is incomplete, say so clearly.
3. **Communicate caveats** — if data quality is poor, mention it (e.g., "Note: 30% of deals have no close date").
4. **Be concise but insightful** — founders want the key numbers + a brief interpretation, not raw dumps.
5. **Ask clarifying questions** when the query is ambiguous (e.g., "Did you mean this quarter by calendar or fiscal year?").
6. **Support follow-up context** — remember the conversation history.

## Response Format
- Lead with the key answer/metric
- Follow with supporting breakdown (use bullet points or a table)
- End with a brief insight or recommendation if relevant
- Flag any data quality issues at the bottom

## Data Quality Handling
- Missing values → report as "N/A" or note the gap
- Inconsistent formats → normalize silently, note if significant
- Partial data → give best estimate with caveat

Today's date context: Use this to interpret "this quarter", "this month", "YTD" etc.
"""


class BIAgent:
    """
    Business Intelligence Agent.
    Manages conversation history and executes the agentic tool-call loop.
    """

    def __init__(self):
        self.conversation_history: list[dict] = []
        self.tool_call_trace: list[dict] = []

    def reset(self):
        """Reset conversation and trace."""
        self.conversation_history = []
        self.tool_call_trace = []

    async def query(self, user_message: str) -> AsyncGenerator[dict, None]:
        """
        Process a user query through the agentic loop.
        Yields events: tool_call, tool_result, thinking, answer_chunk, done.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        date_context = (
            f"Current date: {now.strftime('%Y-%m-%d')} (UTC). "
            f"Current quarter: Q{(now.month - 1) // 3 + 1} {now.year}. "
            f"Current month: {now.strftime('%B %Y')}."
        )
        system_with_date = SYSTEM_PROMPT.replace(
            "Today's date context: Use this to interpret \"this quarter\", \"this month\", \"YTD\" etc.",
            f"Today's date context: {date_context}"
        )

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        messages = [
            {"role": "system", "content": system_with_date},
            *self.conversation_history,
        ]

        # Agentic loop: keep calling tools until LLM produces a final answer
        max_iterations = 8
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Call LLM with retry on 429
            yield {"type": "thinking", "content": f"🤔 Reasoning... (step {iteration})"}

            response = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=messages,
                        tools=cast(list[ChatCompletionToolParam], agent_tools.TOOLS),
                        tool_choice="auto",
                        temperature=0.1,
                        max_tokens=4096,
                    )
                    print(f"LLM response: {response}")
                    break  # success
                except RateLimitError as e:
                    print(e)
                    if attempt < MAX_RETRIES - 1:
                        wait = RETRY_BASE_DELAY * (2 ** attempt)
                        yield {
                            "type": "thinking",
                            "content": f"⏳ Rate limited by provider. Retrying in {wait}s... (attempt {attempt + 2}/{MAX_RETRIES})",
                        }
                        await asyncio.sleep(wait)
                    else:
                        raise RuntimeError(
                            f"The model '{OPENAI_MODEL}' is temporarily rate-limited by the upstream provider. "
                            f"Please wait a minute and try again, or switch to a different model in your .env file."
                        ) from e

            if response is None:
                raise RuntimeError("No response received from LLM after retries.")

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # Add assistant message to conversation
            messages.append(message.model_dump(exclude_unset=False))

            # If no tool calls → final answer
            if finish_reason == "stop" or not message.tool_calls:
                final_answer = message.content or ""
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_answer,
                })
                yield {"type": "answer", "content": final_answer}
                yield {"type": "done", "trace": self.tool_call_trace}
                return

            # Process tool calls
            for tool_call in message.tool_calls:
                tc = cast(ChatCompletionMessageToolCall, tool_call)
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                # Emit tool call event (visible trace)
                trace_entry = {
                    "tool": tool_name,
                    "args": tool_args,
                    "call_id": tool_call.id,
                    "status": "calling",
                }
                yield {"type": "tool_call", "data": trace_entry}

                # Execute the tool
                try:
                    result, action_desc = await agent_tools.execute_tool(tool_name, tool_args)
                    trace_entry["status"] = "success"
                    trace_entry["action_description"] = action_desc
                    trace_entry["result_summary"] = _summarize_result(result)

                    yield {
                        "type": "tool_result",
                        "data": {
                            "tool": tool_name,
                            "action": action_desc,
                            "summary": trace_entry["result_summary"],
                            "status": "success",
                        },
                    }

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str),
                    })

                except Exception as e:
                    error_msg = str(e)
                    trace_entry["status"] = "error"
                    trace_entry["error"] = error_msg

                    yield {
                        "type": "tool_result",
                        "data": {
                            "tool": tool_name,
                            "status": "error",
                            "error": error_msg,
                        },
                    }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": error_msg}),
                    })

                self.tool_call_trace.append(trace_entry)

        # Max iterations reached
        yield {
            "type": "answer",
            "content": "I've reached the maximum number of reasoning steps. Please try rephrasing your question.",
        }
        yield {"type": "done", "trace": self.tool_call_trace}


def _summarize_result(result: Any) -> str:
    """Create a brief human-readable summary of a tool result."""
    if isinstance(result, dict):
        if "items" in result:
            count = len(result.get("items", []))
            board = result.get("board_name", "board")
            return f"Retrieved {count} items from {board}"
        if "groups" in result:
            groups = result.get("groups", {})
            group_by = result.get("group_by", "field")
            return f"Aggregated by '{group_by}': {len(groups)} groups found"
        if "total_count" in result:
            return f"Board has {result['total_count']} total items"
        if "analysis_type" in result:
            return f"Cross-board analysis ({result['analysis_type']}) complete"
        if "total_items" in result:
            return f"Summary: {result['total_items']} items, columns: {', '.join(result.get('columns', [])[:5])}"
    return str(result)[:200]

# Made with Bob
