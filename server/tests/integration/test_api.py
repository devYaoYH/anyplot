"""Integration tests for the FastAPI endpoints.

Tests the API endpoints with mocked Claude SDK responses.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


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


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestVisualizeEndpoint:
    """Tests for the /visualize endpoint."""

    def test_visualize_with_mocked_agent(self, client, sample_data):
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
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "image" in data
        assert "code" in data

        # Verify image is valid base64 PNG
        image_bytes = base64.b64decode(data["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_visualize_with_tool_calls(self, client, sample_data):
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
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "image" in data

    def test_visualize_empty_data_returns_error(self, client):
        """Empty data should return 400 error."""
        response = client.post(
            "/visualize",
            json={
                "data": [],
                "prompt": "Create a chart",
            },
        )

        assert response.status_code == 400

    def test_visualize_invalid_code_from_agent(self, client, sample_data):
        """Invalid code from agent should return error."""
        # Code that uses dangerous imports
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
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post(
                "/visualize",
                json={
                    "data": sample_data,
                    "prompt": "Create a chart",
                },
            )

        assert response.status_code == 400
        assert "validation" in response.json()["detail"].lower()

    def test_visualize_no_code_block_returns_error(self, client, sample_data):
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
                },
            )

        assert response.status_code == 400
        assert "code" in response.json()["detail"].lower()


class TestColumnMapping:
    """Tests for correct column mapping in visualizations."""

    def test_masked_columns_mapped_correctly(self, client):
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
                },
            )

        assert response.status_code == 200
        # Code should have been executed successfully with column mapping
        data = response.json()
        assert "image" in data

        # Verify it's a valid PNG
        image_bytes = base64.b64decode(data["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


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
