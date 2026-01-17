"""Tests for health endpoint."""

from fastapi.testclient import TestClient

from wintern.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test that health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
