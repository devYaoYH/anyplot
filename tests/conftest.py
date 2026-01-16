"""Pytest configuration for E2E tests."""

import sys
from pathlib import Path

# Add project paths for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "mcp"))
sys.path.insert(0, str(PROJECT_ROOT / "server"))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "timeout: mark test with timeout")
