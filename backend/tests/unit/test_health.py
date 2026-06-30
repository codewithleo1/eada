from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_liveness():
    """Health check should always return alive."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness():
    """Readiness check should always return ready."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}