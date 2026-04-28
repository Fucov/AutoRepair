import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.adapters.github import _load_mock_issues, _save_mock_issue, _save_mock_pr
from autorepair.repair.job_store import create_repair_job, load_repair_jobs, update_repair_job
from autorepair.repair.schemas import RepairJobStatus
from scripts.sync_pr_status_once import sync_once


def test_sync_merged_pr_closes_issue_and_job_without_unsafe_delete():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as issue_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as pr_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as job_file:
        issue_path = Path(issue_file.name)
        pr_path = Path(pr_file.name)
        job_path = Path(job_file.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", issue_path), \
             patch("autorepair.adapters.github.MOCK_GITHUB_PRS_PATH", pr_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""), \
             patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("scripts.sync_pr_status_once.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("scripts.sync_pr_status_once.remove_repair_worktree"), \
             patch("scripts.sync_pr_status_once.delete_local_branch"), \
             patch("scripts.sync_pr_status_once.delete_remote_branch"):
            _save_mock_issue({
                "number": 31,
                "title": "Bug",
                "body": "Body",
                "html_url": "mock://local/issue/31",
                "labels": ["bug", "autorepair:pr-ready"],
                "state": "open",
                "comments": [],
            })
            _save_mock_pr({
                "number": 5,
                "title": "Fix",
                "body": "Body",
                "html_url": "mock://local/pr/5",
                "state": "closed",
                "head": "autorepair/inc-31-bug",
                "base": "main",
                "merged": True,
            })
            job = create_repair_job(
                incident_id="INC-31",
                issue_number=31,
                repo_owner="owner",
                repo_name="repo",
                base_branch="main",
                repair_branch="autorepair/inc-31-bug",
                worktree_path=".worktrees/INC-31",
                policy_decision="accepted",
                risk_level="low",
                path=job_path,
            )
            update_repair_job(job.job_id, path=job_path, status=RepairJobStatus.pr_created, pr_number=5, pr_url="mock://local/pr/5")

            sync_once()

            assert _load_mock_issues()[0]["state"] == "closed"
            assert "autorepair:closed" in _load_mock_issues()[0]["labels"]
            assert load_repair_jobs(job_path)[0].status == RepairJobStatus.merged
    finally:
        issue_path.unlink()
        pr_path.unlink()
        job_path.unlink()


def test_sync_closed_unmerged_pr_marks_human_required():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as issue_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as pr_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as job_file:
        issue_path = Path(issue_file.name)
        pr_path = Path(pr_file.name)
        job_path = Path(job_file.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", issue_path), \
             patch("autorepair.adapters.github.MOCK_GITHUB_PRS_PATH", pr_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""), \
             patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("scripts.sync_pr_status_once.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("autorepair.adapters.feishu.send_manual_intervention"):
            _save_mock_issue({
                "number": 32,
                "title": "Bug",
                "body": "Body",
                "html_url": "mock://local/issue/32",
                "labels": ["bug", "autorepair:pr-ready"],
                "state": "open",
                "comments": [],
            })
            _save_mock_pr({
                "number": 6,
                "title": "Fix",
                "body": "Body",
                "html_url": "mock://local/pr/6",
                "state": "closed",
                "head": "autorepair/inc-32-bug",
                "base": "main",
                "merged": False,
            })
            job = create_repair_job(
                incident_id="INC-32",
                issue_number=32,
                repo_owner="owner",
                repo_name="repo",
                base_branch="main",
                repair_branch="autorepair/inc-32-bug",
                worktree_path=".worktrees/INC-32",
                policy_decision="accepted",
                risk_level="low",
                path=job_path,
            )
            update_repair_job(job.job_id, path=job_path, status=RepairJobStatus.pr_created, pr_number=6, pr_url="mock://local/pr/6")

            sync_once()

            assert _load_mock_issues()[0]["state"] == "open"
            assert "autorepair:human-required" in _load_mock_issues()[0]["labels"]
            assert load_repair_jobs(job_path)[0].status == RepairJobStatus.human_required
    finally:
        issue_path.unlink()
        pr_path.unlink()
        job_path.unlink()
