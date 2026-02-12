"""Unit tests for the sandbox module.

Tests:
- Successful code execution produces PNG
- Column mapping works correctly
- Timeout enforcement
- Code validation for dangerous patterns
- Cleanup of temporary files
- Altair/Vega-Lite support
"""

import base64
import tempfile
from pathlib import Path

import pytest

from src.sandbox import Sandbox, SandboxConfig, SandboxResult, validate_code


class TestSandboxExecution:
    """Tests for sandbox code execution."""

    @pytest.fixture
    def sandbox(self):
        """Create a sandbox instance."""
        return Sandbox()

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return [
            {"col_abc": 10, "col_def": 100},
            {"col_abc": 20, "col_def": 200},
            {"col_abc": 30, "col_def": 300},
        ]

    @pytest.fixture
    def column_mapping(self):
        """Column mapping from masked to original names."""
        return {"col_abc": "x_values", "col_def": "y_values"}

    def test_simple_plot_produces_png(self, sandbox, sample_data, column_mapping):
        """Simple matplotlib code should produce a PNG image."""
        code = """
plt.figure(figsize=(8, 6))
plt.plot(df['x_values'], df['y_values'])
plt.title('Test Plot')
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert result.success, f"Execution failed: {result.error}"
        assert result.image_bytes is not None
        assert result.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
        assert result.image_base64 is not None

    def test_bar_chart_works(self, sandbox, sample_data, column_mapping):
        """Bar chart code should work."""
        code = """
plt.figure()
plt.bar(df['x_values'], df['y_values'])
plt.xlabel('X')
plt.ylabel('Y')
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert result.success, f"Execution failed: {result.error}"
        assert result.image_bytes is not None

    def test_histogram_works(self, sandbox):
        """Histogram code should work."""
        data = [{"col_a": i} for i in range(100)]
        mapping = {"col_a": "values"}

        code = """
plt.figure()
plt.hist(df['values'], bins=10)
plt.title('Histogram')
"""
        result = sandbox.execute(code, data, mapping)

        assert result.success, f"Execution failed: {result.error}"
        assert result.image_bytes is not None

    def test_column_mapping_applied(self, sandbox, sample_data, column_mapping):
        """Masked column names should be mapped to original names."""
        # Code uses original column names (which come from mapping)
        code = """
# These column names should work after mapping
assert 'x_values' in df.columns, f"x_values not in {df.columns.tolist()}"
assert 'y_values' in df.columns, f"y_values not in {df.columns.tolist()}"
plt.plot(df['x_values'], df['y_values'])
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert result.success, f"Execution failed: {result.error}\nStderr: {result.stderr}"

    def test_code_without_savefig_still_saves(self, sandbox, sample_data, column_mapping):
        """Code that doesn't call savefig should still produce image via postlude."""
        code = """
plt.figure()
plt.plot(df['x_values'], df['y_values'])
# No explicit savefig call
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert result.success, f"Execution failed: {result.error}"
        assert result.image_bytes is not None

    def test_invalid_code_returns_error(self, sandbox, sample_data, column_mapping):
        """Invalid Python code should return an error."""
        code = """
this is not valid python!!!
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert not result.success
        assert result.error is not None

    def test_missing_column_returns_error(self, sandbox, sample_data, column_mapping):
        """Accessing non-existent column should return error."""
        code = """
plt.plot(df['nonexistent_column'])
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert not result.success
        assert "error" in result.error.lower() or "error" in result.stderr.lower()

    def test_result_includes_stdout(self, sandbox, sample_data, column_mapping):
        """Result should include stdout from code execution."""
        code = """
print("Hello from sandbox!")
plt.figure()
plt.plot([1, 2, 3])
"""
        result = sandbox.execute(code, sample_data, column_mapping)

        assert result.success
        assert "Hello from sandbox!" in result.stdout


class TestSandboxTimeout:
    """Tests for sandbox timeout enforcement."""

    def test_timeout_enforced(self):
        """Long-running code should be terminated."""
        sandbox = Sandbox(SandboxConfig(timeout_seconds=2))
        data = [{"x": 1}]
        mapping = {"x": "x"}

        code = """
import time
time.sleep(10)  # Sleep longer than timeout
plt.plot([1, 2, 3])
"""
        result = sandbox.execute(code, data, mapping)

        assert not result.success
        assert "timed out" in result.error.lower()


class TestSandboxSecurity:
    """Tests for sandbox security features."""

    @pytest.fixture
    def sandbox(self):
        """Create a sandbox instance."""
        return Sandbox()

    @pytest.fixture
    def data(self):
        """Minimal data for security tests."""
        return [{"x": 1}]

    @pytest.fixture
    def mapping(self):
        """Minimal mapping for security tests."""
        return {"x": "x"}

    def test_cannot_read_arbitrary_files(self, sandbox, data, mapping):
        """Sandbox should not allow reading arbitrary files."""
        code = """
# Attempt to read a system file
try:
    with open('/etc/passwd', 'r') as f:
        content = f.read()
    print(f"READ FILE: {content[:100]}")
except Exception as e:
    print(f"BLOCKED: {e}")
plt.plot([1, 2])
"""
        # Code validation should catch this
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "file access" in error.lower()

    def test_cannot_make_network_requests(self, sandbox, data, mapping):
        """Sandbox should not allow network access."""
        code = """
import urllib.request
urllib.request.urlopen('http://example.com')
plt.plot([1, 2])
"""
        is_valid, error = validate_code(code)
        assert not is_valid

    def test_no_subprocess_access(self, sandbox, data, mapping):
        """Sandbox should not allow subprocess creation."""
        code = """
import subprocess
subprocess.run(['ls', '-la'])
plt.plot([1, 2])
"""
        is_valid, error = validate_code(code)
        assert not is_valid

    def test_no_eval_exec(self, sandbox, data, mapping):
        """Sandbox should not allow eval/exec."""
        code = """
eval('print("evil")')
plt.plot([1, 2])
"""
        is_valid, error = validate_code(code)
        assert not is_valid


class TestCodeValidation:
    """Tests for the validate_code function."""

    def test_valid_matplotlib_code(self):
        """Valid matplotlib code should pass validation."""
        code = """
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

plt.figure()
plt.plot([1, 2, 3], [1, 4, 9])
plt.title('Test')
"""
        is_valid, error = validate_code(code)
        assert is_valid
        assert error is None

    def test_valid_seaborn_code(self):
        """Valid seaborn code should pass validation."""
        code = """
import seaborn as sns
import matplotlib.pyplot as plt

sns.histplot(df['values'])
"""
        is_valid, error = validate_code(code)
        assert is_valid

    def test_os_import_blocked(self):
        """Direct os import should be blocked."""
        code = "import os\nos.system('rm -rf /')"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "os" in error.lower()

    def test_socket_blocked(self):
        """Socket module should be blocked."""
        code = "import socket"
        is_valid, error = validate_code(code)
        assert not is_valid

    def test_requests_blocked(self):
        """Requests module should be blocked."""
        code = "import requests"
        is_valid, error = validate_code(code)
        assert not is_valid

    def test_dunder_import_blocked(self):
        """__import__ should be blocked."""
        code = "__import__('os')"
        is_valid, error = validate_code(code)
        assert not is_valid

    def test_compile_blocked(self):
        """compile() should be blocked."""
        code = "compile('print(1)', '<string>', 'exec')"
        is_valid, error = validate_code(code)
        assert not is_valid


class TestAltairExecution:
    """Tests for Altair/Vega-Lite mode execution."""

    @pytest.fixture
    def sandbox(self):
        """Create a sandbox instance."""
        return Sandbox()

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return [
            {"col_abc": 10, "col_def": 100},
            {"col_abc": 20, "col_def": 200},
            {"col_abc": 30, "col_def": 300},
        ]

    @pytest.fixture
    def column_mapping(self):
        """Column mapping from masked to original names."""
        return {"col_abc": "x_values", "col_def": "y_values"}

    def test_altair_produces_vega_spec(self, sandbox, sample_data, column_mapping):
        """Altair code should produce a Vega-Lite JSON spec."""
        code = """
chart = alt.Chart(df).mark_point().encode(
    x='x_values',
    y='y_values'
)
save_chart(chart)
"""
        result = sandbox.execute(code, sample_data, column_mapping, viz_mode="altair")

        assert result.success, f"Execution failed: {result.error}\nStderr: {result.stderr}"
        assert result.vega_spec is not None
        assert result.viz_type == "vega_lite"
        assert "$schema" in result.vega_spec
        assert result.image_bytes is None  # No PNG for altair mode

    def test_altair_bar_chart(self, sandbox, sample_data, column_mapping):
        """Altair bar chart should work."""
        code = """
chart = alt.Chart(df).mark_bar().encode(
    x='x_values:O',
    y='y_values:Q'
).properties(title='Test Bar Chart')
save_chart(chart)
"""
        result = sandbox.execute(code, sample_data, column_mapping, viz_mode="altair")

        assert result.success, f"Execution failed: {result.error}\nStderr: {result.stderr}"
        assert result.vega_spec is not None
        assert result.viz_type == "vega_lite"

    def test_altair_interactive_chart(self, sandbox, sample_data, column_mapping):
        """Altair interactive chart with tooltips should work."""
        code = """
chart = alt.Chart(df).mark_circle().encode(
    x='x_values',
    y='y_values',
    tooltip=['x_values', 'y_values']
).interactive()
save_chart(chart)
"""
        result = sandbox.execute(code, sample_data, column_mapping, viz_mode="altair")

        assert result.success, f"Execution failed: {result.error}\nStderr: {result.stderr}"
        assert result.vega_spec is not None

    def test_altair_without_save_chart_fails(self, sandbox, sample_data, column_mapping):
        """Altair code without save_chart() should fail."""
        code = """
chart = alt.Chart(df).mark_point().encode(
    x='x_values',
    y='y_values'
)
# Missing save_chart(chart) call
"""
        result = sandbox.execute(code, sample_data, column_mapping, viz_mode="altair")

        assert not result.success
        assert "No Vega-Lite spec was produced" in result.error

    def test_altair_column_mapping_applied(self, sandbox, sample_data, column_mapping):
        """Masked column names should be mapped to original names in altair mode."""
        code = """
# Verify column names are mapped correctly
assert 'x_values' in df.columns, f"x_values not in {df.columns.tolist()}"
assert 'y_values' in df.columns, f"y_values not in {df.columns.tolist()}"
chart = alt.Chart(df).mark_line().encode(x='x_values', y='y_values')
save_chart(chart)
"""
        result = sandbox.execute(code, sample_data, column_mapping, viz_mode="altair")

        assert result.success, f"Execution failed: {result.error}\nStderr: {result.stderr}"

    def test_matplotlib_mode_still_works(self, sandbox, sample_data, column_mapping):
        """Matplotlib mode should still work when explicitly specified."""
        code = """
plt.figure()
plt.plot(df['x_values'], df['y_values'])
"""
        result = sandbox.execute(code, sample_data, column_mapping, viz_mode="matplotlib")

        assert result.success, f"Execution failed: {result.error}"
        assert result.image_bytes is not None
        assert result.viz_type == "image"
        assert result.vega_spec is None


class TestSandboxCleanup:
    """Tests for sandbox cleanup."""

    def test_temp_files_cleaned_up(self):
        """Temporary files should be cleaned up after execution."""
        sandbox = Sandbox()
        data = [{"x": 1}]
        mapping = {"x": "x"}

        code = """
plt.figure()
plt.plot([1, 2, 3])
"""
        result = sandbox.execute(code, data, mapping)

        # The session directory should be cleaned up
        # We can't easily test this without exposing internals,
        # but at minimum the execution should complete
        assert result.success


class TestSandboxConfig:
    """Tests for sandbox configuration."""

    def test_custom_temp_dir(self):
        """Custom temp directory should be used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(temp_dir=Path(tmpdir))
            sandbox = Sandbox(config)
            data = [{"x": 1}]
            mapping = {"x": "x"}

            code = "plt.plot([1, 2, 3])"
            result = sandbox.execute(code, data, mapping)

            assert result.success

    def test_custom_timeout(self):
        """Custom timeout should be respected."""
        config = SandboxConfig(timeout_seconds=1)
        sandbox = Sandbox(config)

        assert sandbox.config.timeout_seconds == 1
