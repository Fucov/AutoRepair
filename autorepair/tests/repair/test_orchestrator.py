import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.adapters.github import _load_mock_issues, _save_mock_issue
from autorepair.repair.job_store import load_repair_jobs
from autorepair.repair.orchestrator import process_issue_for_repair


def test_process_issue_for_repair_creates_queued_job_for_valid_issue():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as issue_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as job_file:
        issue_path = Path(issue_file.name)
        job_path = Path(job_file.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", issue_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""), \
             patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("autorepair.repair.orchestrator.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("autorepair.adapters.feishu.send_repair_plan_ready"):
            _save_mock_issue({
                "number": 21,
                "title": "[Bug] ticket SLA TypeError",
                "body": "Incident ID: INC-21\nFingerprint: fp21\nSteps to Reproduce\nExpected Behavior\nActual Behavior\nTypeError",
                "html_url": "mock://local/issue/21",
                "labels": ["bug", "source:issue"],
                "state": "open",
            })

            job = process_issue_for_repair(21)

            assert job is not None
            assert job.issue_number == 21
            assert job.status == "queued"
            assert len(load_repair_jobs(job_path)) == 1
            labels = _load_mock_issues()[0]["labels"]
            assert "autorepair:accepted" in labels
    finally:
        issue_path.unlink()
        job_path.unlink()


def test_process_issue_for_repair_marks_needs_info_for_invalid_issue():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as issue_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as job_file:
        issue_path = Path(issue_file.name)
        job_path = Path(job_file.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", issue_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""), \
             patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("autorepair.repair.orchestrator.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("autorepair.adapters.feishu.send_manual_intervention"):
            _save_mock_issue({
                "number": 22,
                "title": "[Bug] broken",
                "body": "Please fix.",
                "html_url": "mock://local/issue/22",
                "labels": ["bug"],
                "state": "open",
            })

            job = process_issue_for_repair(22)

            assert job is None
            issue = _load_mock_issues()[0]
            assert "autorepair:needs-info" in issue["labels"]
            assert len(issue["comments"]) == 1
            assert load_repair_jobs(job_path) == []
    finally:
        issue_path.unlink()
        job_path.unlink()
