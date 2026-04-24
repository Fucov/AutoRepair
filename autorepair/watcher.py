import logging
from datetime import datetime
from typing import Optional, List, Tuple
from pathlib import Path

from .config import LOG_PATH
from .log_parser import read_latest_traceback, extract_error_summary, extract_traceback_blocks, read_new_log_text
from .watch_state import get_log_offset, set_log_offset
from .schemas import Incident
from .incident_store import has_fingerprint, append_incident, upsert_incident_by_fingerprint

logger = logging.getLogger(__name__)


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


def scan_new_log_events_once(log_path: Optional[str] = None) -> List[Tuple[Incident, str]]:
    """
    增量扫描日志中的新增错误事件，支持重复错误聚合
    :param log_path: 可选自定义日志路径
    :return: 列表，每个元素是(Incident对象, action: "created"|"updated")
    """
    log_path = log_path or LOG_PATH
    results = []
    
    # 1. 获取上次读取偏移量
    offset = get_log_offset(log_path)
    
    # 2. 读取新增日志内容
    new_text, new_offset = read_new_log_text(log_path, offset)
    if not new_text:
        # 没有新增内容，更新偏移量后直接返回
        set_log_offset(log_path, new_offset)
        return results
    
    # 3. 提取所有Traceback块
    traceback_blocks = extract_traceback_blocks(new_text)
    if not traceback_blocks:
        set_log_offset(log_path, new_offset)
        return results
    
    # 4. 处理每个Traceback
    now = datetime.now()
    resolved_log_path = str(Path(log_path).resolve())
    
    for i, traceback in enumerate(traceback_blocks):
        try:
            # 提取错误摘要
            error_summary = extract_error_summary(traceback)
            if not error_summary:
                continue
            
            # 生成source_ref
            source_ref = f"local_log:{resolved_log_path}:{offset + i}"
            
            # 生成Incident ID
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M%S")
            short_fingerprint = error_summary.fingerprint[:6]
            incident_id = f"INC-{date_str}-{time_str}-{short_fingerprint}"
            created_at = now.isoformat()
            
            # 创建Incident对象
            incident = Incident(
                incident_id=incident_id,
                source="local_log",
                service="demo_service",
                status="NEW",
                error_summary=error_summary,
                raw_traceback=traceback,
                created_at=created_at,
                updated_at=created_at,
                source_ref=source_ref
            )
            
            # 新增或更新Incident
            final_incident, action = upsert_incident_by_fingerprint(incident)
            results.append((final_incident, action))
            
        except Exception as e:
            logger.warning(f"处理Traceback块失败: {str(e)}")
            continue
    
    # 5. 更新偏移量
    set_log_offset(log_path, new_offset)
    
    return results
