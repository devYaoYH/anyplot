"""
Sandbox testing utilities
"""

import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class SandboxTester:
    """
    Helper for testing sandbox execution
    
    Example:
        >>> tester = SandboxTester()
        >>> result = tester.execute("print('hello')")
        >>> assert result.stdout == "hello\n"
    """
    
    def __init__(self, timeout: int = 5, memory_limit_mb: int = 256):
        """
        Initialize sandbox tester
        
        Args:
            timeout: Execution timeout in seconds
            memory_limit_mb: Memory limit in MB
        """
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
    
    def execute(
        self,
        code: str,
        expected_output: Optional[str] = None,
        should_fail: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Execute code in a sandbox-like environment
        
        Args:
            code: Python code to execute
            expected_output: Expected output (for assertion)
            should_fail: Whether execution should fail
        
        Returns:
            CompletedProcess result
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            code_file = f.name
        
        try:
            result = subprocess.run(
                ['python3', code_file],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if should_fail:
                assert result.returncode != 0, \
                    f"Code should have failed but succeeded: {result.stdout}"
            else:
                assert result.returncode == 0, \
                    f"Code failed: {result.stderr}"
            
            if expected_output is not None:
                assert expected_output in result.stdout, \
                    f"Expected '{expected_output}' in output, got: {result.stdout}"
            
            return result
            
        finally:
            Path(code_file).unlink()
    
    def test_imports(self, import_statement: str, should_allow: bool = True):
        """
        Test if an import is allowed/blocked
        
        Args:
            import_statement: Import statement to test (e.g., "import os")
            should_allow: Whether import should be allowed
        """
        code = f"{import_statement}\nprint('success')"
        result = self.execute(code, should_fail=not should_allow)
        
        if should_allow:
            assert "success" in result.stdout
        else:
            assert result.returncode != 0
    
    def test_timeout(self, sleep_time: int = 10):
        """
        Test that long-running code times out
        
        Args:
            sleep_time: How long to sleep (should exceed timeout)
        """
        code = f"import time\ntime.sleep({sleep_time})"
        
        try:
            self.execute(code)
            raise AssertionError("Code should have timed out")
        except subprocess.TimeoutExpired:
            pass  # Expected
    
    def test_file_access(self, file_path: str, mode: str = 'r', should_allow: bool = False):
        """
        Test file access restrictions
        
        Args:
            file_path: Path to test
            mode: File mode ('r', 'w', etc.)
            should_allow: Whether access should be allowed
        """
        code = f"open('{file_path}', '{mode}')"
        self.execute(code, should_fail=not should_allow)
    
    def validate_visualization_code(
        self,
        code: str,
        blocked_imports: Optional[list[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that visualization code is safe
        
        Args:
            code: Code to validate
            blocked_imports: List of blocked import modules
        
        Returns:
            (is_valid, error_message)
        """
        blocked_imports = blocked_imports or [
            'os', 'subprocess', 'socket', 'sys', '__import__'
        ]
        
        # Check for blocked imports
        for blocked in blocked_imports:
            if f"import {blocked}" in code or f"from {blocked}" in code:
                return False, f"Blocked import: {blocked}"
        
        # Check for dangerous built-ins
        dangerous = ['eval', 'exec', 'compile', '__import__']
        for func in dangerous:
            if func in code:
                return False, f"Dangerous function: {func}"
        
        # Try to execute
        try:
            result = self.execute(code, should_fail=False)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def create_mock_dataset(self, rows: int = 10) -> str:
        """
        Create mock dataset code for testing
        
        Args:
            rows: Number of rows
        
        Returns:
            Python code that creates a DataFrame
        """
        return f"""
import pandas as pd
import numpy as np

df = pd.DataFrame({{
    'x': np.arange({rows}),
    'y': np.random.rand({rows})
}})
"""
    
    def test_visualization_output(self, code: str) -> bool:
        """
        Test that code produces a visualization file
        
        Args:
            code: Visualization code (should save to 'output.png')
        
        Returns:
            True if visualization file is created
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'output.png'
            
            # Modify code to save to temp location
            code_with_save = f"{code}\nplt.savefig('{output_path}')"
            
            result = self.execute(code_with_save)
            
            assert output_path.exists(), "Visualization file not created"
            assert output_path.stat().st_size > 0, "Visualization file is empty"
            
            # Check PNG header
            with open(output_path, 'rb') as f:
                header = f.read(8)
                assert header == b'\x89PNG\r\n\x1a\n', "Invalid PNG file"
            
            return True
