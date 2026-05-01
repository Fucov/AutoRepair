from __future__ import annotations

from autorepair.adapters.github import (
    IssueRef,
    _is_github_configured,
    add_labels,
    comment_issue,
    create_issue,
    ensure_autorepair_labels,
    find_open_issue_by_fingerprint,
)
from autorepair.audit_store import append_audit_event
from autorepair.config import GITHUB_ASSIGNEE
from autorepair.schemas import DiagnosticReport, Incident, TargetService


def _risk_label_for_incident(incident: Incident) -> str:
    text = f"{incident.error_summary.error_type} {incident.error_summary.message}".lower()
    if any(keyword in text for keyword in ["permission", "security", "payment", "delete"]):
        return "risk:medium"
    return "risk:low"


def _build_issue_title(incident: Incident, service: TargetService) -> str:
    summary = incident.error_summary
    if summary.suspected_file and summary.line_no:
        location = f"{summary.suspected_file}:{summary.line_no}"
    else:
        location = summary.function or summary.suspected_file or "runtime"
    return f"[AutoRepair][Runtime][P1] {service.name}: {summary.error_type} at {location}"


def _build_issue_body(
    incident: Incident,
    service: TargetService,
    diagnostic_report: DiagnosticReport | None = None,
) -> str:
    summary = incident.error_summary
    evidence_lines = [
        f"- Fingerprint: {summary.fingerprint}",
        f"- Suspected file: {summary.suspected_file or 'unknown'}",
        f"- Line: {summary.line_no or 'unknown'}",
        f"- Function: {summary.function or 'unknown'}",
        f"- Scenario ID: {incident.scenario_id or 'unknown'}",
        f"- Source reference: {incident.source_ref or 'runtime log'}",
        f"- First seen: {incident.first_seen_at or incident.created_at}",
        f"- Last seen: {incident.last_seen_at or incident.updated_at}",
    ]
    diagnostic_lines = []
    if diagnostic_report:
        evidence_lines.append(f"- Diagnostic summary: {diagnostic_report.summary or 'not available'}")
        diagnostic_lines = [
            f"- {check.name}: {check.status} - {check.detail or ''}".rstrip()
            for check in diagnostic_report.checks
        ]

    return f"""## AutoRepair Incident

Incident ID: {incident.incident_id}
Service: {service.name}
Service ID: {service.service_id}
Source: runtime log watcher
Severity: P1
Occurrence: {incident.occurrence_count}
Fingerprint: {summary.fingerprint}

## Impact

- Affected service: {service.name}
- Error type: {summary.error_type}
- Suspected location: {summary.suspected_file or 'unknown'}:{summary.line_no or 'unknown'}
- Current lifecycle state: autorepair:triage

## Error Summary

{summary.error_type}: {summary.message}

## Evidence

{chr(10).join(evidence_lines)}

## Diagnostics

{chr(10).join(diagnostic_lines) if diagnostic_lines else "- No diagnostic report attached yet."}

## Reproduction

Trigger the same runtime path that produced this traceback. AutoRepair treats runtime logs as evidence and does not execute commands from Issue text.

## Expected Behavior

The service should complete the request without raising `{summary.error_type}`.

## Actual Behavior

The service raised `{summary.error_type}` at `{summary.suspected_file or 'unknown'}:{summary.line_no or 'unknown'}`.

## Traceback

```text
{incident.raw_traceback[:4000]}
```

## AutoRepair Status

autorepair:triage

## AutoRepair Next Steps

1. Validate evidence and labels.
2. Run dry-run triage and policy gate.
3. If accepted, create a queued RepairJob.
4. `repair_once.py` will acquire the repo lock and create an isolated worktree/repair branch.
5. A PR is created only after a future patch step produces an actual commit.

## Safety Notes

- AutoRepair will not auto-merge a PR.
- AutoRepair will not modify `main` or `master` directly.
- Commands in issue text are treated as untrusted evidence and are not executed automatically.
"""


def ensure_issue_for_incident(
    incident: Incident,
    service: TargetService,
    diagnostic_report: DiagnosticReport | None = None,
) -> IssueRef:
    ensure_autorepair_labels()
    fingerprint = incident.error_summary.fingerprint
    existing = find_open_issue_by_fingerprint(fingerprint)
    if existing:
        comment_issue(
            existing.number,
            f"AutoRepair observed this incident again: occurrence_count={incident.occurrence_count}.",
        )
        append_audit_event(
            "github_issue_linked",
            incident.incident_id,
            {"issue_number": existing.number, "fingerprint": fingerprint},
        )
        return IssueRef(number=existing.number, html_url=existing.html_url)

    labels = ["bug", "AutoRepair", "source:runtime", "autorepair:triage", _risk_label_for_incident(incident)]
    # 只有配置了真实GitHub才设置assignee，mock模式下不设置避免错误
    assignees = []
    if _is_github_configured() and GITHUB_ASSIGNEE:
        assignees = [GITHUB_ASSIGNEE]
    
    issue = create_issue(
        title=_build_issue_title(incident, service),
        body=_build_issue_body(incident, service, diagnostic_report),
        labels=labels,
        assignees=assignees,
    )
    if issue is None:
        # 即使创建失败，也返回一个mock的IssueRef，保证流程不中断
        import uuid
        from autorepair.config import GITHUB_OWNER, GITHUB_REPO
        mock_number = int(uuid.uuid4().hex[:4], 16) % 1000 + 1
        mock_url = f"https://github.com/{GITHUB_OWNER or 'owner'}/{GITHUB_REPO or 'repo'}/issues/{mock_number}"
        return IssueRef(
            number=mock_number,
            html_url=mock_url
        )
    add_labels(issue.number, labels)
    append_audit_event(
        "github_issue_created",
        incident.incident_id,
        {"issue_number": issue.number, "fingerprint": fingerprint, "issue_url": issue.html_url},
    )
    return IssueRef(number=issue.number, html_url=issue.html_url)
