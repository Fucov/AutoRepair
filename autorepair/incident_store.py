import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .config import PROJECT_ROOT
from .schemas import Incident


DEFAULT_INCIDENT_PATH = PROJECT_ROOT / "autorepair" / "records" / "incidents.jsonl"


def _ensure_path_exists(path: Path) -> None:
    """确保路径的父目录存在"""
    path.parent.mkdir(parents=True, exist_ok=True)


def append_incident(incident: Incident, path: Optional[str | Path] = None) -> None:
    """
    追加Incident到jsonl文件
    :param incident: Incident对象
    :param path: 可选自定义路径，默认使用autorepair/records/incidents.jsonl
    """
    file_path = Path(path) if path else DEFAULT_INCIDENT_PATH
    _ensure_path_exists(file_path)
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(incident.model_dump_json() + "\n")


def load_incidents(path: Optional[str | Path] = None) -> List[Incident]:
    """
    加载所有Incident记录
    :param path: 可选自定义路径
    :return: Incident对象列表
    """
    file_path = Path(path) if path else DEFAULT_INCIDENT_PATH
    if not file_path.exists():
        return []
    
    incidents = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                incident = Incident.model_validate_json(line)
                incidents.append(incident)
            except Exception:
                # 忽略无效行
                continue
    
    return incidents


def has_fingerprint(fingerprint: str, path: Optional[str | Path] = None) -> bool:
    """
    检查指定fingerprint是否已经存在
    :param fingerprint: 错误指纹
    :param path: 可选自定义路径
    :return: True表示已存在，False表示不存在
    """
    incidents = load_incidents(path)
    for incident in incidents:
        if incident.error_summary.fingerprint == fingerprint:
            return True
    return False


def upsert_incident_by_fingerprint(incident: Incident, path: Optional[str | Path] = None) -> Tuple[Incident, str]:
    """
    根据fingerprint更新或创建Incident
    :param incident: 新的Incident对象
    :param path: 可选自定义路径
    :return: (最终的Incident对象, action: "created"|"updated")
    """
    file_path = Path(path) if path else DEFAULT_INCIDENT_PATH
    incidents = load_incidents(path)
    now = datetime.now().isoformat()
    
    # 查找是否已有相同fingerprint的Incident
    existing_index = None
    for i, inc in enumerate(incidents):
        if inc.error_summary.fingerprint == incident.error_summary.fingerprint:
            existing_index = i
            break
    
    if existing_index is None:
        # 新建Incident
        action = "created"
        # 设置首次和最近发现时间
        incident.first_seen_at = incident.first_seen_at or now
        incident.last_seen_at = incident.last_seen_at or now
        # 确保source_refs包含当前source_ref
        if incident.source_ref and incident.source_ref not in incident.source_refs:
            incident.source_refs.append(incident.source_ref)
        incidents.append(incident)
    else:
        # 更新已有Incident
        action = "updated"
        existing = incidents[existing_index]
        existing.occurrence_count += 1
        existing.last_seen_at = now
        # 追加source_ref（去重）
        if incident.source_ref and incident.source_ref not in existing.source_refs:
            existing.source_refs.append(incident.source_ref)
        # 更新其他可能变化的字段
        existing.updated_at = now
        incident = existing
    
    # 全量重写文件
    _ensure_path_exists(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        for inc in incidents:
            f.write(inc.model_dump_json() + "\n")
    
    return (incident, action)
