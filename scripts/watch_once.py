import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.watcher import scan_latest_log_once

if __name__ == "__main__":
    incident = scan_latest_log_once()
    if incident:
        summary = incident.error_summary
        print(f"发现新 Incident:")
        print(f"  incident_id: {incident.incident_id}")
        print(f"  error_type: {summary.error_type}")
        print(f"  suspected_file: {summary.suspected_file}")
        print(f"  line_no: {summary.line_no}")
        print(f"  function: {summary.function}")
        print(f"  fingerprint: {summary.fingerprint}")
    else:
        print("No new incident.")
