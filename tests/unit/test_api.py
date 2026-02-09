"""
Unit tests for the API layer.
"""

import pytest
from fastapi.testclient import TestClient

from orgmind.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_liveness(self, client: TestClient) -> None:
        """Test the liveness probe returns alive."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness(self, client: TestClient) -> None:
        """Test the readiness probe returns ready."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "version" in data
        assert "checks" in data
