from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class DiagnosticReportData(BaseModel):
    report_id: str
    incident_id: str
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    service_name: str
    error_brief: str
    evidence_summary: str
    validation_result: str
    root_cause: str
    repair_strategies: List[str]
    risk_level: str
    policy_result: str
    next_steps: List[str]
    traceback_excerpt: Optional[str] = None
    created_at: str = datetime.utcnow().isoformat()
