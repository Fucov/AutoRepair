from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


def test_create_normal_ticket_success():
    """测试不带时区的正常工单创建成功"""
    response = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1001",
            "title": "普通咨询工单",
            "priority": "P2",
            "channel": "web",
            "sla_deadline": "2099-01-01T00:00:00"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "c_1001"
    assert data["title"] == "普通咨询工单"
    assert data["priority"] == "P2"
    assert "ticket_id" in data


def test_get_ticket_success():
    """测试查询工单成功"""
    # 先创建工单
    create_resp = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1002",
            "title": "测试查询工单",
            "priority": "P3",
            "channel": "api",
            "sla_deadline": "2099-01-01T00:00:00"
        }
    )
    ticket_id = create_resp.json()["ticket_id"]
    
    # 查询工单
    get_resp = client.get(f"/tickets/{ticket_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["ticket_id"] == ticket_id
