from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


def test_get_existing_user_profile():
    response = client.get("/users/u_1001/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "u_1001"
    assert data["name"] == "Alice"
    assert data["role"] == "developer"
