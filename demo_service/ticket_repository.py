from typing import Dict, Optional
import uuid

# 内存存储工单
tickets: Dict[str, Dict] = {}
idempotency_map: Dict[str, str] = {}  # key: idempotency_key, value: ticket_id


def create_ticket(data: Dict) -> Dict:
    """创建工单"""
    ticket_id = f"t_{uuid.uuid4().hex[:8]}"
    ticket = {
        "ticket_id": ticket_id,
        "customer_id": data["customer_id"],
        "title": data["title"],
        "priority": data["priority"],
        "channel": data["channel"],
        "sla_deadline": data["sla_deadline"],
        "idempotency_key": data.get("idempotency_key"),
        "status": "open",
        "created_at": data.get("created_at")
    }
    
    tickets[ticket_id] = ticket
    
    # 保存幂等键映射
    if ticket["idempotency_key"]:
        idempotency_map[ticket["idempotency_key"]] = ticket_id
    
    return ticket


def get_ticket(ticket_id: str) -> Optional[Dict]:
    """根据ticket_id查询工单"""
    return tickets.get(ticket_id)


def find_by_idempotency_key(key: str) -> Optional[Dict]:
    """根据幂等键查询工单"""
    if not key:
        return None
    ticket_id = idempotency_map.get(key)
    return get_ticket(ticket_id) if ticket_id else None
