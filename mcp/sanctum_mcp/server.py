"""MCP Server implementation for Sanctum.

This module implements the Model Context Protocol server that exposes
privacy-preserving data analysis tools to the Claude agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from .budget import BudgetExhaustedError, PrivacyBudget
from .privacy import (
    MaskedColumn,
    SchemaMapper,
    extract_masked_schema,
    get_histogram,
    query_aggregate,
)
from .tools import get_tool_definitions


@dataclass
class MCPSession:
    """Represents a single MCP session with data and budget tracking."""

    session_id: str
    df: pd.DataFrame
    budget: PrivacyBudget = field(default_factory=lambda: PrivacyBudget(total_budget=10.0))
    _schema: dict[str, MaskedColumn] | None = field(default=None, repr=False)
    _mapper: SchemaMapper | None = field(default=None, repr=False)
    _salt: str | None = field(default=None, repr=False)
    _rng: np.random.Generator = field(default_factory=np.random.default_rng, repr=False)

    def __post_init__(self):
        """Initialize schema and mapper after dataclass creation."""
        if self._schema is None:
            self._schema, self._mapper = extract_masked_schema(self.df, salt=self._salt)

    @property
    def schema(self) -> dict[str, MaskedColumn]:
        """Get the masked schema."""
        if self._schema is None:
            self._schema, self._mapper = extract_masked_schema(self.df, salt=self._salt)
        return self._schema

    @property
    def mapper(self) -> SchemaMapper:
        """Get the schema mapper."""
        if self._mapper is None:
            self._schema, self._mapper = extract_masked_schema(self.df, salt=self._salt)
        return self._mapper

    def get_original_column(self, masked_name: str) -> str | None:
        """Get original column name from masked name."""
        return self.mapper.get_original(masked_name)


class MCPError(Exception):
    """Base exception for MCP errors."""

    pass


class ToolNotFoundError(MCPError):
    """Raised when a requested tool is not found."""

    pass


class InvalidInputError(MCPError):
    """Raised when tool input is invalid."""

    pass


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class MCPServer:
    """MCP Server that handles tool requests for a session.

    This server maintains session state and provides privacy-preserving
    data analysis tools through the MCP protocol.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        session_id: str = "default",
        total_budget: float = 10.0,
        salt: str | None = None,
        rng: np.random.Generator | None = None,
    ):
        """Initialize the MCP server with a DataFrame.

        Args:
            df: The DataFrame to analyze
            session_id: Unique session identifier
            total_budget: Total privacy budget for the session
            salt: Optional salt for deterministic column hashing (for testing)
            rng: Optional random generator for reproducibility (for testing)
        """
        self._session = MCPSession(
            session_id=session_id,
            df=df,
            budget=PrivacyBudget(total_budget=total_budget),
            _salt=salt,
            _rng=rng or np.random.default_rng(),
        )

    @property
    def session(self) -> MCPSession:
        """Get the current session."""
        return self._session

    @property
    def budget_remaining(self) -> float:
        """Get remaining privacy budget."""
        return self._session.budget.remaining

    def get_tools(self) -> list[dict[str, Any]]:
        """Return available tool definitions."""
        return get_tool_definitions()

    def get_column_mapping(self) -> dict[str, str]:
        """Get mapping from masked names to original names.

        This is used by the sandbox to map column names back.
        """
        return self._session.mapper.get_reverse_mapping()

    def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> ToolResult:
        """Execute a tool and return the result.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            ToolResult with success status and data or error
        """
        arguments = arguments or {}

        try:
            if name == "get_schema":
                return self._handle_get_schema()
            elif name == "query_stat":
                return self._handle_query_stat(arguments)
            elif name == "get_histogram":
                return self._handle_get_histogram(arguments)
            else:
                raise ToolNotFoundError(f"Unknown tool: {name}")
        except BudgetExhaustedError as e:
            return ToolResult(success=False, error=str(e))
        except (ToolNotFoundError, InvalidInputError) as e:
            return ToolResult(success=False, error=str(e))
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"Internal error: {str(e)}")

    def _handle_get_schema(self) -> ToolResult:
        """Handle get_schema tool request."""
        columns = [
            {"masked_name": col.masked_name, "dtype": col.dtype}
            for col in self._session.schema.values()
        ]
        return ToolResult(
            success=True,
            data={"columns": columns},
        )

    def _handle_query_stat(self, arguments: dict[str, Any]) -> ToolResult:
        """Handle query_stat tool request."""
        column = arguments.get("column")
        statistic = arguments.get("statistic")

        if not column:
            raise InvalidInputError("Missing required argument: column")
        if not statistic:
            raise InvalidInputError("Missing required argument: statistic")

        valid_stats = ["mean", "max", "min", "count", "sum"]
        if statistic not in valid_stats:
            raise InvalidInputError(f"Invalid statistic. Must be one of: {valid_stats}")

        # Get original column name
        original_col = self._session.get_original_column(column)
        if original_col is None:
            raise InvalidInputError(f"Unknown column: {column}")

        # Check and spend budget
        cost = self._session.budget.get_cost("query_stat")
        self._session.budget.spend(cost)

        # Compute noisy statistic
        value = query_aggregate(
            self._session.df,
            original_col,
            statistic,  # type: ignore
            epsilon=cost,
            rng=self._session._rng,
        )

        return ToolResult(
            success=True,
            data={
                "value": value,
                "budget_remaining": self._session.budget.remaining,
            },
        )

    def _handle_get_histogram(self, arguments: dict[str, Any]) -> ToolResult:
        """Handle get_histogram tool request."""
        column = arguments.get("column")
        num_bins = arguments.get("num_bins", 10)

        if not column:
            raise InvalidInputError("Missing required argument: column")

        if not isinstance(num_bins, int) or num_bins < 2 or num_bins > 50:
            raise InvalidInputError("num_bins must be an integer between 2 and 50")

        # Get original column name
        original_col = self._session.get_original_column(column)
        if original_col is None:
            raise InvalidInputError(f"Unknown column: {column}")

        # Check and spend budget
        cost = self._session.budget.get_cost("get_histogram", num_bins=num_bins)
        self._session.budget.spend(cost)

        # Compute noisy histogram
        result = get_histogram(
            self._session.df,
            original_col,
            num_bins=num_bins,
            epsilon=cost,
            rng=self._session._rng,
        )

        return ToolResult(
            success=True,
            data={
                "edges": result["edges"],
                "counts": result["counts"],
                "budget_remaining": self._session.budget.remaining,
            },
        )
