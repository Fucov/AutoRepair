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


def upsert_incident_from_issue(issue: "GitHubIssue") -> Incident:
    """从GitHub Issue创建或更新Incident，用于手动提交的Bug Issue"""
    import uuid
    from datetime import datetime
    import re
    from .adapters.github import GitHubIssue
    from .schemas import ErrorSummary

    body = issue.body or ""
    title = issue.title or ""

    # 尝试从body中提取Incident ID
    incident_id = None
    for line in body.splitlines():
        if "Incident ID:" in line:
            incident_id = line.split("Incident ID:", 1)[1].strip().strip("`")
            break

    if not incident_id:
        incident_id = f"INC-GH-{issue.number}-{uuid.uuid4().hex[:6]}"

    # 查找是否已存在
    existing = None
    for inc in load_incidents():
        if inc.incident_id == incident_id:
            existing = inc
            break

    if existing:
        existing.occurrence_count += 1
        existing.updated_at = datetime.utcnow().isoformat()
        existing.issue_number = issue.number
        existing.issue_url = issue.html_url
        # 全量重写文件
        from pathlib import Path
        file_path = DEFAULT_INCIDENT_PATH
        _ensure_path_exists(file_path)
        incidents = load_incidents()
        for i, inc in enumerate(incidents):
            if inc.incident_id == existing.incident_id:
                incidents[i] = existing
                break
        with open(file_path, "w", encoding="utf-8") as f:
            for inc in incidents:
                f.write(inc.model_dump_json() + "\n")
        return existing

    # 构造ErrorSummary
    error_type = "UnknownError"
    error_message = "Manual bug report"
    suspected_file = None
    line_no = None
    function = None
    fingerprint = f"github-issue-{issue.number}"

    # 尝试从body中提取错误信息
    type_error_match = re.search(r'(TypeError|AttributeError|IndexError|KeyError|ZeroDivisionError|ValueError)', body)
    if type_error_match:
        error_type = type_error_match.group(1)

    message_match = re.search(r'## Error\n\n(.+?)\n\n##', body, re.DOTALL)
    if message_match:
        error_message = message_match.group(1).strip()[:500]

    file_match = re.search(r'File ["\']([^"\']+)["\']', body)
    if file_match:
        suspected_file = file_match.group(1)

    line_match = re.search(r'line (\d+)', body)
    if line_match:
        line_no = int(line_match.group(1))

    now = datetime.utcnow().isoformat()
    incident = Incident(
        incident_id=incident_id,
        source="github_issue",
        service="demo_service",
        service_name="demo_service",
        error_summary=ErrorSummary(
            error_type=error_type,
            message=error_message,
            suspected_file=suspected_file,
            line_no=line_no,
            function=function,
            fingerprint=fingerprint,
        ),
        raw_traceback=body[:4000],
        created_at=now,
        updated_at=now,
        occurrence_count=1,
        issue_number=issue.number,
        issue_url=issue.html_url,
    )

    append_incident(incident)
    return incident


def update_incident_fields(
    incident_id: str,
    issue_number: Optional[int] = None,
    issue_url: Optional[str] = None,
    status: Optional[str] = None,
    path: Optional[str | Path] = None,
) -> None:
    """
    更新Incident的指定字段（如issue链接、状态等）并持久化到文件
    :param incident_id: Incident ID
    :param issue_number: GitHub Issue编号
    :param issue_url: GitHub Issue链接
    :param status: Incident状态
    :param path: 可选自定义路径
    """
    file_path = Path(path) if path else DEFAULT_INCIDENT_PATH
    incidents = load_incidents(path)
    
    for inc in incidents:
        if inc.incident_id == incident_id:
            if issue_number is not None:
                inc.issue_number = issue_number
            if issue_url is not None:
                inc.issue_url = issue_url
            if status is not None:
                inc.status = status
            inc.updated_at = datetime.now().isoformat()
            break
    
    # 全量重写文件
    _ensure_path_exists(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        for inc in incidents:
            f.write(inc.model_dump_json() + "\n")
