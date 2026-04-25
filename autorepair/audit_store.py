import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

DEFAULT_AUDIT_PATH = Path(__file__).parent / "records" / "audit_events.jsonl"


def _ensure_audit_dir_exists(audit_path: Path):
    """确保审计文件目录存在"""
    audit_path.parent.mkdir(parents=True, exist_ok=True)


def append_audit_event(event_type: str, incident_id: Optional[str] = None, payload: dict = None) -> None:
    """
    追加审计事件
    :param event_type: 事件类型，如 incident_created, feishu_card_sent 等
    :param incident_id: 关联的事件ID（可选）
    :param payload: 事件额外数据（可选）
    """
    audit_path = DEFAULT_AUDIT_PATH
    _ensure_audit_dir_exists(audit_path)
    
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "incident_id": incident_id,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat()
    }
    
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_audit_events(path: Optional[str | Path] = None) -> List[dict]:
    """
    加载所有审计事件
    :param path: 审计文件路径，默认使用内置路径
    :return: 审计事件列表
    """
    audit_path = Path(path) if path else DEFAULT_AUDIT_PATH
    if not audit_path.exists():
        return []
    
    events = []
    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    
    return events
