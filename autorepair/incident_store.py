import json
from pathlib import Path
from typing import List, Optional

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
