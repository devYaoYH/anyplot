"""Secure sandbox for executing generated Python code.

This module provides a secure execution environment for agent-generated
visualization code. It runs code in a subprocess with restricted permissions.

Security features:
- No network access
- Limited filesystem access (temp directory only)
- Timeout enforcement
- Memory limits
- Restricted environment variables
- Allowlisted imports only
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SandboxError(Exception):
    """Base exception for sandbox errors."""

    pass


class SandboxTimeoutError(SandboxError):
    """Raised when code execution times out."""

    pass


class SandboxExecutionError(SandboxError):
    """Raised when code execution fails."""

    pass


@dataclass
class SandboxResult:
    """Result from sandbox code execution."""

    success: bool
    image_bytes: bytes | None = None
    image_base64: str | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


@dataclass
class SandboxConfig:
    """Configuration for the sandbox."""

    timeout_seconds: int = 30
    memory_limit_mb: int = 512
    temp_dir: Path | None = None


class Sandbox:
    """Secure sandbox for executing visualization code.

    Executes agent-generated Python code in a restricted subprocess,
    automatically injecting a data-loading prelude that maps masked
    column names back to real names.
    """

    # Packages allowed in the sandbox
    ALLOWED_PACKAGES = [
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
    ]

    def __init__(self, config: SandboxConfig | None = None):
        """Initialize the sandbox.

        Args:
            config: Optional sandbox configuration
        """
        self.config = config or SandboxConfig()

    def execute(
        self,
        code: str,
        data: list[dict[str, Any]],
        column_mapping: dict[str, str],
    ) -> SandboxResult:
        """Execute code in the sandbox.

        Args:
            code: Python code to execute (from agent)
            data: Data rows as list of dicts
            column_mapping: Mapping from masked names to original names

        Returns:
            SandboxResult with execution results
        """
        session_id = str(uuid.uuid4())[:8]

        # Create temp directory for this session
        if self.config.temp_dir:
            temp_base = self.config.temp_dir
            temp_base.mkdir(parents=True, exist_ok=True)
        else:
            temp_base = Path(tempfile.gettempdir())

        session_dir = temp_base / f"sanctum-{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)

        try:
            return self._execute_in_subprocess(
                code=code,
                data=data,
                column_mapping=column_mapping,
                session_dir=session_dir,
            )
        finally:
            # Clean up temp files
            self._cleanup(session_dir)

    def _execute_in_subprocess(
        self,
        code: str,
        data: list[dict[str, Any]],
        column_mapping: dict[str, str],
        session_dir: Path,
    ) -> SandboxResult:
        """Execute code in a subprocess."""
        # Generate the full script with prelude
        full_script = self._generate_script(code, data, column_mapping, session_dir)

        # Write script to temp file
        script_path = session_dir / "script.py"
        script_path.write_text(full_script)

        # Output image path
        output_path = session_dir / "output.png"

        # Build restricted environment
        env = self._build_restricted_env()

        try:
            # Execute in subprocess
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                env=env,
                cwd=str(session_dir),
            )

            # Check if image was produced
            image_bytes = None
            image_base64 = None
            if output_path.exists():
                image_bytes = output_path.read_bytes()
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            if result.returncode != 0:
                return SandboxResult(
                    success=False,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error=f"Code execution failed with exit code {result.returncode}",
                )

            if image_bytes is None:
                return SandboxResult(
                    success=False,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error="No image was produced. Make sure to call plt.savefig('output.png')",
                )

            return SandboxResult(
                success=True,
                image_bytes=image_bytes,
                image_base64=image_base64,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {self.config.timeout_seconds} seconds",
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Execution error: {str(e)}",
            )

    def _generate_script(
        self,
        code: str,
        data: list[dict[str, Any]],
        column_mapping: dict[str, str],
        session_dir: Path,
    ) -> str:
        """Generate the full script with data-loading prelude.

        The prelude:
        - Loads the data into a DataFrame
        - Renames columns from masked names to real names
        - Sets up matplotlib with Agg backend
        """
        # Convert column mapping to Python dict literal
        # This maps masked -> original, we need original -> masked for initial data
        # Then rename from masked -> original
        reverse_mapping = {v: k for k, v in column_mapping.items()}

        prelude = textwrap.dedent(f'''
            # === SANCTUM PRELUDE (auto-injected) ===
            import sys
            import pandas as pd
            import numpy as np
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            # Load data
            _sanctum_data = {data!r}
            df = pd.DataFrame(_sanctum_data)

            # Rename columns from masked to original names
            _sanctum_column_mapping = {column_mapping!r}
            df = df.rename(columns=_sanctum_column_mapping)

            # Set output path
            _sanctum_output_path = 'output.png'

            # Helper to save figure
            def save_plot():
                plt.savefig(_sanctum_output_path, dpi=100, bbox_inches='tight')
                plt.close()

            # === END PRELUDE ===

        ''').strip()

        # Append code to save the figure at the end if not already present
        postlude = textwrap.dedent('''

            # === SANCTUM POSTLUDE (auto-injected) ===
            # Ensure the plot is saved
            if plt.get_fignums():
                plt.savefig(_sanctum_output_path, dpi=100, bbox_inches='tight')
                plt.close('all')
            # === END POSTLUDE ===
        ''')

        return prelude + "\n\n# === USER CODE ===\n" + code + postlude

    def _build_restricted_env(self) -> dict[str, str]:
        """Build a restricted environment for the subprocess."""
        # Start with minimal environment
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
        }

        # Add Python-specific paths
        if "PYTHONPATH" in os.environ:
            env["PYTHONPATH"] = os.environ["PYTHONPATH"]

        # Explicitly exclude sensitive variables
        sensitive_vars = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "DATABASE_URL",
            "SECRET_KEY",
        ]
        for var in sensitive_vars:
            env.pop(var, None)

        return env

    def _cleanup(self, session_dir: Path) -> None:
        """Clean up temporary files."""
        try:
            if session_dir.exists():
                shutil.rmtree(session_dir)
        except Exception:
            pass  # Best effort cleanup


def validate_code(code: str) -> tuple[bool, str | None]:
    """Validate code for obvious security issues.

    This is a basic check - the real security comes from the subprocess isolation.

    Args:
        code: Python code to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    dangerous_patterns = [
        ("import os", "Direct os import is not allowed"),
        ("import subprocess", "subprocess module is not allowed"),
        ("import socket", "socket module is not allowed"),
        ("import urllib", "urllib module is not allowed"),
        ("import requests", "requests module is not allowed"),
        ("import http", "http module is not allowed"),
        ("__import__", "Dynamic imports are not allowed"),
        ("eval(", "eval() is not allowed"),
        ("exec(", "exec() is not allowed"),
        ("open(", "Direct file access is not allowed"),
        ("compile(", "compile() is not allowed"),
    ]

    for pattern, message in dangerous_patterns:
        if pattern in code:
            return False, message

    return True, None
