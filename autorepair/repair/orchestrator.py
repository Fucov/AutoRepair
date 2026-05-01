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
from autorepair.incident_store import load_incidents
from autorepair.issue_validator import validate_bug_issue
from autorepair.repair.git_workspace import build_repair_branch
from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH, create_repair_job
from autorepair.repair.schemas import RepairJob
from autorepair.service_registry import get_default_service


def _incident_id_from_body(body: str, issue_number: int) -> str:
    for line in body.splitlines():
        if "Incident ID:" in line:
            return line.split("Incident ID:", 1)[1].strip().strip("`")
    return f"ISSUE-{issue_number}"


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
    incident_id = _incident_id_from_body(issue.body, issue.number)
    service = get_default_service()

    if not validation.is_valid:
        comment_issue(issue.number, validation.suggested_comment)
        label = "autorepair:human-required" if "high risk" in validation.reason.lower() else "autorepair:needs-info"
        replace_autorepair_status_label(issue.number, label)
        append_audit_event(
            "issue_validation_rejected",
            incident_id,
            {"issue_number": issue.number, "reason": validation.reason},
        )
        feishu.send_manual_intervention(
            incident_id=incident_id,
            service_name=service.name,
            reason_brief=validation.reason,
            evidence_brief=validation.evidence_level,
            suggested_action=validation.suggested_comment,
            issue_url=issue.html_url,
        )
        return None

    decision = _dry_run_decision(issue.number, issue.title, issue.body)
    allowed, reason = should_auto_fix(decision)
    if not allowed:
        comment_issue(issue.number, f"AutoRepair policy rejected this issue: {reason}")
        replace_autorepair_status_label(issue.number, "autorepair:human-required")
        append_audit_event("repair_policy_rejected", incident_id, {"issue_number": issue.number, "reason": reason})
        feishu.send_manual_intervention(
            incident_id=incident_id,
            service_name=service.name,
            reason_brief=reason,
            evidence_brief=decision.summary,
            suggested_action="Please review the issue manually.",
            issue_url=issue.html_url,
        )
        return None

    repair_branch = build_repair_branch(incident_id, issue.title)
    worktree_path = str(Path(service.repo_path) / ".worktrees" / incident_id)
    job = create_repair_job(
        incident_id=incident_id,
        issue_number=issue.number,
        repo_owner=GITHUB_OWNER or "local",
        repo_name=GITHUB_REPO or Path(service.repo_path).name,
        base_branch=os.getenv("GITHUB_BASE_BRANCH", "main"),
        repair_branch=repair_branch,
        worktree_path=worktree_path,
        policy_decision=decision.model_dump(mode="json"),
        risk_level="low",
        path=DEFAULT_REPAIR_JOBS_PATH,
    )
    replace_autorepair_status_label(issue.number, "autorepair:accepted")
    add_labels(issue.number, ["source:issue"] if "source:runtime" not in issue.labels else [])
    comment_issue(issue.number, f"AutoRepair accepted this issue and queued repair job `{job.job_id}`.")
    append_audit_event("repair_job_queued", incident_id, {"issue_number": issue.number, "job_id": job.job_id})
    feishu.send_repair_plan_ready(
        incident_id=incident_id,
        service_name=service.name,
        diagnosis_brief=decision.summary,
        fix_strategy=decision.fix_plan or "Dry-run repair orchestration",
        risk_level=job.risk_level,
        policy_result="accepted",
    )
    return job
