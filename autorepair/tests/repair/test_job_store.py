import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.repair.job_store import (
    create_repair_job,
    find_active_job_by_incident,
    find_active_job_by_issue,
    find_oldest_queued_job,
    load_repair_jobs,
    update_repair_job,
)
from autorepair.repair.schemas import RepairJobStatus


def test_create_repair_job_prevents_duplicate_active_issue_and_incident():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", temp_path):
            first = create_repair_job(
                incident_id="INC-1",
                issue_number=10,
                repo_owner="owner",
                repo_name="repo",
                base_branch="main",
                repair_branch="autorepair/inc-1-bug",
                worktree_path=".worktrees/INC-1",
                policy_decision="accepted",
                risk_level="low",
            )
            same_issue = create_repair_job(
                incident_id="INC-2",
                issue_number=10,
                repo_owner="owner",
                repo_name="repo",
                base_branch="main",
                repair_branch="autorepair/inc-2-bug",
                worktree_path=".worktrees/INC-2",
                policy_decision="accepted",
                risk_level="low",
            )
            same_incident = create_repair_job(
                incident_id="INC-1",
                issue_number=11,
                repo_owner="owner",
                repo_name="repo",
                base_branch="main",
                repair_branch="autorepair/inc-1-other",
                worktree_path=".worktrees/INC-1-other",
                policy_decision="accepted",
                risk_level="low",
            )

            assert same_issue.job_id == first.job_id
            assert same_incident.job_id == first.job_id
            assert len(load_repair_jobs()) == 1
            assert find_active_job_by_issue(10).job_id == first.job_id
            assert find_active_job_by_incident("INC-1").job_id == first.job_id
    finally:
        temp_path.unlink()


def test_update_job_and_find_oldest_queued_job():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", temp_path):
            job = create_repair_job(
                incident_id="INC-1",
                issue_number=10,
                repo_owner="owner",
                repo_name="repo",
                base_branch="main",
                repair_branch="autorepair/inc-1-bug",
                worktree_path=".worktrees/INC-1",
                policy_decision="accepted",
                risk_level="low",
            )
            assert find_oldest_queued_job().job_id == job.job_id

            updated = update_repair_job(job.job_id, status=RepairJobStatus.running, last_error="dry-run")

            assert updated.status == RepairJobStatus.running
            assert updated.last_error == "dry-run"
            assert find_oldest_queued_job() is None
    finally:
        temp_path.unlink()
