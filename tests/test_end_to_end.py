"""End-to-end tests for AnyPlot.

These tests use the real Claude API and require ANTHROPIC_API_KEY to be set.
Run with: ANTHROPIC_API_KEY=sk-... pytest tests/test_end_to_end.py -v

These tests are expensive and should only be run:
- On pre-merge or nightly builds
- When explicitly requested
"""

import base64
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

# Mark all tests in this module as e2e
pytestmark = pytest.mark.e2e

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def api_key():
    """Get the API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture(scope="module")
def server_process(api_key):
    """Start the FastAPI server for testing."""
    server_dir = PROJECT_ROOT / "server"

    # Start the server
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = api_key

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        cwd=str(server_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    base_url = "http://127.0.0.1:8765"
    max_wait = 30
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{base_url}/health", timeout=1)
            if response.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        proc.kill()
        stdout, stderr = proc.communicate()
        pytest.fail(
            f"Server failed to start within {max_wait}s. "
            f"stdout: {stdout.decode()}, stderr: {stderr.decode()}"
        )

    yield base_url

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def sample_data():
    """Sample dataset for testing."""
    return [
        {"region": "North", "sales": 1000, "year": 2023},
        {"region": "South", "sales": 1500, "year": 2023},
        {"region": "East", "sales": 1200, "year": 2023},
        {"region": "West", "sales": 800, "year": 2023},
        {"region": "North", "sales": 1100, "year": 2024},
        {"region": "South", "sales": 1600, "year": 2024},
        {"region": "East", "sales": 1300, "year": 2024},
        {"region": "West", "sales": 900, "year": 2024},
    ]


class TestEndToEnd:
    """End-to-end tests using real Claude API."""

    @pytest.mark.timeout(300)  # 5 minute timeout
    def test_full_visualization_flow(self, server_process, sample_data):
        """Test the full visualization flow with real Claude API.

        This test:
        1. Sends a visualization request to the server
        2. Verifies the server returns a valid PNG image
        3. Verifies the generated code is included in the response
        """
        response = requests.post(
            f"{server_process}/visualize",
            json={
                "data": sample_data,
                "prompt": "Create a bar chart showing total sales by region",
            },
            timeout=120,
        )

        assert response.status_code == 200, f"Request failed: {response.text}"

        data = response.json()

        # Verify image is present and valid PNG
        assert "image" in data, "Response missing 'image' field"
        image_bytes = base64.b64decode(data["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n", "Invalid PNG header"

        # Verify code is present
        assert "code" in data, "Response missing 'code' field"
        assert len(data["code"]) > 0, "Generated code is empty"

        # Verify code contains matplotlib usage
        assert "plt" in data["code"], "Code doesn't appear to use matplotlib"

    @pytest.mark.timeout(300)
    def test_histogram_visualization(self, server_process):
        """Test histogram visualization."""
        # Create data with a distribution
        data = [{"value": i % 10 * 10} for i in range(100)]

        response = requests.post(
            f"{server_process}/visualize",
            json={
                "data": data,
                "prompt": "Create a histogram of the values",
            },
            timeout=120,
        )

        assert response.status_code == 200, f"Request failed: {response.text}"

        result = response.json()
        assert "image" in result
        assert "code" in result

        # Verify it's a valid PNG
        image_bytes = base64.b64decode(result["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.timeout(300)
    def test_line_chart_visualization(self, server_process):
        """Test line chart visualization."""
        data = [{"x": i, "y": i * 2 + (i % 3)} for i in range(20)]

        response = requests.post(
            f"{server_process}/visualize",
            json={
                "data": data,
                "prompt": "Create a line chart showing y vs x",
            },
            timeout=120,
        )

        assert response.status_code == 200, f"Request failed: {response.text}"

        result = response.json()
        image_bytes = base64.b64decode(result["image"])
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_endpoint(self, server_process):
        """Health endpoint should return ok."""
        response = requests.get(f"{server_process}/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestErrorHandling:
    """Tests for error handling in E2E scenarios."""

    def test_empty_data_returns_error(self, server_process):
        """Empty data should return 400 error."""
        response = requests.post(
            f"{server_process}/visualize",
            json={
                "data": [],
                "prompt": "Create a chart",
            },
            timeout=30,
        )

        assert response.status_code == 400
