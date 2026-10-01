from fastapi.testclient import TestClient

from app.main import app


def test_health_exposes_security_headers_and_request_id() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "test-request-123"})

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_invalid_request_id_is_replaced() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "x".repeat(129)})

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 16
    assert len(request_id) == 16
    assert all(character in "0123456789abcdef" for character in request_id)
