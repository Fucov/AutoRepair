import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from autorepair.adapters.github import (
    _save_mock_issue,
    _load_mock_issues,
    _update_mock_issue,
    create_demo_bug_issue,
    list_open_bug_issues,
    mark_issue_processing,
    comment_issue
)


def test_mock_issue_save_load():
    """测试mock Issue的保存和加载"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        mock_issue = {
            "number": 123,
            "title": "Test Bug",
            "body": "Test Body",
            "html_url": "https://github.com/test/repo/issues/123",
            "labels": ["bug"],
            "state": "open",
            "comments": []
        }
        
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path):
            _save_mock_issue(mock_issue)
            loaded = _load_mock_issues()
            assert len(loaded) == 1
            assert loaded[0]["number"] == 123
            assert loaded[0]["title"] == "Test Bug"
    finally:
        temp_path.unlink()


def test_mock_issue_update():
    """测试mock Issue的更新"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        mock_issue = {
            "number": 123,
            "title": "Test Bug",
            "body": "Test Body",
            "html_url": "https://github.com/test/repo/issues/123",
            "labels": ["bug"],
            "state": "open"
        }
        
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path):
            _save_mock_issue(mock_issue)
            _update_mock_issue(123, {"title": "Updated Title", "labels": ["bug", "autorepair:processing"]})
            
            loaded = _load_mock_issues()
            assert len(loaded) == 1
            assert loaded[0]["title"] == "Updated Title"
            assert "autorepair:processing" in loaded[0]["labels"]
    finally:
        temp_path.unlink()


def test_create_demo_bug_issue_writes_to_mock_file():
    """测试创建演示Issue时会写入mock文件"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path), \
             patch('autorepair.adapters.github.GITHUB_TOKEN', ""), \
             patch('autorepair.adapters.github.GITHUB_OWNER', "test"), \
             patch('autorepair.adapters.github.GITHUB_REPO', "test"):
            
            issue = create_demo_bug_issue("ticket-timezone-sla")
            assert issue is not None
            
            loaded = _load_mock_issues()
            assert len(loaded) == 1
            assert loaded[0]["number"] == issue.number
            assert "带时区 SLA 截止时间导致工单创建失败" in loaded[0]["title"]
    finally:
        temp_path.unlink()


def test_list_open_bug_issues_from_mock():
    """测试从mock文件读取open状态的bug Issue"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        # 写入两个Issue，一个open，一个已处理
        issues = [
            {
                "number": 1,
                "title": "Open Bug",
                "body": "Open",
                "html_url": "https://github.com/test/repo/issues/1",
                "labels": ["bug"],
                "state": "open"
            },
            {
                "number": 2,
                "title": "Processing Bug",
                "body": "Processing",
                "html_url": "https://github.com/test/repo/issues/2",
                "labels": ["bug", "autorepair:processing"],
                "state": "open"
            },
            {
                "number": 3,
                "title": "Closed Bug",
                "body": "Closed",
                "html_url": "https://github.com/test/repo/issues/3",
                "labels": ["bug"],
                "state": "closed"
            }
        ]
        
        with open(temp_path, "w", encoding="utf-8") as f:
            for issue in issues:
                f.write(json.dumps(issue) + "\n")
        
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path), \
             patch('autorepair.adapters.github.GITHUB_TOKEN', ""), \
             patch('autorepair.adapters.github.GITHUB_OWNER', "test"), \
             patch('autorepair.adapters.github.GITHUB_REPO', "test"):
            
            open_issues = list_open_bug_issues()
            assert len(open_issues) == 1
            assert open_issues[0].number == 1
            assert open_issues[0].title == "Open Bug"
    finally:
        temp_path.unlink()


def test_mark_issue_processing_updates_mock():
    """测试标记处理中会更新mock Issue的标签"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        mock_issue = {
            "number": 123,
            "title": "Test Bug",
            "body": "Test",
            "html_url": "https://github.com/test/repo/issues/123",
            "labels": ["bug"],
            "state": "open"
        }
        
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path), \
             patch('autorepair.adapters.github.GITHUB_TOKEN', ""), \
             patch('autorepair.adapters.github.GITHUB_OWNER', "test"), \
             patch('autorepair.adapters.github.GITHUB_REPO', "test"):
            
            _save_mock_issue(mock_issue)
            mark_issue_processing(123)
            
            loaded = _load_mock_issues()
            assert "autorepair:processing" in loaded[0]["labels"]
    finally:
        temp_path.unlink()


def test_comment_issue_updates_mock_comments():
    """测试评论会保存到mock Issue的comments字段"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        mock_issue = {
            "number": 123,
            "title": "Test Bug",
            "body": "Test",
            "html_url": "https://github.com/test/repo/issues/123",
            "labels": ["bug"],
            "state": "open"
        }
        
        with patch('autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH', temp_path), \
             patch('autorepair.adapters.github.GITHUB_TOKEN', ""), \
             patch('autorepair.adapters.github.GITHUB_OWNER', "test"), \
             patch('autorepair.adapters.github.GITHUB_REPO', "test"):
            
            _save_mock_issue(mock_issue)
            comment_issue(123, "Test comment")
            
            loaded = _load_mock_issues()
            assert "comments" in loaded[0]
            assert len(loaded[0]["comments"]) == 1
            assert loaded[0]["comments"][0]["body"] == "Test comment"
    finally:
        temp_path.unlink()
