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


class ErrorSummary(BaseModel):
    error_type: str
    message: str
    suspected_file: str | None = None
    line_no: int | None = None
    function: str | None = None
    fingerprint: str
