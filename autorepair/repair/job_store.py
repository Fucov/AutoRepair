from __future__ import annotations

from pathlib import Path
from typing import Any

from autorepair.config import PROJECT_ROOT
from autorepair.repair.schemas import RepairJob, RepairJobStatus, is_active_status, utc_now


DEFAULT_REPAIR_JOBS_PATH = PROJECT_ROOT / "autorepair" / "records" / "repair_jobs.jsonl"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_repair_jobs(path: str | Path | None = None) -> list[RepairJob]:
    file_path = Path(path) if path else DEFAULT_REPAIR_JOBS_PATH
    if not file_path.exists():
        return []
    jobs: list[RepairJob] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(RepairJob.model_validate_json(line))
    return jobs


def _write_jobs(jobs: list[RepairJob], path: str | Path | None = None) -> None:
    file_path = Path(path) if path else DEFAULT_REPAIR_JOBS_PATH
    _ensure_parent(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.model_dump_json() + "\n")


def find_active_job_by_issue(issue_number: int, path: str | Path | None = None) -> RepairJob | None:
    for job in load_repair_jobs(path):
        if job.issue_number == issue_number and is_active_status(job.status):
            return job
    return None


def find_active_job_by_incident(incident_id: str, path: str | Path | None = None) -> RepairJob | None:
    for job in load_repair_jobs(path):
        if job.incident_id == incident_id and is_active_status(job.status):
            return job
    return None


def find_oldest_queued_job(path: str | Path | None = None) -> RepairJob | None:
    queued = [job for job in load_repair_jobs(path) if job.status == RepairJobStatus.queued]
    return sorted(queued, key=lambda job: job.created_at)[0] if queued else None


def create_repair_job(
    *,
    incident_id: str,
    issue_number: int,
    issue_url: str | None = None,
    report_url: str | None = None,
    service_name: str | None = None,
    repo_owner: str,
    repo_name: str,
    base_branch: str,
    repair_branch: str,
    worktree_path: str,
    policy_decision: str | dict[str, Any] | None,
    policy_result: str | None = None,
    risk_level: str,
    path: str | Path | None = None,
) -> RepairJob:
    existing = find_active_job_by_issue(issue_number, path) or find_active_job_by_incident(incident_id, path)
    if existing:
        return existing

    jobs = load_repair_jobs(path)
    job = RepairJob(
        incident_id=incident_id,
        issue_number=issue_number,
        issue_url=issue_url,
        report_url=report_url,
        service_name=service_name,
        repo_owner=repo_owner,
        repo_name=repo_name,
        base_branch=base_branch,
        repair_branch=repair_branch,
        worktree_path=worktree_path,
        policy_decision=policy_decision,
        policy_result=policy_result,
        risk_level=risk_level,
    )
    jobs.append(job)
    _write_jobs(jobs, path)
    return job


def update_repair_job(job_id: str, path: str | Path | None = None, **fields: Any) -> RepairJob:
    jobs = load_repair_jobs(path)
    for index, job in enumerate(jobs):
        if job.job_id == job_id:
            data = job.model_dump()
            data.update(fields)
            data["updated_at"] = utc_now()
            updated = RepairJob.model_validate(data)
            jobs[index] = updated
            _write_jobs(jobs, path)
            return updated
    raise ValueError(f"Repair job not found: {job_id}")


def find_jobs_by_incident_id(incident_id: str, path: str | Path | None = None) -> list[RepairJob]:
    return [job for job in load_repair_jobs(path) if job.incident_id == incident_id]


def find_jobs_by_issue_number(issue_number: int, path: str | Path | None = None) -> list[RepairJob]:
    return [job for job in load_repair_jobs(path) if job.issue_number == issue_number]


def find_next_queued_job(path: str | Path | None = None) -> RepairJob | None:
    queued = [job for job in load_repair_jobs(path) if job.status == RepairJobStatus.queued]
    return sorted(queued, key=lambda job: job.created_at)[0] if queued else None


def create_repair_job_from_issue(
    incident: "Incident",
    issue: "GitHubIssue",
    report_url: str,
    policy_result: str,
    path: str | Path | None = None,
) -> RepairJob:
    """
    从Issue创建RepairJob，避免重复创建
    :param incident: 关联的Incident对象
    :param issue: GitHubIssue对象
    :param report_url: 诊断报告URL
    :param policy_result: 策略检查结果
    :param path: 可选自定义路径
    :return: RepairJob对象
    """
    from ..schemas import Incident
    from ..adapters.github import GitHubIssue
    from ..repair.git_workspace import build_repair_branch
    from ..config import GITHUB_OWNER, GITHUB_REPO, BASE_BRANCH
    from ..service_registry import get_default_service
    
    # 检查是否已有active job
    existing_job = find_active_job_by_issue(issue.number, path)
    if existing_job:
        return existing_job
    
    existing_job = find_active_job_by_incident(incident.incident_id, path)
    if existing_job:
        return existing_job
    
    service = get_default_service()
    repair_branch = build_repair_branch(incident.incident_id, issue.title)
    worktree_path = str(Path(service.repo_path) / ".worktrees" / incident.incident_id)
    
    # 创建新job
    job = RepairJob(
        incident_id=incident.incident_id,
        issue_number=issue.number,
        issue_url=issue.html_url,
        report_url=report_url,
        service_name=incident.service_name or incident.service,
        repo_owner=GITHUB_OWNER or "local",
        repo_name=GITHUB_REPO or Path(service.repo_path).name,
        base_branch=BASE_BRANCH,
        repair_branch=repair_branch,
        worktree_path=worktree_path,
        policy_result=policy_result,
        risk_level=incident.risk_level if hasattr(incident, 'risk_level') else "medium",
    )
    
    # 追加job
    jobs = load_repair_jobs(path)
    jobs.append(job)
    _write_jobs(jobs, path)
    
    # 记录audit event
    from ..audit_store import append_audit_event
    append_audit_event(
        "repair_job_created",
        incident.incident_id,
        {
            "job_id": job.job_id,
            "issue_number": issue.number,
            "report_url": report_url,
            "policy_result": policy_result
        },
    )
    
    return job
