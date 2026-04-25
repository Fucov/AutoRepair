import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.watcher import scan_new_log_events_once
from autorepair.adapters.feishu import send_incident_card

if __name__ == "__main__":
    results = scan_new_log_events_once()
    if not results:
        print("No new incident.")
        sys.exit(0)
    
    # 统计数据
    created_count = 0
    updated_count = 0
    feishu_sent_count = 0
    details = []
    
    for incident, action in results:
        summary = incident.error_summary
        if action == "created":
            created_count += 1
            prefix = "[created]"
            # 只有新创建的Incident才发送飞书卡片
            send_incident_card(incident)
            feishu_sent_count += 1
            detail = f"{prefix} {incident.incident_id} {summary.error_type} {summary.suspected_file}:{summary.line_no} occurrence_count={incident.occurrence_count}"
        else:
            updated_count += 1
            prefix = "[updated]"
            detail = f"{prefix} {incident.incident_id} occurrence_count {incident.occurrence_count - 1} -> {incident.occurrence_count}"
        details.append(detail)
    
    # 输出汇总
    print("\n" + "=" * 60)
    print("📊 Scan Summary")
    print("=" * 60)
    print(f"- Created incidents: {created_count}")
    print(f"- Updated occurrences: {updated_count}")
    print(f"- Feishu cards sent: {feishu_sent_count}")
    print("=" * 60)
    
    # 输出详情
    if details:
        print("\nDetails:")
        for detail in details:
            print(detail)
