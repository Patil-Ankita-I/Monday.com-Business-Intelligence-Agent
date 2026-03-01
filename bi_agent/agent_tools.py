"""
Agent Tools - MCP-style tool definitions for the BI Agent.
Each tool maps to a live Monday.com API call.
Tools are passed to the LLM as function definitions.
"""

from typing import Any, Optional
import json
import monday_client as mc

# ─────────────────────────────────────────────
# Tool Definitions (OpenAI function-calling format)
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_deals",
            "description": (
                "Fetch all deals from the Monday.com Deals board. "
                "Returns deal name, stage, sector/industry, value, close date, owner, status, and other fields. "
                "Use this for pipeline analysis, revenue forecasting, sector performance, deal health queries."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_orders",
            "description": (
                "Fetch all work orders from the Monday.com Work Orders board. "
                "Returns work order details including client, status, assigned team, dates, value, and completion. "
                "Use this for operational queries, delivery status, team workload, and project tracking."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deals_summary",
            "description": (
                "Get a high-level summary of the Deals board: total count, column names, board metadata. "
                "Use this for quick overviews before diving into detailed analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_orders_summary",
            "description": (
                "Get a high-level summary of the Work Orders board: total count, column names, board metadata. "
                "Use this for quick overviews before diving into detailed analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_deals",
            "description": (
                "Filter deals from the Deals board by specific criteria. "
                "Supports filtering by sector, stage, owner, date range, value range, or status. "
                "Use this for targeted queries like 'energy sector deals this quarter'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": "Filter by industry/sector (e.g., 'energy', 'tech', 'healthcare'). Case-insensitive partial match.",
                    },
                    "stage": {
                        "type": "string",
                        "description": "Filter by deal stage (e.g., 'proposal', 'negotiation', 'closed won', 'qualified'). Case-insensitive partial match.",
                    },
                    "owner": {
                        "type": "string",
                        "description": "Filter by deal owner/sales rep name. Case-insensitive partial match.",
                    },
                    "min_value": {
                        "type": "number",
                        "description": "Minimum deal value in dollars.",
                    },
                    "max_value": {
                        "type": "number",
                        "description": "Maximum deal value in dollars.",
                    },
                    "close_date_from": {
                        "type": "string",
                        "description": "Filter deals closing on or after this date (YYYY-MM-DD).",
                    },
                    "close_date_to": {
                        "type": "string",
                        "description": "Filter deals closing on or before this date (YYYY-MM-DD).",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by deal status (e.g., 'active', 'won', 'lost', 'stalled').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_work_orders",
            "description": (
                "Filter work orders from the Work Orders board by specific criteria. "
                "Supports filtering by client, status, assigned team, date range, or value range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client": {
                        "type": "string",
                        "description": "Filter by client name. Case-insensitive partial match.",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by work order status (e.g., 'in progress', 'completed', 'pending', 'overdue').",
                    },
                    "assigned_to": {
                        "type": "string",
                        "description": "Filter by assigned team or person. Case-insensitive partial match.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Filter work orders starting on or after this date (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Filter work orders starting on or before this date (YYYY-MM-DD).",
                    },
                    "min_value": {
                        "type": "number",
                        "description": "Minimum work order value.",
                    },
                    "max_value": {
                        "type": "number",
                        "description": "Maximum work order value.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_deals_by_field",
            "description": (
                "Aggregate and group deals by a specific field to get counts, totals, and averages. "
                "Use this for questions like 'breakdown by sector', 'pipeline by stage', 'revenue by owner'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": {
                        "type": "string",
                        "description": "The field/column to group by (e.g., 'sector', 'stage', 'owner', 'status').",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["count", "sum_value", "avg_value", "all"],
                        "description": "The metric to compute per group. 'all' returns count, sum, and average.",
                    },
                },
                "required": ["group_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_work_orders_by_field",
            "description": (
                "Aggregate and group work orders by a specific field. "
                "Use this for questions like 'work orders by status', 'workload by team', 'orders by client'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": {
                        "type": "string",
                        "description": "The field/column to group by (e.g., 'status', 'client', 'assigned_to').",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["count", "sum_value", "avg_value", "all"],
                        "description": "The metric to compute per group.",
                    },
                },
                "required": ["group_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cross_board_analysis",
            "description": (
                "Perform analysis that spans both the Deals and Work Orders boards. "
                "Use this for questions about deal-to-delivery conversion, client overlap, "
                "revenue vs operational cost, or any query requiring data from both boards."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "enum": ["client_overlap", "revenue_vs_operations", "full_summary"],
                        "description": "Type of cross-board analysis to perform.",
                    },
                },
                "required": ["analysis_type"],
            },
        },
    },
]


# ─────────────────────────────────────────────
# Tool Execution Functions
# ─────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_args: dict) -> tuple[Any, str]:
    """
    Execute a tool by name with given arguments.
    Returns (result, description_of_action).
    """
    import os
    deals_board_id = os.getenv("DEALS_BOARD_ID", "")
    work_orders_board_id = os.getenv("WORK_ORDERS_BOARD_ID", "")

    if tool_name == "get_deals":
        action_desc = f"📡 Calling Monday.com API → GET board items (Deals board: {deals_board_id})"
        result = await mc.get_deals_data()
        return result, action_desc

    elif tool_name == "get_work_orders":
        action_desc = f"📡 Calling Monday.com API → GET board items (Work Orders board: {work_orders_board_id})"
        result = await mc.get_work_orders_data()
        return result, action_desc

    elif tool_name == "get_deals_summary":
        action_desc = f"📡 Calling Monday.com API → GET board metadata (Deals board: {deals_board_id})"
        result = await mc.get_board_summary(deals_board_id)
        return result, action_desc

    elif tool_name == "get_work_orders_summary":
        action_desc = f"📡 Calling Monday.com API → GET board metadata (Work Orders board: {work_orders_board_id})"
        result = await mc.get_board_summary(work_orders_board_id)
        return result, action_desc

    elif tool_name == "filter_deals":
        action_desc = f"📡 Calling Monday.com API → GET deals + applying filters: {json.dumps(tool_args)}"
        deals_data = await mc.get_deals_data()
        items = deals_data.get("items", [])
        filtered = _apply_filters(items, tool_args, board_type="deals")
        result = {
            "board_name": deals_data.get("board_name"),
            "filters_applied": tool_args,
            "total_before_filter": len(items),
            "total_after_filter": len(filtered),
            "items": filtered,
            "data_quality_notes": _get_data_quality_notes(items, filtered),
        }
        return result, action_desc

    elif tool_name == "filter_work_orders":
        action_desc = f"📡 Calling Monday.com API → GET work orders + applying filters: {json.dumps(tool_args)}"
        wo_data = await mc.get_work_orders_data()
        items = wo_data.get("items", [])
        filtered = _apply_filters(items, tool_args, board_type="work_orders")
        result = {
            "board_name": wo_data.get("board_name"),
            "filters_applied": tool_args,
            "total_before_filter": len(items),
            "total_after_filter": len(filtered),
            "items": filtered,
            "data_quality_notes": _get_data_quality_notes(items, filtered),
        }
        return result, action_desc

    elif tool_name == "aggregate_deals_by_field":
        group_by = tool_args.get("group_by", "stage")
        metric = tool_args.get("metric", "all")
        action_desc = f"📡 Calling Monday.com API → GET deals + aggregating by '{group_by}' (metric: {metric})"
        deals_data = await mc.get_deals_data()
        items = deals_data.get("items", [])
        result = _aggregate_items(items, group_by, metric)
        result["board_name"] = deals_data.get("board_name")
        result["total_items"] = len(items)
        return result, action_desc

    elif tool_name == "aggregate_work_orders_by_field":
        group_by = tool_args.get("group_by", "status")
        metric = tool_args.get("metric", "all")
        action_desc = f"📡 Calling Monday.com API → GET work orders + aggregating by '{group_by}' (metric: {metric})"
        wo_data = await mc.get_work_orders_data()
        items = wo_data.get("items", [])
        result = _aggregate_items(items, group_by, metric)
        result["board_name"] = wo_data.get("board_name")
        result["total_items"] = len(items)
        return result, action_desc

    elif tool_name == "cross_board_analysis":
        analysis_type = tool_args.get("analysis_type", "full_summary")
        action_desc = f"📡 Calling Monday.com API → GET both boards for cross-board analysis: {analysis_type}"
        deals_data = await mc.get_deals_data()
        wo_data = await mc.get_work_orders_data()
        result = _cross_board_analysis(deals_data, wo_data, analysis_type)
        return result, action_desc

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


# ─────────────────────────────────────────────
# Data Processing Helpers
# ─────────────────────────────────────────────

def _find_field(item: dict, candidates: list[str]) -> Any:
    """Find a field value by trying multiple candidate key names."""
    for key in item:
        for candidate in candidates:
            if candidate.lower() in key.lower():
                val = item[key]
                if val is not None and val != "":
                    return val
    return None


def _apply_filters(items: list[dict], filters: dict, board_type: str) -> list[dict]:
    """Apply filter criteria to a list of normalized items."""
    result = items

    # Sector filter (deals)
    if filters.get("sector"):
        sector_val = filters["sector"].lower()
        result = [
            i for i in result
            if _field_contains(i, ["sector", "industry", "vertical", "segment"], sector_val)
        ]

    # Stage filter (deals)
    if filters.get("stage"):
        stage_val = filters["stage"].lower()
        result = [
            i for i in result
            if _field_contains(i, ["stage", "deal_stage", "pipeline_stage", "status"], stage_val)
        ]

    # Owner filter (deals)
    if filters.get("owner"):
        owner_val = filters["owner"].lower()
        result = [
            i for i in result
            if _field_contains(i, ["owner", "sales_rep", "account_executive", "assigned", "person"], owner_val)
        ]

    # Status filter
    if filters.get("status"):
        status_val = filters["status"].lower()
        result = [
            i for i in result
            if _field_contains(i, ["status", "state", "stage"], status_val)
        ]

    # Client filter (work orders)
    if filters.get("client"):
        client_val = filters["client"].lower()
        result = [
            i for i in result
            if _field_contains(i, ["client", "customer", "company", "account", "name"], client_val)
        ]

    # Assigned to filter (work orders)
    if filters.get("assigned_to"):
        assigned_val = filters["assigned_to"].lower()
        result = [
            i for i in result
            if _field_contains(i, ["assigned", "team", "owner", "person", "engineer"], assigned_val)
        ]

    # Value range filters
    VALUE_FIELDS = ["value", "amount", "deal_value", "revenue", "contract_value"]
    if filters.get("min_value") is not None:
        min_val = float(filters["min_value"])
        result = [
            i for i in result
            if (v := _get_numeric_field(i, VALUE_FIELDS)) is not None and v >= min_val
        ]

    if filters.get("max_value") is not None:
        max_val = float(filters["max_value"])
        result = [
            i for i in result
            if (v := _get_numeric_field(i, VALUE_FIELDS)) is not None and v <= max_val
        ]

    # Date range filters
    if filters.get("close_date_from") or filters.get("date_from"):
        date_from = filters.get("close_date_from") or filters.get("date_from")
        result = [
            i for i in result
            if _date_in_range(i, ["close_date", "closing_date", "expected_close", "date", "start_date"], date_from, None)
        ]

    if filters.get("close_date_to") or filters.get("date_to"):
        date_to = filters.get("close_date_to") or filters.get("date_to")
        result = [
            i for i in result
            if _date_in_range(i, ["close_date", "closing_date", "expected_close", "date", "end_date"], None, date_to)
        ]

    return result


def _field_contains(item: dict, field_candidates: list[str], search_val: str) -> bool:
    """Check if any candidate field in item contains the search value."""
    for key in item:
        for candidate in field_candidates:
            if candidate.lower() in key.lower():
                val = item[key]
                if val and search_val in str(val).lower():
                    return True
    # Also check item name
    if search_val in str(item.get("name", "")).lower():
        return True
    return False


def _get_numeric_field(item: dict, field_candidates: list[str]) -> Optional[float]:
    """Get a numeric field value from an item."""
    for key in item:
        for candidate in field_candidates:
            if candidate.lower() in key.lower():
                val = item[key]
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
    return None


def _date_in_range(item: dict, field_candidates: list[str], date_from: Optional[str], date_to: Optional[str]) -> bool:
    """Check if item's date field falls within range."""
    for key in item:
        for candidate in field_candidates:
            if candidate.lower() in key.lower():
                val = item[key]
                if val:
                    date_str = str(val)[:10]  # Take YYYY-MM-DD part
                    if date_from and date_str < date_from:
                        return False
                    if date_to and date_str > date_to:
                        return False
                    return True
    return True  # If no date field found, include item


def _aggregate_items(items: list[dict], group_by: str, metric: str) -> dict:
    """Aggregate items by a field, computing count/sum/avg."""
    from collections import defaultdict

    groups: dict[str, list] = defaultdict(list)

    for item in items:
        # Find the group_by field value
        group_val = None
        for key in item:
            if group_by.lower() in key.lower():
                group_val = item[key]
                break

        if group_val is None or group_val == "":
            group_val = "(not set)"
        else:
            group_val = str(group_val).strip()
            if not group_val:
                group_val = "(not set)"

        groups[group_val].append(item)

    # Compute metrics
    aggregated = {}
    for group_val, group_items in sorted(groups.items()):
        values = []
        for gi in group_items:
            num = _get_numeric_field(gi, ["value", "amount", "deal_value", "revenue", "contract_value", "total"])
            if num is not None:
                values.append(num)

        entry: dict[str, Any] = {"count": len(group_items)}
        if values:
            entry["total_value"] = round(sum(values), 2)
            entry["avg_value"] = round(sum(values) / len(values), 2)
            entry["items_with_value"] = len(values)
        else:
            entry["total_value"] = None
            entry["avg_value"] = None
            entry["items_with_value"] = 0

        aggregated[group_val] = entry

    return {
        "group_by": group_by,
        "metric": metric,
        "groups": aggregated,
        "null_count": groups.get("(not set)", []),
    }


def _cross_board_analysis(deals_data: dict, wo_data: dict, analysis_type: str) -> dict:
    """Perform cross-board analysis."""
    deals = deals_data.get("items", [])
    work_orders = wo_data.get("items", [])

    if analysis_type == "full_summary":
        # Compute totals for both boards
        deal_values = [
            _get_numeric_field(d, ["value", "amount", "deal_value", "revenue"])
            for d in deals
        ]
        deal_values = [v for v in deal_values if v is not None]

        wo_values = [
            _get_numeric_field(w, ["value", "amount", "contract_value", "total"])
            for w in work_orders
        ]
        wo_values = [v for v in wo_values if v is not None]

        return {
            "analysis_type": "full_summary",
            "deals": {
                "total_count": len(deals),
                "total_pipeline_value": round(sum(deal_values), 2) if deal_values else None,
                "avg_deal_value": round(sum(deal_values) / len(deal_values), 2) if deal_values else None,
                "deals_with_value": len(deal_values),
            },
            "work_orders": {
                "total_count": len(work_orders),
                "total_value": round(sum(wo_values), 2) if wo_values else None,
                "avg_value": round(sum(wo_values) / len(wo_values), 2) if wo_values else None,
                "orders_with_value": len(wo_values),
            },
        }

    elif analysis_type == "client_overlap":
        # Find clients appearing in both boards
        deal_clients = set()
        for d in deals:
            client = _find_field(d, ["client", "company", "account", "customer"])
            if client:
                deal_clients.add(str(client).lower().strip())

        wo_clients = set()
        for w in work_orders:
            client = _find_field(w, ["client", "company", "account", "customer"])
            if client:
                wo_clients.add(str(client).lower().strip())

        overlap = deal_clients & wo_clients
        return {
            "analysis_type": "client_overlap",
            "deals_unique_clients": len(deal_clients),
            "work_orders_unique_clients": len(wo_clients),
            "overlapping_clients": len(overlap),
            "overlap_list": sorted(list(overlap))[:20],  # Top 20
        }

    elif analysis_type == "revenue_vs_operations":
        deal_values = [
            _get_numeric_field(d, ["value", "amount", "deal_value", "revenue"])
            for d in deals
        ]
        deal_values = [v for v in deal_values if v is not None]

        wo_values = [
            _get_numeric_field(w, ["value", "amount", "contract_value", "total"])
            for w in work_orders
        ]
        wo_values = [v for v in wo_values if v is not None]

        total_pipeline = sum(deal_values) if deal_values else 0
        total_ops = sum(wo_values) if wo_values else 0

        return {
            "analysis_type": "revenue_vs_operations",
            "total_pipeline_value": round(total_pipeline, 2),
            "total_operations_value": round(total_ops, 2),
            "ratio": round(total_pipeline / total_ops, 2) if total_ops > 0 else None,
            "note": "Pipeline value represents potential revenue; operations value represents committed work.",
        }

    return {"error": f"Unknown analysis type: {analysis_type}"}


def _get_data_quality_notes(all_items: list[dict], filtered_items: list[dict]) -> list[str]:
    """Generate data quality notes about missing/null values."""
    notes = []
    if not all_items:
        return ["⚠️ No data found in board."]

    # Check for null values in key fields
    key_fields = ["value", "amount", "deal_value", "stage", "sector", "status", "close_date"]
    for field in key_fields:
        null_count = sum(
            1 for item in filtered_items
            if not any(
                item.get(k) for k in item
                if field.lower() in k.lower()
            )
        )
        if null_count > 0 and filtered_items:
            pct = round(null_count / len(filtered_items) * 100)
            notes.append(f"⚠️ {null_count} items ({pct}%) have missing '{field}' data.")

    return notes


