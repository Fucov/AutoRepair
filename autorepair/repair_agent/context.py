from __future__ import annotations

from autorepair.repair_agent.schemas import RepairAgentContext


def build_repair_agent_context(
    job,
    incident,
    issue: object | None = None,
    service: object | None = None,
) -> RepairAgentContext:
    target_test = getattr(service, "agent_target_test_command", None) if service else None
    full_test = getattr(service, "test_command", "pytest -q") if service else "pytest -q"

    issue_number = getattr(issue, "number", None) if issue else getattr(incident, "issue_number", None)

    worktree_path = getattr(job, "worktree_path", "")
    if worktree_path:
        worktree_path = worktree_path.replace("\\", "/")

    error_summary = getattr(incident, "error_summary", None)
    if error_summary:
        error_type = getattr(error_summary, "error_type", None)
        error_message = getattr(error_summary, "message", None)
        suspected_file = getattr(error_summary, "suspected_file", None) or getattr(job, "suspected_file", None)
        line_no = getattr(error_summary, "line_no", None)
    else:
        error_type = getattr(incident, "error_type", None)
        error_message = getattr(incident, "error_message", None)
        suspected_file = getattr(incident, "suspected_file", None) or getattr(job, "suspected_file", None)
        line_no = getattr(incident, "line_no", None)

    return RepairAgentContext(
        job_id=getattr(job, "job_id", ""),
        incident_id=getattr(incident, "incident_id", ""),
        issue_number=issue_number,
        service_name=getattr(incident, "service_name", None) or getattr(incident, "service", "unknown") or "unknown",
        worktree_path=worktree_path,
        repo_path=getattr(incident, "repo_path", ""),
        error_type=error_type,
        error_message=error_message,
        suspected_file=suspected_file,
        line_no=line_no,
        raw_traceback=getattr(incident, "raw_traceback", None),
        issue_body=getattr(incident, "issue_body", None),
        target_test_command=target_test,
        full_test_command=full_test,
    )
