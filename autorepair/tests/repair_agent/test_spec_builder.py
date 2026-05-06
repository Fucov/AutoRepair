from autorepair.repair_agent.repair_case import build_repair_case
from autorepair.repair_agent.schemas import RepairAgentContext
from autorepair.repair_agent.spec_builder import RepairSpec, build_repair_spec


def _case_and_ctx(error_type, error_message, suspected_file=None, issue_body=None):
    ctx = RepairAgentContext(
        job_id="JOB-TS",
        incident_id="INC-TS",
        worktree_path="/tmp/wt",
        error_type=error_type,
        error_message=error_message,
        suspected_file=suspected_file,
        issue_body=issue_body,
    )
    case = build_repair_case(ctx)
    return case, ctx


def test_spec_timezone():
    case, ctx = _case_and_ctx(
        "TypeError", "can't compare offset-naive and offset-aware datetimes",
        suspected_file="demo_service/ticket_service.py",
    )
    spec = build_repair_spec(case, ctx)
    assert isinstance(spec, RepairSpec)
    assert spec.case_id == case.case_id
    assert spec.incident_id == case.incident_id
    assert spec.function_under_repair == "submit_ticket"
    assert len(spec.caller_expectation) > 0
    assert len(spec.preconditions) > 0
    assert len(spec.postconditions) > 0
    assert len(spec.invariants) > 0
    assert len(spec.violation) > 0
    assert "timezone" in spec.violation.lower() or "naive" in spec.violation.lower()


def test_spec_idempotency():
    case, ctx = _case_and_ctx(
        "BusinessLogicError", "duplicate idempotency_key same ticket_id",
        suspected_file="demo_service/ticket_service.py",
    )
    spec = build_repair_spec(case, ctx)
    assert spec.function_under_repair == "submit_ticket"
    assert any("idempotency" in pc.lower() for pc in spec.postconditions)


def test_spec_nameerror():
    case, ctx = _case_and_ctx(
        "NameError", "name 'overdue' is not defined",
        suspected_file="demo_service/ticket_service.py",
    )
    spec = build_repair_spec(case, ctx)
    assert spec.function_under_repair == "submit_ticket"
    assert any("nameerror" in inv.lower() or "字符串" in inv for inv in spec.invariants)


def test_spec_zero_division():
    case, ctx = _case_and_ctx(
        "ZeroDivisionError", "division by zero",
        suspected_file="demo_service/order_service.py",
    )
    spec = build_repair_spec(case, ctx)
    assert spec.function_under_repair == "calculate_order_discount"
    assert any("400" in pc for pc in spec.postconditions)


def test_spec_missing_profile():
    case, ctx = _case_and_ctx(
        "TypeError", "'NoneType' object is not subscriptable",
        suspected_file="demo_service/service.py",
        issue_body="User not found profile",
    )
    spec = build_repair_spec(case, ctx)
    assert spec.function_under_repair == "build_user_profile"
    assert any("404" in pc for pc in spec.postconditions)


def test_spec_unknown_bug():
    case, ctx = _case_and_ctx(
        "AttributeError", "unknown error",
        suspected_file="src/main.py",
    )
    spec = build_repair_spec(case, ctx)
    assert spec.case_id == case.case_id
    assert spec.incident_id == case.incident_id
    assert len(spec.caller_expectation) > 0


def test_spec_acceptance_tests_from_case():
    case, ctx = _case_and_ctx(
        "TypeError", "can't compare offset-naive and offset-aware datetimes",
        suspected_file="demo_service/ticket_service.py",
    )
    spec = build_repair_spec(case, ctx)
    assert len(spec.acceptance_tests) > 0
    assert spec.acceptance_tests == case.target_tests