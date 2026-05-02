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
    repo_owner: str,
    repo_name: str,
    base_branch: str,
    repair_branch: str,
    worktree_path: str,
    policy_decision: str | dict[str, Any] | None,
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
        repo_owner=repo_owner,
        repo_name=repo_name,
        base_branch=base_branch,
        repair_branch=repair_branch,
        worktree_path=worktree_path,
        policy_decision=policy_decision,
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
