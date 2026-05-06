from __future__ import annotations

import uuid
import re
from typing import Any

from pydantic import BaseModel, Field

from autorepair.repair_agent.schemas import RepairAgentContext


class RepairCase(BaseModel):
    case_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    issue_number: int | None = None
    scenario_id: str | None = None
    bug_type: str = ""
    entrypoint: str | None = None
    suspected_files: list[str] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    target_tests: list[str] = Field(default_factory=list)
    regression_tests: list[str] = Field(default_factory=list)
    expected_behavior: str = ""
    current_failure: str = ""
    confidence: float = 0.0


def build_repair_case(
    context: RepairAgentContext,
    issue: Any | None = None,
    allow_test_edit: bool = False,
) -> RepairCase:
    issue_number = context.issue_number
    issue_body = getattr(issue, "body", None) if issue else getattr(context, "issue_body", None)

    error_type = context.error_type or "UnknownError"
    error_message = context.error_message or ""
    suspected_file = context.suspected_file or ""

    forbidden_files = [".env", ".git", "pyproject.toml", "requirements.txt"]
    if not allow_test_edit:
        forbidden_files.append("tests")

    scenario_id = _infer_scenario_id(error_type, error_message, issue_body)
    bug_type = error_type

    entrypoint = _infer_entrypoint(scenario_id)
    allowed_files = _infer_allowed_files(scenario_id, suspected_file)
    target_tests = _infer_target_tests(scenario_id)
    regression_tests = _infer_regression_tests(scenario_id)
    expected_behavior = _infer_expected_behavior(scenario_id)
    current_failure = f"{error_type}: {error_message}"

    confidence = 0.9 if scenario_id else 0.3
    if not allowed_files:
        confidence = min(confidence, 0.3)

    return RepairCase(
        incident_id=context.incident_id,
        issue_number=issue_number,
        scenario_id=scenario_id,
        bug_type=bug_type,
        entrypoint=entrypoint,
        suspected_files=[suspected_file] if suspected_file else [],
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        target_tests=target_tests,
        regression_tests=regression_tests,
        expected_behavior=expected_behavior,
        current_failure=current_failure,
        confidence=confidence,
    )


def _infer_scenario_id(error_type: str, error_message: str, issue_body: str | None) -> str | None:
    text = f"{error_type} {error_message} {issue_body or ''}".lower()

    if "timezone" in text or "offset-naive" in text or "offset-aware" in text:
        return "ticket-timezone-sla"
    if "idempotency" in text and ("duplicate" in text or "same" in text):
        return "ticket-idempotency-duplicate"
    if "nameerror" in text and ("overdue" in text or "status" in text):
        return "ticket-nameerror-overdue"
    if "zerodivision" in text or ("total_amount" in text and "division" in text):
        return "order-zero-division"
    if "nonetype" in text and ("user" in text or "profile" in text):
        return "user-missing-profile"

    return None


def _infer_entrypoint(scenario_id: str | None) -> str | None:
    mapping = {
        "ticket-timezone-sla": "POST /tickets/submit",
        "ticket-idempotency-duplicate": "POST /tickets/submit",
        "ticket-nameerror-overdue": "POST /tickets/submit",
        "order-zero-division": "POST /orders/preview",
        "user-missing-profile": "GET /users/{user_id}/profile",
    }
    return mapping.get(scenario_id) if scenario_id else None


def _infer_allowed_files(scenario_id: str | None, suspected_file: str) -> list[str]:
    mapping = {
        "ticket-timezone-sla": ["demo_service/ticket_service.py"],
        "ticket-idempotency-duplicate": ["demo_service/ticket_service.py"],
        "ticket-nameerror-overdue": ["demo_service/ticket_service.py"],
        "order-zero-division": ["demo_service/order_service.py"],
        "user-missing-profile": ["demo_service/service.py"],
    }
    if scenario_id and scenario_id in mapping:
        return mapping[scenario_id]

    if suspected_file:
        if suspected_file == "demo_service/app.py":
            return ["demo_service/app.py", "demo_service/service.py", "demo_service/order_service.py", "demo_service/ticket_service.py"]
        return [suspected_file]
    return []


def _infer_target_tests(scenario_id: str | None) -> list[str]:
    mapping = {
        "ticket-timezone-sla": [
            "demo_service/tests/test_ticket_contract.py::test_future_sla_deadline_should_return_open"
        ],
        "ticket-idempotency-duplicate": [
            "demo_service/tests/test_ticket_contract.py::test_duplicate_idempotency_key_should_not_create_two_tickets"
        ],
        "ticket-nameerror-overdue": [
            "demo_service/tests/test_ticket_contract.py::test_expired_sla_deadline_should_return_overdue"
        ],
        "order-zero-division": [
            "demo_service/tests/test_order_contract.py::test_zero_total_amount_should_return_400"
        ],
        "user-missing-profile": [
            "demo_service/tests/test_profile_contract.py::test_missing_user_should_return_404"
        ],
    }
    return mapping.get(scenario_id, []) if scenario_id else []


def _infer_regression_tests(scenario_id: str | None) -> list[str]:
    mapping = {
        "ticket-timezone-sla": [
            "demo_service/tests/test_ticket_contract.py::test_expired_sla_deadline_should_return_overdue",
            "demo_service/tests/test_ticket_contract.py::test_duplicate_idempotency_key_should_not_create_two_tickets"
        ],
        "ticket-idempotency-duplicate": [
            "demo_service/tests/test_ticket_contract.py::test_expired_sla_deadline_should_return_overdue",
            "demo_service/tests/test_ticket_contract.py::test_future_sla_deadline_should_return_open"
        ],
        "ticket-nameerror-overdue": [
            "demo_service/tests/test_ticket_contract.py::test_future_sla_deadline_should_return_open",
            "demo_service/tests/test_ticket_contract.py::test_duplicate_idempotency_key_should_not_create_two_tickets"
        ],
        "order-zero-division": [
            "demo_service/tests/test_order_contract.py"
        ],
        "user-missing-profile": [
            "demo_service/tests/test_profile_contract.py"
        ],
    }
    return mapping.get(scenario_id, []) if scenario_id else []


def _infer_expected_behavior(scenario_id: str | None) -> str:
    mapping = {
        "ticket-timezone-sla": "submit_ticket 应正确处理带时区的 SLA deadline，naive/aware datetime 比较需统一",
        "ticket-idempotency-duplicate": "相同 idempotency_key 重复提交应返回同一 ticket_id，不创建重复工单",
        "ticket-nameerror-overdue": "过期工单应返回 overdue 状态，不应抛出 NameError",
        "order-zero-division": "total_amount <= 0 应返回 400 Invalid order amount，不应抛 ZeroDivisionError",
        "user-missing-profile": "用户不存在时应返回 404 User not found，不应抛 TypeError",
    }
    return mapping.get(scenario_id, "未知预期行为") if scenario_id else "未知预期行为"