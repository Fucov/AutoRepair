#!/usr/bin/env python3
"""
飞书卡片变量构造器
每张卡片变量数不超过10个，仅展示摘要信息，详细信息放到报告/Issue/PR链接中
"""
from typing import Dict, Optional, Any

# 卡片允许的变量key集合常量
INCIDENT_DETECTED_KEYS = {
    "card_title",
    "status_label",
    "incident_id",
    "service_name",
    "severity",
    "error_brief",
    "occurrence_text",
    "next_step",
    "issue_url",
    "report_url"
}

REPAIR_PLAN_READY_KEYS = {
    "card_title",
    "status_label",
    "incident_id",
    "service_name",
    "diagnosis_brief",
    "fix_strategy",
    "risk_level",
    "policy_result",
    "report_url"
}

FIX_PR_READY_KEYS = {
    "card_title",
    "status_label",
    "incident_id",
    "service_name",
    "pr_title",
    "fix_brief",
    "test_brief",
    "risk_level",
    "pr_url",
    "report_url"
}

MANUAL_INTERVENTION_KEYS = {
    "card_title",
    "status_label",
    "incident_id",
    "service_name",
    "reason_brief",
    "evidence_brief",
    "suggested_action",
    "issue_url",
    "report_url"
}

PERIODIC_DIGEST_KEYS = {
    "card_title",
    "period_label",
    "summary_sentence",
    "metric_line_1",
    "metric_line_2",
    "top_issue_1",
    "top_issue_2",
    "todo_brief",
    "report_url",
    "pr_url"
}

CARD_KEY_MAPPING = {
    "incident_detected": INCIDENT_DETECTED_KEYS,
    "repair_plan_ready": REPAIR_PLAN_READY_KEYS,
    "fix_pr_ready": FIX_PR_READY_KEYS,
    "manual_intervention": MANUAL_INTERVENTION_KEYS,
    "periodic_digest": PERIODIC_DIGEST_KEYS
}


def _truncate_text(text: str, max_length: int = 80) -> str:
    """截断文本到指定长度，超出部分用...表示"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def _format_url(url: str) -> Dict[str, str]:
    """格式化URL为飞书卡片要求的多端适配格式"""
    # 飞书要求URL必须是合法的http/https格式
    if not url or not url.startswith(("http://", "https://")):
        return {}
    return {
        "pc_url": url,
        "android_url": url,
        "ios_url": url,
        "url": url
    }


def build_incident_detected_variables(
    incident_id: str,
    service_name: str,
    severity: str,
    error_type: str,
    error_message: str,
    occurrence_count: int,
    time_window: str = "10 分钟",
    issue_url: str = "",
    report_url: str = ""
) -> Dict[str, Any]:
    """构造故障发现卡片变量，最多10个字段"""
    error_brief = _truncate_text(f"{error_type}: {error_message}", max_length=80)
    occurrence_text = f"近 {time_window} 发生 {occurrence_count} 次"
    
    return {
        "card_title": f"【{severity}】检测到服务异常",
        "status_label": "已受理",
        "incident_id": incident_id,
        "service_name": service_name,
        "severity": severity,
        "error_brief": error_brief,
        "occurrence_text": occurrence_text,
        "next_step": "正在收集证据并执行自动诊断",
        "issue_url": _format_url(issue_url),
        "report_url": _format_url(report_url)
    }


def build_repair_plan_ready_variables(
    incident_id: str,
    service_name: str,
    diagnosis_brief: str | None = None,
    fix_strategy: str = "",
    risk_level: str = "",
    policy_result: str | None = None,
    report_url: str = "",
    root_cause: str | None = None,
    policy_summary: str | None = None,
) -> Dict[str, Any]:
    """构造修复计划准备完成卡片变量，最多9个字段"""
    return {
        "card_title": "已生成修复计划",
        "status_label": "待执行",
        "incident_id": incident_id,
        "service_name": service_name,
        "diagnosis_brief": _truncate_text(diagnosis_brief or root_cause or "", max_length=100),
        "fix_strategy": _truncate_text(fix_strategy, max_length=100),
        "risk_level": risk_level,
        "policy_result": policy_result or policy_summary or "",
        "report_url": _format_url(report_url)
    }


def build_fix_pr_ready_variables(
    incident_id: str,
    service_name: str,
    pr_number: int,
    pr_title: str,
    fix_brief: str | None = None,
    test_brief: str | None = None,
    risk_level: str = "",
    pr_url: str = "",
    report_url: str = "",
    fix_summary: str | None = None,
    test_summary: str | None = None,
) -> Dict[str, Any]:
    """构造PR准备完成卡片变量，最多10个字段"""
    return {
        "card_title": "AutoRepair 已完成修复，PR 待 Review",
        "status_label": "待 Review",
        "incident_id": incident_id,
        "service_name": service_name,
        "pr_title": f"#{pr_number} {pr_title}",
        "fix_brief": _truncate_text(fix_brief or fix_summary or "", max_length=80),
        "test_brief": test_brief or test_summary or "",
        "risk_level": risk_level,
        "pr_url": _format_url(pr_url),
        "report_url": _format_url(report_url)
    }


def build_manual_intervention_variables(
    incident_id: str,
    service_name: str,
    reason_brief: str | None = None,
    evidence_brief: str | None = None,
    suggested_action: str | None = None,
    issue_url: str = "",
    report_url: str = "",
    human_reason: str | None = None,
    evidence_summary: str | None = None,
    next_action: str | None = None,
) -> Dict[str, Any]:
    """构造人工介入卡片变量，最多9个字段"""
    return {
        "card_title": "问题需人工介入",
        "status_label": "人工处理",
        "incident_id": incident_id,
        "service_name": service_name,
        "reason_brief": _truncate_text(reason_brief or human_reason or "", max_length=80),
        "evidence_brief": _truncate_text(evidence_brief or evidence_summary or "", max_length=80),
        "suggested_action": _truncate_text(suggested_action or next_action or "", max_length=80),
        "issue_url": _format_url(issue_url),
        "report_url": _format_url(report_url)
    }


def build_periodic_digest_variables(
    period_label: str,
    summary_sentence: str,
    metric_total: int,
    metric_fixed: int,
    metric_manual: int,
    success_rate: str,
    avg_triage_time: str,
    avg_repair_time: str,
    top_errors_text: str,
    top_services_text: str,
    todo_text: str,
    report_url: str = "",
    pr_url: str = ""
) -> Dict[str, Any]:
    """构造周期性总结卡片变量，最多10个字段"""
    metric_line_1 = f"新增 {metric_total}｜自动修复 {metric_fixed}｜人工介入 {metric_manual}"
    metric_line_2 = f"成功率 {success_rate}｜平均诊断 {avg_triage_time}｜平均修复 {avg_repair_time}"
    
    return {
        "card_title": "AutoRepair 每日修复摘要",
        "period_label": period_label,
        "summary_sentence": summary_sentence,
        "metric_line_1": metric_line_1,
        "metric_line_2": metric_line_2,
        "top_issue_1": _truncate_text(top_errors_text, max_length=80),
        "top_issue_2": _truncate_text(top_services_text, max_length=80),
        "todo_brief": _truncate_text(todo_text, max_length=80),
        "report_url": _format_url(report_url),
        "pr_url": _format_url(pr_url)
    }
