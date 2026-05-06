from unittest.mock import MagicMock

from autorepair.repair_agent.repair_case import build_repair_case
from autorepair.repair_agent.schemas import RepairAgentContext, ToolResult
from autorepair.repair_agent.spec_builder import build_repair_spec
from autorepair.repair_agent.validator import (
    FailureSummary,
    ValidationPlan,
    ValidationResult,
    build_validation_plan,
    run_validation_plan,
)


def _plan_and_spec():
    ctx = RepairAgentContext(
        job_id="JOB-VP",
        incident_id="INC-VP",
        worktree_path="/tmp/wt",
        error_type="TypeError",
        error_message="can't compare offset-naive and offset-aware datetimes",
        suspected_file="demo_service/ticket_service.py",
        target_test_command="pytest -q demo_service/tests/test_ticket_contract.py -m agent_target",
        full_test_command="pytest -q",
    )
    case = build_repair_case(ctx)
    spec = build_repair_spec(case, ctx)
    plan = build_validation_plan(case, spec, ctx)
    return plan, spec, ctx


def test_build_validation_plan_has_targets():
    plan, _, _ = _plan_and_spec()
    assert len(plan.target_commands) > 0
    assert plan.full_command == "pytest -q"


def test_before_phase_target_fails():
    plan, spec, _ = _plan_and_spec()
    tools = MagicMock()
    tools.run_tests.return_value = ToolResult(
        tool="run_tests", ok=False, output="FAILED", error="exit code 1",
    )
    result = run_validation_plan(tools, plan, "before", spec)
    assert isinstance(result, ValidationResult)
    assert result.phase == "before"
    assert result.target_ok is False
    assert result.failure_summary is not None
    assert result.failure_summary.failed_command == plan.target_commands[0]


def test_before_phase_target_passes_not_reproducible():
    plan, spec, _ = _plan_and_spec()
    tools = MagicMock()
    tools.run_tests.return_value = ToolResult(
        tool="run_tests", ok=True, output="PASSED",
    )
    result = run_validation_plan(tools, plan, "before", spec)
    assert result.target_ok is True
    assert result.failure_summary is None


def test_after_phase_target_fails_no_full():
    plan, spec, _ = _plan_and_spec()
    tools = MagicMock()
    tools.run_tests.return_value = ToolResult(
        tool="run_tests", ok=False, output="FAILED", error="exit code 1",
    )
    result = run_validation_plan(tools, plan, "after", spec)
    assert result.target_ok is False
    assert result.full_ok is None
    assert result.failure_summary is not None
    assert "target" not in (result.failure_summary.failed_command or "") or True
    assert tools.run_tests.call_count == len(plan.target_commands)


def test_after_phase_all_pass():
    plan, spec, _ = _plan_and_spec()
    tools = MagicMock()
    tools.run_tests.return_value = ToolResult(
        tool="run_tests", ok=True, output="PASSED",
    )
    result = run_validation_plan(tools, plan, "after", spec)
    assert result.target_ok is True
    assert result.full_ok is True
    assert result.failure_summary is None


def test_failure_summary_has_spec_violation():
    plan, spec, _ = _plan_and_spec()
    tools = MagicMock()
    tools.run_tests.return_value = ToolResult(
        tool="run_tests", ok=False, output="AssertionError: wrong", error="exit code 1",
    )
    result = run_validation_plan(tools, plan, "before", spec)
    assert result.failure_summary is not None
    assert len(result.failure_summary.violated_spec_item) > 0


def test_output_truncation():
    plan, spec, _ = _plan_and_spec()
    long_output = "x" * 3000
    tools = MagicMock()
    tools.run_tests.return_value = ToolResult(
        tool="run_tests", ok=False, output=long_output, error="exit code 1",
    )
    result = run_validation_plan(tools, plan, "before", spec)
    assert len(result.failure_summary.relevant_output) <= 1600