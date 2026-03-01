"""
Monday.com API Client
Handles all live API calls to monday.com boards.
Every query triggers a fresh API call - no caching.
"""

import httpx
import os
import re
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")
DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID", "")
WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID", "")


def _get_headers() -> dict:
    return {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }


async def run_graphql(query: str, variables: Optional[dict] = None) -> dict:
    """Execute a GraphQL query against the Monday.com API."""
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MONDAY_API_URL,
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()
        result = response.json()

    if "errors" in result:
        raise ValueError(f"Monday.com API error: {result['errors']}")

    return result.get("data", {})


async def get_board_items(board_id: str, limit: int = 500) -> list[dict]:
    """
    Fetch all items from a monday.com board with their column values.
    Live API call - no caching.
    """
    query = """
    query GetBoardItems($boardId: ID!, $limit: Int!) {
      boards(ids: [$boardId]) {
        id
        name
        columns {
          id
          title
          type
        }
        items_page(limit: $limit) {
          cursor
          items {
            id
            name
            column_values {
              id
              text
              value
              type
            }
          }
        }
      }
    }
    """
    variables = {"boardId": board_id, "limit": limit}
    data = await run_graphql(query, variables)
    boards = data.get("boards", [])
    if not boards:
        return []
    board = boards[0]
    # Build column id -> title map from board metadata
    col_map = {c["id"]: c["title"] for c in board.get("columns", [])}
    items = board.get("items_page", {}).get("items", [])
    return [_normalize_item(item, col_map) for item in items]


async def get_board_metadata(board_id: str) -> dict:
    """Fetch board name and column definitions."""
    query = """
    query GetBoardMeta($boardId: ID!) {
      boards(ids: [$boardId]) {
        id
        name
        columns {
          id
          title
          type
        }
      }
    }
    """
    variables = {"boardId": board_id}
    data = await run_graphql(query, variables)
    boards = data.get("boards", [])
    if not boards:
        return {}
    return boards[0]


async def get_deals_data() -> dict:
    """
    Fetch all deals from the Deals board.
    Returns structured data with items and column metadata.
    """
    board_id = DEALS_BOARD_ID
    if not board_id:
        raise ValueError("DEALS_BOARD_ID not configured in environment.")

    query = """
    query GetDeals($boardId: ID!) {
      boards(ids: [$boardId]) {
        id
        name
        columns {
          id
          title
          type
        }
        items_page(limit: 500) {
          items {
            id
            name
            column_values {
              id
              text
              value
              type
            }
          }
        }
      }
    }
    """
    variables = {"boardId": board_id}
    data = await run_graphql(query, variables)
    boards = data.get("boards", [])
    if not boards:
        return {"board_name": "Deals", "columns": [], "items": []}

    board = boards[0]
    col_map = {c["id"]: c["title"] for c in board.get("columns", [])}
    items = board.get("items_page", {}).get("items", [])
    normalized = [_normalize_item(item, col_map) for item in items]

    return {
        "board_name": board.get("name", "Deals"),
        "board_id": board_id,
        "columns": board.get("columns", []),
        "items": normalized,
        "total_count": len(normalized),
    }


async def get_work_orders_data() -> dict:
    """
    Fetch all work orders from the Work Orders board.
    Returns structured data with items and column metadata.
    """
    board_id = WORK_ORDERS_BOARD_ID
    if not board_id:
        raise ValueError("WORK_ORDERS_BOARD_ID not configured in environment.")

    query = """
    query GetWorkOrders($boardId: ID!) {
      boards(ids: [$boardId]) {
        id
        name
        columns {
          id
          title
          type
        }
        items_page(limit: 500) {
          items {
            id
            name
            column_values {
              id
              text
              value
              type
            }
          }
        }
      }
    }
    """
    variables = {"boardId": board_id}
    data = await run_graphql(query, variables)
    boards = data.get("boards", [])
    if not boards:
        return {"board_name": "Work Orders", "columns": [], "items": []}

    board = boards[0]
    col_map = {c["id"]: c["title"] for c in board.get("columns", [])}
    items = board.get("items_page", {}).get("items", [])
    normalized = [_normalize_item(item, col_map) for item in items]

    return {
        "board_name": board.get("name", "Work Orders"),
        "board_id": board_id,
        "columns": board.get("columns", []),
        "items": normalized,
        "total_count": len(normalized),
    }


async def search_board_items(board_id: str, column_id: str, search_value: str) -> list[dict]:
    """Search items in a board by column value."""
    query = """
    query SearchItems($boardId: ID!, $columnId: String!, $columnValue: String!) {
      items_by_column_values(
        board_id: $boardId,
        column_id: $columnId,
        column_value: $columnValue,
        limit: 200
      ) {
        id
        name
        column_values {
          id
          text
          value
          type
        }
      }
    }
    """
    variables = {
        "boardId": board_id,
        "columnId": column_id,
        "columnValue": search_value,
    }
    data = await run_graphql(query, variables)
    items = data.get("items_by_column_values", [])
    # No board columns metadata available here; col_id used as fallback key
    return [_normalize_item(item) for item in items]


def _normalize_item(item: dict, col_map: dict | None = None) -> dict:
    """
    Normalize a monday.com item into a flat dictionary.
    Handles missing/null values gracefully.

    col_map: optional dict mapping column id -> column title (from board metadata).
             In API v2024-01, ColumnValue no longer exposes a 'title' field,
             so we resolve titles via this map; falls back to the column id.
    """
    if col_map is None:
        col_map = {}

    normalized = {
        "id": item.get("id", ""),
        "name": _clean_text(item.get("name", "")),
    }

    for col in item.get("column_values", []):
        col_id = col.get("id", "unknown")
        # Resolve human-readable title from board metadata; fall back to col id
        col_title = _clean_column_title(col_map.get(col_id, col_id))
        raw_text = col.get("text", "") or ""
        raw_value = col.get("value", "") or ""

        # Normalize the value
        cleaned = _normalize_value(raw_text, raw_value, col.get("type", ""))
        normalized[col_title] = cleaned

    return normalized


def _clean_text(text: str) -> str:
    """Clean and normalize text values."""
    if not text:
        return ""
    return str(text).strip()


def _clean_column_title(title: str) -> str:
    """Convert column title to a clean key."""
    return title.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_value(text: str, value: str, col_type: str) -> Any:
    """
    Normalize column values handling messy data:
    - Currency: strip symbols, convert to float
    - Dates: standardize format
    - Status/dropdown: clean text
    - Numbers: parse safely
    """
    if not text and not value:
        return None

    raw = text.strip() if text else ""

    # Currency normalization
    if col_type in ("numeric", "currency") or _looks_like_currency(raw):
        return _parse_number(raw)

    # Date normalization
    if col_type == "date":
        return _normalize_date(raw)

    # Percentage
    if raw.endswith("%"):
        try:
            return float(raw.rstrip("%")) / 100
        except ValueError:
            return raw

    # Try numeric
    if col_type == "numeric":
        return _parse_number(raw)

    return raw if raw else None


def _looks_like_currency(text: str) -> bool:
    """Detect currency-like strings."""
    return bool(re.match(r"^[\$€£₹]?[\d,]+\.?\d*[KkMmBb]?$", text.replace(" ", "")))


def _parse_number(text: str) -> Any:
    """Parse number from messy string like '$1,234.56' or '1.2M'."""
    if not text:
        return None
    cleaned = re.sub(r"[\$€£₹,\s]", "", str(text))
    # Handle K/M/B suffixes
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if cleaned and cleaned[-1].lower() in multipliers:
        try:
            return float(cleaned[:-1]) * multipliers[cleaned[-1].lower()]
        except ValueError:
            pass
    try:
        return float(cleaned)
    except ValueError:
        return text  # Return original if can't parse


def _normalize_date(text: str) -> str:
    """Normalize date strings to ISO format where possible."""
    if not text:
        return ""
    # Already ISO-like
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text
    # Try common formats
    from datetime import datetime
    formats = ["%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y", "%d-%m-%Y", "%m-%d-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text  # Return as-is if can't parse


async def get_board_summary(board_id: str) -> dict:
    """Get a quick summary of a board (count, column names)."""
    meta = await get_board_metadata(board_id)
    items = await get_board_items(board_id, limit=500)
    return {
        "board_name": meta.get("name", ""),
        "total_items": len(items),
        "columns": [c["title"] for c in meta.get("columns", [])],
    }

# Made with Bob
