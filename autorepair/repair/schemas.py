from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any
import uuid


class RepairJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    test_failed = "test_failed"
    pr_created = "pr_created"
    human_required = "human_required"
    merged = "merged"
    closed = "closed"
    failed = "failed"


ACTIVE_REPAIR_JOB_STATUSES = {
    RepairJobStatus.queued,
    RepairJobStatus.running,
    RepairJobStatus.pr_created,
}


def utc_now() -> str:
    return datetime.utcnow().isoformat()


class RepairJob(BaseModel):
    job_id: str = Field(default_factory=lambda: f"JOB-{uuid.uuid4().hex[:12]}")
    incident_id: str
    issue_number: int
    issue_url: str | None = None
    report_url: str | None = None
    service_name: str | None = None
    repo_owner: str
    repo_name: str
    base_branch: str
    repair_branch: str
    worktree_path: str
    status: RepairJobStatus = RepairJobStatus.queued
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    policy_decision: str | dict[str, Any] | None = None
    policy_result: str | None = None
    risk_level: str = "low"
    pr_number: int | None = None
    pr_url: str | None = None
    last_error: str | None = None
    case_id: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    spec_id: str | None = None
    validation_summary: str | None = None
    transcript_path: str | None = None


def is_active_status(status: RepairJobStatus | str) -> bool:
    return RepairJobStatus(status) in ACTIVE_REPAIR_JOB_STATUSES
