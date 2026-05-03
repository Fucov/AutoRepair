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

def _sanitize_path(p: str) -> str:
    if not p:
        return p
    parts = p.replace("\\", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else p


def _sanitize_traceback(tb: str, max_lines: int = 10) -> str:
    lines = tb.strip().splitlines()
    kept = []
    for line in lines[:max_lines]:
        line = _sanitize_path(line)
        kept.append(line)
    if len(lines) > max_lines:
        kept.append(f"... (共 {len(lines)} 行，已截断)")
    return "\n".join(kept)


def render_diagnostic_report_plaintext(report: DiagnosticReportData) -> str:
    lines = [
        "=" * 50,
        "FeishuAutoRepair 故障诊断报告",
        "=" * 50,
        "",
        f"报告ID: {report.report_id}",
        f"事件ID: {report.incident_id}",
        f"服务名称: {report.service_name}",
        f"生成时间: {report.created_at}",
        "",
        "-" * 50,
        "Issue 信息",
        "-" * 50,
        f"Issue编号: #{report.issue_number}",
        f"Issue链接: {report.issue_url}",
        "",
        "-" * 50,
        "错误摘要",
        "-" * 50,
        report.error_brief,
        "",
        "-" * 50,
        "证据摘要",
        "-" * 50,
        report.evidence_summary,
        "",
        "-" * 50,
        "合理性检查",
        "-" * 50,
        report.validation_result,
        "",
        "-" * 50,
        "根因判断",
        "-" * 50,
        report.root_cause,
        "",
        "-" * 50,
        "修复策略",
        "-" * 50,
    ]
    for i, s in enumerate(report.repair_strategies, 1):
        lines.append(f"{i}. {s}")

    lines += [
        "",
        "-" * 50,
        "风险等级与准入结论",
        "-" * 50,
        f"风险等级: {report.risk_level}",
        f"准入结论: {report.policy_result}",
        "",
        "-" * 50,
        "下一步动作",
        "-" * 50,
    ]
    for i, s in enumerate(report.next_steps, 1):
        lines.append(f"{i}. {s}")

    if report.traceback_excerpt:
        lines += [
            "",
            "-" * 50,
            "Traceback 摘要 (已脱敏截断)",
            "-" * 50,
            _sanitize_traceback(report.traceback_excerpt),
        ]

    lines += [
        "",
        "=" * 50,
        "注意: 本报告包含脱敏后的诊断信息，不包含敏感凭据。",
        "=" * 50,
    ]
    return "\n".join(lines)
