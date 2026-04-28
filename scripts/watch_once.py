import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.watcher import scan_service_logs_once
from autorepair.service_registry import get_default_service
from autorepair.adapters.feishu import send_incident_card
from autorepair.adapters.github import create_issue, create_label
from autorepair.diagnostics import run_basic_diagnostics
from autorepair.audit_store import append_audit_event
from autorepair.schemas import Incident

def create_github_issue_for_incident(incident: Incident) -> str:
    """为Incident创建GitHub Issue，返回Issue URL"""
    # 确保标签存在
    create_label("bug", "d73a4a", "Something isn't working")
    create_label("AutoRepair", "0366d6", "AutoRepair system generated issue")
    
    summary = incident.error_summary
    issue_title = f"[Bug] {incident.incident_id}: {summary.error_type} in {summary.suspected_file}"
    issue_body = f"""## Incident Information
- **Incident ID**: {incident.incident_id}
- **Service**: {incident.service_name or incident.service}
- **Error Type**: {summary.error_type}
- **Error Message**: {summary.message}
- **Location**: {summary.suspected_file}:{summary.line_no}
- **Occurrences**: {incident.occurrence_count}
- **First Seen**: {incident.created_at}

## Error Summary
{summary.message}

## Traceback
```
{incident.raw_traceback[:1500]}...
```
"""
    issue = create_issue(issue_title, issue_body, labels=["bug", "AutoRepair"])
    return issue.html_url if issue else ""


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
            
            # 为新创建的Incident创建GitHub Issue
            issue_url = create_github_issue_for_incident(incident)
            if issue_url:
                incident.issue_url = issue_url
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
