import logging
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel
import httpx
import uuid

from autorepair.config import (
    GITHUB_TOKEN,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_ASSIGNEE,
    GITHUB_API_BASE_URL,
    PROJECT_ROOT,
)

# Mock GitHub Issue 本地存储路径
MOCK_GITHUB_ISSUES_PATH = PROJECT_ROOT / "autorepair" / "records" / "mock_github_issues.jsonl"
MOCK_GITHUB_ISSUE_COMMENTS_PATH = PROJECT_ROOT / "autorepair" / "records" / "mock_github_issue_comments.jsonl"
MOCK_GITHUB_PRS_PATH = PROJECT_ROOT / "autorepair" / "records" / "mock_github_prs.jsonl"
from autorepair.bug_scenarios import get_scenario_by_id

logger = logging.getLogger(__name__)


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str
    html_url: str
    labels: List[str]
    state: str
    comments: List[Dict] = []
    assignees: List[str] = []


class IssueRef(BaseModel):
    number: int
    html_url: str


class PullRequestRef(BaseModel):
    number: int
    html_url: str
    state: str
    head: str
    base: str
    merged: bool = False


AUTOREPAIR_STATUS_LABELS = [
    "autorepair:triage",
    "autorepair:needs-info",
    "autorepair:accepted",
    "autorepair:repairing",
    "autorepair:pr-ready",
    "autorepair:human-required",
    "autorepair:closed",
    # Backward-compatible legacy labels.
    "autorepair:processing",
    "autorepair:pr-created",
]


AUTOREPAIR_LABELS = {
    "bug": ("d73a4a", "Something is not working"),
    "AutoRepair": ("0366d6", "AutoRepair system managed issue"),
    "source:runtime": ("c5def5", "Issue created from a runtime incident"),
    "source:issue": ("bfdadc", "Issue filed manually by a user"),
    "autorepair:triage": ("fbca04", "AutoRepair triage pending"),
    "autorepair:needs-info": ("fef2c0", "AutoRepair needs more information"),
    "autorepair:accepted": ("0e8a16", "AutoRepair accepted this issue"),
    "autorepair:repairing": ("1d76db", "AutoRepair repair is running"),
    "autorepair:pr-ready": ("5319e7", "AutoRepair pull request is ready"),
    "autorepair:human-required": ("b60205", "Human intervention is required"),
    "autorepair:closed": ("6a737d", "AutoRepair lifecycle is closed"),
    "risk:low": ("0e8a16", "Low-risk repair"),
    "risk:medium": ("fbca04", "Medium-risk repair"),
    "risk:high": ("b60205", "High-risk repair"),
}


def _is_github_configured() -> bool:
    """检查GitHub配置是否完整"""
    return all([GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO])


def _ensure_mock_file_exists() -> None:
    """确保mock GitHub Issue存储文件存在"""
    MOCK_GITHUB_ISSUES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MOCK_GITHUB_ISSUES_PATH.exists():
        with open(MOCK_GITHUB_ISSUES_PATH, "w", encoding="utf-8") as f:
            pass


def _ensure_mock_pr_file_exists() -> None:
    MOCK_GITHUB_PRS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MOCK_GITHUB_PRS_PATH.exists():
        with open(MOCK_GITHUB_PRS_PATH, "w", encoding="utf-8"):
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


def _load_mock_prs() -> List[Dict]:
    _ensure_mock_pr_file_exists()
    prs = []
    with open(MOCK_GITHUB_PRS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                prs.append(json.loads(line))
    return prs


def _save_mock_pr(pr: Dict) -> None:
    _ensure_mock_pr_file_exists()
    with open(MOCK_GITHUB_PRS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(pr, ensure_ascii=False) + "\n")


def _update_mock_pr(pr_number: int, updates: Dict) -> None:
    prs = _load_mock_prs()
    with open(MOCK_GITHUB_PRS_PATH, "w", encoding="utf-8") as f:
        for pr in prs:
            if pr["number"] == pr_number:
                pr.update(updates)
            f.write(json.dumps(pr, ensure_ascii=False) + "\n")


def _issue_from_dict(issue: Dict) -> GitHubIssue:
    return GitHubIssue(
        number=issue["number"],
        title=issue["title"],
        body=issue.get("body") or "",
        html_url=issue["html_url"],
        labels=issue.get("labels", []),
        state=issue.get("state", "open"),
        comments=issue.get("comments", []),
        assignees=issue.get("assignees", []),
    )


def _pr_from_dict(pr: Dict) -> PullRequestRef:
    return PullRequestRef(
        number=pr["number"],
        html_url=pr["html_url"],
        state=pr.get("state", "open"),
        head=pr["head"],
        base=pr["base"],
        merged=pr.get("merged", False),
    )


def _get_headers() -> Dict:
    """获取GitHub API请求头"""
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


def ensure_label(name: str, color: str = "ededed", description: str = "") -> bool:
    """
    创建GitHub标签，如果标签已存在则返回True
    配置缺失时返回True（mock模式）
    """
    if not _is_github_configured():
        return True
    
    try:
        # 先检查标签是否存在
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/labels/{name}"
        response = httpx.get(url, headers=_get_headers(), timeout=5)
        if response.status_code == 200:
            # 标签已存在
            return True
        
        # 标签不存在，创建新标签
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/labels"
        payload = {
            "name": name,
            "color": color.lstrip('#'),  # GitHub API不需要#前缀
            "description": description
        }
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"成功创建GitHub标签: {name}")
        return True
    except Exception as e:
        logger.error(f"创建GitHub标签失败: {str(e)}")
        return False


def create_label(name: str, color: str = "ededed", description: str = "") -> bool:
    """Backward-compatible alias for label creation."""
    return ensure_label(name, color, description)


def ensure_autorepair_labels() -> bool:
    ok = True
    for name, (color, description) in AUTOREPAIR_LABELS.items():
        ok = ensure_label(name, color, description) and ok
    return ok


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
                issues.append(_issue_from_dict(issue))
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
            "comments": [],
            "assignees": [GITHUB_ASSIGNEE] if GITHUB_ASSIGNEE else [],
        }
        _save_mock_issue(mock_issue)
        
        return _issue_from_dict(mock_issue)

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
            state=issue_data["state"],
            assignees=[assignee["login"] for assignee in issue_data.get("assignees", [])],
        )
        logger.info(f"成功创建GitHub Issue #{issue.number}: {issue.html_url}")
        return issue
    except Exception as e:
        logger.error(f"创建GitHub Issue失败: {str(e)}")
        return None


def create_issue(
    title: str,
    body: str,
    labels: List[str] = None,
) -> Optional[GitHubIssue]:
    """
    通用创建Issue函数
    配置缺失时写入本地mock Issue存储
    """
    labels = labels or ["bug"]
    
    if not _is_github_configured():
        # 配置缺失时，写入本地mock Issue存储
        print("\n" + "=" * 60)
        print("📝 Mock GitHub Issue (配置不完整，仅模拟创建)")
        print("=" * 60)
        print(f"Title: {title}")
        print(f"Body:\n{body}")
        print("=" * 60 + "\n")
        
        # 生成mock issue数据
        issue_number = int(uuid.uuid4().hex[:4], 16) % 1000 + 1  # 生成1-1000的随机Issue编号
        mock_url = f"https://github.com/{GITHUB_OWNER or 'owner'}/{GITHUB_REPO or 'repo'}/issues/{issue_number}"
        mock_issue = {
            "number": issue_number,
            "title": title,
            "body": body,
            "html_url": mock_url,
            "labels": labels,
            "state": "open",
            "comments": [],
            "assignees": [GITHUB_ASSIGNEE] if GITHUB_ASSIGNEE else ["AutoRepair"],
        }
        _save_mock_issue(mock_issue)
        
        return _issue_from_dict(mock_issue)

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
        payload = {
            "title": title,
            "body": body,
            "labels": labels
        }
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        if response.status_code == 422:
            error_data = response.json()
            logger.error(f"创建GitHub Issue失败 (422): {error_data.get('message', 'Unknown error')}")
            for err in error_data.get('errors', []):
                logger.error(f"  - {err.get('message', '')}")
            print(f"创建GitHub Issue失败: {response.text[:200]}")
            return None
        response.raise_for_status()
        issue_data = response.json()

        issue = GitHubIssue(
            number=issue_data["number"],
            title=issue_data["title"],
            body=issue_data["body"],
            html_url=issue_data["html_url"],
            labels=[label["name"] for label in issue_data["labels"]],
            state=issue_data["state"],
            assignees=[assignee["login"] for assignee in issue_data.get("assignees", [])],
        )
        logger.info(f"成功创建GitHub Issue #{issue.number}: {issue.html_url}")
        return issue
    except Exception as e:
        logger.error(f"创建GitHub Issue失败: {str(e)}")
        print(f"创建GitHub Issue失败: {str(e)}")
        return None


def add_labels(issue_number: int, labels: List[str]) -> bool:
    """
    给Issue添加标签
    配置缺失时更新本地mock Issue
    """
    if not _is_github_configured():
        logger.debug(f"Mock给Issue #{issue_number}添加标签: {labels}")
        # 更新本地mock Issue的标签
        issues = _load_mock_issues()
        for issue in issues:
            if issue["number"] == issue_number:
                issue.setdefault("labels", [])
                for label in labels:
                    if label not in issue["labels"]:
                        issue["labels"].append(label)
                _update_mock_issue(issue_number, {"labels": issue["labels"]})
                break
        return True

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels"
        payload = {"labels": labels}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"成功给Issue #{issue_number}添加标签: {labels}")
        return True
    except Exception as e:
        logger.error(f"给Issue #{issue_number}添加标签失败: {str(e)}")
        return False


def remove_labels(issue_number: int, labels: List[str]) -> bool:
    if not labels:
        return True

    if not _is_github_configured():
        issues = _load_mock_issues()
        for issue in issues:
            if issue["number"] == issue_number:
                existing = issue.get("labels", [])
                _update_mock_issue(issue_number, {"labels": [label for label in existing if label not in labels]})
                break
        return True

    ok = True
    for label in labels:
        try:
            url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels/{label}"
            response = httpx.delete(url, headers=_get_headers(), timeout=10)
            if response.status_code not in {200, 204, 404}:
                response.raise_for_status()
        except Exception as e:
            logger.error(f"移除Issue #{issue_number}标签失败: {label}: {str(e)}")
            ok = False
    return ok


def replace_autorepair_status_label(issue_number: int, new_status_label: str) -> bool:
    if new_status_label not in AUTOREPAIR_STATUS_LABELS:
        raise ValueError(f"Unknown AutoRepair status label: {new_status_label}")
    removed = remove_labels(issue_number, [label for label in AUTOREPAIR_STATUS_LABELS if label != new_status_label])
    added = add_labels(issue_number, [new_status_label])
    return removed and added


def get_issue(issue_number: int) -> Optional[GitHubIssue]:
    if not _is_github_configured():
        for issue in _load_mock_issues():
            if issue["number"] == issue_number:
                return _issue_from_dict(issue)
        return None

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}"
        response = httpx.get(url, headers=_get_headers(), timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        issue = response.json()
        return GitHubIssue(
            number=issue["number"],
            title=issue["title"],
            body=issue.get("body") or "",
            html_url=issue["html_url"],
            labels=[label["name"] for label in issue.get("labels", [])],
            state=issue["state"],
        )
    except Exception as e:
        logger.error(f"获取GitHub Issue #{issue_number}失败: {str(e)}")
        return None


def find_open_issue_by_fingerprint(fingerprint: str) -> Optional[GitHubIssue]:
    if not fingerprint:
        return None

    if not _is_github_configured():
        for issue in _load_mock_issues():
            if issue.get("state") == "open" and fingerprint in (issue.get("body") or ""):
                return _issue_from_dict(issue)
        return None

    for issue in list_open_bug_issues():
        if issue.state == "open" and fingerprint in (issue.body or ""):
            return issue
    return None


def mark_issue_processing(issue_number: int) -> None:
    """
    标记Issue为处理中，添加autorepair:processing标签
    配置缺失时更新本地mock Issue
    """
    add_labels(issue_number, ["autorepair:processing"])
    return

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels"
        payload = {"labels": ["autorepair:processing"]}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"成功标记Issue #{issue_number}为处理中")
    except Exception as e:
        logger.error(f"标记Issue #{issue_number}失败: {str(e)}")


def comment_issue(issue_number: int, body: str) -> bool:
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
        return True

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/comments"
        payload = {"body": body}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"成功给Issue #{issue_number}添加评论")
        return True
    except Exception as e:
        logger.error(f"给Issue #{issue_number}添加评论失败: {str(e)}")
        return False


def close_issue(issue_number: int) -> bool:
    if not _is_github_configured():
        _update_mock_issue(issue_number, {"state": "closed"})
        return True

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}"
        response = httpx.patch(url, headers=_get_headers(), json={"state": "closed"}, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"关闭Issue #{issue_number}失败: {str(e)}")
        return False


def create_pull_request(title: str, body: str, head: str, base: str) -> Optional[PullRequestRef]:
    if not _is_github_configured():
        existing = find_open_pr_for_branch(head)
        if existing:
            return existing
        prs = _load_mock_prs()
        number = max([pr.get("number", 0) for pr in prs] or [0]) + 1
        pr_url = f"https://github.com/{GITHUB_OWNER or 'owner'}/{GITHUB_REPO or 'repo'}/pull/{number}"
        pr = {
            "number": number,
            "title": title,
            "body": body,
            "html_url": pr_url,
            "state": "open",
            "head": head,
            "base": base,
            "merged": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        _save_mock_pr(pr)
        return _pr_from_dict(pr)

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}
        response = httpx.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        pr = response.json()
        return PullRequestRef(
            number=pr["number"],
            html_url=pr["html_url"],
            state=pr["state"],
            head=pr["head"]["ref"],
            base=pr["base"]["ref"],
            merged=pr.get("merged", False),
        )
    except Exception as e:
        logger.error(f"创建PR失败: {str(e)}")
        return None


def get_pull_request(pr_number: int) -> Optional[PullRequestRef]:
    if not _is_github_configured():
        for pr in _load_mock_prs():
            if pr["number"] == pr_number:
                return _pr_from_dict(pr)
        return None

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_number}"
        response = httpx.get(url, headers=_get_headers(), timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        pr = response.json()
        return PullRequestRef(
            number=pr["number"],
            html_url=pr["html_url"],
            state=pr["state"],
            head=pr["head"]["ref"],
            base=pr["base"]["ref"],
            merged=pr.get("merged", False),
        )
    except Exception as e:
        logger.error(f"获取PR #{pr_number}失败: {str(e)}")
        return None


def find_open_pr_for_branch(branch: str) -> Optional[PullRequestRef]:
    if not _is_github_configured():
        for pr in _load_mock_prs():
            if pr.get("head") == branch and pr.get("state") == "open":
                return _pr_from_dict(pr)
        return None

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
        params = {"state": "open", "head": f"{GITHUB_OWNER}:{branch}", "per_page": 10}
        response = httpx.get(url, headers=_get_headers(), params=params, timeout=10)
        response.raise_for_status()
        for pr in response.json():
            return PullRequestRef(
                number=pr["number"],
                html_url=pr["html_url"],
                state=pr["state"],
                head=pr["head"]["ref"],
                base=pr["base"]["ref"],
                merged=pr.get("merged", False),
            )
    except Exception as e:
        logger.error(f"查询分支PR失败: {branch}: {str(e)}")
    return None
