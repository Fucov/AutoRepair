import logging
import json
from pathlib import Path
from typing import List, Dict, Optional
from pydantic import BaseModel
import httpx
import uuid

from autorepair.config import (
    GITHUB_TOKEN,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_API_BASE_URL,
    PROJECT_ROOT,
)

# Mock GitHub Issue 本地存储路径
MOCK_GITHUB_ISSUES_PATH = PROJECT_ROOT / "autorepair" / "records" / "mock_github_issues.jsonl"
from autorepair.bug_scenarios import get_scenario_by_id

logger = logging.getLogger(__name__)


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str
    html_url: str
    labels: List[str]
    state: str


def _is_github_configured() -> bool:
    """检查GitHub配置是否完整"""
    return all([GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO])


def _ensure_mock_file_exists() -> None:
    """确保mock GitHub Issue存储文件存在"""
    MOCK_GITHUB_ISSUES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MOCK_GITHUB_ISSUES_PATH.exists():
        with open(MOCK_GITHUB_ISSUES_PATH, "w", encoding="utf-8") as f:
            pass


def _load_mock_issues() -> List[Dict]:
    """加载本地mock Issue"""
    _ensure_mock_file_exists()
    issues = []
    with open(MOCK_GITHUB_ISSUES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                issues.append(json.loads(line))
    return issues


def _save_mock_issue(issue: Dict) -> None:
    """保存mock Issue到本地文件"""
    _ensure_mock_file_exists()
    with open(MOCK_GITHUB_ISSUES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(issue, ensure_ascii=False) + "\n")


def _update_mock_issue(issue_number: int, updates: Dict) -> None:
    """更新mock Issue"""
    issues = _load_mock_issues()
    updated = []
    for issue in issues:
        if issue["number"] == issue_number:
            issue.update(updates)
        updated.append(issue)
    
    with open(MOCK_GITHUB_ISSUES_PATH, "w", encoding="utf-8") as f:
        for issue in updated:
            f.write(json.dumps(issue, ensure_ascii=False) + "\n")


def _get_headers() -> Dict:
    """获取GitHub API请求头"""
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


def list_open_bug_issues() -> List[GitHubIssue]:
    """
    获取所有打开的Bug Issue
    过滤条件：标签包含bug，不包含autorepair:processing/autorepair:pr-created
    配置缺失时从本地mock文件读取
    """
    if not _is_github_configured():
        # 配置缺失时从本地mock文件读取
        logger.warning("GitHub配置不完整，从本地mock文件读取Issue")
        mock_issues = _load_mock_issues()
        issues = []
        for issue in mock_issues:
            labels = issue.get("labels", [])
            # 过滤已处理的issue
            if "autorepair:processing" in labels or "autorepair:pr-created" in labels:
                continue
            if issue.get("state") == "open" and "bug" in labels:
                issues.append(GitHubIssue(
                    number=issue["number"],
                    title=issue["title"],
                    body=issue["body"],
                    html_url=issue["html_url"],
                    labels=labels,
                    state=issue["state"]
                ))
        return issues

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
        params = {
            "state": "open",
            "labels": "bug",
            "per_page": 100
        }
        response = httpx.get(url, headers=_get_headers(), params=params, timeout=10)
        response.raise_for_status()
        issues_data = response.json()

        issues = []
        for issue in issues_data:
            labels = [label["name"] for label in issue["labels"]]
            # 过滤已处理的issue
            if "autorepair:processing" in labels or "autorepair:pr-created" in labels:
                continue
            issues.append(GitHubIssue(
                number=issue["number"],
                title=issue["title"],
                body=issue["body"] or "",
                html_url=issue["html_url"],
                labels=labels,
                state=issue["state"]
            ))
        return issues
    except Exception as e:
        logger.error(f"获取GitHub Issue列表失败: {str(e)}")
        return []


def create_demo_bug_issue(scenario_id: str) -> Optional[GitHubIssue]:
    """
    根据scenario_id创建演示用的Bug Issue
    配置缺失时打印mock信息并返回None
    """
    scenario = get_scenario_by_id(scenario_id)
    if not scenario:
        logger.error(f"未找到scenario_id: {scenario_id}")
        return None

    issue_title = f"[Bug] {scenario.title}"
    issue_body = f"""## Business Scenario
{scenario.title}

## Steps to Reproduce
1. 调用接口 {scenario.endpoint}
2. 传入对应参数

## Expected Behavior
{scenario.expected_behavior}

## Actual Behavior
触发 {scenario.expected_error_type}，返回500 Internal Server Error

## Error Hint
错误类型: {scenario.expected_error_type}
触发位置: 对应业务代码实现

## Target Test
```bash
{scenario.target_test_command}
```
"""

    if not _is_github_configured():
        # 配置缺失时，写入本地mock Issue存储
        print("\n" + "=" * 60)
        print("📝 Mock GitHub Issue (配置不完整，仅模拟创建)")
        print("=" * 60)
        print(f"Title: {issue_title}")
        print(f"Body:\n{issue_body}")
        print("=" * 60 + "\n")
        
        # 生成mock issue数据
        issue_number = int(uuid.uuid4().hex[:4], 16) % 1000 + 1  # 生成1-1000的随机Issue编号
        mock_issue = {
            "number": issue_number,
            "title": issue_title,
            "body": issue_body,
            "html_url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}",
            "labels": ["bug"],
            "state": "open",
            "comments": []
        }
        _save_mock_issue(mock_issue)
        
        return GitHubIssue(
            number=mock_issue["number"],
            title=mock_issue["title"],
            body=mock_issue["body"],
            html_url=mock_issue["html_url"],
            labels=mock_issue["labels"],
            state=mock_issue["state"]
        )

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
        payload = {
            "title": issue_title,
            "body": issue_body,
            "labels": ["bug"]
        }
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        issue_data = response.json()

        issue = GitHubIssue(
            number=issue_data["number"],
            title=issue_data["title"],
            body=issue_data["body"],
            html_url=issue_data["html_url"],
            labels=[label["name"] for label in issue_data["labels"]],
            state=issue_data["state"]
        )
        logger.info(f"成功创建GitHub Issue #{issue.number}: {issue.html_url}")
        return issue
    except Exception as e:
        logger.error(f"创建GitHub Issue失败: {str(e)}")
        return None


def mark_issue_processing(issue_number: int) -> None:
    """
    标记Issue为处理中，添加autorepair:processing标签
    配置缺失时更新本地mock Issue
    """
    if not _is_github_configured():
        logger.debug(f"Mock标记Issue #{issue_number}为处理中")
        # 更新本地mock Issue的标签
        issues = _load_mock_issues()
        for issue in issues:
            if issue["number"] == issue_number and "autorepair:processing" not in issue["labels"]:
                issue["labels"].append("autorepair:processing")
                _update_mock_issue(issue_number, {"labels": issue["labels"]})
                break
        return

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels"
        payload = {"labels": ["autorepair:processing"]}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"成功标记Issue #{issue_number}为处理中")
    except Exception as e:
        logger.error(f"标记Issue #{issue_number}失败: {str(e)}")


def comment_issue(issue_number: int, body: str) -> None:
    """
    给Issue添加评论
    配置缺失时保存评论到本地mock Issue
    """
    if not _is_github_configured():
        print("\n" + "=" * 60)
        print(f"💬 Mock GitHub Comment on Issue #{issue_number}")
        print("=" * 60)
        print(body)
        print("=" * 60 + "\n")
        
        # 保存评论到本地mock Issue
        issues = _load_mock_issues()
        for issue in issues:
            if issue["number"] == issue_number:
                if "comments" not in issue:
                    issue["comments"] = []
                issue["comments"].append({
                    "body": body,
                    "created_at": datetime.utcnow().isoformat()
                })
                _update_mock_issue(issue_number, {"comments": issue["comments"]})
                break
        return

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/comments"
        payload = {"body": body}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"成功给Issue #{issue_number}添加评论")
    except Exception as e:
        logger.error(f"给Issue #{issue_number}添加评论失败: {str(e)}")
