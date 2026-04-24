from typing import Literal
from pydantic import BaseModel


IncidentSource = Literal["local_log", "github_issue", "manual"]


class Incident(BaseModel):
    incident_id: str
    source: IncidentSource
    service: str
    status: str = "NEW"
    error_summary: ErrorSummary
    raw_traceback: str
    created_at: str
    updated_at: str
    source_ref: str | None = None  # 本地日志路径或GitHub Issue URL
    issue_number: int | None = None
    issue_url: str | None = None
    scenario_id: str | None = None  # 关联的Bug场景ID


class ErrorSummary(BaseModel):
    error_type: str
    message: str
    suspected_file: str | None = None
    line_no: int | None = None
    function: str | None = None
    fingerprint: str
