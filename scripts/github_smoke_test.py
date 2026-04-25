import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autorepair.adapters.github import create_issue, list_open_bug_issues, comment_issue, add_labels, create_label, _is_github_configured
from autorepair.config import config

def github_smoke_test():
    print("=== GitHub Smoke Test ===")
    
    # 先输出模式
    if _is_github_configured():
        print("GitHub mode: real")
    else:
        missing = []
        if not config.GITHUB_TOKEN:
            missing.append("GITHUB_TOKEN")
        if not config.GITHUB_OWNER:
            missing.append("GITHUB_OWNER")
        if not config.GITHUB_REPO:
            missing.append("GITHUB_REPO")
        print(f"GitHub mode: mock, reason: missing {', '.join(missing)}")
    
    # 1. 创建Issue
    title = "[SmokeTest] AutoRepair GitHub integration"
    body = "这是 AutoRepair 的 GitHub API 冒烟测试。\n\n测试内容包括：创建Issue、扫描Issue、添加评论、添加标签。"
    
    issue = create_issue(title, body, labels=["bug"])
    if not issue:
        print("Failed to create issue")
        return None
    
    print(f"\nCreated Issue: #{issue.number}")
    print(f"Issue URL: {issue.html_url}")
    
    # 2. 扫描开放Issue
    issues = list_open_bug_issues()
    found = any(i.number == issue.number for i in issues)
    print(f"\nScan result: Issue {'found' if found else 'not found'} in open bug issues")
    
    # 3. 添加评论
    comment_issue(issue.number, "AutoRepair GitHub smoke test completed.")
    print(f"\nComment result: success")
    
    # 4. 添加标签，如果标签不存在则先创建
    try:
        label_result = add_labels(issue.number, ["autorepair:smoke-test"])
        if not label_result:
            # 标签不存在，尝试创建
            print("Label autorepair:smoke-test not found, trying to create...")
            create_result = create_label(
                name="autorepair:smoke-test",
                color="f2994a",
                description="AutoRepair smoke test label"
            )
            if create_result:
                print("Label created successfully, retrying add label...")
                label_result = add_labels(issue.number, ["autorepair:smoke-test"])
            else:
                print("Failed to create label, skipping label add")
        print(f"Label result: {'success' if label_result else 'failed'}")
    except Exception as e:
        print(f"Label result: failed: {str(e)}")
    
    print("\n=== Smoke test completed ===")
    return issue

if __name__ == "__main__":
    github_smoke_test()
