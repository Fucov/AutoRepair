from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


def test_order_preview_success():
    """测试正常订单预览请求成功"""
    response = client.post(
        "/orders/preview",
        json={
            "order_id": "o_1001",
            "total_amount": 100,
            "discount_amount": 10
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "o_1001"
    assert data["final_amount"] == 90
    assert data["discount_rate"] == 10.0
