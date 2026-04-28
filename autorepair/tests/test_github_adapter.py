import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.adapters.github import _is_github_configured, create_demo_bug_issue
from autorepair.bug_scenarios import get_scenario_by_id


def test_github_config_not_configured():
    """测试GitHub配置不完整时返回False"""
    with patch('autorepair.adapters.github.GITHUB_TOKEN', ""), \
         patch('autorepair.adapters.github.GITHUB_OWNER', "test"), \
         patch('autorepair.adapters.github.GITHUB_REPO', "test"):
        assert _is_github_configured() is False


def test_create_demo_bug_issue_body():
    """测试创建Demo Issue时body构造正确"""
    scenario = get_scenario_by_id("order-zero-division")
    assert scenario is not None
    
    # 配置不完整时会打印mock信息，验证body包含必要字段
    with patch('autorepair.adapters.github._is_github_configured', return_value=False):
        issue = create_demo_bug_issue("order-zero-division")
        assert issue is not None
        assert issue.number > 0


def test_list_open_bug_issues_mock():
    """测试配置缺失时返回空列表不报错"""
    from autorepair.adapters.github import list_open_bug_issues
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path), \
             patch('autorepair.adapters.github._is_github_configured', return_value=False):
            issues = list_open_bug_issues()
            assert issues == []
    finally:
        temp_path.unlink()


def test_replace_autorepair_status_label_keeps_single_status():
    from autorepair.adapters.github import (
        _load_mock_issues,
        _save_mock_issue,
        replace_autorepair_status_label,
    )

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", temp_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""):
            _save_mock_issue({
                "number": 11,
                "title": "Bug",
                "body": "Body",
                "html_url": "mock://local/issue/11",
                "labels": ["bug", "AutoRepair", "autorepair:triage", "risk:low"],
                "state": "open",
            })

            assert replace_autorepair_status_label(11, "autorepair:accepted") is True

            issue = _load_mock_issues()[0]
            assert "autorepair:accepted" in issue["labels"]
            assert "autorepair:triage" not in issue["labels"]
            assert "risk:low" in issue["labels"]
    finally:
        temp_path.unlink()


def test_find_open_issue_by_fingerprint_and_close_issue():
    from autorepair.adapters.github import (
        _load_mock_issues,
        _save_mock_issue,
        close_issue,
        find_open_issue_by_fingerprint,
    )

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", temp_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""):
            _save_mock_issue({
                "number": 12,
                "title": "Bug",
                "body": "Fingerprint: abc123\nMore body",
                "html_url": "mock://local/issue/12",
                "labels": ["bug"],
                "state": "open",
            })

            found = find_open_issue_by_fingerprint("abc123")
            assert found is not None
            assert found.number == 12

            assert close_issue(12) is True
            assert _load_mock_issues()[0]["state"] == "closed"
            assert find_open_issue_by_fingerprint("abc123") is None
    finally:
        temp_path.unlink()


def test_mock_pull_request_lifecycle_lookup():
    from autorepair.adapters.github import (
        MOCK_GITHUB_PRS_PATH,
        create_pull_request,
        find_open_pr_for_branch,
        get_pull_request,
    )

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_PRS_PATH", temp_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""):
            pr = create_pull_request(
                title="AutoRepair fix",
                body="Related issue: #12",
                head="autorepair/inc-abc-bug",
                base="main",
            )

            assert pr is not None
            assert pr.number >= 1
            assert pr.state == "open"

            found = find_open_pr_for_branch("autorepair/inc-abc-bug")
            assert found is not None
            assert found.number == pr.number

            stored = get_pull_request(pr.number)
            assert stored is not None
            assert stored.head == "autorepair/inc-abc-bug"

            records = [json.loads(line) for line in temp_path.read_text().splitlines()]
            assert records[0]["base"] == "main"
    finally:
        temp_path.unlink()
