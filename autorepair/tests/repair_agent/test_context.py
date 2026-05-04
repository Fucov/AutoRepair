from autorepair.repair_agent.context import build_repair_agent_context
from autorepair.repair_agent.schemas import RepairAgentContext


class _MockJob:
    job_id = "JOB-001"
    incident_id = "INC-001"
    issue_number = 42
    worktree_path = "C:\\Users\\test\\worktree"
    repo_owner = "test-owner"
    repo_name = "test-repo"


class _MockIncident:
    incident_id = "INC-001"
    service_name = "demo-service"
    error_type = "TypeError"
    error_message = "cannot compare"
    suspected_file = "demo_service/ticket_service.py"
    line_no = 15
    raw_traceback = "Traceback..."
    issue_number = 42


class _MockService:
    agent_target_test_command = "pytest -q demo_service/tests/test_ticket_contract.py -m agent_target"
    test_command = "pytest -q demo_service/tests/"


def test_build_context_basic():
    ctx = build_repair_agent_context(_MockJob(), _MockIncident())
    assert isinstance(ctx, RepairAgentContext)
    assert ctx.job_id == "JOB-001"
    assert ctx.incident_id == "INC-001"
    assert ctx.error_type == "TypeError"


def test_build_context_backslash_path():
    ctx = build_repair_agent_context(_MockJob(), _MockIncident())
    assert "\\" not in ctx.worktree_path


def test_build_context_timezone_target_test():
    ctx = build_repair_agent_context(_MockJob(), _MockIncident(), service=_MockService())
    assert ctx.target_test_command is not None
    assert "agent_target" in ctx.target_test_command


def test_build_context_missing_fields():
    class _Empty:
        pass
    ctx = build_repair_agent_context(_Empty(), _Empty())
    assert ctx.job_id == ""
    assert ctx.error_type is None
    assert ctx.worktree_path == ""
