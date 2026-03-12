"""
API test client utilities
"""

from typing import Any, Optional
import requests
from dataclasses import dataclass


@dataclass
class APIResponse:
    """Wrapper for API responses"""
    status_code: int
    data: Any
    headers: dict
    
    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300
    
    def assert_success(self):
        assert self.ok, f"API request failed: {self.status_code} - {self.data}"
    
    def assert_has_keys(self, *keys: str):
        for key in keys:
            assert key in self.data, f"Missing key in response: {key}"


class APITestClient:
    """
    Simplified API client for testing
    
    Example:
        >>> client = APITestClient("http://localhost:8000")
        >>> response = client.visualize(data=[...], prompt="plot")
        >>> response.assert_success()
        >>> response.assert_has_keys("image", "code")
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
        api_key: Optional[str] = None
    ):
        """
        Initialize API test client
        
        Args:
            base_url: Base URL for API
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    def get(self, endpoint: str, **kwargs) -> APIResponse:
        """Make GET request"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        return APIResponse(
            status_code=response.status_code,
            data=response.json() if response.content else None,
            headers=dict(response.headers)
        )
    
    def post(self, endpoint: str, **kwargs) -> APIResponse:
        """Make POST request"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(url, timeout=self.timeout, **kwargs)
        return APIResponse(
            status_code=response.status_code,
            data=response.json() if response.content else None,
            headers=dict(response.headers)
        )
    
    def health(self) -> APIResponse:
        """Check API health"""
        return self.get("/health")
    
    def visualize(
        self,
        data: list[dict],
        prompt: str,
        session_id: Optional[str] = None,
        epsilon: Optional[float] = None
    ) -> APIResponse:
        """
        Create visualization
        
        Args:
            data: List of data records
            prompt: Visualization prompt
            session_id: Optional session ID
            epsilon: Optional privacy epsilon
        
        Returns:
            API response with image and code
        """
        payload = {
            "data": data,
            "prompt": prompt
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        if epsilon:
            payload["epsilon"] = epsilon
        
        return self.post("/visualize", json=payload)
    
    def get_session(self, session_id: str) -> APIResponse:
        """Get session information"""
        return self.get(f"/api/session/{session_id}")
    
    def export_session(self, session_id: str, format: str = "json") -> APIResponse:
        """Export session data"""
        return self.get(f"/api/export-session", params={
            "session_id": session_id,
            "format": format
        })
    
    def assert_server_running(self):
        """Assert that server is running and healthy"""
        try:
            response = self.health()
            assert response.ok, f"Server health check failed: {response.status_code}"
        except requests.exceptions.ConnectionError:
            raise AssertionError("Server not running at {self.base_url}")
    
    def create_test_session(self, data: list[dict]) -> str:
        """
        Create a test session and return session ID
        
        Args:
            data: Test data
        
        Returns:
            Session ID
        """
        response = self.visualize(
            data=data,
            prompt="Create a simple test plot"
        )
        response.assert_success()
        
        # Extract session ID from response
        return response.data.get("session_id", "test-session")
