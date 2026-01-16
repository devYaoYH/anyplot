"""Tool definitions for the Sanctum MCP server.

Defines the MCP tools that Claude can use to query data statistics.
"""

from __future__ import annotations

from typing import Any

# Tool definitions following MCP schema format
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_schema",
        "description": "Get the masked schema of the dataset. Returns column names (hashed) and their data types. No privacy cost.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "query_stat",
        "description": "Get a differentially private aggregate statistic for a column. Returns a noisy value that preserves privacy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "The masked column name (e.g., 'col_a1b2c3d4')",
                },
                "statistic": {
                    "type": "string",
                    "enum": ["mean", "max", "min", "count", "sum"],
                    "description": "The aggregate statistic to compute",
                },
            },
            "required": ["column", "statistic"],
        },
    },
    {
        "name": "get_histogram",
        "description": "Get a differentially private histogram for a numeric column. Returns bin edges and noisy counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "The masked column name (e.g., 'col_a1b2c3d4')",
                },
                "num_bins": {
                    "type": "integer",
                    "description": "Number of histogram bins (default: 10)",
                    "default": 10,
                    "minimum": 2,
                    "maximum": 50,
                },
            },
            "required": ["column"],
        },
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return the list of tool definitions for MCP registration."""
    return TOOL_DEFINITIONS
