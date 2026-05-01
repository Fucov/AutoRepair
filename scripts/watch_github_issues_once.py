import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.github import (
    add_labels,
    comment_issue,
    list_open_bug_issues,
    replace_autorepair_status_label,
)
from autorepair.incident_store import upsert_incident_from_issue
from autorepair.issue_validator import validate_bug_issue
from autorepair.repair.job_store import find_active_job_by_issue
from autorepair.repair.orchestrator import process_issue_for_repair


def main() -> int:
    print("开始扫描GitHub Issue...")
    issues = list_open_bug_issues()
    if not issues:
        print("未发现需要处理的Bug Issue")
        return 0

    print(f"发现 {len(issues)} 个未处理的Bug Issue")
    processed_count = 0
    skipped_count = 0
    
    for issue in issues:
        print(f"\n处理Issue #{issue.number}: {issue.title}")
        validation = validate_bug_issue(issue)
        
        if not validation.is_valid:
            comment_issue(issue.number, validation.suggested_comment)
            status = "autorepair:human-required" if "high risk" in validation.reason.lower() else "autorepair:needs-info"
            replace_autorepair_status_label(issue.number, status)
            print(f"Issue #{issue.number} 信息不足或需人工处理: {validation.reason}")
            skipped_count += 1
            continue

        # 检查是否已经有active job
        existing_job = find_active_job_by_issue(issue.number)
        if existing_job:
            print(f"Issue #{issue.number} 已有active RepairJob: {existing_job.job_id} (status: {existing_job.status.value})")
            skipped_count += 1
            continue

        # 对合理的Issue，创建或关联Incident
        incident = upsert_incident_from_issue(issue)
        print(f"Issue #{issue.number} 关联Incident: {incident.incident_id}")

        # 进入Triage/RepairJob队列
        replace_autorepair_status_label(issue.number, "autorepair:triage")
        job = process_issue_for_repair(issue.number)
        if job:
            print(f"Issue #{issue.number} 已进入RepairJob队列: {job.job_id}")
            processed_count += 1
        else:
            print(f"Issue #{issue.number} triage未通过或policy被拒绝")
            skipped_count += 1

    print(f"\n所有Issue处理完成: 处理{processed_count}个, 跳过{skipped_count}个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
