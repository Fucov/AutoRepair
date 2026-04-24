import pytest
from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


@pytest.mark.agent_target
def test_zero_total_amount_should_return_400():
    """测试订单总金额为0时应返回400错误，当前因预埋Bug返回500（预期失败）"""
    response = client.post(
        "/orders/preview",
        json={
            "order_id": "o_1001",
            "total_amount": 0,
            "discount_amount": 10
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid order amount"
