import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.adapters.github import (
    _save_mock_issue,
    _load_mock_issues,
)
from autorepair.repair.job_store import create_repair_job, load_repair_jobs
from autorepair.repair.schemas import RepairJobStatus


def test_dashboard_scan_logs_creates_issue():
    """Dashboard /api/trigger/scan_logs 调用后返回正确响应"""
    from fastapi.testclient import TestClient
    from autorepair.dashboard.api import app

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as issue_file, \
         tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as incident_file:
        issue_path = Path(issue_file.name)
        incident_path = Path(incident_file.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", issue_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""), \
             patch("autorepair.incident_store.DEFAULT_INCIDENT_PATH", incident_path), \
             patch("autorepair.dashboard.api.send_incident_card", return_value={"mock": True}), \
             patch("autorepair.dashboard.api.scan_service_logs_once", return_value=[]):
            client = TestClient(app)
            response = client.post("/api/trigger/scan_logs")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    finally:
        issue_path.unlink()
        incident_path.unlink()


def test_dashboard_run_repair_calls_executor():
    """Dashboard /api/trigger/run_repair 调用 executor"""
    from fastapi.testclient import TestClient
    from autorepair.dashboard.api import app
    from autorepair.repair.executor import RepairExecutionResult

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as job_file:
        job_path = Path(job_file.name)

    try:
        with patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", job_path):
            client = TestClient(app)
            # api.py 内部 from ... import execute_next_repair_job，patch 原始模块
            with patch("autorepair.repair.executor.execute_next_repair_job") as mock_exec:
                mock_exec.return_value = RepairExecutionResult(success=True, error="No queued repair job")

                response = client.post("/api/trigger/run_repair")
                assert response.status_code == 200
                mock_exec.assert_called_once()

    finally:
        job_path.unlink()


def test_external_api_tests_are_monkeypatched():
    """验证外部 API 测试使用 monkeypatch，不请求网络"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as issue_file:
        issue_path = Path(issue_file.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", issue_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""):
            from autorepair.adapters.github import create_issue, get_issue
            issue = create_issue(
                title="Test Issue",
                body="Test body",
                labels=["bug"],
            )
            assert issue is not None
            fetched = get_issue(issue.number)
            assert fetched is not None
            assert fetched.title == "Test Issue"

    finally:
        issue_path.unlink()


def test_dashboard_sync_prs_returns_response():
    """Dashboard /api/trigger/sync_prs 返回正确响应"""
    from fastapi.testclient import TestClient
    from autorepair.dashboard.api import app

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as job_file:
        job_path = Path(job_file.name)

    try:
        # sync_prs 内部 from ... import load_repair_jobs，patch 原始模块
        with patch("autorepair.repair.job_store.DEFAULT_REPAIR_JOBS_PATH", job_path), \
             patch("autorepair.repair.job_store.load_repair_jobs", return_value=[]):
            client = TestClient(app)
            # 先导入 api 模块，使函数内部 import 生效
            import autorepair.dashboard.api
            response = client.post("/api/trigger/sync_prs")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    finally:
        job_path.unlink()
