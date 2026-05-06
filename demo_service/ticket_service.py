from datetime import datetime
from typing import Dict

from .ticket_repository import create_ticket, find_by_idempotency_key


def submit_ticket(payload: Dict) -> Dict:
    """
    提交工单
    【故意预埋Bug 1: NameError】
    当sla_deadline已过期时，尝试设置状态为overdue，但漏掉了引号，
    导致 NameError: name 'overdue' is not defined

    【故意预埋Bug 2: 幂等性缺失】
    同一个idempotency_key重复提交时，会创建多个不同工单，而不是返回已存在的工单
    """
    # 【幂等性Bug】故意省略幂等键检查逻辑，每次都创建新工单
    # if payload.get("idempotency_key"):
    #     existing = find_by_idempotency_key(payload["idempotency_key"])
    #     if existing:
    #         return existing

    ticket_data = {
        "customer_id": payload["customer_id"],
        "title": payload["title"],
        "priority": payload["priority"],
        "channel": payload["channel"],
        "sla_deadline": payload["sla_deadline"],
        "idempotency_key": payload.get("idempotency_key"),
        "created_at": datetime.utcnow().isoformat()
    }

    # 【NameError Bug】漏掉引号，overdue 应该是字符串 "overdue"
    deadline = datetime.fromisoformat(payload["sla_deadline"])
    if deadline < datetime.utcnow():
        ticket_data["status"] = overdue

    return create_ticket(ticket_data)
