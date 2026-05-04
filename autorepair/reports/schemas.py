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


class RepairPlanData(BaseModel):
    plan_id: str
    incident_id: str
    issue_number: Optional[int] = None
    service_name: str
    error_type: str
    error_message: str
    suspected_file: Optional[str] = None
    suspected_line: Optional[int] = None
    suspected_function: Optional[str] = None
    root_cause_analysis: str
    fix_steps: List[str]
    affected_files: List[str]
    test_strategy: str
    target_test_command: Optional[str] = None
    risk_level: str
    estimated_changes: str
    rollback_plan: str
    created_at: str = datetime.utcnow().isoformat()
