import pytest
from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


@pytest.mark.agent_target
def test_timezone_aware_sla_deadline_should_create_ticket():
    """测试带时区的SLA截止时间应该成功创建工单，当前因时区Bug返回500（预期失败）"""
    response = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1001",
            "title": "紧急工单测试",
            "priority": "P1",
            "channel": "feishu",
            "sla_deadline": "2099-01-01T18:00:00+08:00",
            "idempotency_key": "evt_test_001"
        }
    )
    # 期望成功创建工单，返回200
    assert response.status_code == 200
    assert "ticket_id" in response.json()


@pytest.mark.agent_target
def test_duplicate_idempotency_key_should_not_create_two_tickets():
    """测试同一个幂等键重复提交应该返回同一个工单，当前会创建两个不同工单（预期失败）"""
    # 第一次提交
    resp1 = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1002",
            "title": "重复提交测试",
            "priority": "P2",
            "channel": "api",
            "sla_deadline": "2099-01-01T00:00:00",
            "idempotency_key": "evt_duplicate_001"
        }
    )
    assert resp1.status_code == 200
    ticket_id_1 = resp1.json()["ticket_id"]
    
    # 第二次提交相同幂等键
    resp2 = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1002",
            "title": "重复提交测试",
            "priority": "P2",
            "channel": "api",
            "sla_deadline": "2099-01-01T00:00:00",
            "idempotency_key": "evt_duplicate_001"
        }
    )
    assert resp2.status_code == 200
    ticket_id_2 = resp2.json()["ticket_id"]
    
    # 期望返回同一个ticket_id
    assert ticket_id_1 == ticket_id_2
