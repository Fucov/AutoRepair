import pytest
from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


@pytest.mark.agent_target
def test_missing_user_should_return_404():
    response = client.get("/users/not-exist/profile")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
