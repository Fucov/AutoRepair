import logging
from typing import List, Dict, Optional
from pydantic import BaseModel
import httpx

from autorepair.config import (
    GITHUB_TOKEN,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_API_BASE_URL,
)
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
    配置缺失时返回空列表
    """
    if not _is_github_configured():
        logger.warning("GitHub配置不完整，返回空Issue列表（mock模式）")
        return []

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
        print("\n" + "=" * 60)
        print("📝 Mock GitHub Issue (配置不完整，仅模拟创建)")
        print("=" * 60)
        print(f"Title: {issue_title}")
        print(f"Body:\n{issue_body}")
        print("=" * 60 + "\n")
        return None

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
    配置缺失时无操作
    """
    if not _is_github_configured():
        logger.debug(f"Mock标记Issue #{issue_number}为处理中")
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
    配置缺失时打印mock评论
    """
    if not _is_github_configured():
        print("\n" + "=" * 60)
        print(f"💬 Mock GitHub Comment on Issue #{issue_number}")
        print("=" * 60)
        print(body)
        print("=" * 60 + "\n")
        return

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/comments"
        payload = {"body": body}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"成功给Issue #{issue_number}添加评论")
    except Exception as e:
        logger.error(f"给Issue #{issue_number}添加评论失败: {str(e)}")
