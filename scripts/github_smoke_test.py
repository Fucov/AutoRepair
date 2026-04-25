import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from autorepair.adapters.github import create_issue, list_open_bug_issues, comment_issue, add_labels, _is_github_configured

load_dotenv()

def github_smoke_test():
    print("=== GitHub Smoke Test ===")
    
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
    
    # 4. 添加标签
    try:
        label_result = add_labels(issue.number, ["autorepair:smoke-test"])
        print(f"Label result: {'success' if label_result else 'failed'}")
    except Exception as e:
        print(f"Label result: failed (label may not exist: {str(e)})")
    
    print("\n=== Smoke test completed ===")
    return issue

if __name__ == "__main__":
    github_smoke_test()
