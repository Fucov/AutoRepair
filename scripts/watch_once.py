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
    
    for incident, action in results:
        summary = incident.error_summary
        prefix = "[created]" if action == "created" else "[updated]"
        print(f"{prefix} {incident.incident_id} {summary.error_type} {summary.suspected_file}:{summary.line_no} occurrence_count={incident.occurrence_count}")
        
        # 只有新创建的Incident才发送飞书卡片
        if action == "created":
            send_incident_card(incident)
