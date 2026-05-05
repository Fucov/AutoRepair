import logging
from datetime import datetime
from typing import Optional, List, Tuple
from pathlib import Path

from .config import LOG_PATH
from .log_parser import read_latest_traceback, extract_error_summary, extract_traceback_blocks, read_new_log_text
from .watch_state import get_log_offset, set_log_offset
from .schemas import Incident, TargetService
from .incident_store import DEFAULT_INCIDENT_PATH, has_fingerprint, append_incident, upsert_incident_by_fingerprint
from .watch_state import DEFAULT_WATCH_STATE_PATH
from .audit_store import append_audit_event

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


def scan_new_log_events_once(log_path: Optional[str] = None, service: Optional[TargetService] = None) -> List[Tuple[Incident, str]]:
    """
    增量扫描日志中的新增错误事件，支持重复错误聚合
    :param log_path: 可选自定义日志路径
    :param service: 可选目标服务配置，传入时会设置 service_id/service_name
    :return: 列表，每个元素是(Incident对象, action: "created"|"updated")
    """
    log_path = log_path or LOG_PATH
    results = []
    
    # 1. 获取上次读取偏移量
    offset = get_log_offset(log_path, DEFAULT_WATCH_STATE_PATH)
    
    # 2. 读取新增日志内容
    new_text, new_offset = read_new_log_text(log_path, offset)
    if not new_text:
        # 没有新增内容，更新偏移量后直接返回
        set_log_offset(log_path, new_offset, DEFAULT_WATCH_STATE_PATH)
        return results
    
    # 3. 提取所有Traceback块
    traceback_blocks = extract_traceback_blocks(new_text)
    if not traceback_blocks:
        set_log_offset(log_path, new_offset, DEFAULT_WATCH_STATE_PATH)
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
            service_name = service.name if service else "demo_service"
            incident = Incident(
                incident_id=incident_id,
                source="local_log",
                service=service_name,
                status="NEW",
                error_summary=error_summary,
                raw_traceback=traceback,
                created_at=created_at,
                updated_at=created_at,
                source_ref=source_ref,
                service_id=service.service_id if service else None,
                service_name=service_name,
            )
            
            final_incident, action = upsert_incident_by_fingerprint(incident, DEFAULT_INCIDENT_PATH)
            results.append((final_incident, action))
            
            # 写入审计记录
            if action == "created":
                append_audit_event("incident_created", final_incident.incident_id, {
                    "error_type": final_incident.error_summary.error_type,
                    "fingerprint": final_incident.error_summary.fingerprint,
                    "source": final_incident.source
                })
            elif action == "updated":
                append_audit_event("incident_updated", final_incident.incident_id, {
                    "occurrence_count": final_incident.occurrence_count
                })
            
        except Exception as e:
            logger.warning(f"处理Traceback块失败: {str(e)}")
            continue
    
    # 5. 更新偏移量
    set_log_offset(log_path, new_offset, DEFAULT_WATCH_STATE_PATH)
    
    return results


def scan_service_logs_once(service: TargetService) -> List[Tuple[Incident, str]]:
    """
    扫描指定服务的所有日志路径，生成新增或更新的Incident
    :param service: 目标服务配置
    :return: 列表，每个元素是(Incident对象, action: "created"|"updated")
    """
    results = []
    
    for log_path in service.log_paths:
        log_results = scan_new_log_events_once(log_path, service=service)
        
        for incident, action in log_results:
            results.append((incident, action))
    
    return results
