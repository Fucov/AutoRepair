import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.watcher import scan_service_logs_once
from autorepair.service_registry import get_default_service
from autorepair.adapters.feishu import send_incident_card
from autorepair.diagnostics import run_basic_diagnostics
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
    diagnostics_completed = 0
    details = []
    
    for incident, action in results:
        summary = incident.error_summary
        if action == "created":
            created_count += 1
            prefix = "[created]"
            # 只有新创建的Incident才发送飞书卡片
            send_incident_card(incident)
            feishu_sent_count += 1
            
            # 记录飞书发送审计
            append_audit_event("feishu_card_sent" if send_incident_card.__name__ != "mock_send" else "feishu_card_mocked", 
                             incident.incident_id, {"card_type": "incident_created"})
            
            # 运行诊断
            try:
                diagnostic_report = run_basic_diagnostics(incident, service)
                diagnostics_completed += 1
                
                # 记录诊断完成审计
                append_audit_event("diagnostic_completed", incident.incident_id, {
                    "classification": diagnostic_report.classification,
                    "fixability": diagnostic_report.fixability
                })
                
                # 提取检查结果
                healthcheck_status = next((c.status for c in diagnostic_report.checks if c.name == "healthcheck"), "unknown")
                repo_check_status = next((c.status for c in diagnostic_report.checks if c.name == "repo_check"), "unknown")
                
                detail = f"{prefix} {incident.incident_id} {summary.error_type} {incident.service_name} {summary.suspected_file}:{summary.line_no} occurrence_count={incident.occurrence_count}"
                detail += f"\n  diagnosis: {diagnostic_report.classification} / {diagnostic_report.fixability}"
                detail += f"\n  healthcheck: {healthcheck_status}"
                detail += f"\n  repo_check: {repo_check_status}"
            except Exception as e:
                detail = f"{prefix} {incident.incident_id} {summary.error_type} {incident.service_name} {summary.suspected_file}:{summary.line_no} occurrence_count={incident.occurrence_count}"
                detail += f"\n  diagnosis failed: {str(e)}"
        else:
            updated_count += 1
            prefix = "[updated]"
            detail = f"{prefix} {incident.incident_id} occurrence_count {incident.occurrence_count - 1} -> {incident.occurrence_count}"
        details.append(detail)
    
    # 输出汇总
    print("\n" + "=" * 60)
    print("📊 Scan Summary")
    print("=" * 60)
    print(f"- Service: {service.name}")
    print(f"- Created incidents: {created_count}")
    print(f"- Updated occurrences: {updated_count}")
    print(f"- Feishu cards sent: {feishu_sent_count}")
    print(f"- Diagnostics completed: {diagnostics_completed}")
    print("=" * 60)
    
    # 输出详情
    if details:
        print("\nDetails:")
        for detail in details:
            print(detail)
