import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.github import (
    comment_issue,
    list_open_bug_issues,
    replace_autorepair_status_label,
)
from autorepair.issue_validator import validate_bug_issue
from autorepair.repair.orchestrator import process_issue_for_repair


def main() -> int:
    print("开始扫描GitHub Issue...")
    issues = list_open_bug_issues()
    if not issues:
        print("未发现需要处理的Bug Issue")
        return 0

    print(f"发现 {len(issues)} 个未处理的Bug Issue")
    for issue in issues:
        print(f"处理Issue #{issue.number}: {issue.title}")
        validation = validate_bug_issue(issue)
        if not validation.is_valid:
            comment_issue(issue.number, validation.suggested_comment)
            status = "autorepair:human-required" if "high risk" in validation.reason.lower() else "autorepair:needs-info"
            replace_autorepair_status_label(issue.number, status)
            print(f"Issue #{issue.number} 信息不足或需人工处理: {validation.reason}")
            continue

        replace_autorepair_status_label(issue.number, "autorepair:triage")
        job = process_issue_for_repair(issue.number)
        if job:
            print(f"Issue #{issue.number} 已进入RepairJob队列: {job.job_id}")

    print("所有Issue处理完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
