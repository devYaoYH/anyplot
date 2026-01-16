"""Unit tests for the MCP server module.

Tests:
- Tool definitions and registration
- get_schema tool
- query_stat tool
- get_histogram tool
- Budget tracking through tools
- Error handling
"""

import numpy as np
import pandas as pd
import pytest

from sanctum_mcp.server import MCPServer, ToolResult


class TestMCPServerSetup:
    """Tests for MCPServer initialization and setup."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for testing."""
        return pd.DataFrame(
            {
                "salary": [40000, 50000, 60000, 70000, 80000],
                "age": [25, 30, 35, 40, 45],
                "department": ["Sales", "Engineering", "HR", "Marketing", "Finance"],
            }
        )

    def test_server_creation(self, sample_df):
        """Server should be created with a DataFrame."""
        server = MCPServer(df=sample_df, session_id="test-session")

        assert server.session.session_id == "test-session"
        assert server.budget_remaining == 10.0  # default budget

    def test_server_with_custom_budget(self, sample_df):
        """Server should respect custom budget."""
        server = MCPServer(df=sample_df, total_budget=5.0)

        assert server.budget_remaining == 5.0

    def test_get_tools_returns_definitions(self, sample_df):
        """get_tools should return tool definitions."""
        server = MCPServer(df=sample_df)
        tools = server.get_tools()

        assert len(tools) == 3
        tool_names = [t["name"] for t in tools]
        assert "get_schema" in tool_names
        assert "query_stat" in tool_names
        assert "get_histogram" in tool_names

    def test_get_column_mapping(self, sample_df):
        """get_column_mapping should return masked to original mapping."""
        server = MCPServer(df=sample_df, salt="test")
        mapping = server.get_column_mapping()

        assert len(mapping) == 3
        assert "salary" in mapping.values()
        assert "age" in mapping.values()
        assert "department" in mapping.values()


class TestGetSchemaTool:
    """Tests for the get_schema tool."""

    @pytest.fixture
    def server(self):
        """Create a server with sample data."""
        df = pd.DataFrame(
            {
                "salary": [50000, 60000],
                "age": [30, 40],
                "name": ["Alice", "Bob"],
            }
        )
        return MCPServer(df=df, salt="test")

    def test_get_schema_returns_columns(self, server):
        """get_schema should return masked column info."""
        result = server.call_tool("get_schema")

        assert result.success
        assert "columns" in result.data
        assert len(result.data["columns"]) == 3

    def test_schema_columns_are_masked(self, server):
        """Column names in schema should be masked."""
        result = server.call_tool("get_schema")

        for col in result.data["columns"]:
            assert col["masked_name"].startswith("col_")
            assert "salary" not in col["masked_name"]
            assert "age" not in col["masked_name"]
            assert "name" not in col["masked_name"]

    def test_schema_includes_dtype(self, server):
        """Schema should include data types."""
        result = server.call_tool("get_schema")

        dtypes = {col["masked_name"]: col["dtype"] for col in result.data["columns"]}
        dtype_values = list(dtypes.values())

        # Should have integer, integer/float, and string types
        assert "integer" in dtype_values or "float" in dtype_values
        assert "string" in dtype_values

    def test_get_schema_no_budget_cost(self, server):
        """get_schema should not consume budget."""
        initial_budget = server.budget_remaining

        server.call_tool("get_schema")

        assert server.budget_remaining == initial_budget


class TestQueryStatTool:
    """Tests for the query_stat tool."""

    @pytest.fixture
    def server(self):
        """Create a server with sample data."""
        df = pd.DataFrame(
            {
                "salary": [40000, 50000, 60000, 70000, 80000],
                "age": [25, 30, 35, 40, 45],
            }
        )
        rng = np.random.default_rng(42)
        return MCPServer(df=df, salt="test", rng=rng)

    def test_query_stat_mean(self, server):
        """query_stat should return mean value."""
        # Get masked column name
        schema_result = server.call_tool("get_schema")
        columns = schema_result.data["columns"]

        # Find salary column (it's an integer type)
        salary_col = None
        for col in columns:
            masked = col["masked_name"]
            original = server.get_column_mapping().get(masked)
            if original == "salary":
                salary_col = masked
                break

        result = server.call_tool(
            "query_stat", {"column": salary_col, "statistic": "mean"}
        )

        assert result.success
        assert "value" in result.data
        assert isinstance(result.data["value"], float)
        assert "budget_remaining" in result.data

    def test_query_stat_consumes_budget(self, server):
        """query_stat should consume budget."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        initial_budget = server.budget_remaining

        server.call_tool("query_stat", {"column": col, "statistic": "mean"})

        assert server.budget_remaining < initial_budget

    def test_query_stat_all_statistics(self, server):
        """All statistic types should work."""
        schema_result = server.call_tool("get_schema")
        salary_col = None
        for col in schema_result.data["columns"]:
            masked = col["masked_name"]
            original = server.get_column_mapping().get(masked)
            if original == "salary":
                salary_col = masked
                break

        for stat in ["mean", "max", "min", "count", "sum"]:
            result = server.call_tool(
                "query_stat", {"column": salary_col, "statistic": stat}
            )
            assert result.success, f"Failed for statistic: {stat}"

    def test_query_stat_missing_column(self, server):
        """Missing column argument should return error."""
        result = server.call_tool("query_stat", {"statistic": "mean"})

        assert not result.success
        assert "column" in result.error.lower()

    def test_query_stat_missing_statistic(self, server):
        """Missing statistic argument should return error."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        result = server.call_tool("query_stat", {"column": col})

        assert not result.success
        assert "statistic" in result.error.lower()

    def test_query_stat_invalid_statistic(self, server):
        """Invalid statistic should return error."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        result = server.call_tool(
            "query_stat", {"column": col, "statistic": "invalid"}
        )

        assert not result.success

    def test_query_stat_unknown_column(self, server):
        """Unknown column should return error."""
        result = server.call_tool(
            "query_stat", {"column": "col_unknown", "statistic": "mean"}
        )

        assert not result.success
        assert "unknown column" in result.error.lower()


class TestGetHistogramTool:
    """Tests for the get_histogram tool."""

    @pytest.fixture
    def server(self):
        """Create a server with sample data."""
        df = pd.DataFrame({"value": list(range(100))})
        rng = np.random.default_rng(42)
        return MCPServer(df=df, salt="test", rng=rng)

    def test_get_histogram_returns_edges_and_counts(self, server):
        """get_histogram should return edges and counts."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        result = server.call_tool("get_histogram", {"column": col, "num_bins": 10})

        assert result.success
        assert "edges" in result.data
        assert "counts" in result.data
        assert len(result.data["edges"]) == 11  # n+1 edges
        assert len(result.data["counts"]) == 10

    def test_get_histogram_consumes_budget(self, server):
        """get_histogram should consume budget."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        initial_budget = server.budget_remaining

        server.call_tool("get_histogram", {"column": col})

        assert server.budget_remaining < initial_budget

    def test_get_histogram_default_bins(self, server):
        """get_histogram should use default 10 bins."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        result = server.call_tool("get_histogram", {"column": col})

        assert len(result.data["counts"]) == 10

    def test_get_histogram_custom_bins(self, server):
        """get_histogram should respect custom bin count."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        result = server.call_tool("get_histogram", {"column": col, "num_bins": 5})

        assert len(result.data["counts"]) == 5

    def test_get_histogram_invalid_bins(self, server):
        """Invalid bin count should return error."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        # Too few bins
        result = server.call_tool("get_histogram", {"column": col, "num_bins": 1})
        assert not result.success

        # Too many bins
        result = server.call_tool("get_histogram", {"column": col, "num_bins": 100})
        assert not result.success

    def test_get_histogram_missing_column(self, server):
        """Missing column should return error."""
        result = server.call_tool("get_histogram", {})

        assert not result.success


class TestBudgetTracking:
    """Tests for budget tracking through tool calls."""

    @pytest.fixture
    def server(self):
        """Create a server with limited budget."""
        df = pd.DataFrame({"value": list(range(10))})
        return MCPServer(df=df, total_budget=3.0, salt="test")

    def test_budget_exhaustion(self, server):
        """Should fail when budget exhausted."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        # Spend budget (3 queries at 1.0 each)
        server.call_tool("query_stat", {"column": col, "statistic": "mean"})
        server.call_tool("query_stat", {"column": col, "statistic": "max"})
        server.call_tool("query_stat", {"column": col, "statistic": "min"})

        # Next query should fail
        result = server.call_tool(
            "query_stat", {"column": col, "statistic": "sum"}
        )

        assert not result.success
        assert "budget" in result.error.lower()

    def test_budget_remaining_in_response(self, server):
        """Response should include remaining budget."""
        schema_result = server.call_tool("get_schema")
        col = schema_result.data["columns"][0]["masked_name"]

        result = server.call_tool(
            "query_stat", {"column": col, "statistic": "mean"}
        )

        assert "budget_remaining" in result.data
        assert result.data["budget_remaining"] == 2.0


class TestErrorHandling:
    """Tests for error handling in tool calls."""

    @pytest.fixture
    def server(self):
        """Create a server with sample data."""
        df = pd.DataFrame({"value": [1, 2, 3]})
        return MCPServer(df=df, salt="test")

    def test_unknown_tool(self, server):
        """Unknown tool should return error."""
        result = server.call_tool("unknown_tool", {})

        assert not result.success
        assert "unknown tool" in result.error.lower()

    def test_tool_result_success_format(self, server):
        """Successful result should have correct format."""
        result = server.call_tool("get_schema")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data is not None
        assert result.error is None

    def test_tool_result_error_format(self, server):
        """Error result should have correct format."""
        result = server.call_tool("unknown_tool")

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert result.error is not None
