import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.watcher import scan_service_logs_once
from autorepair.service_registry import get_default_service
from autorepair.adapters.feishu import send_incident_card
from autorepair.issue_manager import ensure_issue_for_incident
from autorepair.audit_store import append_audit_event


if __name__ == "__main__":
    # 获取默认服务
    service = get_default_service()
    print(f"Scanning service: {service.name} ({service.service_id})")
    
    # 扫描服务日志
    results = scan_service_logs_once(service)
    if not results:
        print("No new incident.")
        sys.exit(0)
    
    # 统计数据
    created_count = 0
    updated_count = 0
    feishu_sent_count = 0
    issue_created_count = 0
    details = []
    
    for incident, action in results:
        summary = incident.error_summary
        if action == "created":
            created_count += 1
            prefix = "[created]"
            
            issue_ref = ensure_issue_for_incident(incident, service)
            issue_url = issue_ref.html_url
            incident.issue_number = issue_ref.number
            incident.issue_url = issue_url
            if issue_url:
                issue_created_count += 1
                print(f"Created GitHub Issue: {issue_url}")
            
            # 发送飞书卡片（包含Issue链接）
            send_result = send_incident_card(incident)
            if send_result:
                feishu_sent_count += 1
            
            # 记录审计
            append_audit_event("incident_created", incident.incident_id, {
                "error_type": summary.error_type,
                "service": incident.service,
                "issue_url": issue_url
            })
            
            append_audit_event("feishu_card_sent" if not send_result.get("mock") else "feishu_card_mocked", 
                             incident.incident_id, {"card_type": "incident_detected"})
            
            detail = f"{prefix} {incident.incident_id} {summary.error_type} {incident.service_name} {summary.suspected_file}:{summary.line_no} occurrence_count={incident.occurrence_count}"
            if issue_url:
                detail += f" issue={issue_url}"
            details.append(detail)
            
        else:
            updated_count += 1
            prefix = "[updated]"
            detail = f"{prefix} {incident.incident_id} occurrence_count={incident.occurrence_count}"
            details.append(detail)
    
    print("=" * 60)
    print(f"- Service: {service.name}")
    print(f"- Created incidents: {created_count}")
    print(f"- Updated occurrences: {updated_count}")
    print(f"- GitHub Issues created: {issue_created_count}")
    print(f"- Feishu cards sent: {feishu_sent_count}")
    print("=" * 60)
    print("ℹ️ 注意：当前阶段仅创建Issue，不会自动执行修复，修复逻辑将在定时扫描Issue时触发")
    print("=" * 60)
    
    # 输出详情
    if details:
        print("\nDetails:")
        for detail in details:
            print(detail)
