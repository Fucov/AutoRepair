import pytest
from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)


@pytest.mark.agent_target
def test_expired_sla_deadline_should_return_overdue():
    """测试SLA已过期的工单应返回overdue状态，当前因NameError返回500（预期失败）"""
    response = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1001",
            "title": "过期工单测试",
            "priority": "P1",
            "channel": "feishu",
            "sla_deadline": "2020-01-01T00:00:00",
            "idempotency_key": "evt_test_001"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "overdue"


@pytest.mark.agent_target
def test_future_sla_deadline_should_return_open():
    """测试SLA未过期的工单应返回正常状态"""
    response = client.post(
        "/tickets/submit",
        json={
            "customer_id": "c_1001",
            "title": "未过期工单测试",
            "priority": "P2",
            "channel": "web",
            "sla_deadline": "2099-01-01T00:00:00"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "open"


@pytest.mark.agent_target
def test_duplicate_idempotency_key_should_not_create_two_tickets():
    """测试同一个幂等键重复提交应该返回同一个工单，当前会创建两个不同工单（预期失败）"""
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

    assert ticket_id_1 == ticket_id_2


@pytest.mark.agent_target
def test_ticket_create_sla8_should_succeed():
    """测试工单创建接口sla_hours=8时应正常返回，当前因NameError返回500"""
    response = client.post(
        "/ticket/create",
        json={"priority": "P1", "sla_hours": 8},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
