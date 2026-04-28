#!/usr/bin/env python3
"""
定时查询GitHub Issue，执行第二次审查并触发自动修复
"""
import sys
import time
from pathlib import Path
from typing import List

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.github import list_open_bug_issues, GitHubIssue, _update_mock_issue
from autorepair.adapters.feishu import send_template_card
from autorepair.cards import (
    build_repair_plan_ready_variables,
    build_manual_intervention_variables
)
from autorepair.diagnostics import run_basic_diagnostics
from autorepair.service_registry import get_default_service
from autorepair.audit_store import append_audit_event

logger = print


def should_attempt_fix(issue: GitHubIssue) -> bool:
    """
    第二次审查逻辑：判断Issue是否适合自动修复
    返回True表示可以尝试修复，False表示需要人工介入
    """
    # 检查标签是否符合要求
    if "bug" not in issue.labels or "AutoRepair" not in issue.labels:
        return False
    
    # 检查是否包含不需要自动修复的标签
    if "invalid" in issue.labels or "wontfix" in issue.labels or "question" in issue.labels:
        return False
    
    # 简单规则：标题包含特定关键词的适合自动修复
    keywords = ["TypeError", "AttributeError", "IndexError", "KeyError", "ZeroDivisionError", "bug"]
    for keyword in keywords:
        if keyword.lower() in issue.title.lower():
            return True
    
    # 检查Body中是否包含Traceback信息
    if "Traceback" in issue.body or "File \"" in issue.body or "line " in issue.body:
        return True
    
    return False


def mark_issue_processing(issue: GitHubIssue) -> None:
    """标记Issue为处理中，避免重复处理"""
    # 在真实GitHub环境中需要调用API添加标签，这里简化处理
    if hasattr(issue, 'number'):
        # 对于mock模式，更新本地文件
        _update_mock_issue(issue.number, {
            "labels": issue.labels + ["autorepair:processing"]
        })
    logger.info(f"Marked issue #{issue.number} as processing")


def process_issue(issue: GitHubIssue) -> None:
    """处理单个Issue"""
    logger.info(f"\nProcessing issue #{issue.number}: {issue.title}")
    logger.info(f"Issue URL: {issue.html_url}")
    
    # 执行第二次审查
    if not should_attempt_fix(issue):
        # 不适合自动修复，发送人工介入卡片
        logger.info("Issue not suitable for automatic repair, sending manual intervention card")
        
        variables = build_manual_intervention_variables(
            incident_id=f"ISSUE-{issue.number}",
            service_name=get_default_service().name,
            human_reason="系统判断该问题不适合自动修复，需要人工介入处理",
            evidence_brief="Issue不符合自动修复规则或缺少必要的错误信息",
            suggested_action="请查看Issue详情，手动确认问题并处理",
            issue_url=issue.html_url,
            report_url=""
        )
        
        send_template_card("manual_intervention", variables)
        append_audit_event("manual_intervention_required", f"ISSUE-{issue.number}", {
            "issue_url": issue.html_url,
            "reason": "not_suitable_for_auto_fix"
        })
        return
    
    # 标记为处理中
    mark_issue_processing(issue)
    
    # 执行诊断
    logger.info("Running diagnostics for the issue...")
    service = get_default_service()
    # 这里可以从Issue中提取错误信息，构造诊断输入
    # 简化演示，直接使用模拟诊断结果
    diagnostic_result = {
        "root_cause": "代码中存在类型错误，导致运行时异常",
        "fix_strategy": "添加类型检查和空值判断，修复错误逻辑",
        "risk_level": "低风险",
        "policy_result": "允许进入自动修复"
    }
    
    # 发送修复计划准备完成卡片
    logger.info("Sending repair plan ready card")
    variables = build_repair_plan_ready_variables(
        incident_id=f"ISSUE-{issue.number}",
        service_name=service.name,
        root_cause=diagnostic_result["root_cause"],
        fix_strategy=diagnostic_result["fix_strategy"],
        risk_level=diagnostic_result["risk_level"],
        policy_result=diagnostic_result["policy_result"],
        report_url=issue.html_url
    )
    
    send_template_card("repair_plan_ready", variables)
    append_audit_event("repair_plan_generated", f"ISSUE-{issue.number}", {
        "issue_url": issue.html_url,
        "risk_level": diagnostic_result["risk_level"]
    })
    
    # 后续可以在这里继续执行实际的修复流程...
    logger.info("Repair plan generated, ready to execute automatic repair")


def main():
    """主函数，支持单次执行和持续运行模式"""
    import argparse
    parser = argparse.ArgumentParser(description="Watch GitHub issues for automatic repair")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode, check every 5 minutes")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    args = parser.parse_args()
    
    logger("=" * 70)
    logger("AutoRepair GitHub Issue Watcher")
    logger("=" * 70)
    
    while True:
        logger(f"\nChecking for open bug issues at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
        issues = list_open_bug_issues()
        
        if not issues:
            logger("No new bug issues found.")
        else:
            logger(f"Found {len(issues)} open bug issues:")
            for issue in issues:
                logger(f"  #{issue.number}: {issue.title}")
                try:
                    process_issue(issue)
                except Exception as e:
                    logger(f"Error processing issue #{issue.number}: {str(e)}")
                    import traceback
                    traceback.print_exc()
        
        if not args.daemon:
            break
            
        logger(f"\nWaiting {args.interval} seconds before next check...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
