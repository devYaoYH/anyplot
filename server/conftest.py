"""Pytest configuration for Sanctum Server tests."""

import sys
from pathlib import Path

# Add mcp to path before any imports
_server_root = Path(__file__).parent
_mcp_root = _server_root.parent / "mcp"
sys.path.insert(0, str(_mcp_root))
sys.path.insert(0, str(_server_root))
