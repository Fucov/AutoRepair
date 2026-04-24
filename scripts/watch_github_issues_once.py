import sys
import hashlib
from pathlib import Path
from datetime import datetime

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.github import list_open_bug_issues, mark_issue_processing, comment_issue
from autorepair.incident_store import append_incident, has_fingerprint
from autorepair.adapters.feishu import send_incident_card
from autorepair.schemas import Incident, ErrorSummary


def _generate_dummy_error_summary(issue_title: str, issue_number: int) -> ErrorSummary:
    """从Issue生成临时ErrorSummary（本阶段简化实现）"""
    error_type = "UnknownError"
    if "TypeError" in issue_title or "用户画像" in issue_title:
        error_type = "TypeError"
        message = "'NoneType' object is not subscriptable"
        suspected_file = "demo_service/service.py"
        line_no = 11
        function = "build_user_profile"
    elif "ZeroDivisionError" in issue_title or "订单" in issue_title:
        error_type = "ZeroDivisionError"
        message = "division by zero"
        suspected_file = "demo_service/order_service.py"
        line_no = 16
        function = "calculate_order_discount"
    else:
        error_type = "UnknownError"
        message = f"GitHub Issue #{issue_number}: {issue_title}"
        suspected_file = None
        line_no = None
        function = None
    
    # 生成指纹
    fingerprint_raw = f"{error_type}:{suspected_file}:{line_no}:{message}".encode('utf-8')
    fingerprint = hashlib.sha1(fingerprint_raw).hexdigest()[:12]
    
    return ErrorSummary(
        error_type=error_type,
        message=message,
        suspected_file=suspected_file,
        line_no=line_no,
        function=function,
        fingerprint=fingerprint
    )


if __name__ == "__main__":
    print("🔍 开始扫描GitHub Issue...")
    issues = list_open_bug_issues()
    
    if not issues:
        print("ℹ️  未发现需要处理的Bug Issue")
        sys.exit(0)
    
    print(f"发现 {len(issues)} 个未处理的Bug Issue")
    
    for issue in issues:
        print(f"\n处理Issue #{issue.number}: {issue.title}")
        
        # 生成ErrorSummary
        error_summary = _generate_dummy_error_summary(issue.title, issue.number)
        
        # 检查是否已经处理过
        if has_fingerprint(error_summary.fingerprint):
            print(f"✅ Issue #{issue.number} 已存在相同指纹的Incident，跳过")
            continue
        
        # 生成Incident ID
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        short_fingerprint = error_summary.fingerprint[:6]
        incident_id = f"INC-{date_str}-{time_str}-{short_fingerprint}"
        created_at = now.isoformat()
        
        # 创建Incident
        incident = Incident(
            incident_id=incident_id,
            source="github_issue",
            service="demo_service",
            status="NEW",
            error_summary=error_summary,
            raw_traceback=issue.body,
            created_at=created_at,
            updated_at=created_at,
            source_ref=issue.html_url,
            issue_number=issue.number,
            issue_url=issue.html_url
        )
        
        # 写入存储
        append_incident(incident)
        print(f"✅ 生成Incident: {incident_id}")
        
        # 标记Issue为处理中
        mark_issue_processing(issue.number)
        
        # 添加评论
        comment_body = f"""🤖 AutoRepair 已接收此问题并开始处理
Incident ID: `{incident_id}`
错误类型: `{error_summary.error_type}`
错误位置: `{error_summary.suspected_file}:{error_summary.line_no}`

当前状态：等待 Agent 分析与自动修复
"""
        comment_issue(issue.number, comment_body)
        
        # 发送飞书卡片
        send_incident_card(incident)
    
    print("\n🎉 所有Issue处理完成")
