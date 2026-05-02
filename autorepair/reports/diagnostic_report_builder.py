import uuid
from typing import Any
from .schemas import DiagnosticReportData
from ..adapters.github import GitHubIssue
from ..schemas import Incident

def build_diagnostic_report(
    issue: GitHubIssue,
    incident: Incident,
    validation_result: str,
    triage_result: Any,
    policy_result: str
) -> DiagnosticReportData:
    """构建诊断报告数据"""
    # 构造修复策略
    repair_strategies = [
        "最小修复策略：定位并修复导致错误的核心代码，最小化变更范围",
        "测试验证策略：补充单元测试覆盖错误场景，确保修复有效且不破坏现有功能",
        "风险控制策略：在隔离worktree中执行修复，不影响主分支，测试通过后才创建PR"
    ]
    
    # 构造下一步动作
    next_steps = [
        "系统已自动创建RepairJob，进入修复队列等待执行",
        "修复完成后将自动创建PR并通知相关人员",
        "PR审核通过后可手动合并到主分支"
    ]
    
    # 提取traceback摘要
    traceback_excerpt = incident.raw_traceback[:2000] if incident.raw_traceback else None
    
    # 根因和风险等级
    root_cause = triage_result.root_cause if hasattr(triage_result, 'root_cause') else "待进一步分析"
    risk_level = triage_result.risk_level if hasattr(triage_result, 'risk_level') else "medium"
    
    # 证据摘要
    evidence_summary = f"Issue标题：{issue.title}\n错误类型：{incident.error_summary.error_type}"
    if incident.error_summary.suspected_file:
        evidence_summary += f"\n疑似文件：{incident.error_summary.suspected_file}:{incident.error_summary.line_no or 'N/A'}"
    
    return DiagnosticReportData(
        report_id=f"REPORT-{uuid.uuid4().hex[:8]}",
        incident_id=incident.incident_id,
        issue_number=incident.issue_number,
        issue_url=incident.issue_url,
        service_name=incident.service_name or incident.service,
        error_brief=incident.error_summary.message[:200],
        evidence_summary=evidence_summary,
        validation_result=validation_result,
        root_cause=root_cause,
        repair_strategies=repair_strategies,
        risk_level=risk_level,
        policy_result=policy_result,
        next_steps=next_steps,
        traceback_excerpt=traceback_excerpt
    )

def render_diagnostic_report_markdown(report: DiagnosticReportData) -> str:
    """渲染诊断报告为Markdown格式"""
    md = f"""# 故障诊断报告

## 基本信息
- 报告ID：{report.report_id}
- 事件ID：{report.incident_id}
- 服务名称：{report.service_name}
- 生成时间：{report.created_at}

## Issue信息
- Issue编号：#{report.issue_number}
- Issue链接：[{report.issue_url}]({report.issue_url})

## 错误摘要
{report.error_brief}

## 证据摘要
{report.evidence_summary}

## 合理性检查结果
{report.validation_result}

## 根因判断
{report.root_cause}

## 修复策略
{chr(10).join([f"- {s}" for s in report.repair_strategies])}

## 风险等级
{report.risk_level}

## 准入结论
{report.policy_result}

## 下一步动作
{chr(10).join([f"- {s}" for s in report.next_steps])}
"""
    
    if report.traceback_excerpt:
        md += f"""
## Traceback摘要
```
{report.traceback_excerpt}
```
"""
    
    return md

def render_diagnostic_report_blocks(report: DiagnosticReportData) -> list[dict]:
    """渲染诊断报告为飞书文档块格式"""
    blocks = [
        {"type": "heading1", "heading1": {"elements": [{"type": "text", "text_run": {"content": "故障诊断报告"}}]}},
        {"type": "heading2", "heading2": {"elements": [{"type": "text", "text_run": {"content": "基本信息"}}]}},
        {"type": "paragraph", "paragraph": {"elements": [
            {"type": "text", "text_run": {"content": f"报告ID：{report.report_id}\n事件ID：{report.incident_id}\n服务名称：{report.service_name}\n生成时间：{report.created_at}"}}
        ]}},
        {"type": "heading2", "heading2": {"elements": [{"type": "text", "text_run": {"content": "Issue信息"}}]}},
        {"type": "paragraph", "paragraph": {"elements": [
            {"type": "text", "text_run": {"content": f"Issue编号：#{report.issue_number}\nIssue链接："}},
            {"type": "text", "text_run": {"content": report.issue_url, "link": {"url": report.issue_url}}}
        ]}},
        {"type": "heading2", "heading2": {"elements": [{"type": "text", "text_run": {"content": "错误摘要"}}]}},
        {"type": "paragraph", "paragraph": {"elements": [{"type": "text", "text_run": {"content": report.error_brief}}]}},
        {"type": "heading2", "heading2": {"elements": [{"type": "text", "text_run": {"content": "根因判断"}}]}},
        {"type": "paragraph", "paragraph": {"elements": [{"type": "text", "text_run": {"content": report.root_cause}}]}},
        {"type": "heading2", "heading2": {"elements": [{"type": "text", "text_run": {"content": "修复策略"}}]}},
    ]
    
    for strategy in report.repair_strategies:
        blocks.append({
            "type": "paragraph", 
            "paragraph": {"elements": [{"type": "text", "text_run": {"content": f"- {strategy}"}}]}
        })
    
    if report.traceback_excerpt:
        blocks.extend([
            {"type": "heading2", "heading2": {"elements": [{"type": "text", "text_run": {"content": "Traceback摘要"}}]}},
            {"type": "code_block", "code_block": {"language": "python", "elements": [{"type": "text", "text_run": {"content": report.traceback_excerpt}}]}}
        ])
    
    return blocks
