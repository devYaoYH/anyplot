"""Unit tests for the Agent module.

Tests:
- Prompt augmentation with schema context
- AgentResult and AgentConfig dataclasses
"""

import pytest

from src.agent import Agent, AgentConfig, AgentResult


class TestAgentConfig:
    """Tests for AgentConfig defaults and customization."""

    def test_agent_config_defaults(self):
        """AgentConfig should have sensible defaults."""
        config = AgentConfig()

        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.temperature == 0.0
        assert config.max_tool_calls == 10
        assert config.max_execution_retries == 3

    def test_agent_config_custom_values(self):
        """AgentConfig should accept custom values."""
        config = AgentConfig(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            temperature=0.5,
            max_tool_calls=5,
            max_execution_retries=5,
        )

        assert config.model == "claude-3-opus-20240229"
        assert config.max_tokens == 2048
        assert config.temperature == 0.5
        assert config.max_tool_calls == 5
        assert config.max_execution_retries == 5


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_agent_result_success(self):
        """AgentResult should correctly represent success."""
        result = AgentResult(
            success=True,
            code="plt.bar([1,2,3], [4,5,6])",
            tool_calls=[{"tool": "get_schema", "input": {}}],
            messages=[{"role": "user", "content": "test"}],
        )

        assert result.success is True
        assert result.code == "plt.bar([1,2,3], [4,5,6])"
        assert result.error is None
        assert len(result.tool_calls) == 1
        assert len(result.messages) == 1

    def test_agent_result_failure(self):
        """AgentResult should correctly represent failure."""
        result = AgentResult(
            success=False,
            error="API error",
            tool_calls=[],
            messages=[],
        )

        assert result.success is False
        assert result.code is None
        assert result.error == "API error"


class TestPromptAugmentation:
    """Tests for prompt augmentation with schema context."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock MCP server with minimal functionality."""
        class MockMCPServer:
            def get_tools(self):
                return [
                    {
                        "name": "get_schema",
                        "description": "Get schema",
                        "input_schema": {"type": "object", "properties": {}},
                    }
                ]
        return MockMCPServer()

    def test_augment_prompt_with_schema_includes_column_mapping(self, mock_mcp_server):
        """Augmented prompt should include column mapping information."""
        agent = Agent(mcp_server=mock_mcp_server, api_key="test-key")

        schema_context = [
            {"original_name": "sales", "masked_name": "col_abc123", "dtype": "float"},
            {"original_name": "region", "masked_name": "col_def456", "dtype": "string"},
        ]

        prompt = "Create a bar chart of sales by region"
        augmented = agent._augment_prompt_with_schema(prompt, schema_context)

        assert "Create a bar chart of sales by region" in augmented
        assert "sales" in augmented
        assert "col_abc123" in augmented
        assert "region" in augmented
        assert "col_def456" in augmented
        assert "float" in augmented
        assert "string" in augmented
        assert "COLUMN MAPPING" in augmented

    def test_augment_prompt_with_empty_schema_returns_original(self, mock_mcp_server):
        """Augmented prompt with empty schema should return original prompt."""
        agent = Agent(mcp_server=mock_mcp_server, api_key="test-key")

        prompt = "Create a simple chart"
        augmented = agent._augment_prompt_with_schema(prompt, None)

        assert augmented == prompt

    def test_augment_prompt_with_empty_list_returns_original(self, mock_mcp_server):
        """Augmented prompt with empty list should return original prompt."""
        agent = Agent(mcp_server=mock_mcp_server, api_key="test-key")

        prompt = "Create a simple chart"
        augmented = agent._augment_prompt_with_schema(prompt, [])

        assert augmented == prompt

    def test_augment_prompt_preserves_original_prompt(self, mock_mcp_server):
        """Augmentation should preserve the original prompt text."""
        agent = Agent(mcp_server=mock_mcp_server, api_key="test-key")

        schema_context = [
            {"original_name": "value", "masked_name": "col_xyz789", "dtype": "integer"},
        ]

        original_prompt = "Show me a histogram of the value distribution"
        augmented = agent._augment_prompt_with_schema(original_prompt, schema_context)

        assert original_prompt in augmented

    def test_augment_prompt_formats_all_columns(self, mock_mcp_server):
        """Augmentation should include all columns from schema context."""
        agent = Agent(mcp_server=mock_mcp_server, api_key="test-key")

        schema_context = [
            {"original_name": "col1", "masked_name": "col_111", "dtype": "integer"},
            {"original_name": "col2", "masked_name": "col_222", "dtype": "float"},
            {"original_name": "col3", "masked_name": "col_333", "dtype": "string"},
            {"original_name": "col4", "masked_name": "col_444", "dtype": "datetime"},
        ]

        prompt = "Analyze the data"
        augmented = agent._augment_prompt_with_schema(prompt, schema_context)

        for col in schema_context:
            assert col["original_name"] in augmented
            assert col["masked_name"] in augmented
            assert col["dtype"] in augmented
