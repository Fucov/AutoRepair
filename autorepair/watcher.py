from datetime import datetime
from typing import Optional

from .config import LOG_PATH
from .log_parser import read_latest_traceback, extract_error_summary
from .schemas import Incident
from .incident_store import has_fingerprint, append_incident


def scan_latest_log_once(log_path: Optional[str] = None) -> Optional[Incident]:
    """
    单次扫描最新日志，生成新的Incident（去重）
    :param log_path: 可选自定义日志路径
    :return: 新生成的Incident对象，没有新incident则返回None
    """
    log_path = log_path or LOG_PATH
    
    # 1. 读取最新Traceback
    traceback = read_latest_traceback(log_path)
    if not traceback:
        return None
    
    # 2. 提取错误摘要
    error_summary = extract_error_summary(traceback)
    if not error_summary:
        return None
    
    # 3. 检查指纹是否已存在，去重
    if has_fingerprint(error_summary.fingerprint):
        return None
    
    # 4. 生成Incident ID: INC-YYYYMMDD-HHMMSS-短指纹
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    short_fingerprint = error_summary.fingerprint[:6]
    incident_id = f"INC-{date_str}-{time_str}-{short_fingerprint}"
    
    # 5. 创建Incident对象
    created_at = now.isoformat()
    incident = Incident(
        incident_id=incident_id,
        source="local_log",
        service="demo_service",
        status="NEW",
        error_summary=error_summary,
        raw_traceback=traceback,
        created_at=created_at,
        updated_at=created_at
    )
    
    # 6. 写入存储
    append_incident(incident)
    
    return incident
