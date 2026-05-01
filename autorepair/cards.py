from __future__ import annotations

from typing import Any, Dict


def _truncate(text: str, max_length: int = 80) -> str:
    """截断文本到指定长度，超出部分添加省略号"""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _safe_str(value: Any, default: str = "") -> str:
    """安全转换为字符串"""
    if value is None:
        return default
    return str(value)


INCIDENT_DETECTED_KEYS = {
    "incident_id",
    "service_name",
    "severity",
    "error_type",
    "error_brief",
    "occurrence_count",
    "issue_url",
    "report_url",
    "time_window",
}


def build_incident_detected_variables(
    incident_id: str,
    service_name: str,
    severity: str = "P2",
    error_type: str = "",
    error_message: str = "",
    occurrence_count: int = 1,
    issue_url: str = "",
    report_url: str = "",
    time_window: str = "",
) -> Dict[str, Any]:
    """构建故障发现卡片变量"""
    return {
        "incident_id": _safe_str(incident_id),
        "service_name": _safe_str(service_name),
        "severity": _safe_str(severity, "P2"),
        "error_type": _safe_str(error_type),
        "error_brief": _truncate(error_message, 80),
        "occurrence_count": occurrence_count,
        "issue_url": _safe_str(issue_url),
        "report_url": _safe_str(report_url),
        "time_window": _safe_str(time_window),
    }


REPAIR_PLAN_READY_KEYS = {
    "incident_id",
    "service_name",
    "root_cause",
    "fix_strategy",
    "risk_level",
    "policy_summary",
}


def build_repair_plan_ready_variables(
    incident_id: str,
    service_name: str,
    root_cause: str = "",
    fix_strategy: str = "",
    risk_level: str = "",
    policy_summary: str = "",
) -> Dict[str, Any]:
    """构建修复计划准备完成卡片变量"""
    return {
        "incident_id": _safe_str(incident_id),
        "service_name": _safe_str(service_name),
        "root_cause": _truncate(root_cause, 80),
        "fix_strategy": _truncate(fix_strategy, 80),
        "risk_level": _safe_str(risk_level),
        "policy_summary": _safe_str(policy_summary),
    }


FIX_PR_READY_KEYS = {
    "incident_id",
    "service_name",
    "pr_number",
    "pr_title",
    "fix_summary",
    "test_summary",
    "risk_level",
    "pr_url",
}


def build_fix_pr_ready_variables(
    incident_id: str,
    service_name: str,
    pr_number: int,
    pr_title: str,
    fix_summary: str = "",
    test_summary: str = "",
    risk_level: str = "",
    pr_url: str = "",
) -> Dict[str, Any]:
    """构建PR准备完成卡片变量"""
    return {
        "incident_id": _safe_str(incident_id),
        "service_name": _safe_str(service_name),
        "pr_number": pr_number,
        "pr_title": _truncate(pr_title, 80),
        "fix_summary": _truncate(fix_summary, 80),
        "test_summary": _truncate(test_summary, 80),
        "risk_level": _safe_str(risk_level),
        "pr_url": _safe_str(pr_url),
    }


MANUAL_INTERVENTION_KEYS = {
    "incident_id",
    "service_name",
    "human_reason",
    "evidence_summary",
    "next_action",
}


def build_manual_intervention_variables(
    incident_id: str,
    service_name: str,
    human_reason: str = "",
    evidence_summary: str = "",
    next_action: str = "",
) -> Dict[str, Any]:
    """构建人工介入卡片变量"""
    return {
        "incident_id": _safe_str(incident_id),
        "service_name": _safe_str(service_name),
        "human_reason": _truncate(human_reason, 80),
        "evidence_summary": _truncate(evidence_summary, 80),
        "next_action": _truncate(next_action, 80),
    }


PERIODIC_DIGEST_KEYS = {
    "period_label",
    "summary_sentence",
    "metric_total",
    "metric_fixed",
    "metric_manual",
    "success_rate",
    "avg_triage_time",
    "avg_repair_time",
    "top_errors_text",
    "top_services_text",
    "todo_text",
}


def build_periodic_digest_variables(
    period_label: str,
    summary_sentence: str,
    metric_total: int = 0,
    metric_fixed: int = 0,
    metric_manual: int = 0,
    success_rate: str = "",
    avg_triage_time: str = "",
    avg_repair_time: str = "",
    top_errors_text: str = "",
    top_services_text: str = "",
    todo_text: str = "",
) -> Dict[str, Any]:
    """构建周期性总结卡片变量"""
    return {
        "period_label": _safe_str(period_label),
        "summary_sentence": _truncate(summary_sentence, 100),
        "metric_total": metric_total,
        "metric_fixed": metric_fixed,
        "metric_manual": metric_manual,
        "success_rate": _safe_str(success_rate),
        "avg_triage_time": _safe_str(avg_triage_time),
        "avg_repair_time": _safe_str(avg_repair_time),
        "top_errors_text": _truncate(top_errors_text, 100),
        "top_services_text": _truncate(top_services_text, 100),
        "todo_text": _truncate(todo_text, 100),
    }
