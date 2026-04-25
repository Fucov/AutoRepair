from datetime import datetime
from typing import Dict

from .ticket_repository import create_ticket, find_by_idempotency_key


def submit_ticket(payload: Dict) -> Dict:
    """
    提交工单
    【故意预埋Bug 1: 时区比较错误】
    当sla_deadline带时区时，和utcnow()比较会触发TypeError: can't compare offset-naive and offset-aware datetimes
    
    【故意预埋Bug 2: 幂等性缺失】
    同一个idempotency_key重复提交时，会创建多个不同工单，而不是返回已存在的工单
    """
    # 【幂等性Bug】故意省略幂等键检查逻辑，每次都创建新工单
    # if payload.get("idempotency_key"):
    #     existing = find_by_idempotency_key(payload["idempotency_key"])
    #     if existing:
    #         return existing
    
    # 准备工单数据
    ticket_data = {
        "customer_id": payload["customer_id"],
        "title": payload["title"],
        "priority": payload["priority"],
        "channel": payload["channel"],
        "sla_deadline": payload["sla_deadline"],
        "idempotency_key": payload.get("idempotency_key"),
        "created_at": datetime.utcnow().isoformat()
    }
    
    # 【时区Bug】直接比较offset-aware和offset-naive datetime
    deadline = datetime.fromisoformat(payload["sla_deadline"])
    if deadline < datetime.utcnow():
        ticket_data["status"] = "overdue"
    
    # 创建工单
    return create_ticket(ticket_data)
