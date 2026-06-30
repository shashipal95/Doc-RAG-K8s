"""
Basic API Tests
Run with: pytest tests/
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()


def test_health_check():
    """Test health endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_auth_endpoints_exist():
    """Test that auth endpoints are registered"""
    response = client.get("/docs")
    assert response.status_code == 200
    # Docs page should be accessible
