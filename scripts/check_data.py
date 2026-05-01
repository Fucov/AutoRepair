import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.incident_store import load_incidents
from autorepair.repair.job_store import load_repair_jobs
from autorepair.adapters.github import _load_mock_issues, _load_mock_prs

print("=" * 60)
print("数据存储检查")
print("=" * 60)

# 检查incidents
incidents = load_incidents()
print(f"Incidents数量: {len(incidents)}")
for inc in incidents[-3:]:
    print(f"  - {inc.incident_id}: {inc.error_summary.error_type} @ {inc.created_at} (Issue: #{inc.issue_number})")

# 检查issues
issues = _load_mock_issues()
print(f"\nIssues数量: {len(issues)}")
for issue in issues[-3:]:
    print(f"  - #{issue['number']}: {issue['title']} ({issue['state']})")

# 检查jobs
jobs = load_repair_jobs()
print(f"\nRepair Jobs数量: {len(jobs)}")
for job in jobs[-3:]:
    print(f"  - {job.job_id}: {job.status.value} (Issue: #{job.issue_number})")

# 检查PRs
prs = _load_mock_prs()
print(f"\nPRs数量: {len(prs)}")
for pr in prs[-3:]:
    print(f"  - #{pr['number']}: {pr['title']} (merged: {pr.get('merged', False)})")

print("\n" + "=" * 60)
print("检查完成！")
