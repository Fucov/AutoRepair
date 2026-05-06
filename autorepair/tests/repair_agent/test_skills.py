from autorepair.repair_agent.repair_case import build_repair_case
from autorepair.repair_agent.schemas import RepairAgentContext
from autorepair.repair_agent.skills import select_repair_skills
from autorepair.repair_agent.skills.datetime_timezone import DateTimeTimezoneSkill
from autorepair.repair_agent.skills.idempotency import IdempotencySkill
from autorepair.repair_agent.skills.import_scope import ImportScopeSkill
from autorepair.repair_agent.skills.name_error import NameErrorSkill
from autorepair.repair_agent.skills.null_guard import NullGuardSkill
from autorepair.repair_agent.skills.zero_division import ZeroDivisionSkill
from autorepair.repair_agent.spec_builder import build_repair_spec


def _skills_for(error_type, error_message, suspected_file=None, issue_body=None):
    ctx = RepairAgentContext(
        job_id="JOB-SK",
        incident_id="INC-SK",
        worktree_path="/tmp/wt",
        error_type=error_type,
        error_message=error_message,
        suspected_file=suspected_file,
        issue_body=issue_body,
    )
    case = build_repair_case(ctx)
    spec = build_repair_spec(case, ctx)
    return select_repair_skills(case, spec), case, spec


def test_match_datetime_timezone():
    skills, _, _ = _skills_for(
        "TypeError", "can't compare offset-naive and offset-aware datetimes",
        suspected_file="demo_service/ticket_service.py",
    )
    names = [s.name for s in skills]
    assert "DateTimeTimezoneSkill" in names


def test_match_zero_division():
    skills, _, _ = _skills_for(
        "ZeroDivisionError", "division by zero",
        suspected_file="demo_service/order_service.py",
    )
    names = [s.name for s in skills]
    assert "ZeroDivisionSkill" in names


def test_match_null_guard():
    skills, _, _ = _skills_for(
        "TypeError", "'NoneType' object is not subscriptable",
        suspected_file="demo_service/service.py",
        issue_body="User not found profile",
    )
    names = [s.name for s in skills]
    assert "NullGuardSkill" in names


def test_match_name_error():
    skills, _, _ = _skills_for(
        "NameError", "name 'overdue' is not defined",
        suspected_file="demo_service/ticket_service.py",
    )
    names = [s.name for s in skills]
    assert "NameErrorSkill" in names


def test_match_idempotency():
    skills, _, _ = _skills_for(
        "BusinessLogicError", "duplicate idempotency_key same ticket_id",
        suspected_file="demo_service/ticket_service.py",
    )
    names = [s.name for s in skills]
    assert "IdempotencySkill" in names


def test_unmatched_returns_empty():
    skills, _, _ = _skills_for(
        "AttributeError", "some unknown attribute error",
        suspected_file="src/main.py",
    )
    names = [s.name for s in skills]
    assert len(names) == 0


def test_skill_prompt_hint_not_empty():
    skill = DateTimeTimezoneSkill()
    ctx = RepairAgentContext(
        job_id="JOB", incident_id="INC", worktree_path="/tmp",
        error_type="TypeError", error_message="timezone",
    )
    case = build_repair_case(ctx)
    spec = build_repair_spec(case, ctx)
    hint = skill.prompt_hint(case, spec)
    assert len(hint) > 0


def test_skill_success_criteria():
    skill = ZeroDivisionSkill()
    ctx = RepairAgentContext(
        job_id="JOB", incident_id="INC", worktree_path="/tmp",
        error_type="ZeroDivisionError", error_message="division by zero",
    )
    case = build_repair_case(ctx)
    spec = build_repair_spec(case, ctx)
    criteria = skill.success_criteria(spec)
    assert len(criteria) > 0