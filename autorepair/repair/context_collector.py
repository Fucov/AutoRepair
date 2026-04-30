from __future__ import annotations
from pathlib import Path
from typing import Any
from pydantic import BaseModel
from autorepair.repair.schemas import RepairJob
from autorepair.schemas import Incident


class RepairContext(BaseModel):
    incident_id: str
    issue_number: int
    service_name: str
    error_type: str
    error_message: str
    suspected_file: str | None
    line_no: int | None
    raw_traceback: str
    target_test_command: str
    full_test_command: str
    code_snippets: dict[str, str]
    existing_tests: dict[str, str]


def collect_repair_context(job: RepairJob, incident: Incident, worktree_path: str) -> RepairContext:
    worktree = Path(worktree_path)
    code_snippets: dict[str, str] = {}
    existing_tests: dict[str, str] = {}
    
    suspected_file = incident.error_summary.suspected_file
    line_no = incident.error_summary.line_no
    
    if suspected_file:
        file_path = worktree / suspected_file
        if file_path.exists() and file_path.is_file():
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                start_line = max(0, line_no - 50) if line_no else 0
                end_line = min(len(lines), line_no + 50) if line_no else len(lines)
                snippet = "\n".join(lines[start_line:end_line])
                code_snippets[suspected_file] = snippet
            except Exception as e:
                print(f"Warning: Failed to read suspected file {suspected_file}: {e}")
    
    ticket_service_path = worktree / "demo_service" / "ticket_service.py"
    if ticket_service_path.exists():
        code_snippets["demo_service/ticket_service.py"] = ticket_service_path.read_text(encoding="utf-8")
    
    test_contract_path = worktree / "demo_service" / "tests" / "test_ticket_contract.py"
    if test_contract_path.exists():
        existing_tests["demo_service/tests/test_ticket_contract.py"] = test_contract_path.read_text(encoding="utf-8")
    
    test_success_path = worktree / "demo_service" / "tests" / "test_ticket_success.py"
    if test_success_path.exists():
        existing_tests["demo_service/tests/test_ticket_success.py"] = test_success_path.read_text(encoding="utf-8")
    
    return RepairContext(
        incident_id=job.incident_id,
        issue_number=job.issue_number,
        service_name="demo_service",
        error_type=incident.error_summary.error_type,
        error_message=incident.error_summary.message,
        suspected_file=suspected_file,
        line_no=line_no,
        raw_traceback=incident.raw_traceback,
        target_test_command="pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target",
        full_test_command="pytest -q",
        code_snippets=code_snippets,
        existing_tests=existing_tests,
    )
