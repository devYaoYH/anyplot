"""Integration tests for the FastAPI endpoints.

Tests the API endpoints with mocked Claude SDK responses.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestServerStartup:
    """Tests that the server can start with all dependencies."""

    def test_server_starts_and_responds_to_health(self):
        """Server should start without import errors and respond to health check.

        This test verifies that all dependencies (including altair) are properly
        installed and importable when the server starts.
        """
        # Creating TestClient imports the app module and all its dependencies
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_all_sandbox_dependencies_importable(self):
        """All packages allowed in sandbox should be importable."""
        from src.sandbox import Sandbox

        # These imports should not fail if dependencies are correctly installed
        import pandas
        import numpy
        import matplotlib
        import altair

        # Verify altair can create a basic chart spec
        import pandas as pd
        df = pd.DataFrame({'x': [1, 2], 'y': [3, 4]})
        chart = altair.Chart(df).mark_point().encode(x='x', y='y')
        spec = chart.to_dict()
        assert '$schema' in spec


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_data():
    """Sample data for visualization requests."""
    return [
        {"salary": 40000, "age": 25},
        {"salary": 50000, "age": 30},
        {"salary": 60000, "age": 35},
        {"salary": 70000, "age": 40},
        {"salary": 80000, "age": 45},
    ]


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "sk-ant-test-key-12345"


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestVisualizeEndpoint:
    """Tests for the /visualize endpoint."""

    def test_visualize_with_mocked_agent(self, client, sample_data, mock_api_key):
        """Visualize endpoint should return image when agent returns valid code."""
        # Mock code that will be "generated" by the agent
        mock_code = """
plt.figure(figsize=(8, 6))
plt.bar(['25', '30', '35', '40', '45'], [40000, 50000, 60000, 70000, 80000])
plt.xlabel('Age')
plt.ylabel('Salary')
plt.title('Salary by Age')
"""

        # Create mock response
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text=f"```python\n{mock_code}\n```")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Create a bar chart of salaries by age",
                    "api_key": mock_api_key,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "image" in data
        assert "code" in data

        # Verify image is valid base64 PNG
        image_bytes = base64.b64decode(data["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_visualize_with_tool_calls(self, client, sample_data, mock_api_key):
        """Visualize should handle tool calls correctly."""
        # First response requests get_schema tool
        schema_response = MagicMock()
        schema_response.stop_reason = "tool_use"
        schema_response.content = [
            MagicMock(
                type="tool_use",
                id="tool_1",
                name="get_schema",
                input={},
            )
        ]

        # Second response generates code
        mock_code = """
plt.figure()
plt.plot(df['salary'])
plt.title('Salary Distribution')
"""
        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [
            MagicMock(type="text", text=f"```python\n{mock_code}\n```")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [schema_response, final_response]
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Plot the salary data",
                    "api_key": mock_api_key,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "image" in data

    def test_visualize_empty_data_returns_error(self, client, mock_api_key):
        """Empty data should return 400 error."""
        response = client.post(
            "/visualize",
            json={
                "data": [],
                "prompt": "Create a chart",
                "api_key": mock_api_key,
            },
        )

        assert response.status_code == 400

    def test_visualize_invalid_code_from_agent(self, client, sample_data, mock_api_key):
        """Invalid code from agent should return error after retries."""
        # Code that uses dangerous imports - agent keeps generating bad code
        mock_code = """
import os
os.system('ls')
"""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text=f"```python\n{mock_code}\n```")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            # Return same bad code for all retry attempts
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Create a chart",
                    "api_key": mock_api_key,
                },
            )

        assert response.status_code == 400
        assert "validation" in response.json()["detail"].lower()

    def test_visualize_no_code_block_returns_error(self, client, sample_data, mock_api_key):
        """Response without code block should return error."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text="I don't know how to help with that.")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Create a chart",
                    "api_key": mock_api_key,
                },
            )

        assert response.status_code == 400
        assert "code" in response.json()["detail"].lower()


class TestColumnMapping:
    """Tests for correct column mapping in visualizations."""

    def test_masked_columns_mapped_correctly(self, client, mock_api_key):
        """Columns should be correctly mapped from masked to original names."""
        data = [
            {"value_x": 1, "value_y": 10},
            {"value_x": 2, "value_y": 20},
            {"value_x": 3, "value_y": 30},
        ]

        # Code that uses original column names
        mock_code = """
plt.figure()
plt.plot(df['value_x'], df['value_y'])
plt.xlabel('X Values')
plt.ylabel('Y Values')
"""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text=f"```python\n{mock_code}\n```")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": data,
                    "prompt": "Plot x vs y",
                    "api_key": mock_api_key,
                },
            )

        assert response.status_code == 200
        # Code should have been executed successfully with column mapping
        resp_data = response.json()
        assert "image" in resp_data

        # Verify it's a valid PNG
        image_bytes = base64.b64decode(resp_data["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


class TestRetryFunctionality:
    """Tests for code refinement and retry on execution errors."""

    def test_retry_on_execution_error_succeeds(self, client, sample_data, mock_api_key):
        """Agent should retry and fix code when execution fails."""
        # First code has a bug (missing figure)
        bad_code = """
# This will fail because 'nonexistent' column doesn't exist
plt.plot(df['nonexistent'])
"""
        # Fixed code that works
        good_code = """
plt.figure()
plt.plot(df['salary'])
plt.title('Salary')
"""
        # First response returns bad code
        first_response = MagicMock()
        first_response.stop_reason = "end_turn"
        first_response.content = [
            MagicMock(type="text", text=f"```python\n{bad_code}\n```")
        ]

        # Second response (after error feedback) returns good code
        second_response = MagicMock()
        second_response.stop_reason = "end_turn"
        second_response.content = [
            MagicMock(type="text", text=f"```python\n{good_code}\n```")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            # First call returns bad code, second call (refinement) returns good code
            mock_client.messages.create.side_effect = [first_response, second_response]
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Plot salary data",
                    "api_key": mock_api_key,
                },
            )

        # Should succeed after retry
        assert response.status_code == 200
        data = response.json()
        assert "image" in data
        # The returned code should be the fixed version
        assert "salary" in data["code"]

    def test_max_retries_exhausted_returns_error(self, client, sample_data, mock_api_key):
        """Should return error after max retries are exhausted."""
        # Code that always fails execution (references non-existent column)
        bad_code = """
plt.figure()
plt.plot(df['this_column_does_not_exist'])
"""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text=f"```python\n{bad_code}\n```")
        ]

        with patch("src.agent.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            # Always return the same bad code
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Plot data",
                    "api_key": mock_api_key,
                },
            )

        # Should fail after exhausting retries
        assert response.status_code == 400
        assert "retries" in response.json()["detail"].lower()


class TestAPIValidation:
    """Tests for API request validation."""

    def test_missing_data_field(self, client):
        """Missing data field should return 422."""
        response = client.post(
            "/visualize",
            json={"prompt": "Create a chart"},
        )

        assert response.status_code == 422

    def test_missing_prompt_field(self, client):
        """Missing prompt field should return 422."""
        response = client.post(
            "/visualize",
            json={"data": [{"x": 1}]},
        )

        assert response.status_code == 422

    def test_invalid_epsilon(self, client):
        """Invalid epsilon value should return 422."""
        response = client.post(
            "/visualize",
            json={
                "data": [{"x": 1}],
                "prompt": "Plot",
                "epsilon": 0.01,  # Below minimum
            },
        )

        assert response.status_code == 422
