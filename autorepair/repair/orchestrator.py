from __future__ import annotations

import os
from pathlib import Path

from autorepair.adapters.github import (
    add_labels,
    comment_issue,
    get_issue,
    replace_autorepair_status_label,
)
from autorepair.adapters import feishu
from autorepair.agent.triage.decision_schema import (
    ConfidenceEnum,
    Decision,
    DecisionEnum,
    Evidence,
    IncidentTypeEnum,
    SeverityEnum,
)
from autorepair.agent.triage.policy_gate import should_auto_fix
from autorepair.audit_store import append_audit_event
from autorepair.config import GITHUB_OWNER, GITHUB_REPO, PROJECT_ROOT
from autorepair.incident_store import load_incidents, create_incident_from_issue
from autorepair.dashboard.api import push_event
from autorepair.issue_validator import validate_bug_issue
from autorepair.repair.git_workspace import build_repair_branch
from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH, create_repair_job
from autorepair.repair.schemas import RepairJob
from autorepair.service_registry import get_default_service


def _incident_id_from_body(body: str, issue_number: int) -> str:
    for line in body.splitlines():
        if "Incident ID:" in line:
            return line.split("Incident ID:", 1)[1].strip().strip("`")
    # 不再生成ISSUE-xxx格式，改用create_incident_from_issue创建正规INC-前缀ID
    return ""


def _linked_incident(incident_id: str):
    for incident in load_incidents():
        if incident.incident_id == incident_id:
            return incident
    return None


def _dry_run_decision(issue_number: int, title: str, body: str) -> Decision:
    evidence = [
        Evidence(
            label="GitHub Issue",
            detail=f"Issue #{issue_number} contains reproduction and error evidence.",
        )
    ]
    return Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p2,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary=f"Dry-run triage accepted issue #{issue_number}: {title}",
        root_cause_hypothesis="Issue contains enough evidence for a constrained repair attempt.",
        evidence=evidence,
        risks=["low risk dry-run orchestration only"],
        recommended_action="Queue repair job and create isolated worktree.",
        fix_plan="Create repair branch and worktree. Do not patch code in Stage 3A dry-run mode.",
        requires_human_approval=False,
        feishu_card={"title": "Repair plan ready"},
    )


def process_issue_for_repair(issue_number: int) -> RepairJob | None:
    issue = get_issue(issue_number)
    if issue is None:
        return None

    # 检查是否已有active job
    from autorepair.repair.job_store import find_active_job_by_issue
    existing_job = find_active_job_by_issue(issue_number)
    if existing_job:
        comment_issue(issue.number, f"AutoRepair 已存在active修复任务 `{existing_job.job_id}` (status: {existing_job.status.value})，不会重复创建。")
        return None

    validation = validate_bug_issue(issue)
    service = get_default_service()
    
    # 创建或查找关联的Incident
    incident = create_incident_from_issue(issue, service)
    incident_id = incident.incident_id
    push_event("incident_detected", {
        "incident_id": incident_id,
        "issue_number": issue.number,
        "message": f"故障关联成功: {incident.error_summary.error_type}"
    })

    # 导入报告相关模块
    from autorepair.reports.diagnostic_report_builder import build_diagnostic_report
    from autorepair.adapters.feishu_docx import FeishuDocxClient
    
    feishu_doc_client = FeishuDocxClient()
    
    if not validation.is_valid:
        # 生成诊断报告
        triage_result = type('MockTriageResult', (), {
            'root_cause': 'Issue信息不足，无法自动修复', 
            'risk_level': 'high'
        })()
        report = build_diagnostic_report(
            issue=issue,
            incident=incident,
            validation_result=f"未通过: {validation.reason}",
            triage_result=triage_result,
            policy_result="rejected"
        )
        
        # 创建诊断报告
        doc_ref = feishu_doc_client.create_diagnostic_report(report)
        push_event("diagnostic_report_created", {
            "incident_id": incident_id,
            "issue_number": issue.number,
            "report_url": doc_ref.url,
            "message": "诊断报告生成完成"
        })
        
        comment_content = f"{validation.suggested_comment}\n\n诊断报告：{doc_ref.url}"
        comment_issue(issue.number, comment_content)
        
        label = "autorepair:human-required" if "high risk" in validation.reason.lower() else "autorepair:needs-info"
        replace_autorepair_status_label(issue.number, label)
        
        append_audit_event(
            "issue_validation_rejected",
            incident_id,
            {"issue_number": issue.number, "reason": validation.reason, "report_url": doc_ref.url},
        )
        append_audit_event(
            "diagnostic_report_created",
            incident_id,
            {"report_url": doc_ref.url, "report_id": report.report_id},
        )
        
        feishu.send_manual_intervention(
            incident_id=incident_id,
            service_name=service.name,
            reason_brief=validation.reason,
            evidence_brief=validation.evidence_level,
            suggested_action=validation.suggested_comment,
            issue_url=issue.html_url,
            report_url=doc_ref.url,
        )
        return None

    decision = _dry_run_decision(issue.number, issue.title, issue.body)
    allowed, reason = should_auto_fix(decision)
    
    # 生成诊断报告
    report = build_diagnostic_report(
        issue=issue,
        incident=incident,
        validation_result="通过",
        triage_result=decision,
        policy_result="allowed" if allowed else f"rejected: {reason}"
    )
    
    # 创建诊断报告
    doc_ref = feishu_doc_client.create_diagnostic_report(report)
    push_event("diagnostic_report_created", {
        "incident_id": incident_id,
        "issue_number": issue.number,
        "report_url": doc_ref.url,
        "message": "诊断报告生成完成"
    })
    append_audit_event(
        "diagnostic_report_created",
        incident_id,
        {"report_url": doc_ref.url, "report_id": report.report_id},
    )
    
    if not allowed:
        comment_content = f"AutoRepair policy rejected this issue: {reason}\n\n诊断报告：{doc_ref.url}"
        comment_issue(issue.number, comment_content)
        replace_autorepair_status_label(issue.number, "autorepair:human-required")
        append_audit_event("repair_policy_rejected", incident_id, {"issue_number": issue.number, "reason": reason, "report_url": doc_ref.url})
        feishu.send_manual_intervention(
            incident_id=incident_id,
            service_name=service.name,
            reason_brief=reason,
            evidence_brief=decision.summary,
            suggested_action="Please review the issue manually.",
            issue_url=issue.html_url,
            report_url=doc_ref.url,
        )
        return None

    repair_branch = build_repair_branch(incident_id, issue.title)
    worktree_path = str(Path(service.repo_path) / ".worktrees" / incident_id)
    job = create_repair_job(
        incident_id=incident_id,
        issue_number=issue.number,
        issue_url=issue.html_url,
        repo_owner=GITHUB_OWNER or "local",
        repo_name=GITHUB_REPO or Path(service.repo_path).name,
        base_branch=os.getenv("GITHUB_BASE_BRANCH", "main"),
        repair_branch=repair_branch,
        worktree_path=worktree_path,
        policy_decision=decision.model_dump(mode="json"),
        risk_level=decision.severity.value if hasattr(decision, 'severity') and hasattr(decision.severity, 'value') else "medium",
        report_url=doc_ref.url,
        path=DEFAULT_REPAIR_JOBS_PATH,
    )
    
    push_event("repair_job_created", {
        "job_id": job.job_id,
        "incident_id": incident_id,
        "issue_number": issue.number,
        "report_url": doc_ref.url,
        "message": "修复任务已加入队列"
    })
    
    replace_autorepair_status_label(issue.number, "autorepair:accepted")
    add_labels(issue.number, ["source:issue"] if "source:runtime" not in issue.labels else [])
    comment_issue(issue.number, f"AutoRepair accepted this issue and queued repair job `{job.job_id}`.\n\n诊断报告：{doc_ref.url}")
    append_audit_event("repair_job_queued", incident_id, {"issue_number": issue.number, "job_id": job.job_id, "report_url": doc_ref.url})
    append_audit_event("repair_plan_generated", incident_id, {"job_id": job.job_id, "report_url": doc_ref.url})
    
    # 发送飞书卡片
    feishu.send_repair_plan_ready(
        incident_id=incident_id,
        service_name=service.name,
        diagnosis_brief=decision.summary,
        fix_strategy=decision.fix_plan or "Dry-run repair orchestration",
        risk_level=job.risk_level,
        policy_result="accepted",
        report_url=doc_ref.url,
    )
    
    push_event("card_sent", {
        "incident_id": incident_id,
        "issue_number": issue.number,
        "job_id": job.job_id,
        "message": "修复计划卡片已发送"
    })
    return job
