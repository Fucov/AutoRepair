from autorepair.repair_agent.repair_case import RepairCase, build_repair_case
from autorepair.repair_agent.schemas import RepairAgentContext


def _ctx(error_type, error_message, suspected_file=None, issue_body=None) -> RepairAgentContext:
    return RepairAgentContext(
        job_id="JOB-TC",
        incident_id="INC-TC",
        worktree_path="/tmp/wt",
        error_type=error_type,
        error_message=error_message,
        suspected_file=suspected_file,
        issue_body=issue_body,
    )


def test_build_case_timezone():
    ctx = _ctx("TypeError", "can't compare offset-naive and offset-aware datetimes",
               suspected_file="demo_service/ticket_service.py")
    case = build_repair_case(ctx)
    assert case.scenario_id == "ticket-timezone-sla"
    assert "demo_service/ticket_service.py" in case.allowed_files
    assert case.confidence >= 0.8
    assert case.entrypoint == "POST /tickets/submit"
    assert len(case.target_tests) > 0


def test_build_case_nameerror():
    ctx = _ctx("NameError", "name 'overdue' is not defined",
               suspected_file="demo_service/ticket_service.py")
    case = build_repair_case(ctx)
    assert case.scenario_id == "ticket-nameerror-overdue"
    assert "demo_service/ticket_service.py" in case.allowed_files


def test_build_case_zero_division():
    ctx = _ctx("ZeroDivisionError", "division by zero",
               suspected_file="demo_service/order_service.py")
    case = build_repair_case(ctx)
    assert case.scenario_id == "order-zero-division"
    assert "demo_service/order_service.py" in case.allowed_files


def test_build_case_missing_profile():
    ctx = _ctx("TypeError", "'NoneType' object is not subscriptable",
               suspected_file="demo_service/service.py",
               issue_body="User not found profile")
    case = build_repair_case(ctx)
    assert case.scenario_id == "user-missing-profile"
    assert "demo_service/service.py" in case.allowed_files


def test_build_case_idempotency():
    ctx = _ctx("BusinessLogicError", "duplicate idempotency_key same ticket_id",
               suspected_file="demo_service/ticket_service.py")
    case = build_repair_case(ctx)
    assert case.scenario_id == "ticket-idempotency-duplicate"
    assert "demo_service/ticket_service.py" in case.allowed_files


def test_build_case_unknown_bug():
    ctx = _ctx("AttributeError", "unknown attribute 'foo'", suspected_file="src/main.py")
    case = build_repair_case(ctx)
    assert case.scenario_id is None
    assert case.confidence < 0.5
    assert "src/main.py" in case.allowed_files


def test_build_case_app_py_redirect():
    ctx = _ctx("AttributeError", "some error",
               suspected_file="demo_service/app.py")
    case = build_repair_case(ctx)
    assert case.confidence < 0.5
    assert len(case.allowed_files) > 0
    assert "demo_service/app.py" not in case.allowed_files


def test_build_case_forbidden_files_default():
    ctx = _ctx("TypeError", "some error")
    case = build_repair_case(ctx)
    assert ".env" in case.forbidden_files
    assert ".git" in case.forbidden_files
    assert "pyproject.toml" in case.forbidden_files
    assert "requirements.txt" in case.forbidden_files
    assert "tests" in case.forbidden_files


def test_build_case_forbidden_files_allow_test_edit():
    ctx = _ctx("TypeError", "some error")
    case = build_repair_case(ctx, allow_test_edit=True)
    assert "tests" not in case.forbidden_files


def test_build_case_allowed_files_nonempty():
    scenarios = [
        ("TypeError", "can't compare offset-naive", "demo_service/ticket_service.py"),
        ("NameError", "name 'overdue' is not defined", "demo_service/ticket_service.py"),
        ("ZeroDivisionError", "division by zero", "demo_service/order_service.py"),
        ("TypeError", "'NoneType' object is not subscriptable", "demo_service/service.py"),
        ("BusinessLogicError", "duplicate idempotency_key", "demo_service/ticket_service.py"),
    ]
    for error_type, error_msg, sus_file in scenarios:
        ctx = _ctx(error_type, error_msg, suspected_file=sus_file)
        case = build_repair_case(ctx)
        assert len(case.allowed_files) > 0, f"allowed_files empty for {error_type}"