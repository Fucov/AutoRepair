from typing import Literal
from pydantic import BaseModel


IncidentSource = Literal["local_log", "github_issue", "manual"]


class Incident(BaseModel):
    incident_id: str
    source: IncidentSource
    service: str
    error_type: str | None = None
    traceback: str
    suspected_file: str | None = None
    line_no: int | None = None
    fingerprint: str | None = None
    status: str = "NEW"


class ErrorSummary(BaseModel):
    error_type: str
    message: str
    suspected_file: str | None = None
    line_no: int | None = None
    function: str | None = None
    fingerprint: str
